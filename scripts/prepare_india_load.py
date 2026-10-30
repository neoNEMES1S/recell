"""Prepare a separately registered Indian load benchmark; do not run or publish dispatch."""

import json
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.india_load import aggregate_iblend
from second_life_battery.data.inventory import sha256_file


def prepare(root: Path) -> dict:
    audit = root / "outputs/india_ci/source_audit"
    raw = root / "data/raw/india_iblend"
    receipt_path = audit / "iblend_selected_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] != "selected_members_verified; semantic_audit_pending":
        raise ValueError("Selected I-BLEND acquisition has not completed")
    if receipt["metadata_sha256"] != sha256_file(audit / "iblend_metadata.json"):
        raise ValueError("Pinned I-BLEND release metadata changed")
    if receipt["directory_sha256"] != sha256_file(audit / "iblend_remote_directory.json"):
        raise ValueError("Pinned I-BLEND archive directory changed")
    inputs = {}
    for name in ["Readme.txt", "acad_build_mains.csv", "data_present_status_buildings.csv"]:
        row = next(r for r in receipt["members"] if r["member"] == f"energy_dataset/{name}")
        path = raw / name
        if row["sha256"] != sha256_file(path):
            raise ValueError(f"Selected I-BLEND member changed: {name}")
        inputs[str(path.relative_to(root))] = row["sha256"]
    config_path = root / "configs/india_public_data_v1.yaml"
    config = yaml.safe_load(config_path.read_text())
    if config["interval_minutes"] != 15 or config["timezone"] != "Asia/Kolkata":
        raise ValueError("Registered load aggregation contract differs")
    meter = pd.read_csv(raw / "acad_build_mains.csv", usecols=["timestamp", "power"])
    flags = pd.read_csv(
        raw / "data_present_status_buildings.csv", usecols=["timestamp", "Academic"]
    )
    frame, quality = aggregate_iblend(meter, flags)
    start, end = [pd.Timestamp(config[key]).tz_convert("UTC") for key in ["start", "end_exclusive"]]
    selected = frame[frame.timestamp.ge(start) & frame.timestamp.lt(end)].copy()
    expected = pd.date_range(start, end, freq="15min", inclusive="left")
    if (
        not pd.DatetimeIndex(selected.timestamp).equals(expected)
        or selected.empty
        or not selected.complete.all()
        or selected.load_kw.isna().any()
    ):
        raise ValueError("Registered public-data window is incomplete; never impute to pass it")
    selected["split"] = ""
    split_counts = {}
    for name, bounds in config["splits"].items():
        first, last = [
            pd.Timestamp(bounds[k]).tz_convert("UTC") for k in ["start", "end_exclusive"]
        ]
        mask = selected.timestamp.ge(first) & selected.timestamp.lt(last)
        if selected.loc[mask, "split"].ne("").any():
            raise ValueError("Registered chronological partitions overlap")
        selected.loc[mask, "split"] = name
        split_counts[name] = int(mask.sum())
        if not split_counts[name]:
            raise ValueError("Registered chronological partition is empty")
    if selected.split.eq("").any():
        raise ValueError("Registered partitions omit benchmark rows")
    run = root / "outputs/india_ci" / config["data_protocol_id"]
    run.mkdir(parents=True, exist_ok=True)
    sealed = run / "data_protocol.yaml"
    if sealed.exists() and sealed.read_bytes() != config_path.read_bytes():
        raise ValueError("Data protocol changed after registration; use a versioned amendment")
    if not sealed.exists():
        sealed.write_bytes(config_path.read_bytes())
    output = root / "data/processed/india_ci"
    output.mkdir(parents=True, exist_ok=True)
    full_path = output / "academic_load_15min.csv"
    selected_path = output / "academic_benchmark_load_15min.csv"
    frame.to_csv(full_path, index=False)
    selected.to_csv(selected_path, index=False)
    result = {
        "status": "load_data_gate_passed; solar_tariff_controller_and_field_gates_pending",
        "data_protocol_id": config["data_protocol_id"],
        "source_doi": receipt["doi"],
        "license": receipt["license"],
        "inputs": inputs,
        "source_receipt_sha256": sha256_file(receipt_path),
        "data_protocol_sha256": sha256_file(config_path),
        "code": {
            str(p.relative_to(root)): sha256_file(p)
            for p in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/india_load.py",
            ]
        },
        "quality": quality,
        "selected_intervals": len(selected),
        "split_intervals": split_counts,
        "selected_start_utc": selected.timestamp.iloc[0].isoformat(),
        "selected_end_exclusive_utc": end.isoformat(),
        "load_energy_sample_estimate_kwh": float(selected.load_kwh.sum()),
        "selected_peak_15min_kw": float(selected.load_kw.max()),
        "outputs": {str(p.relative_to(root)): sha256_file(p) for p in [full_path, selected_path]},
        "interpretation": (
            "Institutional measured-demand benchmark; no PV, bill, battery wear "
            "or site savings validation yet"
        ),
    }
    (run / "load_provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "status",
                    "selected_intervals",
                    "split_intervals",
                    "selected_peak_15min_kw",
                ]
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parent.parent)
