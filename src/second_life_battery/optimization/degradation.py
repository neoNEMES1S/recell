"""Convert held-out health forecasts into explicit, scenario-dependent wear coefficients."""

import numpy as np
import pandas as pd


def forecast_wear(
    forecast: pd.Series, training: pd.DataFrame, settings: dict, conservative: bool
) -> dict:
    """Estimate checkpoint exposure using only training cells."""
    if forecast.cell_id in set(training.cell_id):
        raise ValueError("Held-out battery cannot enter wear calibration")
    increments = (
        training.sort_values(["cell_id", "timestamp"]).groupby("cell_id").cumulative_ah.diff()
    )
    increments = increments[increments > 1e-6]
    if increments.empty:
        raise ValueError("No positive training-cell exposure increments for wear calibration")
    nominal_ah = settings["nominal_cell_capacity_ah"]
    values = [
        nominal_ah,
        forecast.reference_capacity_ah,
        forecast.origin_soh,
        forecast.q10,
        forecast.q50,
        forecast.q90,
        forecast.horizon,
    ]
    if (
        not np.isfinite(values).all()
        or min(values[:3]) <= 0
        or forecast.horizon < 1
        or forecast.horizon != int(forecast.horizon)
        or not 0 < forecast.q10 <= forecast.q50 <= forecast.q90
    ):
        raise ValueError("Wear conversion requires positive finite health and ordered quantiles")
    expected_efc = float(increments.median() / (2 * nominal_ah))
    ratio = forecast.reference_capacity_ah / nominal_ah
    future = float(forecast.q10 if conservative else forecast.q50)
    # shortcut: linear exposure proxy; replace when pack-level aging calibration is available.
    rate = max(
        0.0, (float(forecast.origin_soh) - future) * ratio / (expected_efc * forecast.horizon)
    )
    if not np.isfinite(rate) or not 0 < future * ratio <= 1:
        raise ValueError("Forecast cannot define a physical dispatch capacity")
    return {
        "health_fraction": future * ratio,
        "wear_per_efc": rate,
        "expected_efc_per_checkpoint": expected_efc,
        "origin_health_fraction": float(forecast.origin_soh) * ratio,
        "conversion": "forecast decline / median positive training exposure; scenario proxy",
    }
