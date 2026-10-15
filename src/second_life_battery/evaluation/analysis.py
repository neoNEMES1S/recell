"""Post-evaluation diagnostics; held-out outcomes are never used to retune fitted models."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from second_life_battery.data.sequences import make_sequences, tabular_features
from second_life_battery.evaluation.plots import plt, save_figure


def analyze_forecasts(config: dict, root: Path) -> None:
    """Export calibration, error cases, cell-level paired uncertainty and validation importance."""
    output = root / "outputs/analysis"
    output.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(root / "outputs/lobo/predictions.csv")
    metrics = pd.read_csv(root / "outputs/lobo/fold_metrics.csv")
    summary = pd.read_csv(root / "outputs/lobo/summary.csv")
    overall = summary[(summary.horizon == 0) & (summary.unit == "soh")].sort_values("rmse_mean")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(overall.model, overall.rmse_mean, yerr=overall.rmse_std, capsize=4)
    ax.set(ylabel="SOH RMSE", title="Mean ± SD across six held-out cells; seeds averaged per cell")
    ax.tick_params(axis="x", rotation=20)
    save_figure(fig, output / "model_comparison")
    qmetrics = metrics[
        (metrics.horizon == 0)
        & (metrics.unit == "soh")
        & metrics.model.isin(["pgp_gru", "quantile_gru"])
    ]
    fig, ax = plt.subplots(figsize=(5, 4))
    levels = np.array([0.1, 0.5, 0.9])
    for model, group in qmetrics.groupby("model"):
        values = group.groupby("cell_id")[
            ["empirical_q10", "empirical_q50", "empirical_q90"]
        ].mean()
        ax.plot(levels, values.mean(), "o-", label=model)
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Ideal")
    ax.set(
        xlabel="Nominal quantile",
        ylabel="Empirical fraction at or below prediction",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    ax.legend()
    save_figure(fig, output / "calibration")
    selected = predictions[
        (predictions.model == "pgp_gru")
        & (predictions.horizon == 1)
        & (predictions.seed == config["evaluation"]["seeds"][0])
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), sharey=True)
    for ax, (cell, group) in zip(axes.ravel(), selected.groupby("cell_id")):
        dates = pd.to_datetime(group.target_time)
        ax.fill_between(dates, group.q10, group.q90, alpha=0.2, label="P10–P90")
        ax.plot(dates, group.q50, "o-", markersize=3, label="Median forecast")
        ax.plot(dates, group.y_true, "k.-", label="Measured SOH")
        ax.set(title=cell, ylabel="SOH")
        ax.tick_params(axis="x", rotation=40)
    axes[0, 0].legend(fontsize=8)
    save_figure(fig, output / "held_out_forecasts")
    cases = predictions.copy()
    cases["absolute_error"] = abs(cases.q50 - cases.y_true)
    cases["observed_recovery"] = cases.y_true > cases.origin_soh
    cases.sort_values("absolute_error", ascending=False).groupby(
        ["model", "cell_id"], sort=False
    ).head(3).to_csv(output / "failure_cases.csv", index=False)
    cases.groupby(["model", "observed_recovery"]).absolute_error.agg(
        ["count", "mean", "max"]
    ).to_csv(output / "recovery_error_analysis.csv")
    # The unit of uncertainty is a battery; overlapping origins and seeds are not independent n.
    per_cell = (
        metrics[(metrics.horizon == 0) & (metrics.unit == "soh")]
        .groupby(["model", "cell_id"])
        .rmse.mean()
        .unstack("model")
    )
    rng = np.random.default_rng(config["project"]["seed"])
    comparisons = []
    for other in per_cell.columns.drop("pgp_gru"):
        differences = (per_cell.pgp_gru - per_cell[other]).to_numpy()
        draws = rng.choice(differences, size=(10000, len(differences)), replace=True).mean(axis=1)
        comparisons.append(
            {
                "comparison": f"pgp_gru minus {other}",
                "cells": len(differences),
                "rmse_difference": differences.mean(),
                "bootstrap_low_95": np.quantile(draws, 0.025),
                "bootstrap_high_95": np.quantile(draws, 0.975),
            }
        )
    pd.DataFrame(comparisons).to_csv(output / "paired_cell_comparisons.csv", index=False)
    data = pd.read_csv(root / "data/processed/checkpoints.csv", parse_dates=["timestamp"])
    importance_rows = []
    feature_names = (
        [f"latest:{name}" for name in config["features"]]
        + [f"slope:{name}" for name in config["features"]]
        + ["context_length"]
    )
    for artifact in sorted((root / "outputs/lobo/checkpoints").glob("xgboost_*.joblib")):
        state = joblib.load(artifact)
        validation_cell = state["fold"]["validation"]
        samples = make_sequences(
            data[data.cell_id == validation_cell],
            config["features"],
            config["evaluation"]["horizon"],
            min_history=config["evaluation"]["minimum_history"],
        )
        x = tabular_features(samples, state["preprocessor"])
        y = np.stack([sample.target - sample.origin_soh for sample in samples])
        importance = permutation_importance(
            state["model"],
            x,
            y,
            scoring="neg_mean_absolute_error",
            n_repeats=10,
            random_state=42,
            n_jobs=1,
        )
        importance_rows.extend(
            {
                "artifact": artifact.name,
                "validation_cell": validation_cell,
                "feature": name,
                "mae_increase": mean,
                "permutation_std": std,
            }
            for name, mean, std in zip(
                feature_names, importance.importances_mean, importance.importances_std
            )
        )
    pd.DataFrame(importance_rows).to_csv(output / "validation_feature_importance.csv", index=False)
    averaged = pd.DataFrame(importance_rows).groupby("feature").mae_increase.mean().sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(averaged.index, averaged.values)
    ax.set(
        xlabel="Validation MAE increase after permutation (SOH)", title="XGBoost feature importance"
    )
    save_figure(fig, output / "feature_importance")
    (output / "analysis_notes.json").write_text(
        json.dumps(
            {
                "bootstrap_unit": "battery; descriptive intervals with only six independent cells",
                "importance_partition": "validation battery; not used to refit these runs",
                "forecast_plot_seed": config["evaluation"]["seeds"][0],
                "interval_nominal_coverage": 0.8,
            },
            indent=2,
        )
    )


def analyze_limited_history(root: Path) -> None:
    """Display errors against retained context, preserving identical origins at each fraction."""
    output = root / "outputs/analysis"
    summary = pd.read_csv(root / "outputs/limited_history/summary.csv")
    rows = summary[(summary.horizon == 0) & (summary.unit == "soh")]
    rows.to_csv(output / "limited_history_summary.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for model, group in rows.groupby("model"):
        ax.plot(group.history_fraction * 100, group.rmse_mean, "o-", label=model)
    ax.set(
        xlabel="Retained pre-origin checkpoint history (%)", ylabel="Mean held-out-cell SOH RMSE"
    )
    ax.legend(ncol=2, fontsize=9)
    save_figure(fig, output / "limited_history")
