"""Replay the same solar/load period under four storage scenarios and wear sensitivities."""

import json
from pathlib import Path

import pandas as pd

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.plots import plt, save_figure
from second_life_battery.optimization.degradation import forecast_wear
from second_life_battery.optimization.inputs import prepare_solar
from second_life_battery.optimization.solar_dispatch import solve_dispatch
from second_life_battery.utils.reproducibility import save_run


def run_dispatch(config: dict, root: Path) -> pd.DataFrame:
    """Use latest one-checkpoint held-out forecasts; never select by test error."""
    settings = config["dispatch"]
    output = root / "outputs/dispatch"
    forecast_dir = root / "outputs/lobo"
    data_file = root / "data/processed/checkpoints.csv"
    provenance = json.loads((forecast_dir / "provenance.json").read_text())
    if provenance["checkpoint_data_sha256"] != sha256_file(data_file):
        raise ValueError("Forecasts were fitted on different checkpoint data; rerun LOBO")
    data = pd.read_csv(data_file)
    forecasts = pd.read_csv(forecast_dir / "predictions.csv")
    forecasts = (
        forecasts[
            (forecasts.model == settings["forecast_model"])
            & (forecasts.seed == settings["forecast_seed"])
            & (forecasts.horizon == 1)
            & (forecasts.history_fraction == 1)
        ]
        .sort_values("origin_index")
        .groupby("cell_id")
        .tail(1)
    )
    if set(forecasts.cell_id) != set(data.cell_id):
        raise ValueError("Dispatch needs one held-out probabilistic forecast for every cell")
    folds = {fold["test"]: fold for fold in json.loads((forecast_dir / "folds.json").read_text())}
    frame = prepare_solar(config, root)
    save_run(config, root, output)
    (output / "selected_forecasts.csv").write_text(forecasts.to_csv(index=False))
    summaries, conversions = [], []
    for _, forecast in forecasts.iterrows():
        fold = folds[forecast.cell_id]
        if set(fold["training"]) & {fold["test"], fold["validation"]} or set(
            fold["scaler_fit_cells"]
        ) != set(fold["training"]):
            raise ValueError("Forecast provenance contains overlapping or inconsistent partitions")
        training = data[data.cell_id.isin(fold["training"])]
        median = forecast_wear(forecast, training, settings, conservative=False)
        conservative = forecast_wear(forecast, training, settings, conservative=True)
        conversions.append(
            {
                "cell_id": forecast.cell_id,
                "training_cells": fold["training"],
                "median": median,
                "conservative": conservative,
            }
        )
        scenarios = [
            ("A_no_battery", median, 0.0, True),
            ("B_conventional", {**median, "health_fraction": 1.0}, 0.0, False),
            ("C_second_life", median, 0.0, False),
            *[
                ("D_degradation_aware", median, float(weight), False)
                for weight in settings["degradation_weights"]
            ],
            ("D_conservative", conservative, 1.0, False),
        ]
        for scenario, health, weight, no_battery in scenarios:
            schedule, summary = solve_dispatch(
                frame,
                settings["battery"],
                health["health_fraction"],
                health["wear_per_efc"],
                degradation_weight=weight,
                no_battery=no_battery,
            )
            name = f"{forecast.cell_id}_{scenario}_{weight:g}"
            schedule.to_csv(output / f"{name}.csv", index=False)
            summaries.append(
                {
                    "cell_id": forecast.cell_id,
                    "scenario": scenario,
                    "degradation_weight": weight,
                    **summary,
                }
            )
    results = pd.DataFrame(summaries)
    results.to_csv(output / "summary.csv", index=False)
    (output / "wear_conversion.json").write_text(json.dumps(conversions, indent=2))
    provenance_path = output / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance.update(
        {
            "forecast_predictions_sha256": sha256_file(forecast_dir / "predictions.csv"),
            "forecast_folds_sha256": sha256_file(forecast_dir / "folds.json"),
            "solar_load_sha256": sha256_file(root / "data/processed/solar_load.csv"),
            "interpretation": "Perfect-foresight monthly replay, not observed operational savings",
            "wear_status": "Linear training-exposure proxy; no validated pack aging model",
            "conventional_wear": "Same second-life proxy; controlled capacity comparison",
        }
    )
    provenance_path.write_text(json.dumps(provenance, indent=2))
    main = results[(results.degradation_weight == 0) | (results.degradation_weight == 1)]
    costs = main.groupby("scenario")[
        [
            "electricity_cost_eur",
            "estimated_degradation_cost_eur",
            "electricity_plus_estimated_wear_eur",
        ]
    ].mean()
    costs.columns = ["Net electricity", "Estimated wear", "Electricity + wear"]
    costs = costs.rename(
        index={
            "A_no_battery": "A: No battery",
            "B_conventional": "B: Conventional",
            "C_second_life": "C: Second-life",
            "D_conservative": "D: Conservative",
            "D_degradation_aware": "D: Median",
        }
    )
    ax = costs.plot.bar(figsize=(9, 5))
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set(ylabel="EUR per replay month", xlabel="", title="Mean over six cell health scenarios")
    ax.tick_params(axis="x", rotation=20)
    save_figure(ax.figure, output / "scenario_costs")
    sensitivity = results[results.scenario.isin(["C_second_life", "D_degradation_aware"])]
    fig, ax = plt.subplots(figsize=(7, 4))
    for cell, rows in sensitivity.groupby("cell_id"):
        rows = rows.sort_values("degradation_weight")
        ax.plot(rows.degradation_weight, rows.equivalent_full_cycles, "o-", label=cell)
    ax.set(xlabel="Wear-cost multiplier", ylabel="Equivalent full cycles per replay month")
    ax.legend(ncol=3)
    save_figure(fig, output / "wear_sensitivity")
    return results
