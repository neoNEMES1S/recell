"""Leakage guards, temporal contexts and hand-computable evaluation metrics."""

import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.sequences import fit_preprocessor, make_sequences
from second_life_battery.evaluation.metrics import point_metrics, probabilistic_metrics
from second_life_battery.training.cross_validation import Fold, lobo_folds, split_fold


def checkpoints() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cell_id": cell,
                "timestamp": pd.Timestamp("2023-01-01") + pd.Timedelta(days=i),
                "soh": 1 - i * 0.01,
                "reference_capacity_ah": 4,
                "feature": base + i,
            }
            for cell, base in [("A", 0), ("B", 10), ("C", 100)]
            for i in range(8)
        ]
    )


def test_fold_separation_and_training_only_scaler() -> None:
    frame = checkpoints()
    for fold in lobo_folds(frame):
        train, valid, test = split_fold(frame, fold)
        assert set(train.cell_id).isdisjoint(valid.cell_id)
        assert set(train.cell_id).isdisjoint(test.cell_id)
        scaler = fit_preprocessor(train, ["feature"])
        assert scaler[-1].mean_[0] == pytest.approx(train.feature.mean())
    with pytest.raises(ValueError, match="multiple"):
        split_fold(frame, Fold("A", "B", ("A", "C")))


def test_sequences_never_read_future_features_and_keep_origins_fixed() -> None:
    frame = checkpoints().query("cell_id == 'A'")
    full = make_sequences(frame, ["feature"], 2)
    limited = make_sequences(frame, ["feature"], 2, 0.1)
    assert [s.origin_index for s in full] == [s.origin_index for s in limited]
    assert all(len(s.history) == 1 for s in limited)
    assert full[0].history[:, 0].tolist() == [0, 1, 2]
    assert full[0].target.tolist() == pytest.approx([0.97, 0.96])
    frame.loc[frame.index >= 3, "feature"] = 1e10
    changed = make_sequences(frame, ["feature"], 2)
    np.testing.assert_array_equal(full[0].history, changed[0].history)


def test_metrics_known_values_and_zero_target_mape() -> None:
    result = point_metrics(np.array([1, 3]), np.array([2, 2]))
    assert result["mae"] == result["rmse"] == 1
    assert result["r2"] == 0
    assert np.isnan(point_metrics(np.array([0, 1]), np.array([0, 1]))["mape_percent"])
    quantiles = np.array([[0, 1, 2], [2, 3, 4]])
    probabilistic = probabilistic_metrics(np.array([1, 3]), quantiles)
    assert probabilistic["coverage_80"] == 1 and probabilistic["interval_width"] == 2
    assert probabilistic["quantile_loss"] == pytest.approx(2 / 30)
    with pytest.raises(ValueError, match="cross"):
        probabilistic_metrics(np.array([1]), np.array([[2, 1, 3]]))
