"""Retry confirmed failed selected downloads with exact, version-bound HTTP 206 chunks."""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from acquire_ev_transfer import MAX_FILE_BYTES, MAX_TOTAL_BYTES, verify_file

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.osf import fetch_page

CHUNK_BYTES = 16 * 1024**2


def range_size(headers, start, end, total=None):
    statuses = re.findall(r"(?im)^HTTP/\S+\s+(\d+)", headers)
    ranges = re.findall(r"(?im)^content-range:\s*bytes (\d+)-(\d+)/(\d+)\s*$", headers)
    if not statuses or statuses[-1] != "206" or not ranges:
        raise ValueError("Provider ignored the byte range; response cannot be concatenated")
    left, right, size = map(int, ranges[-1])
    if (left, right) != (start, end) or not 0 <= left <= right < size <= MAX_FILE_BYTES:
        raise ValueError("Provider returned an incorrect or excessive byte range")
    if total is not None and size != total:
        raise ValueError("Remote file size changed during range acquisition")
    return size


def get_range(url, path, start, end, total=None):
    partial, headers = path.with_suffix(".part"), path.with_suffix(".headers")
    for attempt in range(3):
        result = subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "30",
                "--max-time",
                "180",
                "--range",
                f"{start}-{end}",
                "--max-filesize",
                str(end - start + 1),
                "--dump-header",
                str(headers),
                url,
                "--output",
                str(partial),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            break
    else:
        raise ConnectionError(f"Bounded range failed: {start}-{end}; curl {result.returncode}")
    size = range_size(headers.read_text(), start, end, total)
    if partial.stat().st_size != end - start + 1:
        raise ValueError("Incomplete byte range")
    partial.replace(path)
    return size


def revision(record):
    url = record["links"]["self"]
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != "api.osf.io":
        raise ValueError("Unexpected source metadata URL")
    current = json.loads(fetch_page(url))["data"]
    attributes = current["attributes"]
    if current["id"] != record["id"]:
        raise ValueError("Source metadata identity changed")
    value = {key: attributes[key] for key in ["current_version", "date_modified"]}
    if value != {key: record["attributes"][key] for key in value}:
        raise ValueError("Source revision differs from selected release metadata")
    return value


def acquire(root, name):
    audit = root / "outputs/transfer/source_audit"
    selection = json.loads((audit / "source_selection.json").read_text())
    entry = next(row for row in selection["files"] if row["path"] == name)
    raw = root / selection["raw_root"]
    destination = (raw / name).resolve()
    if not destination.is_relative_to(raw.resolve()):
        raise ValueError("Range destination escapes source directory")
    if (
        urlsplit(entry["url"]).hostname != "files.osf.io"
        or urlsplit(entry["url"]).scheme != "https"
    ):
        raise ValueError("Range retries require the reviewed direct provider URL")
    receipt = destination.with_suffix(destination.suffix + ".receipt.json")
    if destination.exists() and receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved["remote_id"] != entry["remote_id"] or saved["sha256"] != sha256_file(destination):
            raise ValueError("Completed source receipt changed")
        return saved
    record = None
    for path in sorted((audit / "selected_metadata").glob("*.json")):
        if ".pages." in path.name:
            continue
        records = json.loads(path.read_text()).get("data", [])
        record = next((row for row in records if row["id"] == entry["remote_id"]), None)
        if record is not None:
            break
    if record is None:
        raise ValueError("Selected source metadata is absent")
    version = revision(record)
    cache = raw / ".range_cache" / entry["remote_id"]
    cache.mkdir(parents=True, exist_ok=True)
    size = get_range(entry["url"], cache / "probe.bin", 0, 0)
    pin = {"remote_id": entry["remote_id"], "url": entry["url"], "bytes": size, **version}
    pin_path = cache / "source.json"
    if pin_path.exists() and json.loads(pin_path.read_text()) != pin:
        raise ValueError("Cached range source revision/size changed")
    pin_path.write_text(json.dumps(pin, indent=2) + "\n")
    acquired = sum(path.stat().st_size for path in raw.rglob("*") if path.is_file())
    if (
        acquired + 2 * size + 4 * MAX_FILE_BYTES > MAX_TOTAL_BYTES
        or shutil.disk_usage(raw).free < 2 * size + 4 * MAX_FILE_BYTES
    ):
        raise OSError("Insufficient bounded range acquisition budget")
    chunks = []
    for start in range(0, size, CHUNK_BYTES):
        end = min(start + CHUNK_BYTES, size) - 1
        path = cache / f"{start}-{end}.bin"
        chunk_receipt = path.with_suffix(".json")
        if path.exists() and chunk_receipt.exists():
            saved = json.loads(chunk_receipt.read_text())
            if (
                saved["source"] != pin
                or saved["sha256"] != sha256_file(path)
                or saved["start"] != start
                or saved["end"] != end
                or path.stat().st_size != end - start + 1
            ):
                raise ValueError("Pinned range chunk changed")
        else:
            get_range(entry["url"], path, start, end, size)
            saved = {"source": pin, "start": start, "end": end, "sha256": sha256_file(path)}
            chunk_receipt.write_text(json.dumps(saved, indent=2) + "\n")
        chunks.append({"path": path.name, **saved})
        print(json.dumps({"range_completed": name, "bytes": end + 1, "total": size}), flush=True)
    assembled = cache / f"assembled{destination.suffix}"
    with assembled.open("wb") as output:
        for chunk in chunks:
            with (cache / chunk["path"]).open("rb") as source:
                shutil.copyfileobj(source, output)
    if assembled.stat().st_size != size or revision(record) != version:
        raise ValueError("Source size/revision changed before range completion")
    verify_file(assembled)
    digest = sha256_file(assembled)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or receipt.exists():
        raise ValueError("Another acquisition completed this destination; do not overwrite it")
    assembled.replace(destination)
    result = {
        "path": name,
        "remote_id": entry["remote_id"],
        "bytes": size,
        "sha256": digest,
        "hash_basis": (
            "Exact HTTP 206 chunks, pinned OSF revision before/after, "
            "local completed SHA256; no upstream checksum supplied"
        ),
        "source_revision": version,
        "chunks": chunks,
    }
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    for chunk in chunks:
        (cache / chunk["path"]).unlink()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", help="Registered input whose previous acquisition is confirmed terminal"
    )
    args = parser.parse_args()
    result = acquire(Path(__file__).resolve().parent.parent, args.path)
    print(json.dumps({key: result[key] for key in ["path", "bytes", "sha256"]}), flush=True)
