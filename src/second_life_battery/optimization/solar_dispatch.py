"""PV-only storage dispatch with exact hourly balance and a declared linear wear proxy."""

import cvxpy as cp
import numpy as np
import pandas as pd

from second_life_battery.optimization.inputs import validate_dispatch_input


def solve_dispatch(
    frame: pd.DataFrame,
    battery: dict,
    health_fraction: float,
    wear_per_efc: float,
    degradation_weight: float = 0,
    no_battery: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Optimize one horizon; only solar surplus charges storage and discharge serves load."""
    validate_dispatch_input(frame)
    n = len(frame)
    nominal = battery["nominal_energy_kwh"]
    power = battery["power_kw"]
    numeric = [
        battery[key]
        for key in [
            "nominal_energy_kwh",
            "power_kw",
            "round_trip_efficiency",
            "soc_min",
            "soc_max",
            "initial_soc",
            "capacity_loss_budget",
            "replacement_cost_eur",
        ]
    ] + [
        health_fraction,
        wear_per_efc,
        degradation_weight,
        battery.get("carbon_price_eur_per_kg", 0),
    ]
    if not np.isfinite(numeric).all() or battery["round_trip_efficiency"] <= 0:
        raise ValueError(
            "Battery and degradation parameters must be finite and efficiency positive"
        )
    efficiency = battery["round_trip_efficiency"] ** 0.5
    lower, upper = battery["soc_min"], battery["soc_max"]
    initial = battery["initial_soc"]
    if not (
        nominal > 0
        and power > 0
        and 0 < efficiency <= 1
        and 0 < health_fraction <= 1
        and 0 <= lower <= initial <= upper <= 1
    ):
        raise ValueError("Invalid energy, power, efficiency, health or SOC bounds")
    if (
        wear_per_efc < 0
        or degradation_weight < 0
        or battery["capacity_loss_budget"] <= 0
        or battery["replacement_cost_eur"] < 0
        or battery.get("carbon_price_eur_per_kg", 0) < 0
    ):
        raise ValueError("Degradation parameters must be nonnegative with a positive loss budget")
    direct = np.minimum(frame.solar_kw, frame.load_kw).to_numpy()
    surplus = frame.solar_kw.to_numpy() - direct
    demand = frame.load_kw.to_numpy() - direct
    # shortcut: fixed health per replay; add aging feedback before multi-year operation.
    capacity = 0.0 if no_battery else nominal * health_fraction
    charge, discharge = cp.Variable(n, nonneg=True), cp.Variable(n, nonneg=True)
    imported, exported, curtailed = (cp.Variable(n, nonneg=True) for _ in range(3))
    energy = cp.Variable(n + 1)
    throughput = efficiency * charge + discharge / efficiency
    efc = cp.sum(throughput) / (2 * nominal)
    wear_cost = (
        battery["replacement_cost_eur"] * wear_per_efc * efc / battery["capacity_loss_budget"]
    )
    electricity = (
        frame.import_price.to_numpy() @ imported - frame.export_price.to_numpy() @ exported
    )
    carbon_weight = battery.get("carbon_price_eur_per_kg", 0)
    if carbon_weight and "carbon_kg_per_kwh" not in frame:
        raise ValueError("Carbon penalty requested without carbon intensity data")
    carbon = frame.carbon_kg_per_kwh.to_numpy() @ imported if "carbon_kg_per_kwh" in frame else 0
    constraints = [
        charge + exported + curtailed == surplus,
        imported + discharge == demand,
        charge <= (0 if no_battery else power),
        discharge <= (0 if no_battery else power),
        energy[1:] == energy[:-1] + efficiency * charge - discharge / efficiency,
        energy >= lower * capacity,
        energy <= upper * capacity,
        energy[0] == initial * capacity,
        energy[-1] == initial * capacity,
    ]
    problem = cp.Problem(
        cp.Minimize(electricity + degradation_weight * wear_cost + carbon_weight * carbon),
        constraints,
    )
    problem.solve(solver=battery["solver"])
    if problem.status != cp.OPTIMAL:
        raise RuntimeError(f"Dispatch optimization failed: {problem.status}")
    schedule = frame.copy()
    for name, variable in [
        ("charge_kw", charge),
        ("discharge_kw", discharge),
        ("grid_import_kw", imported),
        ("grid_export_kw", exported),
        ("curtailed_kw", curtailed),
    ]:
        schedule[name] = variable.value
    schedule["energy_start_kwh"] = energy.value[:-1]
    schedule["energy_end_kwh"] = energy.value[1:]
    schedule["direct_solar_kw"] = direct
    balance_error = np.max(
        np.abs(
            energy.value[1:]
            - energy.value[:-1]
            - efficiency * charge.value
            + discharge.value / efficiency
        )
    )
    constraint_error = max(float(np.max(constraint.violation())) for constraint in constraints)
    nonnegative_error = max(
        float(np.maximum(-variable.value, 0).max())
        for variable in [charge, discharge, imported, exported, curtailed]
    )
    if max(constraint_error, nonnegative_error) > 1e-5:
        raise RuntimeError("Solver result violates dispatch constraints")
    solar_total = frame.solar_kw.sum()
    summary = {
        "electricity_cost_eur": float(electricity.value),
        "estimated_degradation_cost_eur": float(wear_cost.value),
        "electricity_plus_estimated_wear_eur": float(electricity.value + wear_cost.value),
        "objective_eur": float(problem.value),
        "grid_import_kwh": float(imported.value.sum()),
        "grid_export_kwh": float(exported.value.sum()),
        "solar_self_consumption": float((direct.sum() + charge.value.sum()) / solar_total)
        if solar_total
        else np.nan,
        "battery_throughput_kwh": float(throughput.value.sum()),
        "equivalent_full_cycles": float(efc.value),
        "estimated_nominal_capacity_loss": float(wear_per_efc * efc.value),
        "grid_carbon_kg": float(carbon.value) if "carbon_kg_per_kwh" in frame else np.nan,
        "usable_energy_capacity_kwh": capacity,
        "soc_balance_max_error_kwh": float(balance_error),
        "health_fraction": health_fraction,
        "wear_per_efc": wear_per_efc,
        "constraint_max_error": max(constraint_error, nonnegative_error),
    }
    return schedule, summary
