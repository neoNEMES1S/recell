"""Power-sample aggregation for an Indian institutional demand benchmark."""

import numpy as np
import pandas as pd


def aggregate_iblend(meter: pd.DataFrame, availability: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep incomplete quarters missing; availability flags never become zero demand."""
    power = meter[["timestamp", "power"]].copy()
    flags = availability[["timestamp", "Academic"]].copy()
    seconds = pd.to_numeric(power.timestamp, errors="raise")
    if not np.isfinite(seconds).all() or (seconds % 60 != 0).any():
        raise ValueError("I-BLEND meter timestamps must be Unix seconds on the minute grid")
    power["timestamp"] = pd.to_datetime(seconds, unit="s", utc=True, errors="raise")
    flags["timestamp"] = (
        pd.to_datetime(flags.timestamp, errors="raise")
        .dt.tz_localize("Asia/Kolkata")
        .dt.tz_convert("UTC")
    )
    for frame in [power, flags]:
        if (
            frame.empty
            or frame.timestamp.isna().any()
            or frame.timestamp.duplicated().any()
            or not frame.timestamp.is_monotonic_increasing
        ):
            raise ValueError("Meter and availability timestamps must be unique and increasing")
    if not flags.Academic.isin([0, 1]).all():
        raise ValueError("Unrecognized academic-building availability flag")
    if not flags.timestamp.diff().iloc[1:].dt.total_seconds().eq(60).all():
        raise ValueError("Author availability table must cover a complete minute grid")
    if (
        power.timestamp.min() < flags.timestamp.min()
        or power.timestamp.max() > flags.timestamp.max()
    ):
        raise ValueError("Meter timestamps fall outside the author availability grid")
    power["power"] = pd.to_numeric(power.power, errors="raise")
    # Reindex against the complete author grid so absent meter rows are counted too.
    frame = flags.merge(power, on="timestamp", how="left", validate="one_to_one")
    valid = np.isfinite(frame.power) & frame.power.ge(0) & frame.Academic.eq(1)
    frame["usable_power_w"] = frame.power.where(valid)
    frame["usable"] = valid
    local = frame.set_index("timestamp").tz_convert("Asia/Kolkata")
    result = local.resample("15min", label="left", closed="left").agg(
        source_minutes=("Academic", "size"),
        author_available_minutes=("Academic", "sum"),
        observed_minutes=("usable", "sum"),
        load_w=("usable_power_w", "mean"),
    )
    result["complete"] = result.source_minutes.eq(15) & result.observed_minutes.eq(15)
    result["load_kw"] = (result.load_w / 1000).where(result.complete)
    result["load_kwh"] = result.load_kw * 0.25
    result["local_timestamp"] = result.index.astype(str)
    result.index = result.index.tz_convert("UTC")
    result.index.name = "timestamp"
    result = result.drop(columns="load_w").reset_index()
    report = {
        "source_meter_rows": len(power),
        "availability_minutes": len(flags),
        "absent_meter_minutes": int((~flags.timestamp.isin(power.timestamp)).sum()),
        "author_available_but_unusable_minutes": int((frame.Academic.eq(1) & ~valid).sum()),
        "negative_power_minutes": int(frame.power.lt(0).sum()),
        "nonfinite_power_minutes": int((~np.isfinite(frame.power)).sum()),
        "quarter_hour_intervals": len(result),
        "complete_intervals": int(result.complete.sum()),
        "source_units": "Author one-minute-downsampled active power in W; Unix seconds UTC",
        "availability_time_basis": "Naive author wall clocks localized to Asia/Kolkata",
        "energy_basis": (
            "Arithmetic mean of 15 complete minute power samples times 0.25 h; "
            "not a cumulative billing-meter measurement"
        ),
        "missing_rule": (
            "Any absent, nonfinite, negative or author-unavailable minute makes "
            "the quarter missing; no imputation"
        ),
    }
    return result, report
