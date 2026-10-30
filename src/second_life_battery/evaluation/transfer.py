"""Registered paired-cell transfer comparisons; no fitting or test-driven selection."""

from itertools import product

import numpy as np
import pandas as pd

from second_life_battery.evaluation.metrics import point_metrics, probabilistic_metrics


def analyze_transfer(predictions: pd.DataFrame, protocol: dict, cells: list[str]) -> dict:
    """Reject unmatched/incomplete evaluations before seed-then-cell aggregation."""
    arms = [f"R{i}" for i in range(1, 7)]
    target = protocol["target"]
    seeds, fractions = target["seeds"], target["inference_context_fractions"]
    horizons = list(range(1, target["horizon"] + 1))
    keys = [
        "seed",
        "history_fraction",
        "cell_id",
        "origin_index",
        "origin_time",
        "target_time",
        "horizon",
    ]
    if predictions.empty or len(cells) != 6 or len(set(cells)) != 6:
        raise ValueError("Registered comparison requires six independent held-out cells")
    if predictions.duplicated(["model", *keys]).any():
        raise ValueError("Duplicate transfer prediction at one matched origin")
    retained = np.maximum(1, np.ceil((predictions.origin_index + 1) * predictions.history_fraction))
    if not predictions.effective_history.eq(retained).all():
        raise ValueError("Retained transfer history differs from its registered context fraction")
    conditions = ["model", "cell_id", "seed", "history_fraction", "horizon"]
    actual = set(predictions[conditions].itertuples(index=False, name=None))
    if actual != set(product(arms, cells, seeds, fractions, horizons)):
        raise ValueError("Transfer comparison omits a registered arm/cell/seed/context/horizon")
    invariant = ["cell_id", "origin_index", "origin_time", "target_time", "horizon"]
    counts = predictions.groupby(invariant, dropna=False).size()
    if not counts.eq(len(arms) * len(seeds) * len(fractions)).all():
        raise ValueError("Transfer arms/seeds/contexts do not share identical target origins")
    for name in ["y_true", "origin_soh", "reference_capacity_ah"]:
        if not predictions.groupby(invariant)[name].nunique(dropna=False).eq(1).all():
            raise ValueError("Matched transfer forecasts disagree on measured labels/reference")
    if not (
        pd.to_datetime(predictions.target_time) > pd.to_datetime(predictions.origin_time)
    ).all():
        raise ValueError("Transfer labels must follow their forecast origins")
    rows = []
    grouping = ["model", "cell_id", "seed", "history_fraction"]
    for key, group in predictions.groupby(grouping):
        for horizon in [0, *horizons]:
            selected = group if horizon == 0 else group[group.horizon.eq(horizon)]
            metrics = point_metrics(selected.y_true.to_numpy(), selected.q50.to_numpy())
            if key[0] in arms[:4]:
                metrics.update(
                    probabilistic_metrics(
                        selected.y_true.to_numpy(), selected[["q10", "q50", "q90"]].to_numpy()
                    )
                )
            rows.append(
                {
                    **dict(zip(grouping, key)),
                    "horizon": horizon,
                    "n_predictions": len(selected),
                    **metrics,
                }
            )
    metrics = pd.DataFrame(rows)
    measures = [name for name in metrics if name not in grouping + ["horizon", "n_predictions"]]
    per_cell = (
        metrics.groupby(["model", "cell_id", "history_fraction", "horizon"])[measures]
        .mean()
        .reset_index()
    )
    summary = per_cell.groupby(["model", "history_fraction", "horizon"])[measures].agg(
        ["mean", "std"]
    )
    summary.columns = ["_".join(column) for column in summary.columns]
    primary = (
        per_cell[per_cell.history_fraction.eq(0.1) & per_cell.horizon.eq(1)]
        .pivot(index="cell_id", columns="model", values="rmse")
        .loc[cells]
    )
    settings = protocol["evaluation"]
    rng = np.random.default_rng(settings["bootstrap_seed"])
    draws = rng.integers(0, len(cells), size=(settings["bootstrap_repetitions"], len(cells)))
    alpha = (1 - settings["interval"]) / 2
    comparisons, differences = [], []
    for left, right in [("R2", "R1"), ("R4", "R3"), ("R2", "R4"), ("R2", "R5")]:
        delta = primary[left] - primary[right]
        low, high = np.quantile(delta.to_numpy()[draws].mean(axis=1), [alpha, 1 - alpha])
        interpretation = (
            "inconclusive; descriptive interval includes zero"
            if low <= 0 <= high
            else "lower RMSE; independent validation required"
            if high < 0
            else "higher RMSE; negative transfer or comparative disadvantage"
        )
        comparisons.append(
            {
                "comparison": f"{left} minus {right}",
                "cells": len(cells),
                "rmse_difference": float(delta.mean()),
                "bootstrap_low": float(low),
                "bootstrap_high": float(high),
                "interval": settings["interval"],
                "interpretation": interpretation,
            }
        )
        differences.extend(
            {
                "comparison": f"{left} minus {right}",
                "cell_id": cell,
                "rmse_difference": float(value),
                "higher_rmse": bool(value > 0),
            }
            for cell, value in delta.items()
        )
    cases = predictions.copy()
    cases["absolute_error"] = (cases.q50 - cases.y_true).abs()
    cases["observed_recovery"] = cases.y_true > cases.origin_soh
    recovery = (
        cases.groupby([*grouping, "horizon", "observed_recovery"])
        .absolute_error.agg(["count", "mean", "max"])
        .reset_index()
    )
    worst = (
        cases.sort_values("absolute_error", ascending=False)
        .groupby(["model", "cell_id"], sort=False)
        .head(3)
    )
    return {
        "metrics": metrics,
        "per_cell": per_cell,
        "summary": summary.reset_index(),
        "paired_comparisons": pd.DataFrame(comparisons),
        "per_cell_differences": pd.DataFrame(differences),
        "recovery_errors": recovery,
        "failure_cases": worst,
    }
