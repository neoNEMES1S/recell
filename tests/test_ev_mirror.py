"""Only the author-linked, matching-revision mirror may complete a failed input."""

import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_STORED, ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
spec = importlib.util.spec_from_file_location(
    "acquire_ev_mirror", Path(__file__).resolve().parents[1] / "scripts/acquire_ev_mirror.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("defect", [None, "prefix", "etag", "later_bytes"])
@pytest.mark.parametrize("extra_selection", [False, True])
def test_mirror_is_promoted_only_after_prefix_revision_and_format_checks(
    tmp_path, monkeypatch, defect, extra_selection
):
    audit = tmp_path / "outputs/transfer/source_audit"
    meta = audit / "selected_metadata"
    meta.mkdir(parents=True)
    raw = tmp_path / "raw"
    raw.mkdir()
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("data.txt", bytes(range(256)) * 8)
    data = stream.getvalue()
    with ZipFile(raw / "README.xlsx", "w") as readme:
        readme.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships><Relationship Target="{module.AUTHOR_MIRROR}'
            f'?rlkey={module.AUTHOR_KEY}"/></Relationships>',
        )
    entry = {"path": "test.xlsx", "remote_id": "id"}
    folder = tmp_path / "extra_audit" if extra_selection else audit
    folder.mkdir(exist_ok=True)
    selection_path = folder / ("selection.json" if extra_selection else "source_selection.json")
    selection_path.write_text(json.dumps({"raw_root": "raw", "files": [entry]}))
    failure_path = folder / (
        "download_progress.json" if extra_selection else "download_results.json"
    )
    failure_path.write_text(json.dumps({"errors": [{"path": "test.xlsx"}]}))
    (meta / "files.json").write_text(
        json.dumps({"data": [{"id": "id", "attributes": {"materialized_path": "/test.xlsx"}}]})
    )
    partial = data[:1500] + b"different" if defect == "later_bytes" else data[:1024]
    (raw / "test.xlsx.part").write_bytes(b"different" if defect == "prefix" else partial)
    monkeypatch.setattr(
        module, "revision", lambda record: {"current_version": 2, "date_modified": "pinned"}
    )

    def probe(url, path, start, end):
        path.write_bytes(data[:1024])
        path.with_suffix(".headers").write_text("ETag: pinned\r\n")
        return len(data)

    def download(command, **kwargs):
        Path(command[-1]).write_bytes(data)
        Path(command[command.index("--dump-header") + 1]).write_text(
            "ETag: changed\r\n" if defect == "etag" else "ETag: pinned\r\n"
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module, "get_range", probe)
    monkeypatch.setattr(module.subprocess, "run", download)
    options = {"selection_path": selection_path} if extra_selection else {}
    if defect:
        with pytest.raises(ValueError):
            module.acquire(tmp_path, "test.xlsx", **options)
        assert not (raw / "test.xlsx").exists()
        assert not (raw / "test.xlsx.receipt.json").exists()
    else:
        result = module.acquire(tmp_path, "test.xlsx", **options)
        assert (raw / "test.xlsx").read_bytes() == data
        assert result["mirror_etag"] == "pinned"
        assert result["sha256"] == module.sha256_file(raw / "test.xlsx")
        assert result["matching_osf_partial_bytes"] == 1024
