"""Registered calendar models use measured conditions and equal physical-cell weights."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from second_life_battery.models.calendar import fit_calendar, predict_calendar, training_weights


def test_balanced_training_weights_do_not_count_repeated_rows_as_new_cells():
    frame = pd.DataFrame(
        {
            "base_type": ["A"] * 6 + ["B"] * 6,
            "physical_cell_id": ["a1"] * 2 + ["a2"] * 4 + ["b1"] * 6,
            "elapsed_days": [7.0] * 12,
            "soh": [0.99] * 12,
        }
    )
    weights = training_weights(frame)
    assert weights.sum() == pytest.approx(1)
    assert weights[:2].sum() == pytest.approx(0.25)
    assert weights[2:6].sum() == pytest.approx(0.25)
    assert weights[6:].sum() == pytest.approx(0.5)


def test_calendar_model_recovers_synthetic_curve_without_reading_test_labels():
    rows = [
        {
            "base_type": kind,
            "physical_cell_id": f"{kind}_{temp}_{soc}",
            "elapsed_days": age,
            "storage_temperature_c": temp,
            "storage_soc_fraction": soc,
        }
        for kind in ["A", "B"]
        for temp in [24.0, 45.0, 60.0]
        for soc in [0.5, 1.0]
        for age in [7.0, 30.0, 180.0, 365.0]
    ]
    frame = pd.DataFrame(rows)
    frame["soh"] = predict_calendar("C2", [-3.0, 4.0, 1.0], frame)
    config = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/calendar_protocol_v1.yaml").read_text()
    )
    models = fit_calendar(frame, config["optimization"])
    predicted = predict_calendar("C2", models["C2"]["parameters"], frame)
    assert np.allclose(predicted, frame.soh, atol=1e-6)
    changed = frame.assign(soh=-100)
    assert np.array_equal(predicted, predict_calendar("C2", models["C2"]["parameters"], changed))
    assert len(models["C2"]["fixed_starts"]) == 6


def test_calendar_predictions_are_not_clipped_and_invalid_conditions_fail():
    frame = pd.DataFrame(
        {"elapsed_days": [365.25], "storage_temperature_c": [24.0], "storage_soc_fraction": [0.5]}
    )
    assert predict_calendar("C1", [2.0], frame)[0] == -1.0
    with pytest.raises(ValueError, match="conditions"):
        predict_calendar("C1", [0.1], frame.assign(storage_temperature_c=-300))
