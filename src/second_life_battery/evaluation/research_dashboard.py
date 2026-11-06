"""Export completed, independently reviewed extensions without fitting or optimizing."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from second_life_battery.data.inventory import sha256_file
from second_life_battery.utils.reproducibility import verify_artifacts

REPORTS = {
    "implementation": "recell_model_implementation_review.pdf",
    "transfer": "recell_transfer_v3_primary_comparison.pdf",
    "calendar": "recell_calendar_validation_review.pdf",
    "controller": "recell_public_controller_mathematical_review.pdf",
    "method": "recell_attributes_and_mathematical_model_review.pdf",
}


def verified_review(run: Path, review_path: Path) -> tuple[dict, dict]:
    """A successful fit alone is insufficient: require its matching saved review."""
    completion_path = run / "completion.json"
    complete = json.loads(completion_path.read_text())
    review = json.loads(review_path.read_text())
    verify_artifacts(run, complete["artifacts"])
    if review["completion_sha256"] != sha256_file(completion_path):
        raise ValueError("Research review does not match its completed run")
    verify_artifacts(review_path.parent, review["artifacts"])
    if "report_artifacts" in review:
        verify_artifacts(run, review["report_artifacts"])
    return complete, review


def quarter_grid(frame: pd.DataFrame) -> pd.DatetimeIndex:
    """Preserve the site's real clock; reject silent gaps, duplicates and partial days."""
    stamps = pd.DatetimeIndex(pd.to_datetime(frame.timestamp, utc=True))
    local = stamps.tz_convert("Asia/Kolkata")
    if (
        not len(stamps)
        or stamps.has_duplicates
        or not stamps.is_monotonic_increasing
        or len(stamps) % 96
        or not (stamps.to_series().diff().dropna() == pd.Timedelta(minutes=15)).all()
        or local[0].strftime("%H:%M") != "00:00"
        or local[-1].strftime("%H:%M") != "23:45"
    ):
        raise ValueError("Research chart requires complete chronological 15-minute IST days")
    return stamps


def schedule_payload(actions: pd.DataFrame, cases: pd.DataFrame, grid) -> dict:
    """Export seed 42 paths explicitly, never averages disguised as physical schedules."""
    columns = ["charge_kw", "discharge_kw", "grid_import_kw", "energy_end_kwh"]
    selected = actions[actions.seed == 42]
    capacities = cases[cases.seed == 42].set_index("cell_id").capacity_kwh
    if not capacities.index.is_unique or len(capacities) != 6:
        raise ValueError("Representative schedules need six unique capacity cases")
    series = []
    for (cell, policy), rows in selected.groupby(["cell_id", "policy"], sort=True):
        rows = rows.sort_values("timestamp")
        if not quarter_grid(rows).equals(grid):
            raise ValueError("Controller schedule and shared site clock differ")
        if not np.isfinite(rows[columns]).all().all():
            raise ValueError("Nonfinite schedule cannot be displayed")
        capacity = float(capacities.loc[cell])
        if capacity <= 0 or (rows.energy_end_kwh < -1e-7).any():
            raise ValueError("Invalid energy/capacity in representative schedule")
        series.append(
            {
                "cell_id": cell,
                "policy": policy,
                "seed": 42,
                "capacity_kwh": capacity,
                "rows": rows[columns].round(9).to_numpy().tolist(),
            }
        )
    if len(series) != 36 or selected.groupby(["cell_id", "policy"]).ngroups != 36:
        raise ValueError("Representative schedules must cover all six policies and cells")
    return {"columns": columns, "seed": 42, "series": series}


