"""Run the sealed transfer comparison only after complete feature and smoke gates."""

import argparse
import json
import os
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
import yaml
from audit_prefix_transfer import audit as audit_prefix
from audit_transfer_features import audit

from second_life_battery.data.ev_prefix_sequences import source_sequences
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.prefix_transfer import split_prefix_transfer
from second_life_battery.data.sequences import fit_preprocessor, make_sequences, tabular_features
from second_life_battery.data.transfer import FEATURES, physical_folds, split_transfer
from second_life_battery.models.baselines import fit_baseline, predict_baseline
from second_life_battery.training.experiments import export_metrics
from second_life_battery.training.trainer import predict_gru, train_gru
from second_life_battery.utils.reproducibility import save_run, seed_everything, verify_artifacts


def model_config(base, protocol, fold, hashes, scaler_hash, stage, seed, *, stage_roles=None):
    config = {key: deepcopy(base[key]) for key in ["gru", "training", "physics"]}
    config.update(
        features=FEATURES.copy(),
        evaluation={
            "horizon": protocol["source" if stage == "first_life" else "target"]["horizon"]
        },
    )
    config["transfer"] = {
        "stage": stage,
        "seed": seed,
        "protocol_sha256": hashes["protocol"],
        "registry_sha256": hashes["registry"],
        "scaler_sha256": scaler_hash,
        "datasets": {key: hashes[key] for key in ["source", "target"]},
        "feature_order": FEATURES.copy(),
        "feature_units": ["1", "day", "Ah"],
        "normalization": "first_accepted_stage_capacity",
        "quantiles": [0.1, 0.5, 0.9],
        "gradient_cells": list(fold.training),
        "validation_cell": fold.validation,
        "test_cell": fold.test,
    }
    if stage_roles is not None:
        config["transfer"].update(deepcopy(stage_roles[stage]))
        config["transfer"]["stage_roles"] = deepcopy(stage_roles)
        config["transfer"]["source_labels_sha256"] = hashes["source_labels"]
    return config


def prediction_rows(arm, seed, fraction, samples, predicted):
    predicted = np.asarray(predicted)
    probabilistic = predicted.ndim == 3
    shape = (len(samples), len(samples[0].target)) + ((3,) if probabilistic else ())
    if predicted.shape != shape or not np.isfinite(predicted).all():
        raise ValueError("Transfer predictions have invalid shape or nonfinite values")
    if probabilistic and (np.diff(predicted, axis=-1) < 0).any():
        raise ValueError("Transfer quantiles are not ordered")
    rows = []
    for i, sample in enumerate(samples):
        for h, truth in enumerate(sample.target):
            rows.append(
                {
                    "model": arm,
                    "seed": seed,
                    "history_fraction": fraction,
                    "cell_id": sample.cell_id,
                    "origin_index": sample.origin_index,
                    "origin_time": sample.origin_time,
                    "target_time": sample.target_times[h],
                    "horizon": h + 1,
                    "effective_history": len(sample.history),
                    "origin_soh": sample.origin_soh,
                    "reference_capacity_ah": sample.reference_capacity_ah,
                    "y_true": float(truth),
                    "q10": predicted[i, h, 0] if probabilistic else np.nan,
                    "q50": predicted[i, h, 1] if probabilistic else predicted[i, h],
                    "q90": predicted[i, h, 2] if probabilistic else np.nan,
                }
            )
    return rows


