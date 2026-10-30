"""Indian minute readings are neither cumulative meters nor permission to fill gaps."""

import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.india_load import aggregate_iblend


def fixture():
    times = pd.date_range("2014-09-17", periods=30, freq="min", tz="Asia/Kolkata")
    meter = pd.DataFrame({"timestamp": times.as_unit("s").asi8, "power": 1000.0})
    availability = pd.DataFrame({"timestamp": times.tz_localize(None).astype(str), "Academic": 1})
    return meter, availability


def test_watts_to_kw_energy_and_timezone():
    result, report = aggregate_iblend(*fixture())
    assert result.load_kw.tolist() == [1, 1]
    assert result.load_kwh.tolist() == [0.25, 0.25]
    assert result.complete.all()
    assert result.timestamp.iloc[0] == pd.Timestamp("2014-09-16T18:30:00Z")
    assert report["complete_intervals"] == 2


@pytest.mark.parametrize("problem", ["absent", "nonfinite", "negative", "unavailable"])
def test_one_bad_minute_keeps_entire_quarter_missing(problem):
    meter, availability = fixture()
    if problem == "absent":
        meter = meter.drop(index=1)
    elif problem == "unavailable":
        availability.loc[1, "Academic"] = 0
    else:
        meter.loc[1, "power"] = np.nan if problem == "nonfinite" else -1
    result, _ = aggregate_iblend(meter, availability)
    assert not result.complete.iloc[0]
    assert pd.isna(result.load_kw.iloc[0])
    assert result.observed_minutes.iloc[0] == 14
    assert result.load_kw.iloc[1] == 1


def test_measured_zero_preserved_and_absent_quarter_not_zero_filled():
    meter, availability = fixture()
    meter.loc[:14, "power"] = 0
    result, _ = aggregate_iblend(meter, availability)
    assert result.complete.iloc[0] and result.load_kw.iloc[0] == 0
    result, report = aggregate_iblend(meter.iloc[15:], availability)
    assert pd.isna(result.load_kw.iloc[0])
    assert report["absent_meter_minutes"] == 15


def test_irregular_clock_and_unrecognized_flag_rejected():
    meter, availability = fixture()
    meter.loc[1, "timestamp"] += 1
    with pytest.raises(ValueError, match="minute grid"):
        aggregate_iblend(meter, availability)
    meter, availability = fixture()
    availability.loc[1, "Academic"] = 2
    with pytest.raises(ValueError, match="availability flag"):
        aggregate_iblend(meter, availability)
