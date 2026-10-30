"""Causal seasonal day-ahead demand forecasts, separate from battery-health models."""

import numpy as np
import pandas as pd


def seasonal_day_ahead(history: pd.Series, origin: pd.Timestamp, candidates: dict) -> pd.DataFrame:
    """History contains interval-start mean kW; only completed quarters are available."""
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Forecast origin needs an explicit timezone")
    local = origin.tz_convert("Asia/Kolkata")
    if local != local.normalize():
        raise ValueError("Day-ahead forecasts start at local midnight")
    origin = origin.tz_convert("UTC")
    index = history.index
    if (
        not isinstance(index, pd.DatetimeIndex)
        or index.tz is None
        or index.has_duplicates
        or not index.is_monotonic_increasing
        or history.empty
    ):
        raise ValueError("History needs unique ordered timezone-aware interval starts")
    if (index + pd.Timedelta(minutes=15) > origin).any():
        raise ValueError("History includes an interval unavailable at the forecast origin")
    target = pd.date_range(origin, periods=96, freq="15min")
    day, week = target - pd.Timedelta(days=1), target - pd.Timedelta(days=7)
    previous_day, previous_week = history.reindex(day), history.reindex(week)
    values = np.column_stack([previous_day.to_numpy(float), previous_week.to_numpy(float)])
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Required lag intervals are missing or invalid; never impute")
    if not candidates or any(
        not np.isfinite(weight) or not 0 <= weight <= 1 for weight in candidates.values()
    ):
        raise ValueError("Registered blend weights must be finite and between zero and one")
    rows = []
    for model, weight in candidates.items():
        rows.append(
            pd.DataFrame(
                {
                    "model": model,
                    "origin": origin,
                    "timestamp": target,
                    "lag_day_timestamp": day,
                    "lag_week_timestamp": week,
                    "lag_day_kw": values[:, 0],
                    "lag_week_kw": values[:, 1],
                    "latest_feature_interval_end": day + pd.Timedelta(minutes=15),
                    "prediction_kw": weight * values[:, 0] + (1 - weight) * values[:, 1],
                }
            )
        )
    return pd.concat(rows, ignore_index=True)
