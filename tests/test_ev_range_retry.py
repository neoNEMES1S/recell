"""Range retries cannot accept ignored ranges, wrong offsets or changed releases."""

import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

spec = importlib.util.spec_from_file_location(
    "retry_ev_ranges", Path(__file__).resolve().parents[1] / "scripts/retry_ev_ranges.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_http_206_range_and_total_are_required():
    header = "HTTP/1.1 302 Found\r\nHTTP/2 206\r\nContent-Range: bytes 16-31/100\r\n"
    assert module.range_size(header, 16, 31, 100) == 100
    with pytest.raises(ValueError, match="ignored"):
        module.range_size(header.replace("HTTP/2 206", "HTTP/2 200"), 16, 31)
    with pytest.raises(ValueError, match="incorrect"):
        module.range_size(header, 0, 15)
    with pytest.raises(ValueError, match="size changed"):
        module.range_size(header, 16, 31, 101)
    with pytest.raises(ValueError, match="excessive"):
        module.range_size(header.replace("/100", f"/{module.MAX_FILE_BYTES + 1}"), 16, 31)


def test_source_revision_must_equal_selected_release(monkeypatch):
    record = {
        "id": "id",
        "links": {"self": "https://api.osf.io/v2/files/id/"},
        "attributes": {"current_version": 2, "date_modified": "2023-10-05"},
    }
    current = {"data": record}
    monkeypatch.setattr(module, "fetch_page", lambda url: json.dumps(current).encode())
    assert module.revision(record) == record["attributes"]
    current = {"data": {**record, "attributes": {**record["attributes"], "current_version": 3}}}
    with pytest.raises(ValueError, match="revision differs"):
        module.revision(record)


def test_interrupted_chunks_resume_and_only_validated_workbook_is_promoted(tmp_path, monkeypatch):
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("test.txt", "measurement integrity fixture")
    data = stream.getvalue()
    audit = tmp_path / "outputs/transfer/source_audit"
    metadata = audit / "selected_metadata"
    metadata.mkdir(parents=True)
    entry = {
        "path": "review.xlsx",
        "remote_id": "fileid",
        "url": "https://files.osf.io/review.xlsx",
    }
    (audit / "source_selection.json").write_text(json.dumps({"raw_root": "raw", "files": [entry]}))
    (metadata / "folder.json").write_text(json.dumps({"data": [{"id": "fileid"}]}))
    monkeypatch.setattr(
        module, "revision", lambda row: {"current_version": 2, "date_modified": "pinned"}
    )
    monkeypatch.setattr(module, "CHUNK_BYTES", 32)
    calls = []
    interrupted = True

    def fetch(url, path, start, end, total=None):
        calls.append((start, end))
        if interrupted and start == 32:
            raise ConnectionError("interrupted")
        path.write_bytes(data[start : end + 1])
        return len(data)

    monkeypatch.setattr(module, "get_range", fetch)
    with pytest.raises(ConnectionError, match="interrupted"):
        module.acquire(tmp_path, "review.xlsx")
    assert not (tmp_path / "raw/review.xlsx").exists()
    assert not (tmp_path / "raw/review.xlsx.receipt.json").exists()
    assert calls.count((0, 31)) == 1
    interrupted = False
    result = module.acquire(tmp_path, "review.xlsx")
    assert (tmp_path / "raw/review.xlsx").read_bytes() == data
    assert calls.count((0, 31)) == 1  # The validated first chunk survives interruption.
    assert result["bytes"] == len(data)
    assert result["sha256"] == module.sha256_file(tmp_path / "raw/review.xlsx")
    assert not list((tmp_path / "raw/.range_cache/fileid").glob("*-*.bin"))
