"""Independently check interval replay and publish the registered scenario comparison."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.utils.reproducibility import verify_artifacts


def review(root):
    config_path = root / "configs/india_public_controller_v1.yaml"
    protocol = yaml.safe_load(config_path.read_text())
    folder = root / "outputs/india_ci" / protocol["protocol_id"]
    run = folder / "comparison"
    completion_path = run / "completion.json"
    completion = json.loads(completion_path.read_text())
    if completion["status"] != "controller_matrix_complete; review_required":
        raise ValueError("Only the complete registered controller matrix may be reviewed")
    verify_artifacts(run, completion["artifacts"])
    for name, digest in {**completion["inputs"], **completion["code"]}.items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"Controller evidence changed: {name}")
    if (
        completion["health_cases"] != 18
        or completion["days_per_case"] != 16
        or completion["realized_rows"] != 165888
    ):
        raise ValueError("Controller matrix omits a registered case/day/policy")
    actions = pd.read_csv(run / "realized_actions.csv")
    daily = pd.read_csv(run / "daily_scores.csv")
    scores = pd.read_csv(run / "case_scores.csv")
    cases = pd.read_csv(run / "selected_health_cases.csv").set_index(["cell_id", "seed"])
    target = pd.read_csv(root / "data/processed/transfer/target_checkpoints.csv")
    source_predictions = pd.read_csv(
        root / "outputs/transfer/ev_to_second_life_v3/comparison/predictions.csv"
    )
    folds = {
        r["test"]: r
        for r in json.loads(
            (root / "outputs/transfer/ev_to_second_life_v3/comparison/folds.json").read_text()
        )
    }
    nominal_ah = protocol["battery"]["nominal_cell_capacity_ah"]
    for (cell, seed), case in cases.iterrows():
        fold = folds[cell]
        calibration = json.loads(case.calibration)
        if (
            set(json.loads(case.training_cells)) != set(fold["training"])
            or calibration["training_cells"] != sorted(fold["training"])
            or case.validation_cell != fold["validation"]
            or {cell, case.validation_cell} & set(fold["training"])
        ):
            raise ValueError("Actual wear calibration crossed a held-out physical identity")
        exposures, signed_rates = [], []
        for physical in fold["training"]:
            history = target[target.physical_cell_id.eq(physical)].sort_values("timestamp")
            efc = history.cumulative_ah_since_stage_start.diff() / (2 * nominal_ah)
            decline = -history.soh.diff() * history.reference_capacity_ah / nominal_ah
            valid = efc > 1e-6 / (2 * nominal_ah)
            exposures.append(float(efc[valid].median()))
            signed_rates.append(float((decline[valid] / efc[valid]).median()))
        expected = float(np.median(exposures))
        reference = max(0.0, float(np.median(signed_rates)))
        np.testing.assert_allclose(
            [calibration["expected_efc_per_checkpoint"], calibration["reference_wear_per_efc"]],
            [expected, reference],
            rtol=0,
            atol=1e-12,
        )
        selected = source_predictions[
            source_predictions.cell_id.eq(cell)
            & source_predictions.seed.eq(seed)
            & source_predictions.model.isin(["R1", "R2", "R5"])
            & source_predictions.horizon.eq(1)
            & source_predictions.history_fraction.eq(0.1)
        ]
        selected = selected[selected.origin_index.eq(selected.origin_index.max())]
        if len(selected) != 3 or not selected.origin_time.eq(case.origin_time).all():
            raise ValueError("Health cases differ from the registered latest matched origin")
        checkpoint = target[
            target.physical_cell_id.eq(cell)
            & pd.to_datetime(target.timestamp).eq(pd.Timestamp(case.origin_time))
        ]
        if len(checkpoint) != 1:
            raise ValueError("A health case has no unique observed origin checkpoint")
        np.testing.assert_allclose(
            [case.origin_soh, case.reference_capacity_ah],
            [checkpoint.soh.iloc[0], checkpoint.reference_capacity_ah.iloc[0]],
            rtol=0,
            atol=1e-8,
        )
        np.testing.assert_allclose(
            case.capacity_kwh,
            protocol["battery"]["nominal_energy_kwh"]
            * case.origin_soh
            * case.reference_capacity_ah
            / nominal_ah,
            rtol=0,
            atol=1e-10,
        )
        for row in selected.itertuples():
            rate = max(
                0.0,
                (case.origin_soh - row.q50) * case.reference_capacity_ah / nominal_ah / expected,
            )
            np.testing.assert_allclose(
                [case[f"{row.model}_predicted_soh"], case[f"{row.model}_wear_per_efc"]],
                [row.q50, rate],
                rtol=0,
                atol=1e-12,
            )
    profile = pd.read_csv(root / "data/processed/india_ci/academic_load_modeled_pv_v1.csv")
    profile.index = pd.to_datetime(profile.timestamp, utc=True)
    times = pd.to_datetime(actions.timestamp, utc=True)
    actual = profile.reindex(pd.DatetimeIndex(times))
    np.testing.assert_allclose(
        actions[["load_kw", "modeled_pv_kw"]],
        actual[["load_kw", "modeled_pv_ac_kw"]],
        rtol=0,
        atol=1e-10,
    )
    forecasts = pd.read_csv(run / "profile_forecasts.csv")
    future = pd.DatetimeIndex(pd.to_datetime(forecasts.timestamp, utc=True))
    origins = pd.to_datetime(forecasts.origin, utc=True)
    latest = pd.to_datetime(forecasts.latest_feature_interval_end, utc=True)
    if (latest > origins).any():
        raise ValueError("A controller forecast uses future input intervals")
    day = profile.reindex(future - pd.Timedelta(days=1))
    week = profile.reindex(future - pd.Timedelta(days=7))
    np.testing.assert_allclose(
        forecasts.forecast_load_kw,
        0.5 * day.load_kw.to_numpy() + 0.5 * week.load_kw.to_numpy(),
        rtol=0,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        forecasts.forecast_pv_kw, day.modeled_pv_ac_kw.to_numpy(), rtol=0, atol=1e-10
    )
    realized_at_forecast = profile.reindex(future)
    forecast_metrics = {}
    for name, predicted, truth in [
        ("load", forecasts.forecast_load_kw, realized_at_forecast.load_kw.to_numpy()),
        ("modeled_pv", forecasts.forecast_pv_kw, realized_at_forecast.modeled_pv_ac_kw.to_numpy()),
    ]:
        error = np.asarray(predicted) - truth
        forecast_metrics[name] = {
            "rmse_kw": float(np.sqrt(np.mean(error**2))),
            "mae_kw": float(np.mean(abs(error))),
            "bias_kw": float(np.mean(error)),
        }
    battery = protocol["battery"]
    eta = battery["round_trip_efficiency"] ** 0.5
    price = protocol["economics"]["import_price_inr_per_kwh"]
    dt = 0.25
    if not actions.grid_export_kw.eq(0).all():
        raise ValueError("Zero-export scenario exported power")
    keys = ["cell_id", "seed", "policy"]
    case_keys = ["cell_id", "seed"]
    recomputed = []
    residuals = []
    for identity, part in actions.groupby(keys, sort=True):
        cell, seed, policy = identity
        part = part.sort_values("timestamp")
        case = cases.loc[(cell, seed)]
        if len(part) != 1536 or len(part.timestamp.unique()) != 1536:
            raise ValueError("A policy path has missing or duplicate quarters")
        clocks = pd.DatetimeIndex(pd.to_datetime(part.timestamp, utc=True))
        if not np.all(np.diff(clocks.asi8) == pd.Timedelta(minutes=15).value):
            raise ValueError("A realized policy clock is discontinuous")
        capacity = 0.0 if policy == "A_no_battery" else float(case.capacity_kwh)
        start, end = part.energy_start_kwh.to_numpy(), part.energy_end_kwh.to_numpy()
        np.testing.assert_allclose(start[1:], end[:-1], rtol=0, atol=1e-10)
        np.testing.assert_allclose(start[0], capacity * battery["initial_soc"], rtol=0, atol=1e-10)
        direct = np.minimum(part.load_kw, part.modeled_pv_kw)
        surplus = np.maximum(part.modeled_pv_kw - part.load_kw, 0)
        deficit = np.maximum(part.load_kw - part.modeled_pv_kw, 0)
        charge = np.minimum.reduce(
            [
                np.maximum(part.requested_charge_kw, 0),
                np.full(len(part), battery["power_kw"]),
                surplus.to_numpy(),
                np.maximum(capacity * battery["soc_max"] - start, 0) / (eta * dt),
            ]
        )
        discharge = np.minimum.reduce(
            [
                np.maximum(part.requested_discharge_kw, 0),
                np.full(len(part), battery["power_kw"]),
                deficit.to_numpy(),
                np.maximum(start - capacity * battery["soc_min"], 0) * eta / dt,
            ]
        )
        for saved, expected in [
            (part.direct_pv_kw, direct),
            (part.charge_kw, charge),
            (part.discharge_kw, discharge),
            (part.grid_import_kw, deficit - discharge),
            (part.curtailed_pv_kw, surplus - charge),
            (part.internal_throughput_kwh, dt * (eta * charge + discharge / eta)),
        ]:
            np.testing.assert_allclose(saved, expected, rtol=0, atol=1e-9)
        balance = end - start - dt * (eta * charge - discharge / eta)
        residuals.append(float(abs(balance).max()))
        if (
            min(end.min(), start.min()) < capacity * battery["soc_min"] - 1e-8
            or max(end.max(), start.max()) > capacity * battery["soc_max"] + 1e-8
            or np.max(charge * discharge) > 1e-9
        ):
            raise ValueError("A realized policy violates SOC/non-simultaneity")
        calibration = json.loads(case.calibration)
        reference = calibration["reference_wear_per_efc"]
        row = pd.DataFrame(
            {
                "date_ist": clocks.tz_convert("Asia/Kolkata").strftime("%Y-%m-%d"),
                "grid_energy_charge_inr": part.grid_import_kw.to_numpy() * dt * price,
                "reference_wear_cost_inr": battery["replacement_cost_inr"]
                * reference
                * dt
                * (eta * charge + discharge / eta)
                / (2 * battery["nominal_energy_kwh"] * battery["capacity_loss_budget"]),
                "inventory_adjustment_inr": -price * eta * (end - start),
            }
        )
        grouped = row.groupby("date_ist").sum()
        reported = (
            daily[daily.cell_id.eq(cell) & daily.seed.eq(seed) & daily.policy.eq(policy)]
            .set_index("date_ist")
            .sort_index()
        )
        np.testing.assert_allclose(reported[grouped.columns], grouped, rtol=0, atol=1e-7)
        expected_score = grouped.sum().sum()
        record = scores[scores.cell_id.eq(cell) & scores.seed.eq(seed) & scores.policy.eq(policy)]
        if len(record) != 1:
            raise ValueError("Duplicate or absent case score")
        np.testing.assert_allclose(
            record.reference_score_inr.iloc[0], expected_score, rtol=0, atol=1e-7
        )
        recomputed.append(expected_score)
    if len(recomputed) != 108 or len(daily) != 1728:
        raise ValueError("Review does not cover the full fixed policy matrix")
    metrics = [
        "grid_import_kwh",
        "grid_energy_charge_inr",
        "reference_wear_cost_inr",
        "inventory_adjustment_inr",
        "reference_score_inr",
        "internal_throughput_kwh",
        "equivalent_full_cycles",
        "curtailed_pv_kwh",
        "initial_energy_kwh",
        "final_energy_kwh",
        "peak_mean_grid_import_kw",
        "recourse_absolute_change_kwh",
    ]
    per_cell = scores.groupby(["policy", "cell_id"])[metrics].mean()
    summary = per_cell.groupby("policy").mean()
    point = scores.pivot(index=case_keys, columns="policy", values="reference_score_inr")
    ordered_dates = sorted(daily.date_ist.unique())
    mean_daily = (
        daily.groupby(["policy", "date_ist", "cell_id"])
        .reference_score_inr.mean()
        .groupby(["policy", "date_ist"])
        .mean()
        .unstack("policy")
        .reindex(ordered_dates)
    )
    if len(mean_daily) != 16 or mean_daily.isna().any().any():
        raise ValueError("Paired bootstrap dates are incomplete")
    rng = np.random.default_rng(42)
    starts = rng.integers(0, 16, size=(10000, 4))
    indices = ((starts[:, :, None] + np.arange(4)) % 16).reshape(10000, 16)
    contrasts = [
        ("D_R2", "D_R1"),
        ("D_R2", "D_R5"),
        ("B_greedy", "A_no_battery"),
        ("C_energy", "A_no_battery"),
        ("D_R1", "A_no_battery"),
        ("D_R2", "A_no_battery"),
        ("D_R5", "A_no_battery"),
    ]
    pairs = []
    differences = []
    for candidate, reference in contrasts:
        change = point[candidate] - point[reference]
        by_cell = change.groupby("cell_id").mean()
        vector = (mean_daily[candidate] - mean_daily[reference]).to_numpy()
        np.testing.assert_allclose(by_cell.mean(), vector.sum(), rtol=0, atol=1e-7)
        low, high = np.quantile(vector[indices].mean(axis=1) * 16, [0.025, 0.975])
        effect = float(by_cell.mean())
        meaning = (
            "numerically indistinguishable at INR1e-5 scale"
            if abs(effect) < 1e-5
            else "inconclusive; descriptive interval includes zero"
            if low <= 0 <= high
            else "lower simulated reference score; conditional scenario only"
            if effect < 0
            else "higher simulated reference score; no benefit in this scenario"
        )
        pairs.append(
            {
                "candidate": candidate,
                "reference": reference,
                "difference_inr": effect,
                "descriptive_low_95_inr": float(low),
                "descriptive_high_95_inr": float(high),
                "interpretation": meaning,
            }
        )
        for cell, value in by_cell.items():
            differences.append(
                {
                    "candidate": candidate,
                    "reference": reference,
                    "cell_id": cell,
                    "seed_mean_difference_inr": value,
                }
            )
    sensitivities = []
    for multiplier in protocol["wear"]["score_sensitivities"]:
        adjusted = scores.assign(
            score=scores.grid_energy_charge_inr
            + scores.inventory_adjustment_inr
            + multiplier * scores.reference_wear_cost_inr
        )
        values = adjusted.groupby(["policy", "cell_id"]).score.mean().groupby("policy").mean()
        for policy, value in values.items():
            sensitivities.append(
                {
                    "reference_wear_multiplier": multiplier,
                    "policy": policy,
                    "inventory_adjusted_reference_score_inr": value,
                }
            )
    output = run / "review"
    output.mkdir(exist_ok=False)
    summary.to_csv(output / "policy_summary.csv")
    per_cell.to_csv(output / "per_cell_summary.csv")
    pd.DataFrame(pairs).to_csv(output / "paired_comparisons.csv", index=False)
    pd.DataFrame(differences).to_csv(output / "per_cell_differences.csv", index=False)
    pd.DataFrame(sensitivities).to_csv(output / "fixed_score_sensitivities.csv", index=False)
    primary = pairs[0]
    table = "\n".join(
        f"| {policy} | {r.grid_energy_charge_inr:.2f} | {r.reference_wear_cost_inr:.2f} "
        f"| {r.inventory_adjustment_inr:.2f} | {r.reference_score_inr:.2f} |"
        for policy, r in summary.iterrows()
    )
    text = (
        f"# Registered public controller scenario\n\n"
        f"Primary D_R2 minus D_R1: {primary['difference_inr']:.6f} INR per 16-day replay; "
        f"descriptive paired-day block interval [{primary['descriptive_low_95_inr']:.6f}, "
        f"{primary['descriptive_high_95_inr']:.6f}]. {primary['interpretation']}.\n\n"
        "| Policy | Energy charge | Reference wear | Inventory adjustment | Score |\n"
        "| --- | ---: | ---: | ---: | ---: |\n" + table + "\n\n"
        "Amounts are scenario INR, not observed bills or field savings. Seeds are averaged "
        "within health cases, then six cases equally. One institutional meter and 16 familiar "
        "days remain one site/window; repeated health cases are not new sites.\n\n"
        "Physical capacity is common across policies. PV is a horizontal, fixed-temperature "
        "scenario from hourly resource. Past modeled PV is a simulated zero-latency feed, "
        "not an operational NASA forecast. Realized quarter means represent ideal feedback. "
        "The mains meter is treated as hypothetical gross load; existing site PV/net-meter "
        "semantics are unverified. Unused modeled PV is curtailed; export is zero.\n\n"
        "The common wear reference uses target training cells only and remains a mixed-aging "
        "throughput proxy. No calendar model is added or physical pack aging measured. "
        "Terminal inventory uses the assumed price times discharge efficiency, "
        "not a utility payment.\n\n"
        "The planning preference is at most 0.0192 INR/day at declared limits and is excluded "
        "from the reference score. This is not an error bound on realized replay. "
        "Read daily traces, negative cases and fixed score sensitivities with small effects.\n\n"
        "No policy/model/dashboard is promoted. Measured PV, bill/category/PF semantics, "
        "pack/BMS/temperature calibration, live telemetry and supervised operation remain open.\n"
    )
    (output / "review.md").write_text(text)
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "status": "controller_replay_and_primary_review_complete; no_promotion",
        "checked_realized_rows": len(actions),
        "checked_case_scores": len(scores),
        "maximum_recomputed_energy_residual_kwh": max(residuals),
        "primary": primary,
        "forecast_metrics": forecast_metrics,
        "idle_case_policy_paths": int(scores.idle.sum()),
        "completion_sha256": sha256_file(completion_path),
        "artifacts": {path.name: sha256_file(path) for path in output.iterdir()},
    }
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "checked_realized_rows",
                    "primary",
                    "forecast_metrics",
                    "idle_case_policy_paths",
                ]
            },
            indent=2,
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    review(Path(__file__).resolve().parent.parent)
