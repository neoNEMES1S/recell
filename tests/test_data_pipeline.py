"""Physical calculations, duplicate handling and causal reference checks."""

import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.features import (
    add_soh,
    counter_throughput,
    diagnostic_summary,
    integrate_current,
)
from second_life_battery.data.parser import merge_exports


def test_constant_current_capacity_and_time_validation() -> None:
    assert integrate_current(np.array([0, 1800, 3600]), np.array([-2, -2, -2])) == -2
    with pytest.raises(ValueError, match="increase"):
        integrate_current(np.array([0, 0]), np.array([1, 1]))


def test_counter_resets_do_not_destroy_throughput() -> None:
    assert counter_throughput(np.array([0, 1, 2, 0.2, 1.2])) == pytest.approx(3.2)
    assert counter_throughput(np.array([5, 6, 7])) == 2  # Unknown offset is not exposure.
    with pytest.raises(ValueError):
        counter_throughput(np.array([0, np.nan]))


def test_overlapping_exports_are_deduplicated_and_conflicts_rejected() -> None:
    a = pd.DataFrame(
        {
            "timestamp": pd.date_range("2023-01-01", periods=3),
            "value": [1, 2, 3],
            "time_s": [0, 1, 2],
        }
    )
    b = a.iloc[1:].copy()
    merged, removed = merge_exports([a, b])
    assert len(merged) == 3 and removed == 2
    b.iloc[0, 1] = 8
    with pytest.raises(ValueError, match="Conflicting"):
        merge_exports([a, b])


def test_soh_reference_cannot_use_future_maximum_or_another_cell() -> None:
    frame = pd.DataFrame(
        {
            "cell_id": ["A", "A", "B", "B"],
            "timestamp": [1, 2, 1, 2],
            "capacity_ah": [4.0, 4.2, 3.0, 2.7],
        }
    )
    result = add_soh(frame, {"method": "first_observed_rpt"})
    assert result.soh.to_list() == pytest.approx([1.0, 1.05, 1.0, 0.9])
    frame.loc[1, "capacity_ah"] = 100
    assert add_soh(frame, {"method": "first_observed_rpt"}).reference_capacity_ah.iloc[0] == 4
    with pytest.raises(ValueError):
        add_soh(frame, {"method": "fixed", "fixed_capacity_ah": 0})


def test_capacity_uses_low_rate_segments_and_excludes_pulses() -> None:
    records = []
    for index, step in enumerate([5, 9, 13, 17]):
        for offset in [0, 9000, 18000]:
            records.append(
                {
                    "time_s": index * 20000 + offset,
                    "step": step,
                    "current_a": -0.2,
                    "discharge_ah": index + offset / 18000,
                    "voltage_v": 4.18 if offset == 0 else [4, 3.63, 3.26, 2.5][index],
                }
            )
        if index == 0:
            for offset in [18001, 18009]:
                records.append(
                    {
                        "time_s": offset,
                        "step": 6,
                        "current_a": -2,
                        "discharge_ah": 1 + (offset - 18001) / 1800,
                        "voltage_v": 3.95,
                    }
                )
    frame = pd.DataFrame(records)
    frame["timestamp"] = pd.Timestamp("2023-01-01") + pd.to_timedelta(frame.time_s, unit="s")
    frame["aux_temp_c"] = 25.0
    settings = {
        "discharge_current_min_a": 0.15,
        "discharge_current_max_a": 0.3,
        "minimum_segment_seconds": 300,
        "maximum_sample_gap_seconds": 10000,
        "counter_relative_tolerance": 0.01,
        "capacity_min_ah": 2,
        "capacity_max_ah": 5,
    }
    result = diagnostic_summary(frame, settings)
    assert result["capacity_ah"] == pytest.approx(4)
    assert len(result["segments"]) == 4
    assert result["counter_relative_error"] == pytest.approx(0)
    frame.loc[frame.step == 17, "voltage_v"] = 3
    with pytest.raises(ValueError, match="voltage window"):
        diagnostic_summary(frame, settings)
