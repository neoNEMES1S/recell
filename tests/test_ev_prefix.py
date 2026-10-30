"""Later measured labels cannot fabricate unavailable source input covariates."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from second_life_battery.data.ev_prefix import verified_source_prefixes


def fixture():
    diagnostics = pd.DataFrame(
        [
            {
                "cell_id": "W4",
                "physical_cell_id": "secl_m50t_W4",
                "diagnostic": i,
                "diagnostic_start_time": f"2020-01-{i * 5:02d}T00:00:00",
                "diagnostic_end_time": f"2020-01-{i * 5:02d}T01:00:00",
                "capacity_ah": 5 - i * 0.05,
            }
            for i in range(1, 5)
        ]
    )
    batches = pd.DataFrame(
        [
            {
                "cell_id": "W4",
                "number": i,
                "charge_ah": 10,
                "discharge_ah": 9,
                "batch_start_time": f"2020-01-{i * 5 + 1:02d}T00:00:00",
                "batch_end_time": f"2020-01-{i * 5 + 2:02d}T00:00:00",
            }
            for i in [1, 2]
        ]
    )
    return diagnostics, batches


def test_future_label_is_available_without_future_feature_filling():
    features, labels, availability = verified_source_prefixes(*fixture())
    assert features.diagnostic.tolist() == [1, 2, 3]
    assert labels.diagnostic.tolist() == [1, 2, 3, 4]
    assert features.cumulative_ah_since_stage_start.tolist() == [0, 19, 38]
    assert "cumulative_ah_since_stage_start" not in labels
    assert availability.potential_origin_diagnostics.iloc[0] == [3]
    changed, batches = fixture()
    changed.loc[changed.diagnostic.eq(4), "capacity_ah"] = 4.1
    later_features, later_labels, _ = verified_source_prefixes(changed, batches)
    assert_frame_equal(features, later_features)
    assert later_labels.soh.iloc[-1] != labels.soh.iloc[-1]


def test_missing_middle_batch_stops_features_but_keeps_measured_labels():
    diagnostics, batches = fixture()
    features, labels, availability = verified_source_prefixes(diagnostics, batches.iloc[1:])
    assert features.empty and len(labels) == 4
    assert availability.potential_H1_min3_origins.iloc[0] == 0
    assert availability.last_verified_feature_diagnostic.iloc[0] == 1


def test_bad_corridor_is_reported_without_advancing_prefix():
    diagnostics, batches = fixture()
    batches.loc[batches.number.eq(2), "batch_end_time"] = "2020-01-16T00:00:00"
    features, _, availability = verified_source_prefixes(diagnostics, batches)
    assert features.diagnostic.tolist() == [1, 2]
    assert availability.corridor_failure.iloc[0]["batch"] == 2
    assert availability.potential_H1_min3_origins.iloc[0] == 0


def test_aliases_cannot_multiply_physical_source_batteries():
    diagnostics, batches = fixture()
    duplicate_identity = diagnostics.assign(cell_id="W5")
    with pytest.raises(ValueError, match="physical battery"):
        verified_source_prefixes(pd.concat([diagnostics, duplicate_identity]), batches)


def test_iso_clocks_with_optional_fractional_seconds_keep_the_same_prefix():
    diagnostics, batches = fixture()
    expected, _, _ = verified_source_prefixes(diagnostics, batches)
    diagnostics.loc[0, "diagnostic_end_time"] += ".000000"
    diagnostics.loc[0, "diagnostic_start_time"] += ".000000"
    actual, _, availability = verified_source_prefixes(diagnostics, batches)
    assert_frame_equal(actual, expected)
    assert availability.potential_H1_min3_origins.iloc[0] == 1


def test_batch_identity_must_match_diagnostic_identity():
    diagnostics, batches = fixture()
    batches["physical_cell_id"] = "different_cell"
    with pytest.raises(ValueError, match="physical identity"):
        verified_source_prefixes(diagnostics, batches)


@pytest.mark.parametrize("problem", ["missing_first", "overlap", "duplicate", "identity"])
def test_reference_and_identity_guards(problem):
    diagnostics, batches = fixture()
    if problem == "missing_first":
        features, labels, availability = verified_source_prefixes(diagnostics.iloc[1:], batches)
        assert features.empty and labels.empty
        assert availability.status.iloc[0] == "first_reference_unavailable"
        return
    if problem == "overlap":
        diagnostics.loc[1, "diagnostic_start_time"] = diagnostics.diagnostic_start_time.iloc[0]
    elif problem == "duplicate":
        diagnostics = pd.concat([diagnostics, diagnostics.iloc[:1]])
    else:
        diagnostics.loc[1, "physical_cell_id"] = "different_cell"
    with pytest.raises(ValueError):
        verified_source_prefixes(diagnostics, batches)
