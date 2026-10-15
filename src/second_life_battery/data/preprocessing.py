"""Prepare auditable diagnostic targets and as-of cycling features from the real manifest."""

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.features import add_soh, cycling_summary, diagnostic_summary
from second_life_battery.data.parser import merge_exports, read_channel
from second_life_battery.utils.logging import configure_logging


def _prepare_group(arguments: tuple) -> dict:
    root, cache, cell, session, kind, records, settings = arguments
    frames = [read_channel(root, record, cache) for record in records]
    try:
        frame, duplicates = merge_exports(frames)
    except ValueError as error:
        raise ValueError(f"{cell} {session}: {error}") from error
    summary = (
        diagnostic_summary(frame, settings)
        if kind == "capacity_with_pulses"
        else cycling_summary(frame)
    )
    return {
        "cell_id": cell,
        "session": session,
        "test_type": kind,
        "duplicate_rows_removed": duplicates,
        "source_files": [record["source_file"] for record in records],
        **summary,
    }


def prepare_data(config: dict, project_root: Path) -> pd.DataFrame:
    """Build targets only from accepted RPTs; no future cycling summaries enter a checkpoint."""
    output = project_root / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    log = configure_logging(output / "preparation.jsonl")
    manifest = json.loads(
        (project_root / config["inspection"]["output_dir"] / "dataset_manifest.json").read_text()
    )
    root = project_root / config["dataset"]["raw_dir"]
    groups = {}
    excluded = []
    for record in manifest["files"]:
        kind = record["test_type"]
        if kind not in {"cycling", "capacity_with_pulses"} or record["extension"] != ".xlsx":
            excluded.append(
                {
                    "source_file": record["source_file"],
                    "reason": "not a primary cycling/capacity Channel export",
                }
            )
            continue
        if not record.get("cell_id") or not record.get("observation_table"):
            excluded.append(
                {
                    "source_file": record["source_file"],
                    "reason": "ambiguous identity or absent Channel measurements",
                }
            )
            continue
        # RPT exports can overlap; cycling exports are separate tests with their own counters.
        session = (
            record["source_file"].split("/")[1]
            if kind == "capacity_with_pulses"
            else record["source_file"]
        )
        groups.setdefault((record["cell_id"], session, kind), []).append(record)
    arguments = [
        (root, project_root / "data/interim/channel", *key, records, config["parsing"])
        for key, records in sorted(groups.items())
    ]
    summaries = []
    with ProcessPoolExecutor(max_workers=config["inspection"].get("workers", 1)) as pool:
        for summary in pool.map(_prepare_group, arguments):
            summaries.append(summary)
            log.info("session_prepared: cell=%s session=%s", summary["cell_id"], summary["session"])
    pd.DataFrame(summaries).to_json(output / "session_audit.json", orient="records", indent=2)
    (output / "excluded_sources.json").write_text(json.dumps(excluded, indent=2))
    cycling = pd.DataFrame([row for row in summaries if row["test_type"] == "cycling"])
    cycling.to_csv(output / "cycling_sessions.csv", index=False)
    cycling["end_time"] = pd.to_datetime(cycling.end_time)
    targets = []
    for summary in summaries:
        if summary["test_type"] != "capacity_with_pulses":
            continue
        cell = summary["cell_id"]
        past = cycling[
            (cycling.cell_id == cell) & (cycling.end_time <= pd.Timestamp(summary["start_time"]))
        ]
        targets.append(
            {
                **{
                    key: value
                    for key, value in summary.items()
                    if key not in {"segments", "source_files", "test_type"}
                },
                "timestamp": summary["end_time"],
                "cumulative_ah": float(past.charge_ah.sum() + past.discharge_ah.sum()),
                "cumulative_wh": float(past.charge_wh.sum() + past.discharge_wh.sum()),
                "cycling_sessions": len(past),
                "duty_commercial": int(
                    config["review"]["cells"][cell]["duty_cycle_type"] == "commercial"
                ),
                "first_life_capacity_ah": config["parsing"]["first_life_capacity_ah"][cell],
            }
        )
    targets = pd.DataFrame(targets)
    targets["timestamp"] = pd.to_datetime(targets.timestamp)
    targets = add_soh(targets, config["target"]["soh_reference"])
    targets["elapsed_days"] = (
        targets.timestamp - targets.groupby("cell_id").timestamp.transform("min")
    ).dt.total_seconds() / 86400
    targets["checkpoint_index"] = targets.groupby("cell_id").cumcount()
    if targets[["cell_id", "timestamp"]].duplicated().any():
        raise ValueError("Duplicate target checkpoints")
    targets.to_csv(output / "checkpoints.csv", index=False)
    targets.isna().sum().rename("missing_values").to_csv(output / "feature_missingness.csv")
    (output / "config.snapshot.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    log.info(
        "preparation_complete: checkpoints=%s cells=%s", len(targets), targets.cell_id.nunique()
    )
    return targets
