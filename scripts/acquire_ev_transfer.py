"""Acquire only the registered target cells' first-life diagnostics and processed batches."""

import argparse
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

import pandas as pd
import yaml
from scipy.io import whosmat

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.osf import inspect_listing

MAX_FILE_BYTES = 1024**3
MAX_TOTAL_BYTES = 32 * 1024**3


def related(record):
    return record["relationships"]["files"]["links"]["related"]["href"]


def matching_files(records, cell):
    """Keep all diagnostic fragments for exactly the named cell, not similarly named cells."""
    return [
        row
        for row in records
        if row["attributes"]["kind"] == "file"
        and re.search(rf"_{re.escape(cell)}_(?:Part\d+_|New_)?Channel_", row["attributes"]["name"])
        and row["attributes"]["name"].lower().endswith(".xlsx")
    ]


def fragment_order(record):
    match = re.search(r"Channel_\d+(?:[._](\d+)|_Wb_(\d+))?\.xlsx$", record["attributes"]["name"])
    if not match:
        raise ValueError("Cannot determine the chronological export fragment")
    return int(match[1] or match[2] or 0)


def cycling_exports(records, metadata, label, parts=(), depth=0):
    """Some campaigns split a cell's raw exports into numbered Part folders."""
    exports = []
    for record in records:
        if record["attributes"]["kind"] == "file":
            exports.append({**record, "part_order": parts})
            continue
        name = record["attributes"]["name"]
        match = re.fullmatch(r"Part(\d+)", name)
        channel = re.fullmatch(r"Channel_\d+", name)
        if not (match or channel) or depth >= 3:
            raise ValueError(f"Unreviewed raw cycling subfolder: {name}")
        child = inspect_listing(related(record), metadata / f"{label}_{name}.json")
        exports.extend(
            cycling_exports(
                child["data"],
                metadata,
                f"{label}_{name}",
                (*parts, int(match[1])) if match else parts,
                depth + 1,
            )
        )
    return exports


def export_order(record):
    part = re.search(r"_Part(\d+)_Channel_", record["attributes"]["name"])
    return record.get("part_order") or ((int(part[1]),) if part else ()), fragment_order(record)


def export_parts(records, cell):
    """Keep source restart parts separate; a channel subfolder is not another restart."""
    groups = {}
    for record in matching_files(records, cell):
        groups.setdefault(export_order(record)[0], []).append(record)
    if not groups:
        raise ValueError("No reviewed raw exports for declared cell")
    return [
        {
            "source_part_order": list(key),
            "first": min(groups[key], key=fragment_order),
            "last": max(groups[key], key=fragment_order),
        }
        for key in sorted(groups)
    ]


def selection_entry(record, folder, kind, number, cell, legacy=None):
    name = record["attributes"]["name"]
    if Path(name).name != name or "\\" in name or ":" in name or name in {".", ".."}:
        raise ValueError("Unsafe dataset file name")
    # Waterbutler's GET endpoint avoids the slow permalink redirect observed during the audit.
    url = record["links"].get("move") or record["links"]["download"]
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"osf.io", "files.osf.io"}:
        raise ValueError("Unexpected first-life download origin")
    return {
        "cell_id": cell,
        "kind": kind,
        "number": number,
        "remote_id": record["id"],
        "url": url,
        "path": f"{folder}/{name}",
        "legacy": legacy,
        "declared_bytes": record["attributes"].get("size"),
        "filename_review": (
            "New marker in export name; require measured campaign continuity. "
            "Identity remains subject to the source audit."
            if "_New_Channel_" in name
            else None
        ),
    }


