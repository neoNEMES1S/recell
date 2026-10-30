"""Planning uses completed profile history and forecast medians, never future health labels."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

spec = importlib.util.spec_from_file_location(
    "run_public_controller",
    Path(__file__).resolve().parents[1] / "scripts/run_public_controller.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_midnight_forecasts_ignore_all_future_realizations():
    index = pd.date_range("2020-01-01", periods=96 * 9, freq="15min", tz="Asia/Kolkata").tz_convert(
        "UTC"
    )
    profile = pd.DataFrame(
        {
            "load_kw": np.arange(len(index), dtype=float),
            "modeled_pv_ac_kw": np.arange(len(index), dtype=float) * 0.1,
        },
        index=index,
    )
    origin = pd.Timestamp("2020-01-08", tz="Asia/Kolkata").tz_convert("UTC")
    first = module.day_forecasts(profile, origin, 0.5)
    assert len(first) == 96 and first.latest_feature_interval_end.max() == origin
    assert first.forecast_load_kw.iloc[0] == 288.0
    assert first.forecast_pv_kw.iloc[0] == 57.6
    profile.loc[profile.index >= origin, ["load_kw", "modeled_pv_ac_kw"]] = 1e6
    assert_frame_equal(first, module.day_forecasts(profile, origin, 0.5))


def test_future_health_labels_cannot_enter_case_selection_or_calibration():
    target = []
    predictions = []
    cells = [f"p{i}" for i in range(1, 7)]
    for cell in cells:
        for i in range(6):
            time = (pd.Timestamp("2020-01-01") + pd.Timedelta(days=i * 10)).isoformat()
            target.append(
                dict(
                    cell_id=cell,
                    physical_cell_id=cell,
                    life_stage="second_life",
                    timestamp=time,
                    capacity_ah=4.85 * (1 - i * 0.01),
                    reference_capacity_ah=4.85,
                    soh=1 - i * 0.01,
                    elapsed_days=float(i * 10),
                    cumulative_ah_since_stage_start=i * 48.5,
                )
            )
        for seed in [42, 43, 44]:
            for arm in ["R1", "R2", "R5"]:
                predictions.append(
                    dict(
                        cell_id=cell,
                        seed=seed,
                        model=arm,
                        horizon=1,
                        history_fraction=0.1,
                        origin_index=3,
                        origin_time="2020-01-31T00:00:00",
                        origin_soh=0.97,
                        reference_capacity_ah=4.85,
                        q50=0.965,
                        y_true=0.96,
                    )
                )
    protocol = {
        "battery": {"nominal_energy_kwh": 40.0, "nominal_cell_capacity_ah": 4.85},
        "health_cases": {"cells": cells, "seeds": [42, 43, 44]},
    }
    frame = pd.DataFrame(predictions)
    data = pd.DataFrame(target)
    first = module.health_cases(data, frame, protocol)
    frame["y_true"] = -1000
    changed = module.health_cases(data, frame, protocol)
    assert_frame_equal(first, changed)
    assert len(first) == 18 and "y_true" not in first
    assert not any(name.startswith("q10") or name.startswith("q90") for name in first)
