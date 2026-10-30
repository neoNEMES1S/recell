"""Verify quarter-hour accounting, actual-state recourse and held-out wear calibration."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from second_life_battery.optimization.controller import (
    calibrate_reference_wear,
    execute_quarters,
    make_day_planner,
    point_forecast_wear,
    score_quarters,
)


def battery():
    return {
        "nominal_energy_kwh": 10.0,
        "power_kw": 4.0,
        "round_trip_efficiency": 0.81,
        "soc_min": 0.1,
        "soc_max": 0.9,
        "initial_soc": 0.5,
        "replacement_cost_inr": 100000.0,
        "capacity_loss_budget": 0.2,
        "solver": "CLARABEL",
    }


def commands(n, charge=10.0, discharge=10.0):
    return pd.DataFrame(
        {"requested_charge_kw": [charge] * n, "requested_discharge_kw": [discharge] * n}
    )


def training_table():
    rows = []
    for cell in [f"p{i}" for i in range(1, 7)]:
        for i, soh in enumerate([1.0, 0.99, 1.0, 0.985]):
            rows.append(
                dict(
                    physical_cell_id=cell,
                    cell_id=cell,
                    life_stage="second_life",
                    timestamp=(pd.Timestamp("2020-01-01") + pd.Timedelta(days=i * 10)).isoformat(),
                    capacity_ah=4.85 * soh,
                    reference_capacity_ah=4.85,
                    soh=soh,
                    elapsed_days=float(i * 10),
                    cumulative_ah_since_stage_start=i * 48.5,
                )
            )
    return pd.DataFrame(rows)


def test_energy_conversion_actuator_limits_and_realized_balance():
    schedule, residual = execute_quarters(
        [0, 0, 5, 5], [8, 8, 0, 0], commands(4), 4.0, 8.0, battery()
    )
    np.testing.assert_allclose(schedule.charge_kw, [4, 4, 0, 0])
    np.testing.assert_allclose(schedule.discharge_kw, [0, 0, 4, 4])
    assert residual < 1e-12
    score = score_quarters(schedule, battery(), 0.0, 10.0)
    assert score["grid_import_kwh"] == pytest.approx(0.5)
    assert score["final_energy_kwh"] == pytest.approx(4 + 2 * 0.9 - 2 / 0.9)
    assert score["reference_score_inr"] == pytest.approx(8.8)


def test_terminal_inventory_prevents_free_initial_energy_savings():
    loaded, _ = execute_quarters(np.ones(4), np.zeros(4), commands(4), 4.0, 8.0, battery())
    absent, _ = execute_quarters(np.ones(4), np.zeros(4), commands(4), 0.0, 0.0, battery())
    first = score_quarters(loaded, battery(), 0.0, 10.0)
    second = score_quarters(absent, battery(), 0.0, 10.0)
    assert first["grid_energy_charge_inr"] == 0
    assert first["reference_score_inr"] == pytest.approx(second["reference_score_inr"])


def test_score_cannot_silently_skip_a_missing_grid_reading():
    schedule, _ = execute_quarters(np.ones(4), np.zeros(4), commands(4), 0.0, 0.0, battery())
    schedule.loc[1, "grid_import_kw"] = np.nan
    with pytest.raises(ValueError, match="finite physical ledger"):
        score_quarters(schedule, battery(), 0.0, 10.0)


def test_realized_soc_continues_and_future_disturbances_cannot_change_prefix():
    first, _ = execute_quarters([0, 0], [8, 8], commands(2), 4.0, 8.0, battery())
    second, _ = execute_quarters(
        [5, 5], [0, 0], commands(2), first.energy_end_kwh.iloc[-1], 8.0, battery()
    )
    combined, _ = execute_quarters([0, 0, 5, 5], [8, 8, 0, 0], commands(4), 4.0, 8.0, battery())
    assert_frame_equal(pd.concat([first, second], ignore_index=True), combined)
    changed, _ = execute_quarters([0, 0, 5, 20], [8, 8, 0, 0], commands(4), 4.0, 8.0, battery())
    assert_frame_equal(combined.iloc[:3], changed.iloc[:3])


def test_forecast_plan_remains_safe_when_realized_pv_disappears():
    settings = battery()
    planner = make_day_planner(settings, 8.0, 0.0, 10.0, 1e-6)
    load = np.full(96, 2.0)
    pv = np.zeros(96)
    pv[28:64] = 8
    planned, proof = planner(load, pv, 4.0)
    assert proof["constraint_max_error"] < 1e-5
    realized, residual = execute_quarters(load, np.zeros(96), planned, 4.0, 8.0, settings)
    assert residual < 1e-7 and realized.charge_kw.sum() == 0
    assert realized.energy_end_kwh.min() >= 0.8 - 1e-7
    assert realized.energy_end_kwh.max() <= 7.2 + 1e-7
    next_plan, next_proof = planner(load, pv, float(realized.energy_end_kwh.iloc[-1]))
    assert len(next_plan) == 96 and next_proof["constraint_max_error"] < 1e-5


def test_only_four_training_cells_calibrate_and_recoveries_are_retained():
    frame = training_table()
    cells = ["p1", "p2", "p3", "p4"]
    excluded = ["p5", "p6"]
    first = calibrate_reference_wear(frame, cells, excluded, 4.85)
    assert first["expected_efc_per_checkpoint"] == pytest.approx(5.0)
    assert first["reference_wear_per_efc"] == pytest.approx(0.002)
    assert all(r["capacity_recoveries_retained"] == 1 for r in first["per_training_cell"])
    frame.loc[frame.physical_cell_id.isin(excluded), "capacity_ah"] = 1000
    assert calibrate_reference_wear(frame, cells, excluded, 4.85) == first
    with pytest.raises(ValueError):
        calibrate_reference_wear(frame, cells, ["p4", "p6"], 4.85)
    assert point_forecast_wear(1.0, 0.98, 4.85, 4.85, 5.0) == pytest.approx(0.004)
    assert point_forecast_wear(1.0, 1.01, 4.85, 4.85, 5.0) == 0


@pytest.mark.parametrize("defect", ["efficiency", "initial_energy", "missing", "negative_load"])
def test_invalid_physical_inputs_are_rejected(defect):
    settings = deepcopy(battery())
    load = np.ones(4)
    pv = np.zeros(4)
    energy = 4.0
    if defect == "efficiency":
        settings["round_trip_efficiency"] = 1.2
    elif defect == "initial_energy":
        energy = 100
    elif defect == "missing":
        load[1] = np.nan
    else:
        load[1] = -1
    with pytest.raises(ValueError):
        execute_quarters(load, pv, commands(4), energy, 8.0, settings)