def inventory(root):
    audit = root / "outputs/transfer/source_audit"
    metadata = audit / "selected_metadata"
    raw = root / "data/raw/stanford_ev_first_life"
    protocol = yaml.safe_load((root / "configs/transfer_protocol_v2.yaml").read_text())
    cells = set(protocol["target"]["cells"])
    frame = pd.read_csv(audit / "first_life_capacity_checkpoints.csv")
    frame = frame[frame.cell_id.isin(cells)]
    diagnostics = {
        cell: set(group.diagnostic.astype(int)) for cell, group in frame.groupby("cell_id")
    }
    if set(diagnostics) != cells:
        raise ValueError("Source capacity inventory does not cover the registered cells")
    root_url = json.loads((audit / "osf_dropbox_root.json").read_text())["data"]
    folders = {
        row["attributes"]["name"]: related(row)
        for row in root_url
        if row["attributes"]["kind"] == "folder"
    }
    diag_root = inspect_listing(folders["diagnostic_tests"], metadata / "diagnostic_root.json")
    cycle_root = inspect_listing(folders["cycling_tests"], metadata / "cycling_root.json")

    def diagnostic(row):
        name = row["attributes"]["name"]
        n = int(name.split("_")[1])
        chosen = [cell for cell in sorted(cells) if n in diagnostics[cell]]
        listing = inspect_listing(related(row), metadata / f"diag{n}_folders.json")
        capacity = next(r for r in listing["data"] if r["attributes"]["name"] == "Capacity_test")
        records = inspect_listing(related(capacity), metadata / f"diag{n}_files.json")["data"]
        entries = []
        for cell in chosen:
            matches = matching_files(records, cell)
            if not matches:
                raise ValueError(f"No raw capacity file for {cell} diagnostic {n}")
            for record in matches:
                legacy = (
                    f"G1_diag{n}.xlsx"
                    if cell == "G1" and n in {1, 2, 11} and len(matches) == 1
                    else None
                )
                entries.append(
                    selection_entry(record, f"diagnostics/Diag_{n}", "diagnostic", n, cell, legacy)
                )
        return entries

    def cycling(row):
        n = int(row["attributes"]["name"].split("_")[1])
        chosen = [cell for cell in sorted(cells) if n < max(diagnostics[cell])]
        listing = inspect_listing(related(row), metadata / f"cycle{n}_folders.json")["data"]
        folders = {
            r["attributes"]["name"]: r for r in listing if r["attributes"]["kind"] == "folder"
        }
        records = inspect_listing(
            related(folders["_processed_mat"]), metadata / f"cycle{n}_mat.json"
        )["data"]
        entries = []
        for cell in chosen:
            record = next(r for r in records if r["attributes"]["name"] == f"{cell}.mat")
            legacy = "G1_cycling_1.mat" if cell == "G1" and n == 1 else None
            entries.append(
                selection_entry(record, f"cycling/Cycling_{n}", "cycling_mat", n, cell, legacy)
            )
            exports = inspect_listing(
                related(folders[cell]), metadata / f"cycle{n}_{cell}_raw.json"
            )["data"]
            exports = cycling_exports(exports, metadata, f"cycle{n}_{cell}_raw")
            matches = matching_files(exports, cell)
            if not matches:
                raise ValueError(f"No raw time anchor for {cell} batch {n}")
            record = min(matches, key=export_order)
            legacy = "G1_cycling1_first_export.xlsx" if cell == "G1" and n == 1 else None
            entries.append(
                selection_entry(record, f"anchors/Cycling_{n}", "cycling_anchor", n, cell, legacy)
            )
            # Native end clocks establish exposure availability without assuming
            # that the instrument's elapsed clock remained aligned for days.
            tail = max(matches, key=export_order)
            entries.append(
                selection_entry(tail, f"tails/Cycling_{n}", "cycling_end_anchor", n, cell)
            )
        return entries

    jobs = [
        (diagnostic, row)
        for row in diag_root["data"]
        if re.fullmatch(r"Diag_\d+", row["attributes"]["name"])
    ]
    jobs += [
        (cycling, row)
        for row in cycle_root["data"]
        if re.fullmatch(r"Cycling_\d+", row["attributes"]["name"])
    ]
    entries, completed, errors = [], [], []
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = {executor.submit(fn, row): row["attributes"]["name"] for fn, row in jobs}
        for task in as_completed(tasks):
            try:
                entries.extend(task.result())
                completed.append(tasks[task])
                print(
                    json.dumps({"inventoried": tasks[task], "selected_so_far": len(entries)}),
                    flush=True,
                )
            except Exception as error:
                errors.append({"folder": tasks[task], "error": str(error)})
                print(json.dumps({"inventory_error": errors[-1]}), flush=True)
            (audit / "source_inventory_status.json").write_text(
                json.dumps(
                    {
                        "completed_folders": completed,
                        "errors": errors,
                        "selected_files": len(entries),
                    },
                    indent=2,
                )
                + "\n"
            )
    if errors:
        raise ValueError(f"Incomplete source inventory; see source_inventory_status.json: {errors}")
    entries.sort(key=lambda row: (row["kind"], row["number"], row["cell_id"], row["path"]))
    if len({row["path"] for row in entries}) != len(entries):
        raise ValueError("Duplicate acquisition destination")
    result = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha256_file(root / "configs/transfer_protocol_v2.yaml"),
        "raw_root": str(raw.relative_to(root)),
        "files": entries,
    }
    (audit / "source_selection.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def verify_file(path):
    if path.suffix == ".xlsx":
        with ZipFile(path) as archive:
            if archive.testzip() is not None or "xl/workbook.xml" not in archive.namelist():
                raise ValueError("Incomplete or corrupt workbook")
    elif path.suffix == ".mat":
        if not whosmat(path):
            raise ValueError("No readable MATLAB variables")
    else:
        raise ValueError("Unsupported source sample")


def download_one(raw, entry, pinned):
    raw = raw.resolve()
    destination = (raw / entry["path"]).resolve()
    if not destination.is_relative_to(raw):
        raise ValueError("Download destination escapes raw data directory")
    parts = urlsplit(entry["url"])
    if parts.scheme != "https" or parts.hostname not in {"osf.io", "files.osf.io"}:
        raise ValueError("Unexpected first-life download origin")
    receipt = destination.with_suffix(destination.suffix + ".receipt.json")
    if destination.exists() and receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved["remote_id"] != entry["remote_id"] or saved["sha256"] != sha256_file(destination):
            raise ValueError("Acquired file differs from its pinned receipt")
        return saved
    destination.parent.mkdir(parents=True, exist_ok=True)
    legacy = raw / entry["legacy"] if entry["legacy"] else None
    if not destination.exists() and legacy is not None and legacy.exists():
        if pinned.get(legacy.name) != sha256_file(legacy):
            raise ValueError("Legacy audited source changed")
        shutil.copy2(legacy, destination)
    if not destination.exists():
        if shutil.disk_usage(raw).free < 6 * MAX_FILE_BYTES:
            raise OSError("Insufficient space for bounded source acquisition")
        acquired = sum(path.stat().st_size for path in raw.rglob("*") if path.is_file())
        if acquired + 4 * MAX_FILE_BYTES > MAX_TOTAL_BYTES:
            raise OSError("Acquisition reached the 32 GiB audited-source budget")
        partial = destination.with_suffix(destination.suffix + ".part")
        failures = []
        for attempt in range(3):
            cmd = [
                "curl",
                "--fail",
                "--location",
                "--connect-timeout",
                "30",
                "--max-time",
                "1800",
                "--max-filesize",
                str(MAX_FILE_BYTES),
                "--silent",
                "--show-error",
                entry["url"],
                "--output",
                str(partial),
            ]
            # Do not concatenate partial responses when the provider ignores Range headers.
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                partial.rename(destination)
                break
            failures.append(result.stderr.strip()[-300:])
            print(
                json.dumps(
                    {"retry": entry["path"], "attempt": attempt + 1, "curl_exit": result.returncode}
                ),
                flush=True,
            )
        else:
            raise RuntimeError(f"Download failed: {entry['path']}: {failures}")
    verify_file(destination)
    result = {
        "path": entry["path"],
        "remote_id": entry["remote_id"],
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "hash_basis": "Locally pinned completed TLS download; no upstream checksum supplied",
    }
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"downloaded": entry["path"], "bytes": result["bytes"]}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    audit = root / "outputs/transfer/source_audit"
    selection_path = audit / "source_selection.json"
    selection = (
        json.loads(selection_path.read_text()) if selection_path.exists() else inventory(root)
    )
    if selection["protocol_sha256"] != sha256_file(root / "configs/transfer_protocol_v2.yaml"):
        raise ValueError("Cached acquisition selection belongs to a different protocol snapshot")
    print(json.dumps({"selected_files": len(selection["files"])}), flush=True)
    if args.download:
        raw = root / selection["raw_root"]
        summary = json.loads((audit / "audit_summary.json").read_text())
        pinned = {
            Path(row["path"]).name: row["local_snapshot_sha256"]
            for row in summary["acquired_sources"]
        }
        results, errors = [], []
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = {
                executor.submit(download_one, raw, entry, pinned): entry
                for entry in selection["files"]
            }
            for task in as_completed(tasks):
                try:
                    results.append(task.result())
                except Exception as error:
                    errors.append({"path": tasks[task]["path"], "error": str(error)})
                    print(json.dumps(errors[-1]), flush=True)
        (audit / "download_results.json").write_text(
            json.dumps({"completed": results, "errors": errors}, indent=2) + "\n"
        )
        if errors:
            raise SystemExit(1)
        print(
            json.dumps(
                {
                    "status": "acquired",
                    "files": len(results),
                    "bytes": sum(row["bytes"] for row in results),
                }
            ),
            flush=True,
        )
