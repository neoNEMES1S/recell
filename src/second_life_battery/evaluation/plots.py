"""Publication exports retain observed variation and label unvalidated sensor proxies."""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/.matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_figure(fig: plt.Figure, path: Path) -> None:
    """Save matching raster and vector versions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def run_eda(root: Path) -> None:
    """Plot actual targets/exposures and write a per-cell descriptive table."""
    data = pd.read_csv(root / "data/processed/checkpoints.csv", parse_dates=["timestamp"])
    cycling = pd.read_csv(root / "data/processed/cycling_sessions.csv", parse_dates=["end_time"])
    output = root / "outputs/figures/eda"
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    for x, xlabel in [
        ("elapsed_days", "Days since first second-life RPT"),
        ("cumulative_ah", "Recorded cycling charge + discharge throughput (Ah)"),
    ]:
        for y, ylabel in [
            ("capacity_ah", "Low-rate discharge capacity (Ah)"),
            ("soh", "SOH relative to first second-life RPT"),
        ]:
            fig, ax = plt.subplots(figsize=(7.2, 4.5))
            for cell, group in data.groupby("cell_id"):
                ax.plot(group[x], group[y], marker="o", markersize=3.5, linewidth=1, label=cell)
            ax.set(xlabel=xlabel, ylabel=ylabel)
            ax.grid(alpha=0.2)
            ax.legend(ncol=3, fontsize=9)
            save_figure(fig, output / f"{y}_vs_{x}")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for duty, ax in enumerate(axes):
        for cell, group in data[data.duty_commercial == duty].groupby("cell_id"):
            ax.plot(group.elapsed_days, group.soh, "o-", markersize=3, linewidth=1, label=cell)
        ax.set(title=["Residential", "Commercial"][duty], xlabel="Elapsed days")
        ax.legend()
    axes[0].set_ylabel("SOH")
    save_figure(fig, output / "duty_cycle_comparison")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for cell, group in cycling.groupby("cell_id"):
        axes[0].plot(group.end_time, group.aux_temp_mean_c, "o", markersize=3, label=cell)
        axes[1].plot(group.end_time, group.elevated_temp_hours, "o", markersize=3, label=cell)
    axes[0].set(ylabel="Auxiliary channel 1 mean (°C)", title="Sensor assignment unverified")
    axes[1].set(ylabel="Observed hours above 30 °C", title="Auxiliary-temperature exposure proxy")
    axes[0].legend(ncol=2, fontsize=8)
    fig.autofmt_xdate()
    save_figure(fig, output / "temperature_exposure")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for cell, group in data.groupby("cell_id"):
        ax.scatter(group.soh, group.pulse_resistance_ohm * 1000, s=20, label=cell)
    ax.set(xlabel="SOH", ylabel="Apparent 8-second pulse resistance near 3.63 V (mΩ)")
    ax.legend(ncol=3)
    save_figure(fig, output / "resistance_vs_soh")
    summary = data.groupby("cell_id").agg(
        checkpoints=("capacity_ah", "size"),
        first_capacity_ah=("capacity_ah", "first"),
        last_capacity_ah=("capacity_ah", "last"),
        last_soh=("soh", "last"),
        elapsed_days=("elapsed_days", "max"),
        first_life_capacity_ah=("first_life_capacity_ah", "first"),
    )
    summary["capacity_loss_ah"] = summary.first_capacity_ah - summary.last_capacity_ah
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(summary.first_life_capacity_ah, summary.capacity_loss_ah)
    for cell, row in summary.iterrows():
        ax.annotate(
            cell,
            (row.first_life_capacity_ah, row.capacity_loss_ah),
            xytext=(5, 4),
            textcoords="offset points",
        )
    ax.set(
        xlabel="Documented first-life end capacity (Ah)",
        ylabel="Observed second-life capacity loss (Ah)",
        title="Unequal follow-up durations",
    )
    save_figure(fig, output / "first_life_vs_second_life_loss")
    features = ["capacity_ah", "pulse_resistance_ohm", "rpt_aux_temp_c", "cumulative_ah"]
    missing = data.groupby("cell_id")[features].agg(lambda values: values.isna().mean())
    fig, ax = plt.subplots(figsize=(7, 3.5))
    im = ax.imshow(missing, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    ax.set_xticks(np.arange(len(features)), features, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(missing)), missing.index)
    fig.colorbar(im, ax=ax, label="Fraction missing")
    save_figure(fig, output / "checkpoint_missingness")
    tables = root / "outputs/tables"
    tables.mkdir(parents=True, exist_ok=True)
    summary.to_csv(tables / "dataset_summary.csv")
    missing.to_csv(tables / "checkpoint_missingness.csv")
