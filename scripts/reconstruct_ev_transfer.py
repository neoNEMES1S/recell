"""Build the registered first-life common features only after complete causal checks."""

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml
from openpyxl import load_workbook

from second_life_battery.data.ev_exposure import audit_segmented_batch, causal_features
from second_life_battery.data.first_life import audit_raw_capacity
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.parser import is_channel_sheet, merge_exports, read_channel
from second_life_battery.data.transfer import validate_features


def reviewed_raw_batches(root: Path):
    """Accept only explicitly reviewed, hash-bound complete raw reconstructions."""
    config_path = root / "configs/ev_raw_replacements.yaml"
    if not config_path.exists():
        return {}, [], {}
    config = yaml.safe_load(config_path.read_text())
    audit = root / "outputs/transfer/source_audit"
    report_path = audit / "raw_review_audit.json"
    plan_path = audit / "raw_review_selection.json"
    if config["report_sha256"] != sha256_file(report_path) or config[
        "selection_sha256"
    ] != sha256_file(plan_path):
        raise ValueError("Reviewed raw replacement evidence changed")
    report, plan = [json.loads(p.read_text()) for p in [report_path, plan_path]]
    if (
        report["selection_sha256"] != sha256_file(plan_path)
        or plan["source_selection_sha256"] != sha256_file(audit / "source_selection.json")
        or plan["protocol_sha256"] != sha256_file(root / "configs/transfer_protocol_v2.yaml")
    ):
        raise ValueError("Reviewed raw replacement source/protocol mismatch")
    for name, digest in report["code"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or sha256_file(path) != digest:
            raise ValueError("Reviewed raw replacement audit code changed")
    expected = {(row["cell_id"], row["number"]) for row in config["batches"]}
    results = {(row["cell_id"], row["number"]): row for row in report["batches"]}
    plans = {(row["cell_id"], row["number"]): row for row in plan["batches"]}
    if (
        set(results) != expected
        or set(plans) != expected
        or len(results) != len(report["batches"])
        or len(plans) != len(plan["batches"])
    ):
        raise ValueError("Reviewed raw replacement batch coverage changed")
    raw = root / plan["raw_root"]
    entries = {row["path"]: row for row in plan["files"]}
    if set(entries) != set(report["inputs"]) or len(entries) != len(plan["files"]):
        raise ValueError("Reviewed raw replacement input coverage changed")
    inputs = []
    for name, entry in entries.items():
        path = (raw / name).resolve()
        if not path.is_relative_to(raw.resolve()):
            raise ValueError("Reviewed raw replacement escapes source directory")
        receipt = json.loads(path.with_suffix(path.suffix + ".receipt.json").read_text())
        digest = sha256_file(path)
        if (
            receipt["remote_id"] != entry["remote_id"]
            or receipt["sha256"] != digest
            or report["inputs"][name] != digest
        ):
            raise ValueError("Reviewed raw replacement source receipt changed")
        inputs.append({**entry, "sha256": digest})
    replacements = {}
    for key, result in results.items():
        batch = plans[key]
        if (
            result["status"] != "raw_measurements_verified; causal_diagnostic_gate_still_required"
            or result["raw_fragments"] != len(batch["ordered_paths"])
            or any(
                (entries[name]["cell_id"], entries[name]["number"]) != key
                for name in batch["ordered_paths"]
            )
        ):
            raise ValueError("Reviewed raw replacement was not verified for this physical cell")
        replacements[key] = {
            "result": {
                **result,
                "accepted_input_basis": "Explicitly reviewed complete raw exports",
            },
            "inputs": {name: report["inputs"][name] for name in batch["ordered_paths"]},
        }
    bindings = {
        str(p.relative_to(root)): sha256_file(p) for p in [config_path, report_path, plan_path]
    }
    return replacements, inputs, bindings


def reconstruct(root: Path, *, audit_available: bool = False) -> dict:
    audit = root / "outputs/transfer/source_audit"
    selection_path = audit / "source_selection.json"
    selection = json.loads(selection_path.read_text())
    protocol_path = root / "configs/transfer_protocol_v2.yaml"
    if selection["protocol_sha256"] != sha256_file(protocol_path):
        raise ValueError("Acquisition protocol mismatch")
    protocol = yaml.safe_load(protocol_path.read_text())
    segments_path = audit / "source_segments.json"
    segments = json.loads(segments_path.read_text())
    if (
        segments["source_selection_sha256"] != sha256_file(selection_path)
        or segments["protocol_sha256"] != selection["protocol_sha256"]
    ):
        raise ValueError("Source-part selection differs from the pinned acquisition/protocol")
    part_plans = {(row["cell_id"], row["number"]): row for row in segments["batches"]}
    expected_batches = {
        (row["cell_id"], row["number"])
        for row in selection["files"]
        if row["kind"] == "cycling_mat"
    }
    if set(part_plans) != expected_batches or len(part_plans) != len(segments["batches"]):
        raise ValueError("Source-part plan omits or duplicates a registered cycling batch")
    raw = root / selection["raw_root"]
    cache = audit / "reconstruction_cache"
    cache.mkdir(exist_ok=True)
    code = {
        str(path.relative_to(root)): sha256_file(path)
        for path in [
            Path(__file__).resolve(),
            root / "src/second_life_battery/data/ev_exposure.py",
            root / "src/second_life_battery/data/first_life.py",
            root / "src/second_life_battery/data/parser.py",
            root / "src/second_life_battery/data/features.py",
            root / "src/second_life_battery/data/transfer.py",
            root / "src/second_life_battery/data/sequences.py",
        ]
    }
    replacements, reviewed_inputs, bindings = reviewed_raw_batches(root)
    code.update(bindings)
    inputs, pending = [], []
    for entry in [*selection["files"], *segments["extra_files"]]:
        path = (raw / entry["path"]).resolve()
        if not path.is_relative_to(raw.resolve()):
            raise ValueError("Source input escapes the dataset directory")
        receipt_path = path.with_suffix(path.suffix + ".receipt.json")
        if not path.exists() or not receipt_path.exists():
            if not audit_available:
                raise ValueError(f"Incomplete acquisition: {entry['path']}")
            pending.append(entry["path"])
            continue
        receipt = json.loads(receipt_path.read_text())
        if receipt["remote_id"] != entry["remote_id"] or receipt["sha256"] != sha256_file(path):
            raise ValueError(f"Source differs from pinned receipt: {entry['path']}")
        inputs.append({**entry, "sha256": receipt["sha256"]})
    present = {row["path"] for row in inputs}
    inputs.extend(row for row in reviewed_inputs if row["path"] not in present)
    expected_cells = set(protocol["target"]["cells"])
    if set(row["cell_id"] for row in selection["files"]) != expected_cells:
        raise ValueError("Unexpected acquisition cell pool")
    if len({row["path"] for row in inputs}) != len(inputs):
        raise ValueError("Duplicate source input path")
    by_path = {row["path"]: row for row in inputs}
    base_paths = {row["path"] for row in selection["files"]}
    frame = pd.DataFrame(
        [row for row in inputs if row["path"] in base_paths],
        columns=["path", "kind", "cell_id", "number", "sha256"],
    )
    registry_path = root / "configs/cell_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    identities = {row["first_life_source_id"]: row["physical_cell_id"] for row in registry["cells"]}
    reference_path = audit / "first_life_capacity_checkpoints.csv"
    reference = pd.read_csv(reference_path)
    diagnostics, batches, failed = [], [], []
    for (cell, number), group in frame[frame.kind == "diagnostic"].groupby(["cell_id", "number"]):
        needed = [
            row
            for row in selection["files"]
            if row["kind"] == "diagnostic" and row["cell_id"] == cell and row["number"] == number
        ]
        if len(group) != len(needed):
            continue  # A diagnostic is audited only after all its export fragments arrive.
        dependencies = dict(zip(group.path, group.sha256))
        cache_path = cache / f"diagnostic_{cell}_{number}.json"
        saved = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        if saved.get("inputs") == dependencies and saved.get("code") == code:
            result = saved["result"]
        else:
            exports = []
            for row in group.itertuples():
                book = load_workbook(raw / row.path, read_only=True, data_only=True)
                try:
                    sheets = [name for name in book.sheetnames if is_channel_sheet(name)]
                finally:
                    book.close()
                if len(sheets) != 1:
                    raise ValueError("Ambiguous raw diagnostic measurement channel")
                exports.append(
                    read_channel(
                        raw,
                        {
                            "source_file": row.path,
                            "sha256": row.sha256,
                            "observation_table": sheets[0],
                        },
                        root / "data/interim/ev_channel",
                    )
                )
            merged, duplicates = merge_exports(exports)
            result = audit_raw_capacity(merged)
            result["exact_duplicate_rows_removed"] = duplicates
            expected = reference[(reference.cell_id == cell) & (reference.diagnostic == number)]
            if len(expected) != 1:
                raise ValueError("Unexpected diagnostic in selected source")
            error = (
                abs(result["capacity_ah"] - expected.capacity_ah.iloc[0])
                / expected.capacity_ah.iloc[0]
            )
            if error > 0.01:
                raise ValueError("Raw and author-processed capacity differ by more than 1%")
            result["raw_vs_processed_relative_error"] = float(error)
            cache_path.write_text(
                json.dumps({"inputs": dependencies, "code": code, "result": result}, indent=2)
                + "\n"
            )
        diagnostics.append(
            {
                **result,
                "cell_id": cell,
                "physical_cell_id": identities[cell],
                "diagnostic": int(number),
                "source_dataset": "stanford_ev_real_driving_first_life",
                "capacity_protocol": "separate_C20_discharge",
                "diagnostic_source_sha256": json.dumps(dependencies, sort_keys=True),
                "quality_flags": "raw_counter_and_processed_capacity_agree_within_1pct",
            }
        )
        print(json.dumps({"diagnostic_verified": f"{cell}/{number}"}), flush=True)
    cycling = frame[frame.kind != "diagnostic"]
    trajectories = {}
    for (cell, number), group in cycling.groupby(["cell_id", "number"]):
        kinds = group.groupby("kind").size().to_dict()
        if kinds != {"cycling_mat": 1, "cycling_anchor": 1, "cycling_end_anchor": 1}:
            if audit_available and pending:
                continue
            raise ValueError("Every batch requires processed current and both native endpoints")
        dependencies = dict(zip(group.path, group.sha256))
        plan = part_plans[(cell, int(number))]
        mat_row = group[group.kind.eq("cycling_mat")].iloc[0]
        if plan["mat_path"] != mat_row.path or not plan["segments"]:
            raise ValueError("Source-part plan changes the cycling MAT association")
        if audit_available and any(
            part[f"{role}_path"] not in by_path
            for part in plan["segments"]
            for role in ["first", "last"]
        ):
            continue
        endpoints = []
        for index, part in enumerate(plan["segments"], 1):
            if part["segment_index"] != index:
                raise ValueError("Source restart parts are not in reviewed sequence")
            paths = []
            for role in ["first", "last"]:
                name = part[f"{role}_path"]
                row = by_path[name]
                if (
                    row["cell_id"] != cell
                    or row["number"] != number
                    or row["kind"]
                    not in {"cycling_anchor", "cycling_end_anchor", "cycling_segment_anchor"}
                ):
                    raise ValueError("Source-part endpoint crosses a cell/batch boundary")
                dependencies[name] = row["sha256"]
                paths.append(raw / name)
            endpoints.append(tuple(paths))
        cache_path = cache / f"cycling_{cell}_{number}.json"
        replacement = replacements.get((cell, int(number)))
        if replacement is not None:
            dependencies.update(replacement["inputs"])
        saved = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        if (
            saved.get("inputs") == dependencies
            and saved.get("code") == code
            and saved.get("segments") == plan["segments"]
        ):
            result = saved["result"]
        else:
            try:
                result = (
                    replacement["result"]
                    if replacement is not None
                    else audit_segmented_batch(raw / mat_row.path, endpoints)
                )
            except ValueError as error:
                if not audit_available:
                    raise
                failure = {"cell_id": cell, "number": int(number), "error": str(error)}
                failed.append(failure)
                print(json.dumps({"cycling_rejected": failure}), flush=True)
                continue
            cache_path.write_text(
                json.dumps(
                    {
                        "inputs": dependencies,
                        "code": code,
                        "segments": plan["segments"],
                        "result": result,
                    },
                    indent=2,
                )
                + "\n"
            )
        fingerprint = result["numeric_trajectory_sha256"]
        previous = trajectories.get(fingerprint)
        if previous is not None and previous["cell_id"] != cell:
            failure = {
                "cell_id": cell,
                "number": int(number),
                "error": f"Numeric trajectory duplicates another physical cell: {previous}",
            }
            if not audit_available:
                raise ValueError(failure["error"])
            failed.append(failure)
            print(json.dumps({"cycling_rejected": failure}), flush=True)
            continue
        trajectories[fingerprint] = {"cell_id": cell, "number": int(number)}
        batches.append({**result, "cell_id": cell, "number": int(number)})
        print(json.dumps({"cycling_verified": f"{cell}/{number}"}), flush=True)
    if pending or failed:
        progress = {
            "status": (
                "source_validation_failed; no_feature_dataset_promoted"
                if failed
                else "acquisition_incomplete; no_feature_dataset_promoted"
            ),
            "pending_inputs": pending,
            "failed_cycling_batches": failed,
            "verified_diagnostics": len(diagnostics),
            "verified_cycling_batches": len(batches),
            "source_selection_sha256": sha256_file(selection_path),
            "segment_selection_sha256": sha256_file(segments_path),
            "code": code,
        }
        (audit / "reconstruction_progress.json").write_text(json.dumps(progress, indent=2) + "\n")
        print(
            json.dumps(
                {
                    key: progress[key]
                    for key in ["status", "verified_diagnostics", "verified_cycling_batches"]
                }
            ),
            flush=True,
        )
        return progress
    source = causal_features(pd.DataFrame(diagnostics), pd.DataFrame(batches))
    expected = reference[reference.cell_id.isin(expected_cells)]
    if set(zip(source.cell_id, source.diagnostic)) != set(
        zip(expected.cell_id, expected.diagnostic)
    ):
        raise ValueError("Reconstruction omitted accepted source diagnostics")
    validate_features(source)
    target_path = root / "data/processed/transfer/target_checkpoints.csv"
    target = pd.read_csv(target_path)
    validate_features(target)
    for cell, history in source.groupby("physical_cell_id"):
        following = target[target.physical_cell_id == cell]
        if (
            following.empty
            or pd.to_datetime(history.timestamp).max() >= pd.to_datetime(following.timestamp).min()
        ):
            raise ValueError("First/second-life boundary clocks overlap")
    destination = root / "data/processed/transfer/source_checkpoints.csv"
    temporary = destination.with_suffix(".csv.part")
    source.to_csv(temporary, index=False)
    temporary.replace(destination)
    pd.DataFrame(
        [{k: v for k, v in row.items() if not isinstance(v, (list, dict))} for row in batches]
    ).to_csv(audit / "verified_cycling_batches.csv", index=False)
    (audit / "verified_cycling_batches.json").write_text(json.dumps(batches, indent=2) + "\n")
    manifest = {
        "status": "causal_features_verified; fold_and_range_audit_required_before_training",
        "source_rows": len(source),
        "source_cells": sorted(expected_cells),
        "cycling_batches": len(batches),
        "source_sha256": sha256_file(destination),
        "target_sha256": sha256_file(target_path),
        "registry_sha256": sha256_file(registry_path),
        "protocol_sha256": sha256_file(protocol_path),
        "selection_sha256": sha256_file(selection_path),
        "segment_selection_sha256": sha256_file(segments_path),
        "capacity_reference_sha256": sha256_file(reference_path),
        "target_counter_audit_sha256": sha256_file(audit / "target_exposure_counter_audit.json"),
        "code": code,
        "inputs": inputs,
        "timestamp_limitation": (
            "Native instrument wall clocks; timezone unverified. "
            "No weather/timezone alignment implied."
        ),
    }
    (audit / "feature_provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k not in {"inputs", "code"}}, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-available",
        action="store_true",
        help="Cache complete acquired-unit audits; never promote incomplete features",
    )
    args = parser.parse_args()
    reconstruct(Path(__file__).resolve().parent.parent, audit_available=args.audit_available)
