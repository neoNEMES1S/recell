"""Build v3 tables from sealed availability evidence; never open the original v2 gate."""

import json
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.ev_prefix_sequences import source_sequences
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.transfer import physical_folds, validate_features
from second_life_battery.utils.reproducibility import verify_artifacts


def build(root):
    protocol_path = root / "configs/transfer_protocol_v3.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    registered = root / "outputs/transfer" / protocol["protocol_id"]
    registration_path = registered / "registration.json"
    registration = json.loads(registration_path.read_text())
    if (
        registration["protocol_sha256"] != sha256_file(protocol_path)
        or sha256_file(registered / "protocol.yaml") != registration["protocol_sha256"]
    ):
        raise ValueError("Availability protocol differs from its sealed registration")
    inputs = {
        str(protocol_path.relative_to(root)): sha256_file(protocol_path),
        str(registration_path.relative_to(root)): sha256_file(registration_path),
    }
    frames, labels = [], []
    for relative, digest in protocol["availability_evidence"].items():
        path = root / relative
        if sha256_file(path) != digest:
            raise ValueError("Registered availability evidence changed")
        inputs[relative] = digest
        evidence = json.loads(path.read_text())
        verify_artifacts(path.parent, evidence["artifacts"])
        dependencies = evidence.get("inputs", evidence.get("code", {}))
        for name, expected in dependencies.items():
            if sha256_file(root / name) != expected:
                raise ValueError(f"Availability dependency changed: {name}")
        if "present_inputs" in evidence:
            selection_path = root / "outputs/transfer/extra_source_audit_v1/selection.json"
            if sha256_file(selection_path) != evidence["selection_sha256"]:
                raise ValueError("Extra-cell selection changed")
            selection = json.loads(selection_path.read_text())
            for name, expected in selection["inputs"].items():
                if sha256_file(root / name) != expected:
                    raise ValueError("Extra-cell inventory dependency changed")
            for name, expected in evidence["present_inputs"].items():
                if sha256_file(root / selection["raw_root"] / name) != expected:
                    raise ValueError("Extra-cell raw measurement changed")
        elif evidence["prefix_code_sha256"] != sha256_file(
            root / "src/second_life_battery/data/ev_prefix.py"
        ):
            raise ValueError("Verified prefix implementation changed")
        frames.append(pd.read_csv(path.parent / "verified_feature_prefixes.csv"))
        labels.append(pd.read_csv(path.parent / "verified_capacity_labels.csv"))
    features = pd.concat(frames, ignore_index=True)
    capacities = pd.concat(labels, ignore_index=True)
    eligible = set(protocol["source"]["eligible_gradient_physical_cells"])
    validation = protocol["source"]["validation_physical_cell"]
    cells = eligible | {validation}
    features = features[features.physical_cell_id.isin(cells)].copy()
    capacities = capacities[capacities.physical_cell_id.isin(cells)].copy()
    for frame in [features, capacities]:
        if "timestamp" not in frame:
            frame["timestamp"] = frame.diagnostic_end_time
        for name in ["timestamp", "diagnostic_start_time", "diagnostic_end_time"]:
            times = pd.to_datetime(frame[name], format="ISO8601", errors="raise")
            frame[name] = [time.isoformat(timespec="microseconds") for time in times]
        frame.sort_values(["physical_cell_id", "diagnostic"], inplace=True)
    samples = source_sequences(features, capacities)
    counts = {cell: sum(s.cell_id == cell for s in samples) for cell in sorted(cells)}
    if counts != protocol["source"]["registered_origin_counts"]:
        raise ValueError("Measured source origin counts differ from the registration")
    if {"elapsed_days", "cumulative_ah_since_stage_start"} & set(capacities):
        raise ValueError("Unknown future covariates entered the measured-capacity label table")
    target_path = root / protocol["data"]["target"]
    target = pd.read_csv(target_path)
    validate_features(target)
    registry_path = root / "configs/cell_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    physical = {row["physical_cell_id"]: row for row in registry["cells"]}
    if physical[validation]["second_life_source_id"] is not None or validation in set(
        target.physical_cell_id
    ):
        raise ValueError("Source validation must be physically independent of every target cell")
    for row in features.itertuples():
        if physical[row.physical_cell_id]["first_life_source_id"] != row.cell_id:
            raise ValueError("Source feature alias differs from its physical-cell registry")
    folds = []
    for fold in physical_folds(target):
        allowed = sorted(eligible & set(fold.training))
        if not allowed or set(allowed) & {fold.test, fold.validation, validation}:
            raise ValueError("Availability source gradient identities cross a held-out role")
        folds.append(
            {
                "test": fold.test,
                "target_validation": fold.validation,
                "target_gradient": list(fold.training),
                "source_gradient": allowed,
                "source_validation": validation,
                "source_training_origins": sum(counts[cell] for cell in allowed),
                "source_validation_origins": counts[validation],
                "unavailable_source_training_cells": sorted(set(fold.training) - eligible),
            }
        )
    output = (root / protocol["data"]["provenance"]).parent
    output.mkdir(parents=True, exist_ok=False)
    features.to_csv(root / protocol["data"]["source_features"], index=False)
    capacities.to_csv(root / protocol["data"]["source_labels"], index=False)
    paths = {key: protocol["data"][key] for key in ["source_features", "source_labels", "target"]}
    inputs.update({relative: sha256_file(root / relative) for relative in paths.values()})
    inputs[str(registry_path.relative_to(root))] = sha256_file(registry_path)
    result = {
        "status": "v3_tables_verified; fold_range_and_initialization_gates_pending",
        "protocol_id": protocol["protocol_id"],
        "inputs": inputs,
        "source_origins_by_cell": counts,
        "fold_availability": folds,
        "code": {
            str(path.relative_to(root)): sha256_file(path)
            for path in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/ev_prefix_sequences.py",
                root / "src/second_life_battery/data/transfer.py",
            ]
        },
        "runtime": {name: version(name) for name in ["numpy", "pandas", "scipy", "torch"]},
        "limitations": [
            protocol["source"]["limitation"],
            "v2 remains blocked; this separately registered source-pool expansion "
            "is not its result.",
            "No source/transfer fit or model promotion is authorized by the table builder alone.",
        ],
    }
    (output / "feature_provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"status": result["status"], "counts": counts, "fold_availability": folds}, indent=2
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent)
