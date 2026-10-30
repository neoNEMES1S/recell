"""Quarter-hour scenario planning and ideal interval recourse; no field aging claim."""

import cvxpy as cp
import numpy as np
import pandas as pd

from second_life_battery.data.transfer import validate_features

DT_HOURS = 0.25


def calibrate_reference_wear(target, training_cells, excluded_cells, nominal_ah):
    if (
        len(training_cells) != 4
        or len(set(training_cells)) != 4
        or set(training_cells) & set(excluded_cells)
        or not np.isfinite(nominal_ah)
        or nominal_ah <= 0
    ):
        raise ValueError("Wear calibration needs four disjoint target gradient-training cells")
    training = target[target.physical_cell_id.isin(training_cells)].copy()
    if set(training.physical_cell_id) != set(training_cells):
        raise ValueError("Wear calibration omits a declared training battery")
    validate_features(training)
    records = []
    for cell, rows in training.groupby("physical_cell_id"):
        rows = rows.sort_values("timestamp")
        efc = rows.cumulative_ah_since_stage_start.diff() / (2 * nominal_ah)
        decline = -rows.soh.diff() * rows.reference_capacity_ah / nominal_ah
        valid = efc > 1e-6 / (2 * nominal_ah)
        if not valid.any():
            raise ValueError("A training cell has no positive exposure increments")
        rates = decline[valid] / efc[valid]
        records.append(
            {
                "physical_cell_id": cell,
                "positive_exposure_intervals": int(valid.sum()),
                "zero_exposure_intervals": int(efc.iloc[1:].le(1e-6 / (2 * nominal_ah)).sum()),
                "capacity_recoveries_retained": int(decline[valid].lt(0).sum()),
                "median_efc_per_checkpoint": float(efc[valid].median()),
                "median_signed_nominal_loss_per_efc": float(rates.median()),
            }
        )
    expected = float(np.median([r["median_efc_per_checkpoint"] for r in records]))
    signed = float(np.median([r["median_signed_nominal_loss_per_efc"] for r in records]))
    return {
        "training_cells": sorted(training_cells),
        "expected_efc_per_checkpoint": expected,
        "reference_wear_per_efc": max(0.0, signed),
        "pooled_signed_rate": signed,
        "per_training_cell": records,
        "status": "mixed-aging throughput proxy; not physical wear truth",
    }


def point_forecast_wear(origin_soh, predicted_soh, reference_ah, nominal_ah, expected_efc):
    values = np.asarray(
        [origin_soh, predicted_soh, reference_ah, nominal_ah, expected_efc], dtype=float
    )
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(
            "Point wear conversion needs positive finite origin, forecast and exposure"
        )
    return max(0.0, float((origin_soh - predicted_soh) * reference_ah / nominal_ah / expected_efc))


def _physical_parameters(battery, capacity_kwh, energy_kwh):
    values = [
        battery[key]
        for key in [
            "nominal_energy_kwh",
            "power_kw",
            "round_trip_efficiency",
            "soc_min",
            "soc_max",
            "replacement_cost_inr",
            "capacity_loss_budget",
        ]
    ]
    if not np.isfinite([*values, capacity_kwh, energy_kwh]).all():
        raise ValueError("Nonfinite physical or economic scenario parameters")
    nominal, power, rte, minimum, maximum, replacement, budget = values
    if (
        nominal <= 0
        or power <= 0
        or not 0 < rte <= 1
        or not 0 <= minimum < maximum <= 1
        or not 0 <= capacity_kwh <= nominal
        or replacement < 0
        or budget <= 0
    ):
        raise ValueError("Invalid physical or economic scenario bounds")
    lower, upper = minimum * capacity_kwh, maximum * capacity_kwh
    if energy_kwh < lower - 1e-7 or energy_kwh > upper + 1e-7:
        raise ValueError("Initial internal energy violates the common physical capacity")
    return nominal, power, rte**0.5, lower, upper


