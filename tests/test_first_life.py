"""A source capacity audit must retain missing clocks and reject silent identity swaps."""

import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat

from second_life_battery.data.first_life import audit_raw_capacity, reconstruct_capacities


def source_fixture(path, current=-0.25):
    arrays = {}
    for key in ["cap", "curr", "time", "vcell"]:
        values = np.empty((2, 1), dtype=object)
        values[1, 0] = np.nan
        values[0, 0] = {
            "cap": np.array([0, 2.5]),
            "curr": np.array([current, current]),
            "time": np.array([0, 36000]),
            "vcell": np.array([4.2, 2.5]),
        }[key]
        arrays[key] = values
    arrays.update(col_cell_label=np.array([["G1"]], dtype=object), row_diag_number=[[1, 2]])
    savemat(path, arrays)
    return {
        "cells": [
            {
                "first_life_source_id": "G1",
                "physical_cell_id": "physical-G1",
                "first_life_mat_column_zero_based": 0,
            }
        ]
    }


def test_capacity_reconstruction_does_not_fabricate_stage_features(tmp_path):
    source = tmp_path / "capacity.mat"
    registry = source_fixture(source)
    result = reconstruct_capacities(source, registry)
    assert len(result) == 1
    assert result.capacity_ah.iloc[0] == pytest.approx(2.5)
    assert result.soh.iloc[0] == 1
    assert (
        result[["timestamp", "elapsed_days", "cumulative_ah_since_stage_start"]].isna().all().all()
    )
    registry["cells"][0]["first_life_source_id"] = "V4"
    with pytest.raises(ValueError, match="column order"):
        reconstruct_capacities(source, registry)


def test_incorrect_current_convention_rejected(tmp_path):
    source = tmp_path / "capacity.mat"
    registry = source_fixture(source, current=0.25)
    with pytest.raises(ValueError, match="protocol"):
        reconstruct_capacities(source, registry)


def test_raw_clock_and_independent_counter_check():
    n = 36001
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=n, freq="s"),
            "time_s": np.arange(n),
            "step": 1,
            "current_a": -0.25,
            "voltage_v": np.linspace(4.2, 2.5, n),
            "discharge_ah": np.arange(n) * 0.25 / 3600,
        }
    )
    result = audit_raw_capacity(frame)
    assert result["capacity_ah"] == pytest.approx(2.5)
    assert result["diagnostic_start_time"] == "2020-01-01T00:00:00"
    # Native Excel wall clocks may round distinct test-time samples to one timestamp.
    frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
    assert audit_raw_capacity(frame)["capacity_ah"] == pytest.approx(2.5)
    frame["discharge_ah"] *= 2
    with pytest.raises(ValueError, match="counter"):
        audit_raw_capacity(frame)
