"""Audit and align hourly solar resource without inventing subhourly measurements."""

import numpy as np
import pandas as pd


def parse_nasa_hourly(payload: dict) -> pd.DataFrame:
    header, units = payload["header"], payload["parameters"]
    if header["time_standard"] != "UTC":
        raise ValueError("NASA resource requires explicit UTC, not local solar time")
    if units["ALLSKY_SFC_SW_DWN"]["units"] != "Wh/m^2" or units["T2M"]["units"] != "C":
        raise ValueError("Unexpected NASA hourly energy/temperature units")
    data = payload["properties"]["parameter"]
    ghi, temperature = data["ALLSKY_SFC_SW_DWN"], data["T2M"]
    if not ghi or set(ghi) != set(temperature):
        raise ValueError("NASA parameters do not share a complete time index")
    result = (
        pd.DataFrame(
            {
                "timestamp": pd.to_datetime(list(ghi), format="%Y%m%d%H", utc=True, errors="raise"),
                "ghi_wh_m2_hour": list(ghi.values()),
                "ambient_temperature_c": [temperature[key] for key in ghi],
            }
        )
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    values = result[["ghi_wh_m2_hour", "ambient_temperature_c"]].to_numpy(dtype=float)
    if (
        not np.isfinite(values).all()
        or (values == header["fill_value"]).any()
        or result.timestamp.duplicated().any()
        or not result.timestamp.diff().iloc[1:].dt.total_seconds().eq(3600).all()
    ):
        raise ValueError("NASA resource has missing, duplicate or discontinuous hours")
    if (
        result.ghi_wh_m2_hour.lt(0).any()
        or result.ghi_wh_m2_hour.gt(2000).any()
        or not result.ambient_temperature_c.between(-70, 65).all()
    ):
        raise ValueError("NASA resource values are outside the audited physical ranges")
    expected = pd.date_range(
        pd.to_datetime(header["start"], format="%Y%m%d", utc=True),
        pd.to_datetime(header["end"], format="%Y%m%d", utc=True) + pd.Timedelta(days=1),
        freq="h",
        inclusive="left",
    )
    if not pd.DatetimeIndex(result.timestamp).equals(expected):
        raise ValueError("NASA resource does not cover the complete declared request")
    return result


def align_hourly_resource(hourly: pd.DataFrame, timestamps) -> pd.DataFrame:
    """Distribute hourly energy equally to four quarters, preserving source resolution."""
    target = pd.DatetimeIndex(timestamps)
    if target.tz is None:
        raise ValueError("Resource alignment requires timezone-aware load timestamps")
    target = target.tz_convert("UTC")
    if (
        target.empty
        or target.has_duplicates
        or not target.is_monotonic_increasing
        or (target.asi8 % pd.Timedelta(minutes=15).value != 0).any()
        or not np.all(np.diff(target.asi8) == pd.Timedelta(minutes=15).value)
    ):
        raise ValueError("Resource target must be a complete 15-minute grid")
    times = pd.DatetimeIndex(hourly.timestamp)
    if (
        times.tz is None
        or times.has_duplicates
        or not np.all(np.diff(times.asi8) == pd.Timedelta(hours=1).value)
    ):
        raise ValueError("Source resource hours are not contiguous and timezone-aware")
    indices = times.get_indexer(target.floor("h"))
    if (indices < 0).any():
        raise ValueError("Hourly resource does not cover the selected load intervals")
    selected = hourly.iloc[indices].reset_index(drop=True)
    result = pd.DataFrame(
        {
            "timestamp": target,
            "ghi_wh_m2_interval": selected.ghi_wh_m2_hour.to_numpy(dtype=float) / 4,
            "ghi_mean_w_m2": selected.ghi_wh_m2_hour.to_numpy(dtype=float),
            "ambient_temperature_c": selected.ambient_temperature_c.to_numpy(dtype=float),
            "resource_resolution_minutes": 60,
            "resource_alignment": "hourly_piecewise_constant; subhourly_values_are_derived",
        }
    )
    return result
