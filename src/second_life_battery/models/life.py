"""A transparent conditional linear-to-threshold RUL baseline, not observed lifetime."""

import numpy as np


def remaining_to_threshold(axis, health, threshold):
    x, y = np.asarray(axis, float), np.asarray(health, float)
    if (
        x.ndim != 1
        or x.shape != y.shape
        or len(x) < 3
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or (np.diff(x) <= 0).any()
        or not np.isfinite(threshold)
        or not 0 < threshold < 1
    ):
        raise ValueError("Require at least three finite past observations and explicit threshold")
    if y[-1] <= threshold:
        return {"status": "already_below_threshold", "remaining": 0.0}
    slope = float(np.polyfit(x - x[0], y, 1)[0])
    if slope >= 0:
        return {"status": "noncrossing_linear_trend", "remaining": None}
    return {
        "status": "conditional_linear_extrapolation",
        "remaining": float((threshold - y[-1]) / slope),
        "slope_per_axis_unit": slope,
    }
