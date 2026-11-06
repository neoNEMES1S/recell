"""Bounded, fold-specific validation selection without pooling outer-test identities."""

import argparse
import copy
import platform
import time
from dataclasses import asdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import yaml

from second_life_battery.data.sequences import fit_preprocessor, make_sequences, tabular_features
from second_life_battery.models.baselines import fit_baseline, predict_baseline
from second_life_battery.training.cross_validation import lobo_folds, split_fold
from second_life_battery.training.trainer import predict_gru, resolve_device, train_gru
from second_life_battery.utils.reproducibility import seed_everything
from second_life_battery.utils.study import begin, complete, write_json


def candidate_config(base, candidate, device):
    config = copy.deepcopy(base)
    for name in ["tree_depth", "tree_learning_rate"]:
        if name in candidate:
            config["baselines"][name] = candidate[name]
    if "hidden_size" in candidate:
        config["gru"]["hidden_size"] = candidate["hidden_size"]
    if "learning_rate" in candidate:
        config["training"]["learning_rate"] = candidate["learning_rate"]
    config["training"]["device"] = device
    return config


def forecast(model, name, samples, scaler, horizon):
    if name in {"gru", "pgp_gru", "quantile_gru"}:
        values = predict_gru(model, samples, scaler)
        return values if values.ndim == 3 else np.stack([values, values, values], axis=-1)
    values = predict_baseline(
        model, tabular_features(samples, scaler), np.array([s.origin_soh for s in samples]), horizon
    )
    return np.stack([values, values, values], axis=-1)


