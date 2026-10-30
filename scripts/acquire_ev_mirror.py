"""Recover registered terminal failures from the public mirror linked by the author."""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from xml.etree import ElementTree
from zipfile import ZipFile

from acquire_ev_transfer import MAX_FILE_BYTES, MAX_TOTAL_BYTES, verify_file
from retry_ev_ranges import get_range, revision

from second_life_battery.data.inventory import sha256_file

AUTHOR_MIRROR = "https://www.dropbox.com/scl/fo/3ss0age6ggfcm67okldhw/h"
AUTHOR_KEY = "tnczvb82gukfe2n4gol2uyo7x"


def etag(headers):
    tags = re.findall(r"(?im)^etag:\s*([^\r\n]+)", headers)
    if not tags:
        raise ValueError("Author mirror supplied no revision ETag")
    return tags[-1].strip()


def acquire(root, name, *, selection_path=None):
    audit = root / "outputs/transfer/source_audit"
    failure_path = audit / "download_results.json"
    if selection_path is None:
        selection_path = audit / "source_selection.json"
    else:
        selection_path = (root / selection_path).resolve()
        if not selection_path.is_relative_to(root.resolve()):
            raise ValueError("Mirror selection escapes the project directory")
        failure_path = selection_path.parent / "download_progress.json"
    selection = json.loads(selection_path.read_text())
    for relative, digest in selection.get("inputs", {}).items():
        if sha256_file(root / relative) != digest:
            raise ValueError("Mirror selection input changed")
    entry = next(row for row in selection["files"] if row["path"] == name)
    failures = json.loads(failure_path.read_text())["errors"]
    if name not in {row["path"] for row in failures}:
        raise ValueError("Mirror recovery is limited to confirmed terminal failures")
    raw = root / selection["raw_root"]
    with ZipFile(raw / "README.xlsx") as workbook:
        targets = [
            relation.attrib.get("Target", "")
            for member in workbook.namelist()
            if member.endswith(".rels")
            for relation in ElementTree.fromstring(workbook.read(member))
        ]
    if not any(
        target.split("?")[0] == AUTHOR_MIRROR
        and parse_qs(urlsplit(target).query).get("rlkey") == [AUTHOR_KEY]
        for target in targets
    ):
        raise ValueError("Mirror is not linked by the acquired author README")
    destination = (raw / name).resolve()
    if not destination.is_relative_to(raw.resolve()):
        raise ValueError("Mirror destination escapes source directory")
    receipt = destination.with_suffix(destination.suffix + ".receipt.json")
    if destination.exists() and receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved["remote_id"] != entry["remote_id"] or saved["sha256"] != sha256_file(destination):
            raise ValueError("Completed mirrored source changed")
        return saved
    record = None
    for path in sorted((audit / "selected_metadata").glob("*.json")):
        if ".pages." in path.name:
            continue
        rows = json.loads(path.read_text()).get("data", [])
        if isinstance(rows, list):
            record = next((row for row in rows if row["id"] == entry["remote_id"]), None)
        if record is not None:
            break
    if record is None:
        raise ValueError("Selected source metadata is missing")
    materialized = record["attributes"]["materialized_path"]
    if not materialized.startswith("/") or ".." in Path(materialized).parts:
        raise ValueError("Unsafe author mirror path")
    version = revision(record)
    url = AUTHOR_MIRROR + quote(materialized) + "?" + urlencode({"rlkey": AUTHOR_KEY, "dl": 1})
    cache = raw / "mirror_review" / entry["remote_id"]
    cache.mkdir(parents=True, exist_ok=True)
    probe = cache / "probe.bin"
    size = get_range(url, probe, 0, 1023)
    acquired = sum(path.stat().st_size for path in raw.rglob("*") if path.is_file())
    reserve = size + 4 * MAX_FILE_BYTES
    if acquired + reserve > MAX_TOTAL_BYTES or shutil.disk_usage(raw).free < reserve:
        raise OSError("Insufficient bounded mirror acquisition budget")
    mirror_tag = etag(probe.with_suffix(".headers").read_text())
    previous = destination.with_suffix(destination.suffix + ".part")
    with previous.open("rb") as stream:
        if stream.read(1024) != probe.read_bytes():
            raise ValueError("Author mirror prefix differs from the previous OSF response")
    temporary = cache / f"completed{destination.suffix}"
    headers = cache / "download.headers"
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
            "900",
            "--max-filesize",
            str(MAX_FILE_BYTES),
            "--dump-header",
            str(headers),
            url,
            "--output",
            str(temporary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ConnectionError(f"Author mirror transfer failed: curl {result.returncode}")
    if temporary.stat().st_size != size or etag(headers.read_text()) != mirror_tag:
        raise ValueError("Author mirror size/revision changed")
    if revision(record) != version:
        raise ValueError("OSF selected source revision changed during mirror recovery")
    with previous.open("rb") as partial, temporary.open("rb") as complete:
        while chunk := partial.read(1024**2):
            if complete.read(len(chunk)) != chunk:
                raise ValueError("Author mirror differs from retained OSF partial bytes")
    verify_file(temporary)
    digest = sha256_file(temporary)
    if destination.exists() or receipt.exists():
        raise ValueError("Another acquisition completed this input; mirror will not overwrite it")
    temporary.replace(destination)
    saved = {
        "path": name,
        "remote_id": entry["remote_id"],
        "bytes": size,
        "sha256": digest,
        "hash_basis": (
            "Author-linked Dropbox mirror; matching prior OSF prefix, pinned mirror "
            "ETag, selected OSF revision checked before/after; local completed "
            "SHA256, no upstream content checksum supplied"
        ),
        "mirror_url": url,
        "mirror_etag": mirror_tag,
        "source_revision": version,
        "author_readme_sha256": sha256_file(raw / "README.xlsx"),
        "selection_sha256": sha256_file(selection_path),
        "failure_evidence_sha256": sha256_file(failure_path),
        "matching_osf_partial_bytes": previous.stat().st_size,
        "matching_osf_partial_sha256": sha256_file(previous),
    }
    receipt.write_text(json.dumps(saved, indent=2) + "\n")
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--selection", type=Path, help="Separate selective-audit inventory")
    args = parser.parse_args()
    result = acquire(
        Path(__file__).resolve().parent.parent, args.path, selection_path=args.selection
    )
    print(json.dumps({key: result[key] for key in ["path", "bytes", "sha256"]}), flush=True)
