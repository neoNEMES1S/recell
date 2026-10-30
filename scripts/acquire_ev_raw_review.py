"""Acquire complete raw exports for the two confirmed cycling-6 MAT conflicts."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from acquire_ev_transfer import download_one, fragment_order, matching_files, selection_entry

from second_life_battery.data.inventory import sha256_file


def inventory(root):
    audit = root / "outputs/transfer/source_audit"
    source_path = audit / "source_selection.json"
    source = json.loads(source_path.read_text())
    existing = {row["remote_id"]: row for row in source["files"]}
    entries, batches = [], []
    for cell in ["W8", "W9"]:
        path = audit / f"selected_metadata/cycle6_{cell}_raw.json"
        records = sorted(
            matching_files(json.loads(path.read_text())["data"], cell), key=fragment_order
        )
        if [fragment_order(row) for row in records] != list(range(1, 9)):
            raise ValueError("Reviewed cycling-6 export sequence changed")
        group = []
        for record in records:
            entry = existing.get(record["id"]) or selection_entry(
                record, f"raw_review/Cycling_6/{cell}", "cycling_raw_review", 6, cell
            )
            entries.append(entry)
            group.append(entry["path"])
        batches.append(
            {
                "cell_id": cell,
                "number": 6,
                "ordered_paths": group,
                "metadata_sha256": sha256_file(path),
            }
        )
    manifest = {
        "purpose": "Investigate duplicated processed MAT payloads; not accepted training inputs",
        "source_selection_sha256": sha256_file(source_path),
        "protocol_sha256": source["protocol_sha256"],
        "raw_root": source["raw_root"],
        "files": entries,
        "batches": batches,
    }
    destination = audit / "raw_review_selection.json"
    if destination.exists() and json.loads(destination.read_text()) != manifest:
        raise ValueError("Pinned raw-review selection changed")
    destination.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    manifest = inventory(root)
    if args.download:
        completed, errors = [], []
        with ThreadPoolExecutor(max_workers=2) as executor:
            tasks = {
                executor.submit(download_one, root / manifest["raw_root"], row, {}): row
                for row in manifest["files"]
            }
            for task in as_completed(tasks):
                try:
                    completed.append(task.result())
                except Exception as error:
                    errors.append({"path": tasks[task]["path"], "error": str(error)})
        (root / "outputs/transfer/source_audit/raw_review_download_results.json").write_text(
            json.dumps({"completed": completed, "errors": errors}, indent=2) + "\n"
        )
        if errors:
            raise SystemExit(1)
