"""Hourly radiation energy cannot become independent quarter-hour measurements."""

import pandas as pd
import pytest

from second_life_battery.data.solar_resource import align_hourly_resource, parse_nasa_hourly


def fixture():
    keys = [f"20140916{hour:02d}" for hour in range(24)]
    return {
        "header": {
            "start": "20140916",
            "end": "20140916",
            "time_standard": "UTC",
            "fill_value": -999,
        },
        "parameters": {"ALLSKY_SFC_SW_DWN": {"units": "Wh/m^2"}, "T2M": {"units": "C"}},
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": dict.fromkeys(keys, 800),
                "T2M": dict.fromkeys(keys, 25),
            }
        },
    }


def test_hourly_energy_conserved_when_split_into_quarters():
    hourly = parse_nasa_hourly(fixture())
    target = pd.date_range("2014-09-16T00:00Z", periods=4, freq="15min")
    result = align_hourly_resource(hourly, target)
    assert result.ghi_wh_m2_interval.tolist() == [200] * 4
    assert result.ghi_wh_m2_interval.sum() == hourly.ghi_wh_m2_hour.iloc[0]
    assert result.resource_resolution_minutes.eq(60).all()
    assert result.ghi_mean_w_m2.tolist() == [800] * 4


@pytest.mark.parametrize("problem", ["LST", "units", "missing", "fill"])
def test_wrong_time_units_and_missing_resource_rejected(problem):
    payload = fixture()
    if problem == "LST":
        payload["header"]["time_standard"] = "LST"
    elif problem == "units":
        payload["parameters"]["ALLSKY_SFC_SW_DWN"]["units"] = "kWh/m^2"
    elif problem == "missing":
        payload["properties"]["parameter"]["T2M"].pop("2014091601")
    else:
        payload["properties"]["parameter"]["T2M"]["2014091601"] = -999
    with pytest.raises(ValueError):
        parse_nasa_hourly(payload)


def test_alignment_cannot_extrapolate_or_assume_naive_timezone():
    hourly = parse_nasa_hourly(fixture())
    with pytest.raises(ValueError, match="cover"):
        align_hourly_resource(hourly, pd.date_range("2014-09-17T00:00Z", periods=4, freq="15min"))
    with pytest.raises(ValueError, match="timezone-aware"):
        align_hourly_resource(hourly, pd.date_range("2014-09-16", periods=4, freq="15min"))
