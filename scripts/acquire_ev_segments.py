"""Pin each cycling restart's native endpoints without changing the registered feature contract."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from acquire_ev_transfer import cycling_exports, download_one, export_parts, selection_entry

from second_life_battery.data.inventory import sha256_file


def inventory(root):
    audit = root / "outputs/transfer/source_audit"
    source_path = audit / "source_selection.json"
    source = json.loads(source_path.read_text())
    metadata = audit / "selected_metadata"
    originals = {
        (r["cell_id"], r["number"], r["kind"]): r
        for r in source["files"]
        if r["kind"] != "diagnostic"
    }
    batches, extra_files = [], {}
    for cell, number in sorted(
        {(r["cell_id"], r["number"]) for r in source["files"] if r["kind"] == "cycling_mat"}
    ):
        listing = json.loads((metadata / f"cycle{number}_{cell}_raw.json").read_text())
        exports = cycling_exports(listing["data"], metadata, f"cycle{number}_{cell}_raw")
        parts = export_parts(exports, cell)
        original_head = originals[(cell, number, "cycling_anchor")]
        original_tail = originals[(cell, number, "cycling_end_anchor")]
        if (
            parts[0]["first"]["id"] != original_head["remote_id"]
            or parts[-1]["last"]["id"] != original_tail["remote_id"]
        ):
            raise ValueError("Part inventory differs from the pinned batch endpoints")
        known = {row["remote_id"]: row["path"] for row in [original_head, original_tail]}
        segments = []
        for index, part in enumerate(parts, 1):
            segment = {"segment_index": index, "source_part_order": part["source_part_order"]}
            for role in ["first", "last"]:
                record = part[role]
                if record["id"] not in known:
                    entry = selection_entry(
                        record,
                        f"segments/Cycling_{number}/{cell}/Segment_{index}",
                        "cycling_segment_anchor",
                        number,
                        cell,
                    )
                    entry.update(segment_index=index, endpoint_role=role)
                    extra_files[entry["path"]] = entry
                    known[record["id"]] = entry["path"]
                segment[f"{role}_path"] = known[record["id"]]
            segments.append(segment)
        batches.append(
            {
                "cell_id": cell,
                "number": number,
                "mat_path": originals[(cell, number, "cycling_mat")]["path"],
                "segments": segments,
            }
        )
    result = {
        "protocol_id": source["protocol_id"],
        "protocol_sha256": source["protocol_sha256"],
        "source_selection_sha256": sha256_file(source_path),
        "raw_root": source["raw_root"],
        "acquisition_code_sha256": {
            str(p.relative_to(root)): sha256_file(p)
            for p in [
                Path(__file__).resolve(),
                root / "scripts/acquire_ev_transfer.py",
            ]
        },
        "batches": batches,
        "extra_files": sorted(extra_files.values(), key=lambda row: row["path"]),
        "basis": (
            "Source Part folders/filename labels plus raw endpoint validation; "
            "channel subfolders do not define extra restarts"
        ),
    }
    (audit / "source_segments.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "batches": len(batches),
                "multipart_batches": sum(len(row["segments"]) > 1 for row in batches),
                "additional_endpoint_files": len(extra_files),
            }
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    selection = inventory(root)
    if args.download:
        results, errors = [], []
        with ThreadPoolExecutor(max_workers=2) as executor:
            tasks = {
                executor.submit(download_one, root / selection["raw_root"], row, {}): row
                for row in selection["extra_files"]
            }
            for task in as_completed(tasks):
                try:
                    results.append(task.result())
                except Exception as error:
                    errors.append({"path": tasks[task]["path"], "error": str(error)})
                    print(json.dumps(errors[-1]), flush=True)
        (root / "outputs/transfer/source_audit/segment_download_results.json").write_text(
            json.dumps({"completed": results, "errors": errors}, indent=2) + "\n"
        )
        if errors:
            raise SystemExit(1)