def run(config_path, output, smoke=False, device=None):
    protocol = yaml.safe_load(config_path.read_text())
    requested = device or protocol["device"]
    actual_device = resolve_device(requested)
    if len(protocol["candidates"]) != 15 or len({c["id"] for c in protocol["candidates"]}) != 15:
        raise ValueError("Expected 12 registered new settings plus three fixed references")
    base = yaml.safe_load(Path(protocol["base_config"]).read_text())
    record = begin(output, config_path, [protocol["base_config"], protocol["data"]])
    write_json(
        output / "runtime.json",
        {
            "requested": requested,
            "actual": str(actual_device),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda_version": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name() if actual_device.type == "cuda" else None,
            "DGX_verified": False,
            "scope": "local CPU development"
            if requested == "cpu"
            else "GPU execution; DGX host identity still requires its allocation receipt",
        },
    )
    frame = pd.read_csv(protocol["data"], parse_dates=["timestamp"])
    folds = lobo_folds(frame)[:1] if smoke else lobo_folds(frame)
    seeds = protocol["seeds"][:1] if smoke else protocol["seeds"]
    trials, selections, predictions, fits = [], [], [], {}
    for fold in folds:
        train, validation, test = split_fold(frame, fold)
        scaler = fit_preprocessor(train, base["features"])
        samples = [
            make_sequences(
                part,
                base["features"],
                base["evaluation"]["horizon"],
                min_history=base["evaluation"]["minimum_history"],
            )
            for part in [train, validation, test]
        ]
        folder = output / fold.test
        folder.mkdir()
        joblib.dump(scaler, folder / "scaler.joblib")
        write_json(folder / "roles.json", {**asdict(fold), "scaler_cells": list(fold.training)})
        for candidate in protocol["candidates"]:
            for seed in seeds:
                seed_everything(seed)
                config = candidate_config(base, candidate, requested)
                name = candidate["model"]
                start = time.perf_counter()
                if name in {"gru", "pgp_gru", "quantile_gru"}:
                    model = train_gru(
                        samples[0],
                        samples[1],
                        scaler,
                        config,
                        folder / f"{candidate['id']}_{seed}.pt",
                        name,
                    )
                else:
                    model = fit_baseline(
                        name,
                        tabular_features(samples[0], scaler),
                        np.stack([s.target - s.origin_soh for s in samples[0]]),
                        config["baselines"],
                        seed,
                    )
                    joblib.dump(model, folder / f"{candidate['id']}_{seed}.joblib")
                elapsed = time.perf_counter() - start
                q = forecast(model, name, samples[1], scaler, base["evaluation"]["horizon"])
                error = q[:, 0, 1] - np.array([s.target[0] for s in samples[1]])
                if not np.isfinite(q).all():
                    raise ValueError("Nonfinite validation predictions")
                trials.append(
                    {
                        "test_cell": fold.test,
                        "validation_cell": fold.validation,
                        "candidate": candidate["id"],
                        "model": name,
                        "seed": seed,
                        "validation_rmse_soh": float(np.sqrt(np.mean(error**2))),
                        "fit_seconds": elapsed,
                        "status": "success",
                    }
                )
                fits[(candidate["id"], seed)] = model
        ranking = (
            pd.DataFrame([r for r in trials if r["test_cell"] == fold.test])
            .groupby("candidate")
            .validation_rmse_soh.mean()
            .sort_values(kind="stable")
        )
        winner = sorted(ranking.index, key=lambda c: (ranking[c], c))[0]
        selection = {
            "test_cell": fold.test,
            "validation_cell": fold.validation,
            "selected": winner,
            "selected_validation_rmse_soh": float(ranking[winner]),
            "test_scored_at_selection": False,
        }
        selections.append(selection)
        # Seal selection before touching test predictions or their errors.
        write_json(folder / "selection.json", selection)
        candidates = {c["id"]: c for c in protocol["candidates"]}
        for label in [*protocol["fixed_comparators"], "selected"]:
            identifier = winner if label == "selected" else label
            name = candidates[identifier]["model"]
            for seed in seeds:
                model = fits[(identifier, seed)]
                start = time.perf_counter()
                q = forecast(model, name, samples[2], scaler, base["evaluation"]["horizon"])
                latency = (time.perf_counter() - start) / len(samples[2])
                for i, sample in enumerate(samples[2]):
                    for h in range(base["evaluation"]["horizon"]):
                        predictions.append(
                            {
                                "cell_id": fold.test,
                                "model": label,
                                "candidate": identifier,
                                "seed": seed,
                                "origin_time": sample.origin_time,
                                "target_time": sample.target_times[h],
                                "horizon": h + 1,
                                "reference_capacity_ah": sample.reference_capacity_ah,
                                "y_true": float(sample.target[h]),
                                "q10": float(q[i, h, 0]),
                                "q50": float(q[i, h, 1]),
                                "q90": float(q[i, h, 2]),
                                "probabilistic": name in {"pgp_gru", "quantile_gru"},
                                "inference_seconds_per_sample": latency,
                            }
                        )
        fits.clear()
    pd.DataFrame(trials).to_csv(output / "trials.csv", index=False)
    write_json(output / "selections.json", selections)
    predicted = pd.DataFrame(predictions)
    predicted.to_csv(output / "predictions.csv", index=False)
    metrics = []
    for (cell, model, seed, h), rows in predicted.groupby(["cell_id", "model", "seed", "horizon"]):
        error = (rows.q50 - rows.y_true) * 100
        metrics.append(
            {
                "cell_id": cell,
                "model": model,
                "seed": seed,
                "horizon": h,
                "rmse_pp": float(np.sqrt(np.mean(error**2))),
                "mae_pp": float(np.mean(abs(error))),
            }
        )
    per_cell = (
        pd.DataFrame(metrics)
        .groupby(["cell_id", "model", "horizon"])[["rmse_pp", "mae_pp"]]
        .mean()
        .reset_index()
    )
    per_cell.to_csv(output / "per_cell.csv", index=False)
    summary = per_cell.groupby(["model", "horizon"])[["rmse_pp", "mae_pp"]].mean().reset_index()
    summary.to_csv(output / "summary.csv", index=False)
    complete(
        output,
        record,
        smoke=smoke,
        folds=len(folds),
        seeds=seeds,
        trials=len(trials),
        prediction_rows=len(predictions),
        external_validation=False,
        runtime=str(actual_device),
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/model_selection_v1.yaml"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--device", choices=["cpu", "cuda", "auto"])
    a = p.parse_args()
    run(a.config, a.output, a.smoke, a.device)
