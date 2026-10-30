"""Demand baselines must respect availability clocks and validation-only selection."""

import json
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.load_forecast import (
    load_error_tables,
    paired_load_interval,
    select_load_candidate,
)
from second_life_battery.models.load_forecast import seasonal_day_ahead


def history_fixture():
    index = pd.date_range("2014-09-17", periods=8 * 96, freq="15min", tz="Asia/Kolkata")
    return pd.Series(np.arange(1, len(index) + 1, dtype=float), index=index)


def test_exact_lags_units_and_cutoff():
    origin = pd.Timestamp("2014-09-25", tz="Asia/Kolkata")
    frame = seasonal_day_ahead(history_fixture(), origin, {"weekly": 0, "blend": 0.5, "day": 1})
    assert len(frame) == 288
    for model, first in [("weekly", 97), ("blend", 385), ("day", 673)]:
        values = frame[frame.model == model].prediction_kw.to_numpy()
        assert np.array_equal(values, np.arange(first, first + 96))
    assert frame.timestamp.iloc[0] == pd.Timestamp("2014-09-24T18:30:00Z")
    assert (frame.latest_feature_interval_end <= frame.origin).all()
    assert frame.latest_feature_interval_end.max() == origin


@pytest.mark.parametrize("problem", ["future", "missing", "naive", "duplicate", "negative"])
def test_unavailable_or_invalid_history_rejected(problem):
    history = history_fixture()
    origin = pd.Timestamp("2014-09-25", tz="Asia/Kolkata")
    if problem == "future":
        history.loc[origin] = 99999
    elif problem == "missing":
        history = history.drop(history.index[96])
    elif problem == "naive":
        history.index = history.index.tz_localize(None)
    elif problem == "duplicate":
        history = pd.concat([history.iloc[:1], history])
    else:
        history.iloc[96] = -1
    with pytest.raises(ValueError):
        seasonal_day_ahead(history, origin, {"weekly": 0})


def test_origin_and_weight_contract():
    history = history_fixture()
    for origin in [pd.Timestamp("2014-09-25"), pd.Timestamp("2014-09-25T01:00+05:30")]:
        with pytest.raises(ValueError, match="timezone|midnight"):
            seasonal_day_ahead(history, origin, {"weekly": 0})
    for weight in [np.nan, -0.1, 1.1]:
        with pytest.raises(ValueError, match="weights"):
            seasonal_day_ahead(history, pd.Timestamp("2014-09-25T00:00+05:30"), {"x": weight})


def scored_fixture():
    rows = []
    for day in pd.date_range("2014-11-16", periods=2, freq="D", tz="Asia/Kolkata"):
        for model, error in [("weekly", 1), ("blend", 2)]:
            rows.append(
                pd.DataFrame(
                    {
                        "timestamp": pd.date_range(day, periods=96, freq="15min"),
                        "origin": day,
                        "model": model,
                        "split": "validation",
                        "load_kw": np.arange(1, 97),
                        "prediction_kw": np.arange(1, 97) + error,
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def test_power_energy_peak_metrics_and_validation_selection():
    summary, daily = load_error_tables(scored_fixture())
    selected = select_load_candidate(summary, {"weekly": 0, "blend": 0.5})
    assert selected == "weekly"
    weekly = summary.set_index("model").loc["weekly"]
    assert weekly.rmse_kw == weekly.mae_kw == weekly.bias_kw == 1
    assert weekly.mean_energy_error_kwh == 24
    assert weekly.mean_peak_absolute_error_kw == 1
    assert weekly.mean_peak_time_absolute_error_minutes == 0
    assert len(daily) == 4
    summary["rmse_kw"] = 1
    assert select_load_candidate(summary, {"weekly": 0, "blend": 0.5}) == "weekly"
    summary["split"] = "test"
    with pytest.raises(ValueError, match="validation"):
        select_load_candidate(summary, {"weekly": 0, "blend": 0.5})


@pytest.mark.parametrize("problem", ["missing_day", "different_truth", "duplicate"])
def test_unmatched_arms_rejected(problem):
    frame = scored_fixture()
    if problem == "missing_day":
        frame = frame.iloc[96:]
    elif problem == "different_truth":
        frame.loc[96, "load_kw"] += 1
    else:
        frame = pd.concat([frame, frame.iloc[:1]])
    with pytest.raises(ValueError):
        load_error_tables(frame)


def test_paired_block_bootstrap_preserves_matched_days():
    days = pd.date_range("2014-12-01", periods=16, freq="D", tz="UTC")
    frame = pd.DataFrame(
        [
            {"origin": day, "model": model, "mse_kw2": error, "split": "test"}
            for day in days
            for model, error in [("weekly", 9), ("blend", 4)]
        ]
    )
    result = paired_load_interval(frame, "blend", block_days=4, repetitions=100, seed=42)
    assert result["rmse_difference_kw"] == -1
    assert result["descriptive_low_95_kw"] == result["descriptive_high_95_kw"] == -1
    result = paired_load_interval(frame, "weekly", block_days=4, repetitions=100, seed=42)
    assert result["rmse_difference_kw"] == result["descriptive_low_95_kw"] == 0
    with pytest.raises(ValueError, match="matched"):
        paired_load_interval(frame.iloc[1:], "blend", block_days=4, repetitions=100, seed=42)


@pytest.mark.parametrize("problem", ["protocol", "input"])
def test_runner_refuses_changed_registration_before_creating_results(tmp_path, problem):
    config = tmp_path / "configs/india_load_forecast_v1.yaml"
    config.parent.mkdir()
    source = tmp_path / "source.csv"
    source.write_text("pinned\n")
    config.write_text(
        yaml.safe_dump(
            {"protocol_id": "test_registration", "inputs": {"source.csv": sha256_file(source)}}
        )
    )
    run_dir = tmp_path / "outputs/india_ci/test_registration"
    run_dir.mkdir(parents=True)
    sealed = run_dir / "protocol.yaml"
    sealed.write_bytes(config.read_bytes())
    (run_dir / "registration.json").write_text(json.dumps({"protocol_sha256": sha256_file(config)}))
    if problem == "protocol":
        sealed.write_text("changed\n")
    else:
        source.write_text("changed\n")
    runner = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/run_india_load_forecast.py")
    )["run"]
    with pytest.raises(ValueError, match="changed|registration"):
        runner(tmp_path)
    assert not (run_dir / "forecast").exists()
