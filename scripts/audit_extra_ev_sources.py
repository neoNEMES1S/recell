"""Audit acquired extra-cell measurements; keep capacity labels and causal prefixes separate."""

import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yaml
from openpyxl import load_workbook

from second_life_battery.data.ev_exposure import audit_segmented_batch
from second_life_battery.data.ev_prefix import verified_source_prefixes
from second_life_battery.data.first_life import audit_raw_capacity
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.parser import is_channel_sheet, merge_exports, read_channel


def audit(root):
    folder = root / "outputs/transfer/extra_source_audit_v1"
    selection_path = folder / "selection.json"
    selection = json.loads(selection_path.read_text())
    for relative, digest in selection["inputs"].items():
        if sha256_file(root / relative) != digest:
            raise ValueError("Extra-source inventory inputs changed")
    raw = (root / selection["raw_root"]).resolve()
    present, pending = {}, []
    for entry in selection["files"]:
        path = (raw / entry["path"]).resolve()
        if not path.is_relative_to(raw):
            raise ValueError("Extra-source file escapes the raw dataset directory")
        receipt_path = path.with_suffix(path.suffix + ".receipt.json")
        if not path.exists() or not receipt_path.exists():
            pending.append(entry["path"])
            continue
        receipt = json.loads(receipt_path.read_text())
        if receipt["remote_id"] != entry["remote_id"] or receipt["sha256"] != sha256_file(path):
            raise ValueError("Extra-source acquisition differs from pinned receipt")
        present[entry["path"]] = {**entry, "sha256": receipt["sha256"]}
    registry = yaml.safe_load((root / "configs/cell_registry.yaml").read_text())
    identities = {row["first_life_source_id"]: row["physical_cell_id"] for row in registry["cells"]}
    for cell in selection["cells"]:
        row = next(row for row in registry["cells"] if row["first_life_source_id"] == cell)
        if row["second_life_source_id"] is not None:
            raise ValueError("Extra source unexpectedly aliases a target cell")
    reference_path = root / "outputs/transfer/source_audit/first_life_capacity_checkpoints.csv"
    reference = pd.read_csv(reference_path)
    code_paths = [
        Path(__file__).resolve(),
        *[
            root / "src/second_life_battery/data" / name
            for name in [
                "ev_exposure.py",
                "ev_prefix.py",
                "first_life.py",
                "parser.py",
                "features.py",
            ]
        ],
    ]
    code = {str(path.relative_to(root)): sha256_file(path) for path in code_paths}
    code[str(reference_path.relative_to(root))] = sha256_file(reference_path)
    runtime = {name: version(name) for name in ["numpy", "pandas", "scipy", "openpyxl"]}
    cache = folder / "cache"
    cache.mkdir(exist_ok=True)
    diagnostics, batches, failures = [], [], []

    def cached_result(name, dependencies, compute):
        path = cache / name
        saved = json.loads(path.read_text()) if path.exists() else {}
        if saved.get("inputs") == dependencies and saved.get("code") == code:
            return saved["result"]
        result = compute()
        path.write_text(
            json.dumps({"inputs": dependencies, "code": code, "result": result}, indent=2) + "\n"
        )
        return result

    for cell in selection["cells"]:
        for number in range(1, 5):
            entries = [
                row
                for row in selection["files"]
                if row["kind"] == "diagnostic"
                and row["cell_id"] == cell
                and row["number"] == number
            ]
            if not entries or any(row["path"] not in present for row in entries):
                continue
            dependencies = {row["path"]: present[row["path"]]["sha256"] for row in entries}

            def diagnostic():
                frames = []
                for entry in entries:
                    book = load_workbook(raw / entry["path"], read_only=True, data_only=True)
                    try:
                        channels = [name for name in book.sheetnames if is_channel_sheet(name)]
                    finally:
                        book.close()
                    if len(channels) != 1:
                        raise ValueError("Ambiguous extra-cell diagnostic channel")
                    frames.append(
                        read_channel(
                            raw,
                            {
                                "source_file": entry["path"],
                                "sha256": dependencies[entry["path"]],
                                "observation_table": channels[0],
                            },
                            root / "data/interim/extra_ev_channel_v1",
                        )
                    )
                merged, duplicates = merge_exports(frames)
                result = audit_raw_capacity(merged)
                expected = reference[(reference.cell_id == cell) & reference.diagnostic.eq(number)]
                if len(expected) != 1:
                    raise ValueError("Extra-cell diagnostic has no unique numeric reference")
                difference = abs(result["capacity_ah"] - expected.capacity_ah.iloc[0])
                relative = float(difference / expected.capacity_ah.iloc[0])
                if relative > 0.01:
                    raise ValueError("Extra-cell raw/processed capacity differs by more than 1%")
                return {
                    **result,
                    "raw_vs_processed_relative_error": relative,
                    "exact_duplicate_rows_removed": duplicates,
                }

            try:
                result = cached_result(f"diagnostic_{cell}_{number}.json", dependencies, diagnostic)
                diagnostics.append(
                    {
                        **result,
                        "cell_id": cell,
                        "physical_cell_id": identities[cell],
                        "diagnostic": number,
                        "source_hashes": json.dumps(dependencies, sort_keys=True),
                    }
                )
                print(json.dumps({"verified_diagnostic": f"{cell}/{number}"}), flush=True)
            except ValueError as exc:
                failures.append(
                    {"cell_id": cell, "number": number, "kind": "diagnostic", "error": str(exc)}
                )
    trajectories = {}
    original = root / "outputs/transfer/source_audit/reconstruction_cache"
    for path in original.glob("cycling_*.json"):
        record = json.loads(path.read_text())["result"]
        if "numeric_trajectory_sha256" in record:
            trajectories[record["numeric_trajectory_sha256"]] = path.stem
    for plan in selection["batches"]:
        cell, number = plan["cell_id"], plan["number"]
        names = [
            plan["mat_path"],
            *[part[key] for part in plan["segments"] for key in ["first_path", "last_path"]],
        ]
        if any(name not in present for name in names):
            continue
        if any(
            present[name]["cell_id"] != cell or present[name]["number"] != number for name in names
        ):
            raise ValueError("Extra-cell batch input identities differ")
        dependencies = {name: present[name]["sha256"] for name in names}

        def cycling():
            if [p["segment_index"] for p in plan["segments"]] != list(
                range(1, len(plan["segments"]) + 1)
            ):
                raise ValueError("Extra-cell raw restart parts are not in reviewed sequence")
            return audit_segmented_batch(
                raw / plan["mat_path"],
                [(raw / p["first_path"], raw / p["last_path"]) for p in plan["segments"]],
            )

        try:
            result = cached_result(f"cycling_{cell}_{number}.json", dependencies, cycling)
            digest = result["numeric_trajectory_sha256"]
            if digest in trajectories:
                raise ValueError(f"Duplicate numeric trajectory: {trajectories[digest]}")
            trajectories[digest] = f"extra_{cell}_{number}"
            batches.append(
                {
                    **result,
                    "cell_id": cell,
                    "physical_cell_id": identities[cell],
                    "number": number,
                    "source_hashes": json.dumps(dependencies, sort_keys=True),
                }
            )
            print(json.dumps({"verified_batch": f"{cell}/{number}"}), flush=True)
        except ValueError as exc:
            failures.append(
                {"cell_id": cell, "number": number, "kind": "cycling", "error": str(exc)}
            )
    features, labels, availability = verified_source_prefixes(
        pd.DataFrame(diagnostics), pd.DataFrame(batches)
    )
    output = folder / "runs" / datetime.now(timezone.utc).strftime("audit_%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    features.to_csv(output / "verified_feature_prefixes.csv", index=False)
    labels.to_csv(output / "verified_capacity_labels.csv", index=False)
    availability.to_json(output / "availability.json", orient="records", indent=2)
    (output / "batches.json").write_text(json.dumps(batches, indent=2) + "\n")
    (output / "failures.json").write_text(json.dumps(failures, indent=2) + "\n")
    result = {
        "status": "acquisition_incomplete"
        if pending
        else "selective_availability_audit_complete; no_training_authorization",
        "selection_sha256": sha256_file(selection_path),
        "code": code,
        "runtime": runtime,
        "present_inputs": {name: row["sha256"] for name, row in present.items()},
        "pending_inputs": pending,
        "verified_diagnostics": len(diagnostics),
        "verified_cycling_batches": len(batches),
        "failed_units": len(failures),
        "scope": "First four capacity labels and first two cycling batches of W4/W5/W7. "
        "A future label supplies no unknown exposure to its earlier input history. "
        "Source pool and feature protocol v2 remain unchanged; no training gate opens.",
        "artifacts": {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    (folder / "latest.json").write_text(
        json.dumps(
            {
                "run": str(output.relative_to(root)),
                "audit_sha256": sha256_file(output / "audit.json"),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "verified_diagnostics",
                    "verified_cycling_batches",
                    "failed_units",
                ]
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
