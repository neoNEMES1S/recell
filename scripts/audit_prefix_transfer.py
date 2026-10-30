"""Verify v3 provenance, unchanged target origins, physical splits and domain ranges."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.ev_prefix_sequences import source_sequences
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.prefix_transfer import split_prefix_transfer
from second_life_battery.data.sequences import fit_preprocessor, make_sequences
from second_life_battery.data.transfer import FEATURES, physical_folds
from second_life_battery.utils.reproducibility import verify_artifacts


def audit(root):
    protocol_path = root / "configs/transfer_protocol_v3.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    registered = root / "outputs/transfer" / protocol["protocol_id"]
    registration = json.loads((registered / "registration.json").read_text())
    if (
        registration["protocol_sha256"] != sha256_file(protocol_path)
        or sha256_file(registered / "protocol.yaml") != registration["protocol_sha256"]
    ):
        raise ValueError("v3 protocol differs from its sealed registration")
    if protocol["features"]["primary"] != FEATURES:
        raise ValueError("v3 feature order differs from the registered contract")

    def check_inputs(values):
        for relative, digest in values.items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()) or sha256_file(path) != digest:
                raise ValueError(f"v3 provenance input changed: {relative}")

    provenance_path = root / protocol["data"]["provenance"]
    provenance = json.loads(provenance_path.read_text())
    check_inputs(provenance["inputs"])
    check_inputs(provenance["code"])
    check_inputs(protocol["availability_evidence"])
    for relative in protocol["availability_evidence"]:
        path = root / relative
        evidence = json.loads(path.read_text())
        verify_artifacts(path.parent, evidence["artifacts"])
        if "present_inputs" in evidence:
            check_inputs(evidence["code"])
            selection_path = root / "outputs/transfer/extra_source_audit_v1/selection.json"
            if sha256_file(selection_path) != evidence["selection_sha256"]:
                raise ValueError("Extra-cell inventory changed")
            selection = json.loads(selection_path.read_text())
            check_inputs(selection["inputs"])
            check_inputs(
                {
                    str(Path(selection["raw_root"]) / name): digest
                    for name, digest in evidence["present_inputs"].items()
                }
            )
        else:
            check_inputs(evidence["inputs"])
            if evidence["prefix_code_sha256"] != sha256_file(
                root / "src/second_life_battery/data/ev_prefix.py"
            ):
                raise ValueError("Original prefix implementation changed")
    target_evidence_path = root / "data/processed/transfer/target_provenance.json"
    target_evidence = json.loads(target_evidence_path.read_text())
    check_inputs(target_evidence["code_sha256"])
    target_path = root / protocol["data"]["target"]
    original_path = root / "data/processed/checkpoints.csv"
    if target_evidence["target_sha256"] != sha256_file(target_path) or target_evidence[
        "source_checkpoints_sha256"
    ] != sha256_file(original_path):
        raise ValueError("Target feature derivation changed")
    reference = json.loads((root / protocol["reference"]["manifest"]).read_text())
    frozen = next(
        row for row in reference["files"] if row["path"] == str(original_path.relative_to(root))
    )
    if frozen["sha256"] != sha256_file(original_path):
        raise ValueError("Historical target checkpoints changed")
    source = pd.read_csv(root / protocol["data"]["source_features"])
    labels = pd.read_csv(root / protocol["data"]["source_labels"])
    target = pd.read_csv(target_path)
    all_source_samples = source_sequences(source, labels)
    counts = {
        cell: sum(s.cell_id == cell for s in all_source_samples)
        for cell in sorted(source.physical_cell_id.unique())
    }
    if counts != protocol["source"]["registered_origin_counts"]:
        raise ValueError("v3 source origin counts changed")
    registry = yaml.safe_load((root / "configs/cell_registry.yaml").read_text())
    aliases = {
        r["second_life_source_id"]: r["physical_cell_id"]
        for r in registry["cells"]
        if r["second_life_source_id"] is not None
    }
    original = pd.read_csv(original_path)
    original["cell_id"] = original.cell_id.map(aliases)
    settings = yaml.safe_load((root / "outputs/lobo/config.yaml").read_text())
    domain = protocol["target"]

    def origins(samples):
        return [(s.cell_id, s.origin_time, s.target_times, s.target.tolist()) for s in samples]

    expected = make_sequences(
        original, settings["features"], domain["horizon"], min_history=domain["minimum_history"]
    )
    actual = make_sequences(
        target.assign(cell_id=target.physical_cell_id),
        FEATURES,
        domain["horizon"],
        min_history=domain["minimum_history"],
    )
    if origins(expected) != origins(actual):
        raise ValueError("v3 target origins or outcomes differ from the historical benchmark")

    def summary(values):
        finite = [float(value) for value in values if value is not None]
        return {
            "available": len(finite),
            "unavailable": len(values) - len(finite),
            "min": min(finite) if finite else None,
            "median": float(np.median(finite)) if finite else None,
            "max": max(finite) if finite else None,
        }

    folds = []
    for fold in physical_folds(target):
        parts = split_prefix_transfer(source, target, fold, protocol)
        scaler = fit_preprocessor(parts["target_train"], FEATURES)
        minimum = parts["target_train"][FEATURES].min().to_numpy()
        maximum = parts["target_train"][FEATURES].max().to_numpy()
        record = {
            "test": fold.test,
            "validation": fold.validation,
            "training": list(fold.training),
            "features": FEATURES,
            "scaler_fit_physical_cells": sorted(parts["target_train"].physical_cell_id.unique()),
            "scaler_medians": scaler[0].statistics_.tolist(),
            "scaler_mean": scaler[1].mean_.tolist(),
            "scaler_scale": scaler[1].scale_.tolist(),
            "partitions": {},
        }
        for name, rows in parts.items():
            if name.startswith("source"):
                samples = source_sequences(
                    rows, labels[labels.physical_cell_id.isin(rows.physical_cell_id)]
                )
            else:
                samples = make_sequences(
                    rows.assign(cell_id=rows.physical_cell_id),
                    FEATURES,
                    domain["horizon"],
                    min_history=domain["minimum_history"],
                )
            per_cell = {
                cell: sum(s.cell_id == cell for s in samples)
                for cell in sorted(rows.physical_cell_id.unique())
            }
            if not per_cell or any(count == 0 for count in per_cell.values()):
                raise ValueError("A v3 partition has no usable forecast origin")
            if name == "target_test":
                for fraction in domain["inference_context_fractions"]:
                    reduced = make_sequences(
                        rows.assign(cell_id=rows.physical_cell_id),
                        FEATURES,
                        domain["horizon"],
                        fraction,
                        domain["minimum_history"],
                    )
                    if origins(reduced) != origins(samples):
                        raise ValueError("v3 inference context changes target origins")
            lookup = {
                (r.physical_cell_id, str(r.timestamp)): r.cumulative_ah_since_stage_start
                for r in rows.itertuples()
            }
            spacing = {h: {"days": [], "ah": []} for h in range(1, len(samples[0].target) + 1)}
            for sample in samples:
                for horizon, future_time in enumerate(sample.target_times, 1):
                    days = (
                        pd.Timestamp(future_time) - pd.Timestamp(sample.origin_time)
                    ).total_seconds() / 86400
                    if days <= 0:
                        raise ValueError("v3 future label does not follow its origin")
                    future = lookup.get((sample.cell_id, future_time))
                    ah = (
                        None
                        if future is None
                        else future - lookup[(sample.cell_id, sample.origin_time)]
                    )
                    if ah is not None and ah < 0:
                        raise ValueError("v3 future exposure precedes its origin")
                    spacing[horizon]["days"].append(days)
                    spacing[horizon]["ah"].append(ah)
            values = rows[FEATURES].to_numpy(dtype=float)
            record["partitions"][name] = {
                "checkpoint_rows": len(rows),
                "origins_by_cell": per_cell,
                "feature_min": values.min(axis=0).tolist(),
                "feature_max": values.max(axis=0).tolist(),
                "outside_target_training_range_rows_by_feature": (
                    (values < minimum) | (values > maximum)
                )
                .sum(axis=0)
                .tolist(),
                "max_abs_standardized_by_feature": np.abs(scaler.transform(values))
                .max(axis=0)
                .tolist(),
                "forecast_spacing": {
                    h: {key: summary(values) for key, values in metrics.items()}
                    for h, metrics in spacing.items()
                },
            }
        folds.append(record)
    result = {
        "status": "feature_gate_passed",
        "protocol_id": protocol["protocol_id"],
        "inputs": provenance["inputs"],
        "feature_provenance_sha256": sha256_file(provenance_path),
        "target_provenance_sha256": sha256_file(target_evidence_path),
        "code": {
            str(path.relative_to(root)): sha256_file(path)
            for path in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/prefix_transfer.py",
                root / "src/second_life_battery/data/ev_prefix_sequences.py",
            ]
        },
        "folds": folds,
        "target_origin_count": len(actual),
        "limitations": provenance["limitations"]
        + [
            "Six familiar target batteries are not an independent new cohort.",
            "Unavailable future source Ah spacing is reported, never imputed.",
            "Native timestamp timezones remain unverified.",
        ],
    }
    (registered / "feature_gate.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"status": result["status"], "folds": len(folds), "target_origins": len(actual)}
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
