"""Export verified research artifacts for the client dashboard; never fit models here."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.optimization.solar_dispatch import solve_dispatch


def records(frame: pd.DataFrame) -> list[dict]:
    """Represent unavailable metrics as JSON null, not zero or invalid NaN literals."""
    return json.loads(frame.to_json(orient="records", double_precision=15))


def verify_provenance(root: Path) -> None:
    """Refuse to combine forecasts and dispatch produced from different source snapshots."""
    data_hash = sha256_file(root / "data/processed/checkpoints.csv")
    for name in ["lobo", "limited_history", "dispatch"]:
        provenance = json.loads((root / f"outputs/{name}/provenance.json").read_text())
        if provenance["checkpoint_data_sha256"] != data_hash:
            raise ValueError(f"{name} uses different checkpoint data; regenerate that experiment")
    provenance = json.loads((root / "outputs/dispatch/provenance.json").read_text())
    for key, path in {
        "forecast_predictions_sha256": "outputs/lobo/predictions.csv",
        "forecast_folds_sha256": "outputs/lobo/folds.json",
        "solar_load_sha256": "data/processed/solar_load.csv",
    }.items():
        if provenance[key] != sha256_file(root / path):
            raise ValueError(f"Dispatch provenance differs from {path}; rerun dispatch")


def dispatch_comparison(frame: pd.DataFrame, currency: str = "eur") -> dict:
    """Compare matched C and median D cases, then average across the same cells."""
    baseline = frame[frame.scenario == "C_second_life"].set_index("cell_id").sort_index()
    aware = (
        frame[(frame.scenario == "D_degradation_aware") & (frame.degradation_weight == 1)]
        .set_index("cell_id")
        .sort_index()
    )
    if (
        baseline.empty
        or not baseline.index.is_unique
        or not aware.index.is_unique
        or not baseline.index.equals(aware.index)
    ):
        raise ValueError("Dashboard requires paired C and D weight-1 results for every cell")
    if not np.allclose(
        baseline[["health_fraction", "wear_per_efc"]],
        aware[["health_fraction", "wear_per_efc"]],
        rtol=1e-8,
        atol=1e-12,
    ):
        raise ValueError("C and D must use the same health and wear assumptions")
    keys = [
        f"electricity_cost_{currency}",
        f"estimated_degradation_cost_{currency}",
        f"electricity_plus_estimated_wear_{currency}",
        "equivalent_full_cycles",
    ]
    for part in [baseline, aware]:
        if not np.isfinite(part[keys]).all().all():
            raise ValueError("Dispatch comparison contains nonfinite results")
        if not np.allclose(
            part[f"electricity_plus_estimated_wear_{currency}"],
            part[f"electricity_cost_{currency}"] + part[f"estimated_degradation_cost_{currency}"],
        ):
            raise ValueError("Reported electricity-plus-wear costs do not add up")
    return {
        "baseline": baseline[keys].mean().to_dict(),
        "aware": aware[keys].mean().to_dict(),
        "cells": baseline.index.tolist(),
    }


def india_replay(frame: pd.DataFrame, reference: pd.DataFrame, settings: dict, market: dict):
    """Rerun saved health scenarios in INR, preserving measured power and original outputs."""
    if market["currency"] != "INR":
        raise ValueError("India dashboard requires INR assumptions")
    frame = frame.copy()
    frame["import_price"] = market["import_price_inr_per_kwh"]
    frame["export_price"] = market["export_price_inr_per_kwh"]
    battery = {key: value for key, value in settings["battery"].items() if "eur" not in key}
    battery.update(currency="INR", replacement_cost_inr=market["replacement_cost_inr"])
    summaries, schedules = [], []
    for row in reference.itertuples():
        schedule, summary = solve_dispatch(
            frame,
            battery,
            row.health_fraction,
            row.wear_per_efc,
            degradation_weight=row.degradation_weight,
            no_battery=row.scenario == "A_no_battery",
        )
        summaries.append(
            {
                "cell_id": row.cell_id,
                "scenario": row.scenario,
                "degradation_weight": row.degradation_weight,
                **summary,
            }
        )
        if row.scenario in {"C_second_life", "D_degradation_aware"}:
            schedules.append(
                {"cell": row.cell_id, "weight": row.degradation_weight, "frame": schedule}
            )
    return pd.DataFrame(summaries), schedules, {**settings, "battery": battery}


def build_payload(root: Path) -> dict:
    """Keep the exported snapshot self-contained, with exact sources and model settings."""
    verify_provenance(root)
    sources = []

    def table(relative: str) -> pd.DataFrame:
        path = root / relative
        frame = pd.read_csv(path)
        if frame.empty:
            raise ValueError(f"Dashboard source is empty: {relative}")
        sources.append({"path": relative, "rows": len(frame), "sha256": sha256_file(path)})
        return frame

    def document(relative: str) -> dict | list:
        path = root / relative
        sources.append({"path": relative, "sha256": sha256_file(path)})
        return (
            yaml.safe_load(path.read_text())
            if path.suffix == ".yaml"
            else json.loads(path.read_text())
        )

    checkpoints = table("data/processed/checkpoints.csv")
    predictions = table("outputs/lobo/predictions.csv")
    forecast_config = document("outputs/lobo/config.yaml")
    dispatch_config = document("outputs/dispatch/config.yaml")
    reference = table("outputs/dispatch/summary.csv")
    dispatch_comparison(reference)
    market = document("configs/india_ci.yaml")
    dispatch, replay_schedules, dispatch_settings = india_replay(
        table("data/processed/solar_load.csv"), reference, dispatch_config["dispatch"], market
    )
    compared = dispatch_comparison(dispatch, "inr")
    if set(compared["cells"]) != set(checkpoints.cell_id):
        raise ValueError("Dispatch and battery data cover different cells")
    schedule_columns = [
        "timestamp",
        "solar_kw",
        "load_kw",
        "charge_kw",
        "discharge_kw",
        "grid_import_kw",
        "grid_export_kw",
        "energy_end_kwh",
    ]
    schedules = []
    for replay in replay_schedules:
        schedule = replay["frame"]
        schedules.append(
            {
                "cell": replay["cell"],
                "weight": replay["weight"],
                "rows": json.loads(
                    schedule[schedule_columns].to_json(orient="values", double_precision=10)
                ),
            }
        )
    payload = {
        "schema_version": 1,
        "market": market,
        "dispatch_basis": (
            "Fresh INR optimization using saved health scenarios and proxy power inputs; "
            "no FX conversion"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cells": sorted(checkpoints.cell_id.unique()),
        "counts": {
            "checkpoints": len(checkpoints),
            "forecast_predictions": len(predictions),
            "models": predictions.model.nunique(),
            "seeds": predictions.seed.nunique(),
            "dispatch_scenarios": len(dispatch),
        },
        "checkpoints": records(
            checkpoints[
                [
                    "cell_id",
                    "timestamp",
                    "capacity_ah",
                    "soh",
                    "reference_capacity_ah",
                    "elapsed_days",
                    "cumulative_ah",
                    "pulse_resistance_ohm",
                ]
            ]
        ),
        "forecast_summary": records(table("outputs/lobo/summary.csv")),
        "fold_metrics": records(table("outputs/lobo/fold_metrics.csv")),
        "predictions": records(predictions),
        "limited_history": records(table("outputs/limited_history/summary.csv")),
        "paired_comparisons": records(table("outputs/analysis/paired_cell_comparisons.csv")),
        "folds": document("outputs/lobo/folds.json"),
        "dispatch_summary": records(dispatch),
        "dispatch_comparison": compared,
        "schedules": {"columns": schedule_columns, "series": schedules},
        "selected_forecasts": records(table("outputs/dispatch/selected_forecasts.csv")),
        "wear_conversion": document("outputs/dispatch/wear_conversion.json"),
        "solar_provenance": document("data/processed/solar_provenance.json"),
        "settings": {
            "features": forecast_config["features"],
            "evaluation": forecast_config["evaluation"],
            "training": forecast_config["training"],
            "physics": forecast_config["physics"],
            "gru": forecast_config["gru"],
            "parsing": forecast_config["parsing"],
            "solar": {
                "import_price_inr_per_kwh": market["import_price_inr_per_kwh"],
                "export_price_inr_per_kwh": market["export_price_inr_per_kwh"],
                "tariff_timezone": "Asia/Kolkata",
                "tariff_type": "flat",
            },
            "dispatch": dispatch_settings,
        },
        "sources": sources,
    }
    return payload


def build_dashboard(root: Path, output: Path, *, reference_snapshot: Path | None = None) -> None:
    """Build a static dashboard usable offline or behind a private web host."""
    from second_life_battery.evaluation.research_dashboard import REPORTS, build_research_payload

    if reference_snapshot is None:
        payload = build_payload(root)
    else:
        verify_provenance(root)
        text = reference_snapshot.read_text()
        if not text.startswith("window.RECELL_DATA="):
            raise ValueError("Reference snapshot is not a ReCell data export")
        payload = json.loads(text.removeprefix("window.RECELL_DATA=").strip().removesuffix(";"))
        if payload["schema_version"] != 1 or payload["market"]["currency"] != "INR":
            raise ValueError("Expected the preserved original INR reference snapshot")
        for source in payload["sources"]:
            if sha256_file(root / source["path"]) != source["sha256"]:
                raise ValueError(f"Original dashboard input changed: {source['path']}")
    payload["reference_generated_at"] = payload["generated_at"]
    payload["extensions"] = build_research_payload(root)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["schema_version"] = 2
    content = json.dumps(payload, allow_nan=False, separators=(",", ":"))
    # Escape script terminators even when an artifact contains unexpected source text.
    content = content.replace("<", "\\u003c").replace("\u2028", "\\u2028")
    assets = ["index.html", "styles.css", "core.js", "app.js", "lessons.js", "research.js"]
    for name in assets:
        if not (root / "dashboard" / name).is_file():
            raise FileNotFoundError(f"Missing dashboard asset: {name}")
    output.mkdir(parents=True, exist_ok=True)
    for name in assets:
        shutil.copyfile(root / "dashboard" / name, output / name)
    (output / "reports").mkdir(exist_ok=True)
    for name in REPORTS.values():
        shutil.copyfile(root / "output/pdf" / name, output / "reports" / name)
    (output / "data.js").write_text(f"window.RECELL_DATA={content};\n", encoding="utf-8")
    print(f"Built dashboard: {output / 'index.html'}")
