"""Protect irradiance units, source resolution and energy conservation in the PV scenario."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from second_life_battery.data.pv_scenario import horizontal_pv_scenario


def fixture():
    model = {
        "name": "irradiance_linear_horizontal_reference_temperature",
        "tilt_degrees": 0,
        "assumed_pv_cell_temperature_c": 25,
        "reference_irradiance_w_m2": 1000,
        "dc_nameplate_kw": 40,
        "ac_nameplate_kw": 32,
        "fixed_inverter_efficiency": 0.96,
    }
    ghi = np.repeat([0.0, 500.0, 1000.0], 4)
    resource = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=12, freq="15min", tz="UTC"),
            "ghi_mean_w_m2": ghi,
            "ghi_wh_m2_interval": ghi * 0.25,
            "resource_resolution_minutes": 60,
        }
    )
    return resource, model


def test_darkness_reference_power_clipping_and_hourly_energy_conservation():
    resource, model = fixture()
    before = resource.copy(deep=True)
    result = horizontal_pv_scenario(resource, model)
    np.testing.assert_allclose(result.modeled_pv_ac_kw, np.repeat([0.0, 19.2, 32.0], 4))
    hourly = result.groupby(result.timestamp.dt.floor("h")).modeled_pv_ac_kwh.sum()
    np.testing.assert_allclose(hourly, [0.0, 19.2, 32.0])
    assert result.modeled_pv_ac_clipped.tolist() == [False] * 8 + [True] * 4
    assert result.resource_resolution_minutes.eq(60).all()
    assert result.pv_status.str.contains("not_metered_PV").all()
    assert_frame_equal(resource, before)


@pytest.mark.parametrize(
    "defect", ["missing", "units", "resolution", "subhourly", "clock", "tilt", "temperature"]
)
def test_unknown_or_inconsistent_source_assumptions_are_rejected(defect):
    resource, model = fixture()
    model = deepcopy(model)
    if defect == "missing":
        resource.loc[0, "ghi_mean_w_m2"] = np.nan
    elif defect == "units":
        resource["ghi_wh_m2_interval"] *= 1000
    elif defect == "resolution":
        resource["resource_resolution_minutes"] = 15
    elif defect == "subhourly":
        resource.loc[5, "ghi_mean_w_m2"] = 600
        resource.loc[5, "ghi_wh_m2_interval"] = 150
    elif defect == "clock":
        resource["timestamp"] = resource.timestamp.dt.tz_localize(None)
    elif defect == "tilt":
        model["tilt_degrees"] = 20
    else:
        model["assumed_pv_cell_temperature_c"] = 35
    with pytest.raises(ValueError):
        horizontal_pv_scenario(resource, model)
