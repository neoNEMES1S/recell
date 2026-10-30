"""Plot completed demand forecasts and their worst-day failure without model changes."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.plots import plt
from second_life_battery.utils.reproducibility import verify_artifacts


def review(root):
    run = root / "outputs/india_ci/india_load_forecast_v1"
    source = run / "forecast"
    completion = json.loads((source / "completion.json").read_text())
    verify_artifacts(source, completion["artifacts"])
    selected = completion["selected_model"]
    daily = pd.read_csv(source / "test_daily.csv")
    daily["origin"] = pd.to_datetime(daily.origin, utc=True)
    chosen = daily[daily.model == selected]
    worst = chosen.sort_values(["rmse_kw", "origin"], ascending=[False, True]).iloc[0]
    predictions = pd.read_csv(source / "test_predictions.csv")
    for name in ["origin", "timestamp"]:
        predictions[name] = pd.to_datetime(predictions[name], utc=True)
    frame = predictions[predictions.origin == worst.origin].sort_values("timestamp")
    selected_frame = frame[frame.model == selected]
    assert len(chosen) == 16 and len(selected_frame) == 96
    actual_peak = selected_frame.loc[selected_frame.load_kw.idxmax(), "timestamp"]
    forecast_peak = selected_frame.loc[selected_frame.prediction_kw.idxmax(), "timestamp"]
    peak_minutes = abs((actual_peak - forecast_peak).total_seconds()) / 60
    assert peak_minutes == worst.peak_time_absolute_error_minutes
    output = run / "analysis"
    output.mkdir(exist_ok=False)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.5))
    palette = [
        ("weekly", "Weekly", "#929e94"),
        ("previous_day", "Previous day", "#ad843d"),
        (selected, "Validation-selected 50/50 blend", "#497b9e"),
    ]
    for model, label, color in palette:
        rows = daily[daily.model == model].sort_values("origin")
        local = rows.origin.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        axes[0].plot(local, rows.rmse_kw, label=label, color=color, marker="o", markersize=3)
    axes[0].set_ylabel("Daily RMSE (kW)")
    axes[0].set_title("Daily errors: all models stay fixed after validation")
    axes[0].tick_params(axis="x", labelsize=8)
    axes[0].legend(loc="upper right", fontsize=8)
    axes[0].set_ylim(bottom=0)
    local = selected_frame.timestamp.dt.tz_convert("Asia/Kolkata")
    hours = local.dt.hour.to_numpy() + local.dt.minute.to_numpy() / 60
    axes[1].plot(
        hours,
        selected_frame.load_kw,
        color="#243f32",
        linewidth=2.3,
        label="Observed active demand",
    )
    for model, label, color in palette:
        values = frame[frame.model == model].prediction_kw.to_numpy()
        assert len(values) == 96 and np.isfinite(values).all()
        axes[1].plot(
            hours,
            values,
            color=color,
            linewidth=1.8 if model == selected else 1,
            linestyle="-" if model == selected else "--",
            label=label,
        )
    for timestamp, color in [(actual_peak, "#243f32"), (forecast_peak, "#497b9e")]:
        time = timestamp.tz_convert("Asia/Kolkata")
        axes[1].axvline(time.hour + time.minute / 60, color=color, alpha=0.35, linestyle=":")
    day = worst.origin.tz_convert("Asia/Kolkata").strftime("%d %b %Y")
    axes[1].set_title(
        f"Worst selected-model RMSE day: {day}; "
        f"RMSE {worst.rmse_kw:.2f} kW, peak-time error {peak_minutes:g} min"
    )
    axes[1].set_ylabel("Active power (kW)")
    axes[1].set_xlabel("Hour (IST); each point is a 15-minute mean")
    axes[1].set_xticks([0, 6, 12, 18, 23.75], ["00:00", "06:00", "12:00", "18:00", "23:45"])
    axes[1].set_ylim(bottom=0)
    axes[1].legend(loc="upper left", fontsize=8)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Indian public-building day-ahead forecast benchmark", fontsize=15)
    fig.text(
        0.02,
        0.015,
        "One IIIT Delhi academic meter, 2014. Reporting delay assumed zero; "
        "no billing, battery or savings validation.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.96))
    figure = output / "test_errors_and_worst_day.png"
    fig.savefig(figure, dpi=160)
    plt.close(fig)
    findings = {
        "selected_model": selected,
        "worst_rmse_local_date": day,
        "rmse_kw": float(worst.rmse_kw),
        "energy_error_kwh": float(worst.energy_error_kwh),
        "peak_magnitude_error_kw": float(worst.peak_error_kw),
        "actual_peak_ist": actual_peak.tz_convert("Asia/Kolkata").isoformat(),
        "forecast_peak_ist": forecast_peak.tz_convert("Asia/Kolkata").isoformat(),
        "peak_time_absolute_error_minutes": peak_minutes,
        "interpretation": "Near-correct daily peak magnitude can hide a major timing error; "
        "no tariff/controller effectiveness follows from mean forecast RMSE.",
    }
    (output / "failure_review.json").write_text(json.dumps(findings, indent=2) + "\n")
    evidence = {
        "status": "postfit_descriptive_review; no_refit_or_promotion",
        "completion_sha256": sha256_file(source / "completion.json"),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "artifacts": {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "provenance.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    review(Path(__file__).resolve().parent.parent)
