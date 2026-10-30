"""Reproduce local first-life audit results; do not fit a model or fill missing features."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from openpyxl import load_workbook
from scipy.io import loadmat

from second_life_battery.data.ev_exposure import audit_batch
from second_life_battery.data.features import counter_throughput
from second_life_battery.data.first_life import audit_raw_capacity, reconstruct_capacities
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.parser import is_channel_sheet, read_channel


def audit(root: Path) -> dict:
    raw = root / "data/raw/stanford_ev_first_life"
    output = root / "outputs/transfer/source_audit"
    output.mkdir(parents=True, exist_ok=True)
    registry = yaml.safe_load((root / "configs/cell_registry.yaml").read_text())
    capacities = reconstruct_capacities(raw / "capacity_test.mat", registry)
    capacities.to_csv(output / "first_life_capacity_checkpoints.csv", index=False)
    availability = []
    for cell, group in capacities.groupby("cell_id"):
        n = len(group)
        availability.append(
            {
                "cell_id": cell,
                "checkpoints": n,
                "first_capacity_ah": float(group.capacity_ah.iloc[0]),
                "last_capacity_ah": float(group.capacity_ah.iloc[-1]),
                "h2_min3_origins": max(0, n - 4),
                "h1_min3_origins": max(0, n - 3),
            }
        )
    raw_audits = []
    for diagnostic in [1, 2, 11]:
        source = raw / f"G1_diag{diagnostic}.xlsx"
        if not source.exists():
            continue
        workbook = load_workbook(source, read_only=True, data_only=True)
        channels = [name for name in workbook.sheetnames if is_channel_sheet(name)]
        workbook.close()
        if len(channels) != 1:
            raise ValueError(f"Expected one reviewed Channel sheet in {source.name}")
        record = {
            "source_file": source.name,
            "sha256": sha256_file(source),
            "observation_table": channels[0],
        }
        frame = read_channel(raw, record, root / "data/interim/ev_channel")
        result = audit_raw_capacity(frame)
        result.update(
            cell_id="G1",
            diagnostic=diagnostic,
            source_file=source.name,
            source_sha256=record["sha256"],
        )
        reference = capacities.query("cell_id == 'G1' and diagnostic == @diagnostic")
        relative = (
            abs(result["capacity_ah"] - reference.capacity_ah.iloc[0])
            / reference.capacity_ah.iloc[0]
        )
        if relative > 0.01:
            raise ValueError("Raw and author-processed capacity disagree")
        result["raw_vs_processed_relative_error"] = float(relative)
        raw_audits.append(result)
    sample = None
    source = raw / "G1_cycling_1.mat"
    if source.exists():
        values = loadmat(source, squeeze_me=True)
        time = values["t_full_vec_M1_NMC25degC"]
        current = values["I_full_vec_M1_NMC25degC"]
        if not (
            len(time) == len(current) and np.isfinite(time).all() and np.isfinite(current).all()
        ):
            raise ValueError("Cycling time/current arrays are incomplete or nonfinite")
        if not (np.all(np.diff(time) > 0) and np.diff(time).max() < 5):
            raise ValueError("Cycling time is not continuous enough for current integration")
        charge = float(np.trapezoid(np.maximum(current, 0), time) / 3600)
        discharge = float(np.trapezoid(np.maximum(-current, 0), time) / 3600)
        sample = {
            "cell_id": "G1",
            "batch": 1,
            "observations": len(time),
            "relative_start_seconds": float(time[0]),
            "relative_end_seconds": float(time[-1]),
            "maximum_gap_seconds": float(np.diff(time).max()),
            "integrated_charge_ah": charge,
            "integrated_discharge_ah": discharge,
            "integrated_absolute_ah": charge + discharge,
            "legacy_counter_charge_ah": counter_throughput(values["ch_cap_full_vec_M1_NMC25degC"]),
            "legacy_counter_discharge_ah": counter_throughput(
                values["dis_cap_full_vec_M1_NMC25degC"]
            ),
            "status": "Dense-current integral; complete campaign exposure pending",
            "source_sha256": sha256_file(source),
        }
        anchor_path = raw / "G1_cycling1_first_export.xlsx"
        if anchor_path.exists():
            workbook = load_workbook(anchor_path, read_only=True, data_only=True)
            sheet = next(sheet for sheet in workbook if is_channel_sheet(sheet.title))
            rows = iter(sheet.values)
            first = dict(zip(next(rows), next(rows)))
            workbook.close()
            point = int(np.flatnonzero(time >= first["Test_Time(s)"])[0])
            if not all(
                [
                    np.isclose(time[point], first["Test_Time(s)"], atol=1e-5),
                    np.isclose(current[point], first["Current(A)"], atol=1e-5),
                    np.isclose(
                        values["V_full_vec_M1_NMC25degC"][point], first["Voltage(V)"], atol=1e-5
                    ),
                ]
            ):
                raise ValueError("Raw clock anchor does not match the processed measurements")
            origin = pd.Timestamp(first["Date_Time"]) - pd.Timedelta(seconds=first["Test_Time(s)"])
            sample.update(
                batch_start_time=(origin + pd.Timedelta(seconds=time[point])).isoformat(),
                batch_end_time=(origin + pd.Timedelta(seconds=time[-1])).isoformat(),
                clock_basis="Native export anchor + matched Test_Time; timezone unverified",
                anchor_sha256=sha256_file(anchor_path),
            )
            tails = list((raw / "tails/Cycling_1").glob("*G1_Channel_*.xlsx"))
            if len(tails) > 1:
                raise ValueError("Ambiguous G1 end export")
            if tails:
                native = audit_batch(source, anchor_path, tails[0])
                sample.update(
                    batch_start_time=native["batch_start_time"],
                    batch_end_time=native["batch_end_time"],
                    clock_basis="Native first and last exports; both processed endpoints matched",
                    native_minus_instrument_duration_seconds=(
                        native["native_minus_instrument_duration_seconds"]
                    ),
                    end_anchor_sha256=sha256_file(tails[0]),
                )
            clocks = {row["diagnostic"]: row for row in raw_audits}
            if 1 in clocks and 2 in clocks:
                if pd.Timestamp(sample["batch_start_time"]) < pd.Timestamp(
                    clocks[1]["diagnostic_end_time"]
                ) or pd.Timestamp(sample["batch_end_time"]) > pd.Timestamp(
                    clocks[2]["diagnostic_start_time"]
                ):
                    raise ValueError("Cycling exposure crosses its declared diagnostic interval")
                sample["as_of_next_diagnostic_check"] = "passed"
                interval = capacities.query("cell_id == 'G1' and diagnostic in [1, 2]").copy()
                interval["timestamp"] = [clocks[n]["diagnostic_end_time"] for n in [1, 2]]
                stamps = pd.to_datetime(interval.timestamp)
                interval["elapsed_days"] = (stamps - stamps.iloc[0]).dt.total_seconds() / 86400
                interval["cumulative_ah_since_stage_start"] = [0.0, charge + discharge]
                interval["feature_status"] = "verified_sample_interval; not_full_campaign"
                interval.to_csv(output / "g1_verified_first_interval.csv", index=False)
    sources = []
    for source in sorted(raw.iterdir()):
        if source.is_file() and source.suffix != ".part":
            sources.append(
                {
                    "path": str(source.relative_to(root)),
                    "bytes": source.stat().st_size,
                    "local_snapshot_sha256": sha256_file(source),
                    "upstream_hash_status": "Not supplied by linked Dropbox provider",
                }
            )
    summary = {
        "accepted_capacity_checkpoints": len(capacities),
        "physical_cells": len(availability),
        "capacity_availability": availability,
        "raw_capacity_audits": raw_audits,
        "cycling_sample": sample,
        "acquired_sources": sources,
        "training_gate": "not_ready",
        "protocol_amendment": (
            "v2 registers source H1/min3 and target H2/min3 before fitting; "
            "V5 then has one source-validation origin"
        ),
        "unresolved": [
            "Recover native clocks for all remaining diagnostics and batches",
            "Complete stage-relative causal exposure is not yet reconstructed",
            "Legacy resets overcount counter jitter; do not use those totals as features",
        ],
    }
    (output / "audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: summary[key]
                for key in [
                    "accepted_capacity_checkpoints",
                    "physical_cells",
                    "training_gate",
                    "unresolved",
                ]
            },
            indent=2,
        )
    )
    return summary


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
