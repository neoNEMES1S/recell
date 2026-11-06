"""Threshold events retain interval/left/right censoring rather than invented failure times."""

import numpy as np
import pandas as pd


def threshold_event(axis, health, threshold):
    x, y = np.asarray(axis, float), np.asarray(health, float)
    if (
        x.ndim != 1
        or x.shape != y.shape
        or not len(x)
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
        or (np.diff(x) <= 0).any()
        or not np.isfinite(threshold)
        or not 0 < threshold < 1
    ):
        raise ValueError(
            "Life data require a declared fractional threshold and finite increasing axis"
        )
    crossed = np.flatnonzero(y <= threshold)
    if not len(crossed):
        return {"censoring": "right", "lower": float(x[-1]), "upper": None}
    k = crossed[0]
    return {
        "censoring": "left" if k == 0 else "interval",
        "lower": None if k == 0 else float(x[k - 1]),
        "upper": float(x[k]),
    }


def life_inventory(frame):
    rows = []
    for cell, part in frame.groupby("cell_id"):
        part = part.sort_values("elapsed_days")
        rows.append(
            {
                "cell_id": cell,
                "checkpoints": len(part),
                "observed_days": float(part.elapsed_days.max() - part.elapsed_days.min()),
                "minimum_observed_relative_soh": float(part.soh.min()),
                "capacity_reference": "first observed second-life RPT",
                "event_status": "unclassified: SOL/threshold unconfirmed",
            }
        )
    return pd.DataFrame(rows)
