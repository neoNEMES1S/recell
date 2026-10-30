"""Check battery-level estimands and reject mismatched comparisons before reporting."""

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.transfer import analyze_transfer
from second_life_battery.utils.reproducibility import verify_artifacts


def predictions():
    protocol = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/transfer_protocol_v2.yaml").read_text()
    )
    cells = [f"cell_{i}" for i in range(6)]
    rows = []
    for arm, seed, fraction, cell, horizon in product(
        [f"R{i}" for i in range(1, 7)],
        protocol["target"]["seeds"],
        protocol["target"]["inference_context_fractions"],
        range(6),
        [1, 2],
    ):
        for origin in range(cell + 1):  # Unequal origins must not weight batteries unequally.
            delta = [-0.01, -0.005, 0, 0.005, 0.01, 0.015][cell] if arm == "R2" else 0
            median = 0.9 + 0.02 + 0.001 * (seed - 42) + delta
            index = origin + 2
            rows.append(
                {
                    "model": arm,
                    "cell_id": cells[cell],
                    "seed": seed,
                    "history_fraction": fraction,
                    "horizon": horizon,
                    "origin_index": index,
                    "origin_time": f"2022-01-{index + 1:02d}",
                    "target_time": f"2022-01-{index + 1 + horizon:02d}",
                    "origin_soh": 1.0,
                    "reference_capacity_ah": 4.9,
                    "y_true": 0.9,
                    "q50": median,
                    "q10": median - 0.03 if arm in ["R1", "R2", "R3", "R4"] else np.nan,
                    "q90": median + 0.03 if arm in ["R1", "R2", "R3", "R4"] else np.nan,
                    "effective_history": max(1, int(np.ceil((index + 1) * fraction))),
                }
            )
    return pd.DataFrame(rows), protocol, cells


def test_seed_then_equal_cell_primary_difference_and_negative_transfer():
    frame, protocol, cells = predictions()
    result = analyze_transfer(frame, protocol, cells)
    primary = result["paired_comparisons"].iloc[0]
    assert primary.comparison == "R2 minus R1"
    assert primary.cells == 6
    assert primary.rmse_difference == pytest.approx(0.0025)
    assert "inconclusive" in primary.interpretation
    cell = result["per_cell"]
    assert cell[
        (cell.model == "R1") & (cell.horizon == 1) & (cell.history_fraction == 0.1)
    ].rmse.mean() == pytest.approx(0.021)
    assert (
        result["per_cell_differences"].query("comparison == 'R2 minus R1'").higher_rmse.sum() == 3
    )
    assert np.allclose(result["summary"].query("model == 'R1'").interval_width_mean, 0.06)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "label", "context", "quantile"])
def test_invalid_or_unmatched_comparison_is_rejected(defect):
    frame, protocol, cells = predictions()
    if defect == "missing":
        frame = frame.iloc[1:]
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    elif defect == "label":
        frame.loc[0, "y_true"] = 0.8
    elif defect == "context":
        frame.loc[0, "effective_history"] = 100
    else:
        frame.loc[0, "q10"] = 2
    with pytest.raises(ValueError):
        analyze_transfer(frame, protocol, cells)


def test_completed_artifacts_are_hash_checked_and_confined(tmp_path):
    file = tmp_path / "model.pt"
    file.write_bytes(b"not executed; only hashed")
    expected = {file.name: sha256_file(file)}
    verify_artifacts(tmp_path, expected)
    file.write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact changed"):
        verify_artifacts(tmp_path, expected)
    with pytest.raises(ValueError, match="escaped"):
        verify_artifacts(tmp_path, {"../outside.pt": "a" * 64})
