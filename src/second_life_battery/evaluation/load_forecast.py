"""Matched day-ahead demand errors, validation-only selection and paired day blocks."""

import numpy as np
import pandas as pd

from second_life_battery.evaluation.metrics import point_metrics


def load_error_tables(predictions):
    required = ["split", "model", "origin", "timestamp", "load_kw", "prediction_kw"]
    if not set(required).issubset(predictions):
        raise ValueError("Load predictions lack required labels or identities")
    if predictions.duplicated(required[:4]).any():
        raise ValueError("Duplicate forecast origin/target/model")
    counts = predictions.groupby(["split", "origin", "model"]).size().unstack("model")
    if counts.isna().any().any() or counts.ne(96).any().any():
        raise ValueError("Forecast models do not cover identical complete days")
    if predictions.groupby(["split", "origin", "timestamp"]).load_kw.nunique().gt(1).any():
        raise ValueError("Matched candidates have different demand observations")
    values = predictions[["load_kw", "prediction_kw"]].to_numpy(float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Demand observations and forecasts must be finite and nonnegative")
    records = []
    for key, frame in predictions.groupby(["split", "model", "origin"]):
        frame = frame.sort_values("timestamp")
        expected = pd.date_range(pd.Timestamp(key[2]), periods=96, freq="15min")
        if not pd.DatetimeIndex(frame.timestamp).equals(expected):
            raise ValueError("Demand metrics require a complete matched 96-quarter day")
        truth, estimate = frame.load_kw.to_numpy(), frame.prediction_kw.to_numpy()
        error = estimate - truth
        actual_peak, forecast_peak = int(np.argmax(truth)), int(np.argmax(estimate))
        records.append(
            {
                "split": key[0],
                "model": key[1],
                "origin": key[2],
                "mse_kw2": float(np.mean(error**2)),
                "rmse_kw": point_metrics(truth, estimate)["rmse"],
                "mae_kw": float(np.mean(abs(error))),
                "bias_kw": float(np.mean(error)),
                "energy_error_kwh": float(error.sum() * 0.25),
                "peak_error_kw": float(estimate.max() - truth.max()),
                "peak_absolute_error_kw": float(abs(estimate.max() - truth.max())),
                "peak_time_absolute_error_minutes": abs(actual_peak - forecast_peak) * 15,
                "underestimated_peak": bool(estimate.max() < truth.max()),
            }
        )
    daily = pd.DataFrame(records)
    if daily.empty:
        raise ValueError("Demand evaluation is empty")
    summary = (
        daily.groupby(["split", "model"])
        .agg(
            days=("origin", "size"),
            mse_kw2=("mse_kw2", "mean"),
            mae_kw=("mae_kw", "mean"),
            bias_kw=("bias_kw", "mean"),
            mean_energy_error_kwh=("energy_error_kwh", "mean"),
            mean_peak_absolute_error_kw=("peak_absolute_error_kw", "mean"),
            mean_peak_time_absolute_error_minutes=("peak_time_absolute_error_minutes", "mean"),
            underestimated_peak_days=("underestimated_peak", "sum"),
        )
        .reset_index()
    )
    summary["rmse_kw"] = np.sqrt(summary.mse_kw2)
    return summary, daily


def select_load_candidate(validation_summary, candidates):
    if set(validation_summary.split) != {"validation"}:
        raise ValueError("Candidate selection requires validation scores only")
    if (
        validation_summary.model.duplicated().any()
        or set(validation_summary.model) != set(candidates)
        or not np.isfinite(validation_summary.rmse_kw).all()
        or validation_summary.days.nunique() != 1
    ):
        raise ValueError("Validation candidates or evaluation coverage differ")
    ranked = validation_summary.assign(day_weight=validation_summary.model.map(candidates))
    return ranked.sort_values(["rmse_kw", "day_weight", "model"]).iloc[0].model


def paired_load_interval(test_daily, selected, *, block_days, repetitions, seed):
    if set(test_daily.split) != {"test"}:
        raise ValueError("Paired forecast comparison requires test days only")
    table = test_daily.pivot(index="origin", columns="model", values="mse_kw2").sort_index()
    if selected not in table or "weekly" not in table or table.isna().any().any():
        raise ValueError("Test origins are not matched across forecast candidates")
    days = len(table)
    if (
        not days
        or block_days < 1
        or days % block_days
        or repetitions < 1
        or not np.isfinite(table.to_numpy()).all()
        or (table.to_numpy() < 0).any()
        or not pd.DatetimeIndex(table.index).equals(
            pd.date_range(table.index[0], periods=days, freq="D")
        )
    ):
        raise ValueError("Bootstrap requires consecutive days and valid complete blocks")
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, days, size=(repetitions, days // block_days))
    indices = ((starts[..., None] + np.arange(block_days)) % days).reshape(repetitions, days)
    chosen, weekly = table[selected].to_numpy(), table.weekly.to_numpy()
    draws = np.sqrt(chosen[indices].mean(axis=1)) - np.sqrt(weekly[indices].mean(axis=1))
    low, high = np.quantile(draws, [0.025, 0.975])
    return {
        "selected": selected,
        "reference": "weekly",
        "days": days,
        "rmse_difference_kw": float(np.sqrt(chosen.mean()) - np.sqrt(weekly.mean())),
        "descriptive_low_95_kw": float(low),
        "descriptive_high_95_kw": float(high),
        "block_days": block_days,
        "repetitions": repetitions,
        "seed": seed,
    }
