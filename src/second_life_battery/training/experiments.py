"""Reproducible outer-fold experiments and per-cell/seed/horizon metric exports."""

import json
from dataclasses import asdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from second_life_battery.data.sequences import fit_preprocessor, make_sequences, tabular_features
from second_life_battery.evaluation.metrics import point_metrics, probabilistic_metrics
from second_life_battery.models.baselines import fit_baseline, predict_baseline
from second_life_battery.training.cross_validation import lobo_folds, split_fold
from second_life_battery.training.trainer import predict_gru, train_gru
from second_life_battery.utils.logging import configure_logging
from second_life_battery.utils.reproducibility import save_run, seed_everything


def export_metrics(predictions: pd.DataFrame, output: Path) -> pd.DataFrame:
    """Report fold metrics and macro means/std across cells after averaging repeated seeds."""
    records = []
    keys = ["model", "seed", "history_fraction", "cell_id"]
    for key, group in predictions.groupby(keys):
        for horizon in [0, *sorted(group.horizon.unique())]:
            rows = group if horizon == 0 else group[group.horizon == horizon]
            for unit in ["soh", "capacity_ah"]:
                scale = rows.reference_capacity_ah.to_numpy() if unit == "capacity_ah" else 1
                target = rows.y_true.to_numpy() * scale
                prediction = rows.q50.to_numpy() * scale
                metrics = point_metrics(target, prediction)
                if rows.q10.notna().all() and rows.q90.notna().all():
                    q = rows[["q10", "q50", "q90"]].to_numpy()
                    q = q * (scale[:, None] if isinstance(scale, np.ndarray) else scale)
                    metrics.update(probabilistic_metrics(target, q))
                records.append(
                    {
                        **dict(zip(keys, key)),
                        "horizon": horizon,
                        "unit": unit,
                        "n_predictions": len(rows),
                        **metrics,
                    }
                )
    fold_metrics = pd.DataFrame(records)
    fold_metrics.to_csv(output / "fold_metrics.csv", index=False)
    fold_metrics.to_json(output / "fold_metrics.json", orient="records", indent=2)
    metric_names = [
        name for name in fold_metrics if name not in keys + ["horizon", "unit", "n_predictions"]
    ]
    averaged = fold_metrics.groupby(["model", "history_fraction", "cell_id", "horizon", "unit"])[
        metric_names
    ].mean()
    summary = averaged.groupby(["model", "history_fraction", "horizon", "unit"]).agg(
        ["mean", "std"]
    )
    summary.columns = ["_".join(column) for column in summary.columns]
    summary.reset_index().to_csv(output / "summary.csv", index=False)
    return fold_metrics


def run_experiments(
    config: dict, root: Path, limited: bool = False, output_name: str | None = None
) -> pd.DataFrame:
    """Train each model once per fold/seed; vary only test context in limited-history evaluation."""
    output = root / "outputs" / (output_name or ("limited_history" if limited else "lobo"))
    save_run(config, root, output)
    checkpoints = output / "checkpoints"
    checkpoints.mkdir(exist_ok=True)
    log = configure_logging(output / "experiments.jsonl")
    frame = pd.read_csv(root / "data/processed/checkpoints.csv", parse_dates=["timestamp"])
    features = config["features"]
    horizon = config["evaluation"]["horizon"]
    minimum = config["evaluation"]["minimum_history"]
    fractions = config["evaluation"]["history_fractions"] if limited else [1.0]
    predictions = []
    fold_records = []
    for fold in lobo_folds(frame):
        train, validation, test = split_fold(frame, fold)
        scaler = fit_preprocessor(train, features)
        train_samples = make_sequences(train, features, horizon, min_history=minimum)
        validation_samples = make_sequences(validation, features, horizon, min_history=minimum)
        train_x = tabular_features(train_samples, scaler)
        origins = np.array([sample.origin_soh for sample in train_samples])
        labels = np.stack([sample.target for sample in train_samples])
        fold_records.append(
            {
                **asdict(fold),
                "scaler_fit_cells": sorted(train.cell_id.unique()),
                "train_samples": len(train_samples),
                "validation_samples": len(validation_samples),
            }
        )
        for seed in config["evaluation"]["seeds"]:
            for name in config["evaluation"]["models"]:
                seed_everything(seed)
                recurrent = name in {"gru", "pgp_gru", "quantile_gru"}
                if recurrent:
                    model = train_gru(
                        train_samples,
                        validation_samples,
                        scaler,
                        config,
                        checkpoints / f"{name}_{fold.test}_{seed}.pt",
                        name,
                    )
                else:
                    model = fit_baseline(
                        name, train_x, labels - origins[:, None], config["baselines"], seed
                    )
                joblib.dump(
                    {
                        "model": None if recurrent else model,
                        "preprocessor": scaler,
                        "features": features,
                        "fold": asdict(fold),
                        "horizon": horizon,
                    },
                    checkpoints / f"{name}_{fold.test}_{seed}.joblib",
                )
                for fraction in fractions:
                    samples = make_sequences(test, features, horizon, fraction, minimum)
                    test_x = tabular_features(samples, scaler)
                    predicted = (
                        predict_gru(model, samples, scaler)
                        if recurrent
                        else predict_baseline(
                            model,
                            test_x,
                            np.array([sample.origin_soh for sample in samples]),
                            horizon,
                        )
                    )
                    probabilistic = predicted.ndim == 3
                    point = predicted[..., 1] if probabilistic else predicted
                    for index, sample in enumerate(samples):
                        for step in range(horizon):
                            predictions.append(
                                {
                                    "model": name,
                                    "seed": seed,
                                    "history_fraction": fraction,
                                    "cell_id": sample.cell_id,
                                    "origin_index": sample.origin_index,
                                    "origin_time": sample.origin_time,
                                    "target_time": sample.target_times[step],
                                    "horizon": step + 1,
                                    "effective_history": len(sample.history),
                                    "origin_soh": sample.origin_soh,
                                    "reference_capacity_ah": sample.reference_capacity_ah,
                                    "y_true": sample.target[step],
                                    "q10": predicted[index, step, 0] if probabilistic else np.nan,
                                    "q50": point[index, step],
                                    "q90": predicted[index, step, 2] if probabilistic else np.nan,
                                }
                            )
                log.info("fold_model_complete: test=%s model=%s seed=%s", fold.test, name, seed)
    results = pd.DataFrame(predictions)
    results.to_csv(output / "predictions.csv", index=False)
    (output / "folds.json").write_text(json.dumps(fold_records, indent=2))
    export_metrics(results, output)
    return results
