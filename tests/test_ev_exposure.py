"""Reject exposure that is incomplete, mismatched or unavailable at prediction time."""

import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.ev_exposure import (
    causal_features,
    integrate_batch,
    integrate_segments,
)


def endpoints():
    return [
        {"Test_Time(s)": t, "Current(A)": i, "Voltage(V)": 3.7, "Date_Time": stamp}
        for t, i, stamp in [(1, 1, "2021-01-02"), (3, -1, "2021-01-02T00:00:02")]
    ]


def test_dense_integral_excludes_only_proven_synthetic_zero():
    result = integrate_batch([0, 1, 2, 3], [0, 1, 0, -1], [0, 3.7, 3.7, 3.7], *endpoints())
    assert result["removed_synthetic_zero"]
    assert result["charge_ah"] == pytest.approx(0.5 / 3600)
    assert result["discharge_ah"] == pytest.approx(0.5 / 3600)
    assert result["native_minus_instrument_duration_seconds"] == 0


@pytest.mark.parametrize(
    "time,current,voltage",
    [
        ([1, 2, 3.01], [1, 0, -1], [3.7] * 3),
        ([1, 2, 3], [1, np.nan, -1], [3.7] * 3),
        ([1, 2, 3], [1, 0, -1], [3.7, 3.7, 3.8]),
        ([1, 2, 2], [1, 0, -1], [3.7] * 3),
        ([1, 2, 9], [1, 0, -1], [3.7] * 3),
    ],
)
def test_bad_measurements_or_endpoints_rejected(time, current, voltage):
    with pytest.raises(ValueError):
        integrate_batch(time, current, voltage, *endpoints())


def histories():
    diagnostics = pd.DataFrame(
        {
            "cell_id": ["G1"] * 3,
            "diagnostic": [1, 2, 3],
            "capacity_ah": [4.9, 4.8, 4.7],
            "diagnostic_start_time": ["2021-01-01", "2021-01-04", "2021-01-07"],
            "diagnostic_end_time": ["2021-01-02", "2021-01-05", "2021-01-08"],
        }
    )
    batches = pd.DataFrame(
        {
            "cell_id": ["G1"] * 2,
            "number": [1, 2],
            "batch_start_time": ["2021-01-02", "2021-01-05"],
            "batch_end_time": ["2021-01-03", "2021-01-06"],
            "charge_ah": [10, 20],
            "discharge_ah": [9, 19],
        }
    )
    return diagnostics, batches


def test_stage_exposure_uses_only_completed_intervals():
    result = causal_features(*histories())
    assert result.cumulative_ah_since_stage_start.tolist() == [0, 19, 58]
    assert result.elapsed_days.tolist() == [0, 3, 6]
    assert result.soh.iloc[0] == 1


def test_missing_batch_and_future_exposure_rejected():
    diagnostics, batches = histories()
    with pytest.raises(ValueError, match="Missing or duplicate"):
        causal_features(diagnostics, batches.iloc[:1])
    batches.loc[0, "batch_end_time"] = "2021-01-04T00:00:01"
    with pytest.raises(ValueError, match="boundary"):
        causal_features(diagnostics, batches)


def part_anchors():
    return [
        (
            dict(
                zip(
                    ["Test_Time(s)", "Current(A)", "Voltage(V)", "Date_Time"],
                    [1, 1, 3.7, f"2021-01-0{day}"],
                )
            ),
            dict(
                zip(
                    ["Test_Time(s)", "Current(A)", "Voltage(V)", "Date_Time"],
                    [2, -1, 3.7, f"2021-01-0{day}T00:00:01"],
                )
            ),
        )
        for day in [2, 3]
    ]


def test_explicit_rebases_integrate_parts_without_cross_pause_exposure():
    result = integrate_segments(
        [0, 1, 2, 2, 3, 4], [0, 1, -1, 0, 1, -1], [0, 3.7, 3.7, 0, 3.7, 3.7], part_anchors()
    )
    assert result["removed_synthetic_rows"] == 2
    assert result["source_parts"] == 2
    assert result["charge_ah"] == pytest.approx(1 / 3600)
    assert result["discharge_ah"] == pytest.approx(1 / 3600)
    assert result["native_inter_part_gaps_seconds"] == [86399]


def test_unknown_rebase_missing_anchor_and_native_overlap_rejected():
    args = ([0, 1, 2, 2, 3, 4], [0, 1, -1, 0, 1, -1], [0, 3.7, 3.7, 0, 3.7, 3.7])
    with pytest.raises(ValueError, match="markers"):
        integrate_segments(*args, part_anchors()[:1])
    with pytest.raises(ValueError, match="rebase"):
        integrate_segments([0, 1, 2, 2.1, 3.1, 4.1], *args[1:], part_anchors())
    anchors = part_anchors()
    anchors[1][0]["Date_Time"] = "2021-01-02"
    with pytest.raises(ValueError, match="overlap"):
        integrate_segments(*args, anchors)


def test_trajectory_fingerprint_uses_values_order_and_boundaries():
    from second_life_battery.data.ev_exposure import trajectory_sha256

    arrays = [np.array([0, 1, 2]), np.array([0, 1, -1]), np.array([3.7, 3.8, 3.9])]
    expected = trajectory_sha256(arrays)
    assert expected == trajectory_sha256([a.astype(">f8") for a in arrays])
    assert expected != trajectory_sha256([arrays[0], -arrays[1], arrays[2]])
    assert expected != trajectory_sha256([arrays[0][::-1], arrays[1], arrays[2]])
    assert expected != trajectory_sha256([np.array([0]), np.array([1, 2, 0, 1, -1]), arrays[2]])


def test_raw_fragment_review_integrates_across_boundaries_without_sorting():
    from second_life_battery.data.ev_exposure import audit_raw_cycling_fragments

    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2021-01-01", periods=4, freq="s"),
            "time_s": [0.1, 1.1, 2.1, 3.1],
            "current_a": [1.0, 1.0, -1.0, -1.0],
            "voltage_v": [3.7] * 4,
        }
    )
    result = audit_raw_cycling_fragments([frame.iloc[:2], frame.iloc[2:]])
    assert result["observations"] == 4
    assert result["raw_fragments"] == 2
    assert result["charge_ah"] == pytest.approx(1.5 / 3600)
    assert result["discharge_ah"] == pytest.approx(1.5 / 3600)
    with pytest.raises(ValueError, match="wall clocks reverse"):
        audit_raw_cycling_fragments([frame.iloc[2:], frame.iloc[:2]])
    changed = frame.copy()
    changed.loc[2:, "time_s"] += 10
    with pytest.raises(ValueError, match="sampling gap"):
        audit_raw_cycling_fragments([changed])
    with pytest.raises(ValueError, match="sampling gap"):
        audit_raw_cycling_fragments([frame.iloc[:2], frame.iloc[1:]])
