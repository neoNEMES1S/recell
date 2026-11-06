import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.bms import prepare_bms
from second_life_battery.data.life import threshold_event
from second_life_battery.models.ecm import Parameters
from second_life_battery.models.health_ecm import effective_capacity, simulate_health_case
from second_life_battery.models.life import remaining_to_threshold

HEALTH = dict(
    soh=0.9,
    reference_capacity_ah=4,
    reference_basis="first_observed_rpt",
    feature_cutoff="2025-01-01",
    forecast_origin="2025-01-02",
    reference_available_at="2024-01-01",
)


def test_bridge_preserves_reference_and_changes_capacity_not_resistance():
    assert effective_capacity(**HEALTH) == pytest.approx(3.6)
    case = simulate_health_case(
        [0, 360], [1, 1], Parameters(0.03), HEALTH, initial_soc=0.5, ocv_soc=[0, 1], ocv_v=[3, 4]
    )
    assert case["soc"][-1] == pytest.approx(0.5 - 0.1 / 3.6)
    baseline = simulate_health_case(
        [0, 360],
        [1, 1],
        Parameters(0.03),
        {**HEALTH, "soh": 1.0},
        initial_soc=0.5,
        ocv_soc=[0, 1],
        ocv_v=[3, 4],
    )
    assert case["voltage_v"][-1] < baseline["voltage_v"][-1]
    with pytest.raises(ValueError, match="Future"):
        effective_capacity(**{**HEALTH, "feature_cutoff": "2025-01-03"})
    with pytest.raises(ValueError, match="conversion"):
        effective_capacity(**{**HEALTH, "reference_basis": "nominal"})


def test_bms_flags_preserve_order_and_do_not_fabricate_health():
    f = pd.DataFrame(
        {
            "pack_id": ["P"] * 4,
            "cell_id": ["C"] * 4,
            "timestamp": [
                "2025-01-01T00:00:00",
                "2025-01-01T00:00:02",
                "2025-01-01T00:00:01",
                "2025-01-01T00:00:01",
            ],
            "current_a": [-1] * 4,
            "voltage_v": [3.7, 3.6, 3.65, np.nan],
        }
    )
    c = dict(
        columns={k: k for k in f.columns},
        timezone="UTC",
        current_unit="A",
        voltage_unit="V",
        current_convention="charge_positive",
        maximum_gap_s=5,
        maximum_delay_s=5,
    )
    r = prepare_bms(f, c)
    assert r.current_a.tolist() == [1] * 4
    assert "out_of_order" in r.quality.iloc[2]
    assert "duplicate_event" in r.quality.iloc[2]
    assert "invalid_electrical" in r.quality.iloc[3]
    assert not r.arrival_timing_verified.any() and "soh" not in r


def test_stale_arrival_and_units():
    f = pd.DataFrame(
        dict(
            pack_id=["P"],
            cell_id=["C"],
            timestamp=["2025-01-01"],
            arrival_timestamp=["2025-01-02"],
            voltage_v=[3.7],
            current_a=[0],
        )
    )
    c = dict(
        columns={k: k for k in f.columns},
        timezone="UTC",
        current_unit="A",
        voltage_unit="V",
        current_convention="discharge_positive",
        maximum_gap_s=5,
        maximum_delay_s=5,
    )
    assert prepare_bms(f, c).quality.iloc[0] == "stale_record"
    with pytest.raises(ValueError, match="units"):
        prepare_bms(f, {**c, "current_unit": "mA"})


def test_life_events_retain_interval_and_right_censoring_and_recoveries():
    assert threshold_event([0, 10, 20], [1, 0.9, 0.95], 0.8) == {
        "censoring": "right",
        "lower": 20,
        "upper": None,
    }
    assert threshold_event([0, 10, 20], [1, 0.9, 0.79], 0.8) == {
        "censoring": "interval",
        "lower": 10,
        "upper": 20,
    }
    assert threshold_event([0, 10], [0.7, 0.6], 0.8)["censoring"] == "left"
    assert remaining_to_threshold([0, 10, 20], [1, 0.95, 0.9], 0.8)["remaining"] == pytest.approx(
        20
    )
    assert remaining_to_threshold([0, 10, 20], [0.9, 0.95, 1], 0.8)["remaining"] is None