def make_day_planner(battery, capacity_kwh, wear_per_efc, import_price, regularization):
    nominal, power, eta, lower, upper = _physical_parameters(
        battery, capacity_kwh, battery["initial_soc"] * capacity_kwh
    )
    if (
        capacity_kwh <= 0
        or not np.isfinite([wear_per_efc, import_price, regularization]).all()
        or min(wear_per_efc, import_price, regularization) < 0
    ):
        raise ValueError("Invalid day-planner objective parameters")
    surplus, demand = cp.Parameter(96, nonneg=True), cp.Parameter(96, nonneg=True)
    initial = cp.Parameter(nonneg=True)
    charge, discharge = cp.Variable(96, nonneg=True), cp.Variable(96, nonneg=True)
    energy = cp.Variable(97)
    internal_throughput = DT_HOURS * (eta * charge + discharge / eta)
    wear_price = (
        battery["replacement_cost_inr"]
        * wear_per_efc
        / (battery["capacity_loss_budget"] * 2 * nominal)
    )
    electricity = import_price * DT_HOURS * cp.sum(demand - discharge)
    wear = wear_price * cp.sum(internal_throughput)
    inventory = -import_price * eta * (energy[-1] - initial)
    preference = regularization * DT_HOURS * (cp.sum_squares(charge) + cp.sum_squares(discharge))
    constraints = [
        charge <= power,
        charge <= surplus,
        discharge <= power,
        discharge <= demand,
        energy[0] == initial,
        energy >= lower,
        energy <= upper,
        energy[1:] == energy[:-1] + DT_HOURS * (eta * charge - discharge / eta),
    ]
    problem = cp.Problem(cp.Minimize(electricity + wear + inventory + preference), constraints)

    def plan(load_kw, pv_kw, energy_kwh):
        _physical_parameters(battery, capacity_kwh, energy_kwh)
        load, pv = np.asarray(load_kw, dtype=float), np.asarray(pv_kw, dtype=float)
        if (
            load.shape != (96,)
            or pv.shape != (96,)
            or not np.isfinite([load, pv]).all()
            or min(load.min(), pv.min()) < 0
        ):
            raise ValueError("Day planner needs 96 nonnegative finite forecast means")
        surplus.value, demand.value = np.maximum(pv - load, 0), np.maximum(load - pv, 0)
        initial.value = energy_kwh
        problem.solve(
            solver=battery["solver"],
            warm_start=True,
            tol_gap_abs=1e-9,
            tol_gap_rel=1e-9,
            tol_feas=1e-9,
        )
        if problem.status != cp.OPTIMAL:
            raise RuntimeError(f"Quarter-hour planning failed: {problem.status}")
        residual = max(float(np.max(c.violation())) for c in constraints)
        residual = max(
            residual,
            float(np.maximum(-charge.value, 0).max()),
            float(np.maximum(-discharge.value, 0).max()),
        )
        if residual > 1e-5:
            raise RuntimeError("Planner violates physical constraints")
        commands = pd.DataFrame(
            {"requested_charge_kw": charge.value, "requested_discharge_kw": discharge.value}
        )
        return commands, {
            "solver_status": problem.status,
            "constraint_max_error": residual,
            "forecast_electricity_inr": float(electricity.value),
            "forecast_planner_wear_inr": float(wear.value),
            "forecast_inventory_adjustment_inr": float(inventory.value),
            "numerical_preference_inr": float(preference.value),
            "forecast_objective_inr": float(problem.value),
            "forecast_final_energy_kwh": float(energy.value[-1]),
        }

    return plan


