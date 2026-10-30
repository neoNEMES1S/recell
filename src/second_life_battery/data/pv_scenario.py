"""Declared horizontal reference-temperature PV scenario, not metered generation."""

import numpy as np
import pandas as pd


def horizontal_pv_scenario(resource: pd.DataFrame, model: dict) -> pd.DataFrame:
    if (
        model["name"] != "irradiance_linear_horizontal_reference_temperature"
        or model["tilt_degrees"] != 0
        or model["assumed_pv_cell_temperature_c"] != 25
        or model["reference_irradiance_w_m2"] != 1000
    ):
        raise ValueError("Unimplemented tilt, thermal or irradiance reference assumption")
    dc, ac, efficiency = [
        float(model[key])
        for key in ["dc_nameplate_kw", "ac_nameplate_kw", "fixed_inverter_efficiency"]
    ]
    if not np.isfinite([dc, ac, efficiency]).all() or min(dc, ac) <= 0 or not 0 < efficiency <= 1:
        raise ValueError("PV scenario ratings/efficiency must be finite and physically bounded")
    required = {"timestamp", "ghi_mean_w_m2", "ghi_wh_m2_interval", "resource_resolution_minutes"}
    if resource.empty or not required.issubset(resource):
        raise ValueError("PV scenario requires complete irradiance and resolution metadata")
    clocks = pd.DatetimeIndex(pd.to_datetime(resource.timestamp, errors="raise"))
    if (
        clocks.tz is None
        or clocks.hasnans
        or clocks.has_duplicates
        or not clocks.is_monotonic_increasing
    ):
        raise ValueError("PV scenario clocks must be unique, ordered and timezone-aware")
    clocks = clocks.tz_convert("UTC")
    if (clocks.asi8 % pd.Timedelta(minutes=15).value != 0).any() or not np.all(
        np.diff(clocks.asi8) == pd.Timedelta(minutes=15).value
    ):
        raise ValueError("PV scenario requires a contiguous 15-minute grid")
    values = resource[["ghi_mean_w_m2", "ghi_wh_m2_interval"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values[:, 0] > 2000).any():
        raise ValueError(
            "PV scenario irradiance must be available, finite and within audited bounds"
        )
    if not resource.resource_resolution_minutes.eq(60).all() or not np.allclose(
        values[:, 1], values[:, 0] * 0.25, rtol=0, atol=1e-9
    ):
        raise ValueError("PV scenario source resolution or Wh-to-W conversion differs")
    if resource.assign(hour=clocks.floor("h")).groupby("hour").ghi_mean_w_m2.nunique().gt(1).any():
        raise ValueError("Subhourly irradiance variation contradicts the hourly source contract")
    if any(name.startswith("modeled_pv_") for name in resource):
        raise ValueError("Do not overwrite an existing modeled PV scenario")
    result = resource.copy()
    result["timestamp"] = clocks
    result["modeled_pv_dc_kw"] = dc * values[:, 0] / 1000
    unconstrained_ac = result.modeled_pv_dc_kw * efficiency
    result["modeled_pv_ac_kw"] = np.minimum(ac, unconstrained_ac)
    result["modeled_pv_ac_kwh"] = result.modeled_pv_ac_kw * 0.25
    result["modeled_pv_ac_clipped"] = unconstrained_ac > ac
    result["pv_status"] = "modeled_horizontal_reference_temperature; not_metered_PV"
    return result