def daily_score_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Weight cells equally and never present averaged seed IDs as a physical case."""
    metrics = [
        "grid_import_kwh",
        "grid_energy_charge_inr",
        "reference_wear_cost_inr",
        "inventory_adjustment_inr",
        "reference_score_inr",
        "internal_throughput_kwh",
        "equivalent_full_cycles",
        "curtailed_pv_kwh",
    ]
    cells = frame.groupby(["date_ist", "policy", "cell_id"], as_index=False)[metrics].mean()
    return cells.groupby(["date_ist", "policy"], as_index=False)[metrics].mean()


def build_research_payload(root: Path) -> dict:
    sources = []

    def read(relative):
        path = root / relative
        sources.append({"path": relative, "sha256": sha256_file(path)})
        return json.loads(path.read_text())

    def table(relative):
        path = root / relative
        frame = pd.read_csv(path)
        if frame.empty:
            raise ValueError(f"Empty research source: {relative}")
        sources.append({"path": relative, "sha256": sha256_file(path), "rows": len(frame)})
        return frame

    def rows(frame):
        return json.loads(frame.to_json(orient="records", double_precision=12))

    def completed(relative, review_relative):
        run, review_path = root / relative, root / review_relative
        complete, review = verified_review(run, review_path)
        for path, expected in complete["inputs"].items():
            if "/" in path and sha256_file(root / path) != expected:
                raise ValueError(f"Research input changed: {path}")
        if "protocol_sha256" in complete:
            if sha256_file(run.parent / "protocol.yaml") != complete["protocol_sha256"]:
                raise ValueError("Registered research protocol changed")
        read(f"{relative}/completion.json")
        read(review_relative)
        return complete, review

    tr = "outputs/transfer/ev_to_second_life_v3/comparison"
    transfer_complete, transfer_review = completed(tr, f"{tr}/review/verification.json")
    # Transfer manifests use semantic input names rather than relative path keys.
    for key, path in {
        "source": "data/processed/transfer/ev_to_second_life_v3/source_features.csv",
        "source_labels": "data/processed/transfer/ev_to_second_life_v3/source_labels.csv",
        "target": "data/processed/transfer/target_checkpoints.csv",
        "protocol": "configs/transfer_protocol_v3.yaml",
        "registry": "configs/cell_registry.yaml",
        "feature_gate": "outputs/transfer/ev_to_second_life_v3/feature_gate.json",
        "reference_settings": "outputs/lobo/config.yaml",
    }.items():
        if sha256_file(root / path) != transfer_complete["inputs"][key]:
            raise ValueError(f"Transfer input changed: {key}")
    transfer = {
        "summary": rows(table(f"{tr}/report/summary.csv")),
        "per_cell": rows(table(f"{tr}/report/per_cell.csv")),
        "paired": rows(table(f"{tr}/report/paired_comparisons.csv")),
        "differences": rows(table(f"{tr}/report/per_cell_differences.csv")),
        "prediction_rows": transfer_review["checked_prediction_rows"],
        "protocol": "ev_to_second_life_v3",
        "full_history_v2": "source gate failed; not fitted",
    }

    ca = "outputs/calendar/calendar_validation_v1"
    calendar_complete, calendar_review = completed(
        f"{ca}/validation", f"{ca}/analysis/provenance.json"
    )
    calendar = {
        "summary": rows(table(f"{ca}/validation/summary.csv").query("role == 'test'")),
        "types": rows(table(f"{ca}/validation/type_metrics.csv").query("role == 'test'")),
        "failures": rows(table(f"{ca}/analysis/nonphysical_predictions.csv")),
        "worst": rows(table(f"{ca}/analysis/worst_cases_by_type.csv")),
        "primary": calendar_complete["primary"],
        "nonphysical_predictions": calendar_review["nonphysical_predictions"],
        "worst_absolute_error": calendar_review["worst_absolute_error"],
        "protocol": "calendar_validation_v1",
    }

    lo = "outputs/india_ci/india_load_forecast_v1"
    forecast = read(f"{lo}/forecast/completion.json")
    verify_artifacts(root / lo / "forecast", forecast["artifacts"])
    for path, expected in forecast["inputs"].items():
        if sha256_file(root / path) != expected:
            raise ValueError(f"Demand source changed: {path}")
    if sha256_file(root / lo / "protocol.yaml") != forecast["protocol_sha256"]:
        raise ValueError("Load forecast protocol changed")
    load_review = read(f"{lo}/integrity_recheck.json")
    if load_review["completion_sha256"] != sha256_file(root / lo / "forecast/completion.json"):
        raise ValueError("Demand forecast review no longer matches its run")
    selection = read(f"{lo}/forecast/selection.json")
    if selection["test_errors_scored_at_selection"] or selection["selected_model"] != "blend50":
        raise ValueError("Frozen validation-only forecaster selection changed")

    pv = "outputs/india_ci/india_public_pv_scenario_v1"
    pv_info = read(f"{pv}/conversion/provenance.json")
    verify_artifacts(root / pv / "conversion", pv_info["artifacts"])
    for path, expected in pv_info["inputs"].items():
        if sha256_file(root / path) != expected:
            raise ValueError(f"PV conversion input changed: {path}")
    pv_review = read(f"{pv}/integrity_recheck.json")
    if not (
        pv_info["output_sha256"]
        == pv_review["data_sha256"]
        == sha256_file(root / pv_info["output"])
    ):
        raise ValueError("Modeled PV review/output mismatch")

    co = "outputs/india_ci/india_public_controller_v1/comparison"
    controller_complete, controller_review = completed(co, f"{co}/review/verification.json")
    profiles = table(f"{co}/profile_forecasts.csv").sort_values("timestamp")
    grid = quarter_grid(profiles)
    actual = table(pv_info["output"])
    actual["timestamp"] = pd.to_datetime(actual.timestamp, utc=True)
    actual = actual.set_index("timestamp").loc[grid]
    profiles["date_ist"] = grid.tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
    local = grid.tz_convert("Asia/Kolkata")
    profiles["hour_ist"] = local.hour + local.minute / 60
    profiles["load_kw"] = actual.load_kw.to_numpy()
    profiles["modeled_pv_kw"] = actual.modeled_pv_ac_kw.to_numpy()
    profile_columns = [
        "date_ist",
        "hour_ist",
        "load_kw",
        "forecast_load_kw",
        "modeled_pv_kw",
        "forecast_pv_kw",
    ]
    prediction = table(f"{lo}/forecast/test_predictions.csv")
    load_predictions = {}
    for model, part in prediction.groupby("model"):
        part = part.sort_values("timestamp")
        if not quarter_grid(part).equals(grid):
            raise ValueError("Load-forecast and controller chart clocks differ")
        if not np.allclose(part.load_kw, profiles.load_kw, rtol=0, atol=1e-9):
            raise ValueError("Load studies have different measured targets")
        load_predictions[model] = part.prediction_kw.round(9).tolist()
    load_daily = table(f"{lo}/forecast/test_daily.csv")
    load_daily["date_ist"] = (
        pd.to_datetime(load_daily.origin, utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.strftime("%Y-%m-%d")
    )
    india = {
        "validation": rows(table(f"{lo}/forecast/validation_summary.csv")),
        "test": rows(table(f"{lo}/forecast/test_summary.csv")),
        "daily": rows(load_daily),
        "selection": selection,
        "paired": read(f"{lo}/forecast/paired_comparison.json"),
        "profiles": rows(profiles[profile_columns]),
        "predictions": load_predictions,
        "pv_daily": rows(table(f"{pv}/conversion/modeled_daily_totals.csv")),
        "pv": {
            key: pv_info[key]
            for key in [
                "quarter_rows",
                "source_resolution_minutes",
                "modeled_pv_total_ac_kwh",
                "modeled_pv_peak_ac_kw",
                "modeled_AC_clipped_quarters",
                "model",
                "limitations",
            ]
        },
        "load_protocol": "india_load_forecast_v1",
        "pv_protocol": "india_public_pv_scenario_v1",
    }
    cases = table(f"{co}/selected_health_cases.csv")
    schedules = schedule_payload(table(f"{co}/realized_actions.csv"), cases, grid)
    daily = table(f"{co}/daily_scores.csv")
    daily = daily_score_summary(daily)
    controller = {
        "summary": rows(table(f"{co}/review/policy_summary.csv")),
        "per_cell": rows(table(f"{co}/review/per_cell_summary.csv")),
        "differences": rows(table(f"{co}/review/per_cell_differences.csv")),
        "paired": rows(table(f"{co}/review/paired_comparisons.csv")),
        "sensitivities": rows(table(f"{co}/review/fixed_score_sensitivities.csv")),
        "daily": rows(daily),
        "schedules": schedules,
        "primary": controller_review["primary"],
        "forecast_metrics": controller_review["forecast_metrics"],
        "realized_rows": controller_complete["realized_rows"],
        "protocol": "india_public_controller_v1",
    }
    for name in REPORTS.values():
        path = root / "output/pdf" / name
        sources.append({"path": f"output/pdf/{name}", "sha256": sha256_file(path)})
    return {
        "transfer": transfer,
        "calendar": calendar,
        "india": india,
        "controller": controller,
        "reports": {key: f"reports/{name}" for key, name in REPORTS.items()},
        "sources": sources,
        "status": (
            "completed research comparisons; no operational model promotion or field validation"
        ),
    }
