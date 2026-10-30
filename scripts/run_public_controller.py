"""Execute the sealed public scenario; keep simulated scores separate from field validation."""

import argparse
import json
import os
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.transfer import physical_folds
from second_life_battery.models.load_forecast import seasonal_day_ahead
from second_life_battery.optimization.controller import (
    calibrate_reference_wear,
    execute_quarters,
    make_day_planner,
    point_forecast_wear,
    score_quarters,
)
from second_life_battery.utils.reproducibility import verify_artifacts


def verify_inputs(root, protocol):
    folder = root / "outputs/india_ci" / protocol["protocol_id"]
    protocol_path = root / "configs/india_public_controller_v1.yaml"
    registration = json.loads((folder / "registration.json").read_text())
    if (
        registration["protocol_sha256"] != sha256_file(protocol_path)
        or sha256_file(folder / "protocol.yaml") != registration["protocol_sha256"]
    ):
        raise ValueError("Controller protocol differs from its sealed registration")
    for relative, digest in protocol["inputs"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or sha256_file(path) != digest:
            raise ValueError(f"Controller input changed: {relative}")
    for relative in [
        "outputs/india_ci/india_load_forecast_v1/forecast/completion.json",
        "outputs/transfer/ev_to_second_life_v3/comparison/completion.json",
    ]:
        path = root / relative
        record = json.loads(path.read_text())
        verify_artifacts(path.parent, record["artifacts"])
        for name, digest in record["code"].items():
            if sha256_file(root / name) != digest:
                raise ValueError("Previously fitted model/forecast implementation changed")
    path = root / "outputs/india_ci/india_public_pv_scenario_v1/conversion/provenance.json"
    evidence = json.loads(path.read_text())
    verify_artifacts(path.parent, evidence["artifacts"])
    for name, digest in {**evidence["inputs"], **evidence["code"]}.items():
        if sha256_file(root / name) != digest:
            raise ValueError("Modeled PV derivation changed")
    if sha256_file(root / evidence["output"]) != evidence["output_sha256"]:
        raise ValueError("Modeled PV output changed")
    return {
        **protocol["inputs"],
        str(protocol_path.relative_to(root)): sha256_file(protocol_path),
        str((folder / "registration.json").relative_to(root)): sha256_file(
            folder / "registration.json"
        ),
    }


def health_cases(target, predictions, protocol):
    settings = protocol["battery"]
    nominal = settings["nominal_cell_capacity_ah"]
    rows = predictions[
        predictions.model.isin(["R1", "R2", "R5"])
        & predictions.horizon.eq(1)
        & predictions.history_fraction.eq(0.1)
    ].copy()
    records = []
    for fold in physical_folds(target):
        calibration = calibrate_reference_wear(
            target, list(fold.training), [fold.validation, fold.test], nominal
        )
        for seed in protocol["health_cases"]["seeds"]:
            selected = rows[rows.cell_id.eq(fold.test) & rows.seed.eq(seed)]
            if selected.empty:
                raise ValueError("Missing registered health case")
            origin = selected.origin_index.max()
            selected = selected[selected.origin_index.eq(origin)]
            if (
                len(selected) != 3
                or set(selected.model) != {"R1", "R2", "R5"}
                or selected.model.duplicated().any()
            ):
                raise ValueError("Health arms do not share the latest matched origin")
            first = selected.iloc[0]
            for name in ["origin_time", "origin_soh", "reference_capacity_ah"]:
                if selected[name].nunique() != 1:
                    raise ValueError("Matched health cases have different origin state")
            checkpoint = target[
                target.physical_cell_id.eq(fold.test)
                & pd.to_datetime(target.timestamp).eq(pd.Timestamp(first.origin_time))
            ]
            if len(checkpoint) != 1 or not np.allclose(
                [first.origin_soh, first.reference_capacity_ah],
                [checkpoint.soh.iloc[0], checkpoint.reference_capacity_ah.iloc[0]],
                rtol=0,
                atol=1e-8,
            ):
                raise ValueError("Selected origin differs from the observed past checkpoint")
            health = float(first.origin_soh * first.reference_capacity_ah / nominal)
            if not 0 < health <= 1:
                raise ValueError("Origin cannot define a nominal physical capacity")
            record = {
                "cell_id": fold.test,
                "seed": seed,
                "origin_index": int(origin),
                "origin_time": str(first.origin_time),
                "origin_soh": float(first.origin_soh),
                "reference_capacity_ah": float(first.reference_capacity_ah),
                "physical_health_fraction": health,
                "capacity_kwh": settings["nominal_energy_kwh"] * health,
                "training_cells": json.dumps(list(fold.training)),
                "validation_cell": fold.validation,
                "calibration": calibration,
            }
            for row in selected.itertuples():
                record[f"{row.model}_predicted_soh"] = float(row.q50)
                record[f"{row.model}_wear_per_efc"] = point_forecast_wear(
                    row.origin_soh,
                    row.q50,
                    row.reference_capacity_ah,
                    nominal,
                    calibration["expected_efc_per_checkpoint"],
                )
            records.append(record)
    cases = pd.DataFrame(records)
    if len(cases) != 18 or set(cases.cell_id) != set(protocol["health_cases"]["cells"]):
        raise ValueError("Controller requires all six cells and three registered seeds")
    return cases


def day_forecasts(profile, origin, weight):
    cutoff = profile.index + pd.Timedelta(minutes=15) <= origin
    load = seasonal_day_ahead(profile.loc[cutoff, "load_kw"], origin, {"blend50": weight})
    pv = seasonal_day_ahead(
        profile.loc[cutoff, "modeled_pv_ac_kw"], origin, {"pv_previous_day": 1.0}
    )
    if not load.timestamp.equals(pv.timestamp):
        raise ValueError("Demand and modeled PV forecasts have different clocks")
    result = load[
        [
            "origin",
            "timestamp",
            "latest_feature_interval_end",
            "lag_day_timestamp",
            "lag_week_timestamp",
            "lag_day_kw",
            "lag_week_kw",
            "prediction_kw",
        ]
    ].rename(
        columns={
            "prediction_kw": "forecast_load_kw",
            "lag_day_kw": "lag_day_load_kw",
            "lag_week_kw": "lag_week_load_kw",
        }
    )
    result["forecast_pv_kw"] = pv.prediction_kw.to_numpy()
    result["lag_day_modeled_pv_kw"] = pv.lag_day_kw.to_numpy()
    if (result.latest_feature_interval_end > origin).any():
        raise ValueError("Forecast input extends beyond the midnight cutoff")
    return result


def replay(profile, forecasts, case, policy, protocol):
    battery = protocol["battery"]
    price = protocol["economics"]["import_price_inr_per_kwh"]
    capacity = 0.0 if policy == "A_no_battery" else float(case.capacity_kwh)
    energy = capacity * battery["initial_soc"]
    reference = case.calibration["reference_wear_per_efc"]
    rate = float(getattr(case, f"{policy[2:]}_wear_per_efc")) if policy.startswith("D_") else 0.0
    optimized = policy == "C_energy" or policy.startswith("D_")
    planner = (
        make_day_planner(
            battery,
            capacity,
            rate,
            price,
            protocol["planner"]["power_regularization_inr_per_kw2_hour"],
        )
        if optimized
        else None
    )
    daily, actions, plans = [], [], []
    for origin, predicted in forecasts.groupby("origin", sort=True):
        actual = profile.reindex(pd.DatetimeIndex(predicted.timestamp))
        if len(actual) != 96 or actual[["load_kw", "modeled_pv_ac_kw"]].isna().any().any():
            raise ValueError("Replay day lacks complete realized inputs")
        if optimized:
            requested, proof = planner(predicted.forecast_load_kw, predicted.forecast_pv_kw, energy)
            planned = requested.copy()
            planned["timestamp"] = predicted.timestamp.to_numpy()
            planned["planned_origin"] = origin
            plans.append(planned)
        else:
            if policy == "B_greedy":
                charge = np.maximum(
                    actual.modeled_pv_ac_kw.to_numpy() - actual.load_kw.to_numpy(), 0
                )
                discharge = np.maximum(
                    actual.load_kw.to_numpy() - actual.modeled_pv_ac_kw.to_numpy(), 0
                )
            else:
                charge, discharge = np.zeros(96), np.zeros(96)
            requested = pd.DataFrame(
                {"requested_charge_kw": charge, "requested_discharge_kw": discharge}
            )
            proof = {"constraint_max_error": 0.0, "numerical_preference_inr": 0.0}
        schedule, residual = execute_quarters(
            actual.load_kw, actual.modeled_pv_ac_kw, requested, energy, capacity, battery
        )
        schedule["timestamp"] = predicted.timestamp.to_numpy()
        schedule["origin"] = origin
        score = score_quarters(schedule, battery, reference, price)
        date = pd.Timestamp(origin).tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
        daily.append(
            {
                "date_ist": date,
                **score,
                "realized_constraint_max_error": residual,
                "planner_constraint_max_error": proof["constraint_max_error"],
                "numerical_preference_inr": proof["numerical_preference_inr"],
            }
        )
        energy = score["final_energy_kwh"]
        actions.append(schedule)
    ledger = pd.DataFrame(daily)
    total = {
        name: float(ledger[name].sum())
        for name in [
            "grid_import_kwh",
            "grid_energy_charge_inr",
            "reference_wear_cost_inr",
            "inventory_adjustment_inr",
            "reference_score_inr",
            "internal_throughput_kwh",
            "equivalent_full_cycles",
            "curtailed_pv_kwh",
            "recourse_absolute_change_kwh",
            "numerical_preference_inr",
        ]
    }
    total.update(
        initial_energy_kwh=float(ledger.initial_energy_kwh.iloc[0]),
        final_energy_kwh=float(ledger.final_energy_kwh.iloc[-1]),
        peak_mean_grid_import_kw=float(ledger.peak_mean_grid_import_kw.max()),
        realized_constraint_max_error=float(ledger.realized_constraint_max_error.max()),
        planner_constraint_max_error=float(ledger.planner_constraint_max_error.max()),
        idle=total["internal_throughput_kwh"] <= 1e-4,
        planned_days=len(plans),
        planner_wear_per_efc=rate,
        reference_wear_per_efc=reference,
        physical_capacity_kwh=capacity,
    )
    expected_inventory = (
        -price
        * battery["round_trip_efficiency"] ** 0.5
        * (total["final_energy_kwh"] - total["initial_energy_kwh"])
    )
    if not np.isclose(expected_inventory, total["inventory_adjustment_inr"], rtol=0, atol=1e-7):
        raise ValueError("Daily inventory accounting does not telescope across the replay")
    return (
        pd.concat(actions, ignore_index=True),
        ledger,
        pd.concat(plans, ignore_index=True) if plans else pd.DataFrame(),
        total,
    )


def run(root, *, smoke):
    protocol = yaml.safe_load((root / "configs/india_public_controller_v1.yaml").read_text())
    inputs = verify_inputs(root, protocol)
    folder = root / "outputs/india_ci" / protocol["protocol_id"]
    dependencies = [
        Path(__file__).resolve(),
        *[
            root / "src/second_life_battery" / name
            for name in [
                "optimization/controller.py",
                "models/load_forecast.py",
                "data/transfer.py",
                "data/sequences.py",
                "training/cross_validation.py",
                "utils/reproducibility.py",
                "data/inventory.py",
            ]
        ],
    ]
    code = {str(path.relative_to(root)): sha256_file(path) for path in dependencies}
    runtime = {
        "python": platform.python_version(),
        "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
        "packages": {name: version(name) for name in ["numpy", "pandas", "cvxpy", "clarabel"]},
    }
    if not smoke:
        completion = json.loads((folder / "smoke/completion.json").read_text())
        if (
            completion["status"] != "smoke_passed"
            or completion["inputs"] != inputs
            or completion["code"] != code
            or completion["runtime"] != runtime
        ):
            raise ValueError("A matching completed controller smoke is required")
        verify_artifacts(folder / "smoke", completion["artifacts"])
    output = folder / ("smoke" if smoke else "comparison")
    if output.exists():
        raise FileExistsError("Preserve completed controller evidence")
    profile = pd.read_csv(root / "data/processed/india_ci/academic_load_modeled_pv_v1.csv")
    clocks = pd.DatetimeIndex(pd.to_datetime(profile.timestamp, errors="raise"))
    if (
        clocks.tz is None
        or clocks.has_duplicates
        or not clocks.is_monotonic_increasing
        or not np.all(np.diff(clocks.asi8) == pd.Timedelta(minutes=15).value)
    ):
        raise ValueError("Controller profile clocks are incomplete or ambiguous")
    profile.index = clocks.tz_convert("UTC")
    if not profile.complete.eq(True).all() or not profile.resource_resolution_minutes.eq(60).all():
        raise ValueError("Controller profile quality or hourly PV labels changed")
    target = pd.read_csv(root / "data/processed/transfer/target_checkpoints.csv")
    predictions = pd.read_csv(
        root / "outputs/transfer/ev_to_second_life_v3/comparison/predictions.csv"
    )
    cases = health_cases(target, predictions, protocol)
    selected = json.loads(
        (root / "outputs/india_ci/india_load_forecast_v1/forecast/selection.json").read_text()
    )
    if selected["selected_model"] != "blend50" or selected["day_weight"] != 0.5:
        raise ValueError("Registered demand forecast selection changed")
    origins = pd.date_range(
        protocol["period"]["start"], protocol["period"]["end_exclusive"], freq="D", inclusive="left"
    ).tz_convert("UTC")
    if len(origins) != 16:
        raise ValueError("Registered controller window changed")
    if smoke:
        cases, origins = cases.iloc[:1], origins[:1]
    forecasts = pd.concat(
        [day_forecasts(profile, origin, selected["day_weight"]) for origin in origins],
        ignore_index=True,
    )
    output.mkdir()
    forecasts.to_csv(output / "profile_forecasts.csv", index=False)
    serializable = cases.copy()
    serializable["calibration"] = serializable.calibration.map(
        lambda value: json.dumps(value, sort_keys=True)
    )
    serializable.to_csv(output / "selected_health_cases.csv", index=False)
    for path in dependencies:
        destination = output / "code_snapshot" / path.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    actions, daily, planned, summaries = [], [], [], []
    cache = {}
    optimization_days = 0
    for case in cases.itertuples(index=False):
        for policy in protocol["policies"]:
            key = (case.cell_id, policy)
            common = (
                case.capacity_kwh,
                case.origin_soh,
                case.reference_capacity_ah,
                case.calibration,
            )
            cached = policy in {"A_no_battery", "B_greedy", "C_energy"} and key in cache
            if cached:
                if cache[key][0] != common:
                    raise ValueError("Cached policy physical assumptions changed")
                result = cache[key][1]
            else:
                result = replay(profile, forecasts, case, policy, protocol)
                if policy in {"A_no_battery", "B_greedy", "C_energy"}:
                    cache[key] = (common, result)
                optimization_days += result[3]["planned_days"]
            realized, day, plan, summary = result
            identifiers = {
                "cell_id": case.cell_id,
                "seed": case.seed,
                "policy": policy,
                "path_computed_seed": protocol["health_cases"]["seeds"][0] if cached else case.seed,
                "reused_path": cached,
            }
            actions.append(realized.assign(**identifiers))
            daily.append(day.assign(**identifiers))
            if not plan.empty and not cached:
                planned.append(plan.assign(**identifiers))
            summaries.append({**identifiers, **summary})
        print(
            json.dumps({"cell_id": case.cell_id, "seed": case.seed, "all_policies_complete": True}),
            flush=True,
        )
    realized = pd.concat(actions, ignore_index=True)
    day = pd.concat(daily, ignore_index=True)
    realized.to_csv(output / "realized_actions.csv", index=False)
    day.to_csv(output / "daily_scores.csv", index=False)
    pd.DataFrame(summaries).to_csv(output / "case_scores.csv", index=False)
    pd.concat(planned, ignore_index=True).to_csv(output / "planned_actions.csv", index=False)
    expected_rows = len(cases) * len(protocol["policies"]) * len(origins) * 96
    if len(realized) != expected_rows or not np.isfinite(day.reference_score_inr).all():
        raise ValueError("Incomplete or nonfinite controller matrix")
    result = {
        "status": "smoke_passed" if smoke else "controller_matrix_complete; review_required",
        "inputs": inputs,
        "code": code,
        "runtime": runtime,
        "health_cases": len(cases),
        "days_per_case": len(origins),
        "policies": list(protocol["policies"]),
        "realized_rows": len(realized),
        "daily_rows": len(day),
        "optimized_days": optimization_days,
        "maximum_realized_constraint_error": float(day.realized_constraint_max_error.max()),
        "maximum_planner_constraint_error": float(day.planner_constraint_max_error.max()),
        "scope": "Offline modeled PV and ideal interval feedback; "
        "no bill, physical wear or field validation",
        "artifacts": {
            str(path.relative_to(output)): sha256_file(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    }
    (output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "health_cases",
                    "days_per_case",
                    "realized_rows",
                    "optimized_days",
                    "maximum_realized_constraint_error",
                    "maximum_planner_constraint_error",
                ]
            },
            indent=2,
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    run(Path(__file__).resolve().parent.parent, smoke=args.smoke)