def run(root: Path, *, smoke: bool, protocol_version: int = 2):
    if protocol_version not in {2, 3}:
        raise ValueError("Transfer protocol version must be 2 or 3")
    prefix = protocol_version == 3
    gate = audit_prefix(root) if prefix else audit(root)
    protocol_path = root / f"configs/transfer_protocol_v{protocol_version}.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    registered = root / "outputs/transfer" / protocol["protocol_id"]
    base_path = root / "outputs/lobo/config.yaml"
    reference = json.loads((root / protocol["reference"]["manifest"]).read_text())
    original = next(row for row in reference["files"] if row["path"] == "outputs/lobo/config.yaml")
    if sha256_file(base_path) != original["sha256"]:
        raise ValueError("Reference model settings changed since the freeze")
    base = yaml.safe_load(base_path.read_text())
    paths = {
        "source": root
        / (
            protocol["data"]["source_features"]
            if prefix
            else "data/processed/transfer/source_checkpoints.csv"
        ),
        "target": root
        / (
            protocol["data"]["target"]
            if prefix
            else "data/processed/transfer/target_checkpoints.csv"
        ),
        "protocol": protocol_path,
        "registry": root / "configs/cell_registry.yaml",
        "feature_gate": registered / "feature_gate.json",
        "reference_settings": base_path,
    }
    if prefix:
        paths["source_labels"] = root / protocol["data"]["source_labels"]
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    implementation = [
        Path(__file__).resolve(),
        *sorted((root / "src/second_life_battery").rglob("*.py")),
    ]
    code = {str(path.relative_to(root)): sha256_file(path) for path in implementation}
    runtime = {"OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS")}
    if not smoke:
        completed = json.loads((registered / "smoke/completion.json").read_text())
        if (
            completed.get("status") != "smoke_passed"
            or completed["inputs"] != hashes
            or completed["code"] != code
            or completed.get("runtime") != runtime
        ):
            raise ValueError("A matching successful one-fold/seed smoke run is required")
        verify_artifacts(registered / "smoke", completed["artifacts"])
    output = registered / ("smoke" if smoke else "comparison")
    output.mkdir(exist_ok=False)
    save_run(protocol, root, output, inputs=paths)
    (output / "implementation.json").write_text(json.dumps(code, indent=2) + "\n")
    (output / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
    for path in implementation:
        snapshot = output / "code_snapshot" / path.relative_to(root)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(path.read_bytes())
    source, target = [pd.read_csv(paths[key]) for key in ["source", "target"]]
    labels = pd.read_csv(paths["source_labels"]) if prefix else None
    folds = physical_folds(target)
    seeds = protocol["target"]["seeds"]
    if smoke:
        folds, seeds = folds[:1], seeds[:1]
    records, times = [], []
    for fold in folds:
        folder = output / fold.test
        folder.mkdir()
        parts = (
            split_prefix_transfer(source, target, fold, protocol)
            if prefix
            else split_transfer(source, target, fold)
        )
        stage_roles = (
            {
                "first_life": {
                    "gradient_cells": sorted(parts["source_train"].physical_cell_id.unique()),
                    "validation_cell": protocol["source"]["validation_physical_cell"],
                },
                "second_life": {
                    "gradient_cells": list(fold.training),
                    "validation_cell": fold.validation,
                },
            }
            if prefix
            else None
        )
        scaler = fit_preprocessor(parts["target_train"], FEATURES)
        scaler_path = folder / "scaler.joblib"
        joblib.dump(scaler, scaler_path)
        samples = {}
        for key, rows in parts.items():
            domain = protocol["source" if key.startswith("source") else "target"]
            samples[key] = (
                source_sequences(rows, labels[labels.physical_cell_id.isin(rows.physical_cell_id)])
                if prefix and key.startswith("source")
                else make_sequences(
                    rows.assign(cell_id=rows.physical_cell_id),
                    FEATURES,
                    domain["horizon"],
                    min_history=domain["minimum_history"],
                )
            )
        test_contexts = {
            fraction: make_sequences(
                parts["target_test"].assign(cell_id=parts["target_test"].physical_cell_id),
                FEATURES,
                protocol["target"]["horizon"],
                fraction,
                protocol["target"]["minimum_history"],
            )
            for fraction in protocol["target"]["inference_context_fractions"]
        }

        def origins(rows):
            return [(s.cell_id, s.origin_time, s.target_times) for s in rows]

        if any(origins(rows) != origins(samples["target_test"]) for rows in test_contexts.values()):
            raise ValueError("Transfer inference contexts change target origins")
        for seed in seeds:
            parents = {}
            for name in ["pgp_gru", "quantile_gru"]:
                seed_everything(seed)
                parent = folder / f"source_{name}_{seed}.pt"
                config = model_config(
                    base,
                    protocol,
                    fold,
                    hashes,
                    sha256_file(scaler_path),
                    "first_life",
                    seed,
                    stage_roles=stage_roles,
                )
                started = perf_counter()
                train_gru(
                    samples["source_train"],
                    samples["source_validation"],
                    scaler,
                    config,
                    parent,
                    name,
                )
                times.append(
                    {
                        "test": fold.test,
                        "seed": seed,
                        "stage": "source",
                        "model": name,
                        "fit_wall_seconds": perf_counter() - started,
                    }
                )
                parents[name] = parent
            for arm, name, transfer in [
                ("R1", "pgp_gru", False),
                ("R2", "pgp_gru", True),
                ("R3", "quantile_gru", False),
                ("R4", "quantile_gru", True),
                ("R5", "xgboost", False),
                ("R6", "persistence", False),
            ]:
                seed_everything(seed)
                started = perf_counter()
                if arm in {"R1", "R2", "R3", "R4"}:
                    config = model_config(
                        base,
                        protocol,
                        fold,
                        hashes,
                        sha256_file(scaler_path),
                        "second_life",
                        seed,
                        stage_roles=stage_roles,
                    )
                    model = train_gru(
                        samples["target_train"],
                        samples["target_validation"],
                        scaler,
                        config,
                        folder / f"{arm}_{seed}.pt",
                        name,
                        parent_checkpoint=parents[name] if transfer else None,
                    )
                else:
                    train = samples["target_train"]
                    model = fit_baseline(
                        name,
                        tabular_features(train, scaler),
                        np.stack([s.target - s.origin_soh for s in train]),
                        base["baselines"],
                        seed,
                    )
                    joblib.dump(model, folder / f"{arm}_{seed}.joblib")
                times.append(
                    {
                        "test": fold.test,
                        "seed": seed,
                        "stage": "target",
                        "model": arm,
                        "fit_wall_seconds": perf_counter() - started,
                    }
                )
                for fraction, test in test_contexts.items():
                    predicted = (
                        predict_gru(model, test, scaler)
                        if arm in {"R1", "R2", "R3", "R4"}
                        else predict_baseline(
                            model,
                            tabular_features(test, scaler),
                            np.array([s.origin_soh for s in test]),
                            protocol["target"]["horizon"],
                        )
                    )
                    records.extend(prediction_rows(arm, seed, fraction, test, predicted))
            print(
                json.dumps({"test": fold.test, "seed": seed, "all_arms_complete": True}), flush=True
            )
    predictions = pd.DataFrame(records)
    predictions.to_csv(output / "predictions.csv", index=False)
    export_metrics(predictions, output)
    pd.DataFrame(times).to_csv(output / "fit_times.csv", index=False)
    (output / "folds.json").write_text(
        json.dumps([asdict(fold) for fold in folds], indent=2) + "\n"
    )
    completion = {
        "status": "smoke_passed" if smoke else "comparison_fits_complete; report_required",
        "inputs": hashes,
        "code": code,
        "runtime": runtime,
        "folds": len(folds),
        "seeds": seeds,
        "arms": ["R1", "R2", "R3", "R4", "R5", "R6"],
        "prediction_rows": len(predictions),
        "feature_gate_status": gate["status"],
        "predictions_sha256": sha256_file(output / "predictions.csv"),
        "artifacts": {
            str(path.relative_to(output)): sha256_file(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    }
    (output / "completion.json").write_text(json.dumps(completion, indent=2) + "\n")
    return completion


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="First registered fold and seed only")
    parser.add_argument("--protocol-version", type=int, choices=[2, 3], default=2)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(
                    Path(__file__).resolve().parent.parent,
                    smoke=args.smoke,
                    protocol_version=args.protocol_version,
                ),
                indent=2,
            )
        )
    except (ValueError, FileNotFoundError) as error:
        raise SystemExit(f"Transfer training gate closed: {error}") from error
