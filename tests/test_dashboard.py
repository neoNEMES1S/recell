"""Client headlines must preserve matched assumptions, aggregation and missing metrics."""

import json

import pandas as pd
import pytest

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.dashboard import (
    dispatch_comparison,
    india_replay,
    records,
    verify_provenance,
)


def comparison_rows():
    return pd.DataFrame(
        [
            {
                "cell_id": cell,
                "scenario": scenario,
                "degradation_weight": weight,
                "health_fraction": 0.8,
                "wear_per_efc": 0.001,
                "electricity_cost_eur": electric,
                "estimated_degradation_cost_eur": wear,
                "electricity_plus_estimated_wear_eur": electric + wear,
                "equivalent_full_cycles": 10,
            }
            for cell, offset in [("A", 0), ("B", 2)]
            for scenario, weight, electric, wear in [
                ("C_second_life", 0, -5 + offset, 18),
                ("D_degradation_aware", 1, 0 + offset, 11),
                ("D_conservative", 1, 30, 4),
            ]
        ]
    )


def test_matched_policy_comparison_preserves_negative_electricity_cost():
    result = dispatch_comparison(comparison_rows())
    assert result["baseline"]["electricity_plus_estimated_wear_eur"] == 14
    assert result["aware"]["electricity_plus_estimated_wear_eur"] == 12
    assert result["baseline"]["electricity_cost_eur"] == -4
    assert result["cells"] == ["A", "B"]


def test_comparison_rejects_changed_assumptions_or_unpaired_cells():
    frame = comparison_rows()
    frame.loc[frame.scenario == "D_degradation_aware", "health_fraction"] = 0.7
    with pytest.raises(ValueError, match="same health"):
        dispatch_comparison(frame)
    frame = comparison_rows()
    frame = frame[~((frame.cell_id == "B") & (frame.scenario == "D_degradation_aware"))]
    with pytest.raises(ValueError, match="paired"):
        dispatch_comparison(frame)


def test_missing_metrics_are_null_not_zero():
    assert records(pd.DataFrame({"coverage": [float("nan"), 0.8]})) == [
        {"coverage": None},
        {"coverage": 0.8},
    ]


def test_india_replay_reoptimizes_without_mutating_reference_inputs():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=2, freq="h", tz="UTC"),
            "solar_kw": [2.0, 0.0],
            "load_kw": [1.0, 2.0],
            "import_price": [0.4, 0.4],
            "export_price": [0.08, 0.08],
        }
    )
    settings = {
        "battery": {
            "nominal_energy_kwh": 4,
            "power_kw": 2,
            "round_trip_efficiency": 0.81,
            "soc_min": 0,
            "soc_max": 1,
            "initial_soc": 0,
            "replacement_cost_eur": 1000,
            "capacity_loss_budget": 0.2,
            "solver": "CLARABEL",
        }
    }
    market = {
        "currency": "INR",
        "import_price_inr_per_kwh": 10,
        "export_price_inr_per_kwh": 0,
        "replacement_cost_inr": 100000,
    }
    original = frame.copy(deep=True)
    reference = comparison_rows().query("cell_id == 'A' and scenario != 'D_conservative'")
    results, schedules, actual_settings = india_replay(frame, reference, settings, market)
    comparison = dispatch_comparison(results, "inr")
    assert comparison["aware"]["electricity_plus_estimated_wear_inr"] <= (
        comparison["baseline"]["electricity_plus_estimated_wear_inr"] + 1e-5
    )
    pd.testing.assert_frame_equal(frame, original)
    assert settings["battery"]["replacement_cost_eur"] == 1000
    assert "replacement_cost_eur" not in actual_settings["battery"]
    assert actual_settings["battery"]["replacement_cost_inr"] == 100000
    assert len(schedules) == 2
    assert schedules[0]["frame"].import_price.tolist() == [10, 10]
    assert schedules[0]["frame"].export_price.tolist() == [0, 0]


def test_provenance_rejects_mixed_runs(tmp_path):
    checkpoint = tmp_path / "data/processed/checkpoints.csv"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("cell_id,capacity_ah\nA,4\n")
    for run in ["lobo", "limited_history", "dispatch"]:
        folder = tmp_path / "outputs" / run
        folder.mkdir(parents=True)
        (folder / "provenance.json").write_text(
            json.dumps(
                {"checkpoint_data_sha256": sha256_file(checkpoint) if run == "lobo" else "stale"}
            )
        )
    with pytest.raises(ValueError, match="limited_history"):
        verify_provenance(tmp_path)