def execute_quarters(load_kw, pv_kw, commands, energy_kwh, capacity_kwh, battery):
    nominal, power, eta, lower, upper = _physical_parameters(battery, capacity_kwh, energy_kwh)
    load, pv = np.asarray(load_kw, dtype=float), np.asarray(pv_kw, dtype=float)
    requested = commands[["requested_charge_kw", "requested_discharge_kw"]].to_numpy(float)
    if (
        load.ndim != 1
        or len(load) == 0
        or load.shape != pv.shape
        or requested.shape != (len(load), 2)
        or not np.isfinite(load).all()
        or not np.isfinite(pv).all()
        or not np.isfinite(requested).all()
        or min(load.min(), pv.min()) < 0
        or requested.min() < -1e-5
    ):
        raise ValueError("Invalid realized interval inputs or requested actions")
    records = []
    for demand, solar, (want_charge, want_discharge) in zip(load, pv, requested, strict=True):
        direct = min(demand, solar)
        surplus, deficit = solar - direct, demand - direct
        charge = min(
            max(want_charge, 0), power, surplus, max(upper - energy_kwh, 0) / (eta * DT_HOURS)
        )
        discharge = min(
            max(want_discharge, 0), power, deficit, max(energy_kwh - lower, 0) * eta / DT_HOURS
        )
        following = energy_kwh + DT_HOURS * (eta * charge - discharge / eta)
        records.append(
            {
                "load_kw": demand,
                "modeled_pv_kw": solar,
                "direct_pv_kw": direct,
                "requested_charge_kw": want_charge,
                "requested_discharge_kw": want_discharge,
                "charge_kw": charge,
                "discharge_kw": discharge,
                "grid_import_kw": deficit - discharge,
                "grid_export_kw": 0.0,
                "curtailed_pv_kw": surplus - charge,
                "energy_start_kwh": energy_kwh,
                "energy_end_kwh": following,
                "internal_throughput_kwh": DT_HOURS * (eta * charge + discharge / eta),
                "recourse_absolute_change_kw": abs(charge - want_charge)
                + abs(discharge - want_discharge),
            }
        )
        energy_kwh = following
    result = pd.DataFrame(records)
    residuals = [
        abs(
            result.load_kw - result.direct_pv_kw - result.grid_import_kw - result.discharge_kw
        ).max(),
        abs(
            result.modeled_pv_kw - result.direct_pv_kw - result.charge_kw - result.curtailed_pv_kw
        ).max(),
        abs(
            result.energy_end_kwh
            - result.energy_start_kwh
            - DT_HOURS * (eta * result.charge_kw - result.discharge_kw / eta)
        ).max(),
        max(0.0, lower - result.energy_end_kwh.min(), result.energy_end_kwh.max() - upper),
        max(0.0, -result.grid_import_kw.min(), -result.curtailed_pv_kw.min()),
        float((result.charge_kw * result.discharge_kw).max()),
    ]
    if max(residuals) > 1e-7:
        raise RuntimeError("Realized recourse violates balance, SOC or non-simultaneity")
    return result, float(max(residuals))


def score_quarters(schedule, battery, reference_wear, import_price):
    required = [
        "internal_throughput_kwh",
        "grid_import_kw",
        "energy_start_kwh",
        "energy_end_kwh",
        "curtailed_pv_kw",
        "recourse_absolute_change_kw",
    ]
    if (
        schedule.empty
        or not set(required).issubset(schedule)
        or not np.isfinite(schedule[required].to_numpy(float)).all()
        or (schedule[required] < -1e-7).any().any()
    ):
        raise ValueError("Reference score requires a complete finite physical ledger")
    parameters = [
        battery[key]
        for key in [
            "nominal_energy_kwh",
            "round_trip_efficiency",
            "replacement_cost_inr",
            "capacity_loss_budget",
        ]
    ]
    if (
        not np.isfinite(parameters).all()
        or parameters[0] <= 0
        or not 0 < parameters[1] <= 1
        or parameters[2] < 0
        or parameters[3] <= 0
    ):
        raise ValueError("Invalid reference-score battery parameters")
    if (
        not np.isfinite([reference_wear, import_price]).all()
        or min(reference_wear, import_price) < 0
    ):
        raise ValueError("Reference score coefficients must be finite and nonnegative")
    throughput = float(schedule.internal_throughput_kwh.sum())
    efc = throughput / (2 * battery["nominal_energy_kwh"])
    energy_change = float(schedule.energy_end_kwh.iloc[-1] - schedule.energy_start_kwh.iloc[0])
    electricity = float(schedule.grid_import_kw.sum() * DT_HOURS * import_price)
    wear = battery["replacement_cost_inr"] * reference_wear * efc / battery["capacity_loss_budget"]
    inventory = -import_price * battery["round_trip_efficiency"] ** 0.5 * energy_change
    return {
        "grid_import_kwh": float(schedule.grid_import_kw.sum() * DT_HOURS),
        "grid_energy_charge_inr": electricity,
        "reference_wear_cost_inr": wear,
        "inventory_adjustment_inr": inventory,
        "reference_score_inr": electricity + wear + inventory,
        "internal_throughput_kwh": throughput,
        "equivalent_full_cycles": efc,
        "curtailed_pv_kwh": float(schedule.curtailed_pv_kw.sum() * DT_HOURS),
        "final_energy_kwh": float(schedule.energy_end_kwh.iloc[-1]),
        "initial_energy_kwh": float(schedule.energy_start_kwh.iloc[0]),
        "peak_mean_grid_import_kw": float(schedule.grid_import_kw.max()),
        "recourse_absolute_change_kwh": float(
            schedule.recourse_absolute_change_kw.sum() * DT_HOURS
        ),
    }
