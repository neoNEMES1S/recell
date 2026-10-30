"""Selective extra-cell availability audit; never expand the sealed training source pool."""

import argparse
import json
import runpy
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.osf import inspect_listing


def inventory(root):
    original = root / "outputs/transfer/source_audit/selected_metadata"
    output = root / "outputs/transfer/extra_source_audit_v1"
    output.mkdir(exist_ok=True)
    selection_path = output / "selection.json"
    if selection_path.exists():
        result = json.loads(selection_path.read_text())
        for relative, digest in result["inputs"].items():
            if sha256_file(root / relative) != digest:
                raise ValueError("Completed extra-cell inventory input changed")
        return result
    helpers = runpy.run_path(str(root / "scripts/acquire_ev_transfer.py"))
    related, select = helpers["related"], helpers["selection_entry"]
    cells = ["W4", "W5", "W7"]
    entries, batches = [], []
    inputs = {"configs/cell_registry.yaml": sha256_file(root / "configs/cell_registry.yaml")}

    def read(name):
        path = original / name
        inputs[str(path.relative_to(root))] = sha256_file(path)
        return json.loads(path.read_text())["data"]

    for number in range(1, 5):
        records = read(f"diag{number}_files.json")
        for cell in cells:
            matches = helpers["matching_files"](records, cell)
            if not matches:
                raise ValueError("Expected external-cell capacity diagnostic is absent")
            entries.extend(
                select(
                    row,
                    f"extra_source_audit_v1/diagnostics/Diag_{number}",
                    "diagnostic",
                    number,
                    cell,
                )
                for row in matches
            )
    jobs = []
    for number in [1, 2]:
        listing = read(f"cycle{number}_folders.json")
        mats = read(f"cycle{number}_mat.json")
        folders = {
            r["attributes"]["name"]: r for r in listing if r["attributes"]["kind"] == "folder"
        }
        for cell in cells:
            mat = next(row for row in mats if row["attributes"]["name"] == f"{cell}.mat")
            chosen = select(
                mat, f"extra_source_audit_v1/cycling/Cycling_{number}", "cycling_mat", number, cell
            )
            entries.append(chosen)
            jobs.append((number, cell, folders[cell], chosen["path"]))

    def raw_anchors(job):
        number, cell, source_folder, mat_path = job
        metadata = output / "metadata"
        label = f"cycling{number}_{cell}"
        listing = inspect_listing(related(source_folder), metadata / f"{label}.json")
        exports = helpers["cycling_exports"](listing["data"], metadata, label)
        parts = helpers["export_parts"](exports, cell)
        selected, segments = [], []
        for index, part in enumerate(parts, start=1):
            first = select(
                part["first"],
                f"extra_source_audit_v1/anchors/Cycling_{number}/{cell}/Part_{index}",
                "cycling_segment_anchor",
                number,
                cell,
            )
            last = select(
                part["last"],
                f"extra_source_audit_v1/tails/Cycling_{number}/{cell}/Part_{index}",
                "cycling_segment_end",
                number,
                cell,
            )
            selected.extend([first, last])
            segments.append(
                {
                    "segment_index": index,
                    "source_part_order": part["source_part_order"],
                    "first_path": first["path"],
                    "last_path": last["path"],
                }
            )
        return selected, {
            "cell_id": cell,
            "number": number,
            "mat_path": mat_path,
            "segments": segments,
        }

    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = [executor.submit(raw_anchors, job) for job in jobs]
        for task in as_completed(tasks):
            selected, batch = task.result()
            entries.extend(selected)
            batches.append(batch)
            print(
                json.dumps({"inventoried": batch["cell_id"], "batch": batch["number"]}), flush=True
            )
    assert len(batches) == 6 and len({r["path"] for r in entries}) == len(entries)
    for path in sorted((output / "metadata").glob("*.json")):
        inputs[str(path.relative_to(root))] = sha256_file(path)
    inputs[str(Path(__file__).resolve().relative_to(root))] = sha256_file(Path(__file__).resolve())
    inputs["scripts/acquire_ev_transfer.py"] = sha256_file(root / "scripts/acquire_ev_transfer.py")
    result = {
        "purpose": "Audit first four capacity diagnostics and first two complete cycling "
        "batches of W4/W5/W7 before deciding whether a separate source-pool "
        "amendment is feasible; these records are not training-eligible in v2.",
        "raw_root": "data/raw/stanford_ev_first_life",
        "cells": cells,
        "selection_basis": "Original plan requires other EV cells to be audited. Earliest "
        "four diagnostics supply the minimum H1/min3 label count; "
        "no new predictive-model outcomes were used.",
        "W3_exclusion": "Only three source capacity checkpoints; zero H1/min3 origins.",
        "boundaries": "Do not change target folds, source roles, feature definitions, "
        "historical outputs or sealed transfer protocol v2. Native chronology, "
        "capacity agreement, full exposure and identity still require audit.",
        "inputs": inputs,
        "batches": sorted(batches, key=lambda x: (x["cell_id"], x["number"])),
        "files": sorted(entries, key=lambda x: (x["kind"], x["cell_id"], x["number"], x["path"])),
    }
    with selection_path.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def download(root, selection):
    helper = runpy.run_path(str(root / "scripts/acquire_ev_transfer.py"))["download_one"]
    completed, errors = [], []
    output = root / "outputs/transfer/extra_source_audit_v1"
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = {
            executor.submit(helper, root / selection["raw_root"], row, {}): row
            for row in selection["files"]
        }
        for task in as_completed(tasks):
            try:
                completed.append(task.result())
            except Exception as exc:
                errors.append({"path": tasks[task]["path"], "error": str(exc)})
            progress = {
                "status": "acquisition_complete_not_validated"
                if len(completed) == len(selection["files"])
                else "acquisition_incomplete",
                "completed": len(completed),
                "selected": len(selection["files"]),
                "errors": errors,
            }
            (output / "download_progress.json").write_text(json.dumps(progress, indent=2) + "\n")
    if errors:
        raise ValueError("Some extra-source acquisitions failed; inspect download_progress.json")
    return completed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    selection = inventory(root)
    print(
        json.dumps({"selected": len(selection["files"]), "cells": selection["cells"]}), flush=True
    )
    if args.download:
        download(root, selection)
