"""Derive audited common target features without changing the historical checkpoints."""

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.transfer import FEATURES, physical_folds, target_features


def build(root: Path) -> dict:
    source = root / "data/processed/checkpoints.csv"
    registry_path = root / "configs/cell_registry.yaml"
    protocol_path = root / "configs/transfer_protocol_v2.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    protocol = yaml.safe_load(protocol_path.read_text())
    if protocol["features"]["primary"] != FEATURES:
        raise ValueError("Registered feature order differs from the implementation")
    original = pd.read_csv(source)
    if set(original.cell_id) != set(protocol["target"]["cells"]):
        raise ValueError("Target cell pool differs from the registered protocol")
    frame = target_features(original, registry)
    metadata = original[["cell_id", "timestamp", "start_time", "end_time", "session"]]
    frame = frame.merge(metadata, on=["cell_id", "timestamp"], validate="one_to_one")
    frame = frame.rename(
        columns={
            "start_time": "diagnostic_start_time",
            "end_time": "diagnostic_end_time",
        }
    )
    frame["source_dataset"] = "stanford_second_life_grid_storage"
    frame["capacity_protocol"] = "capacity_with_pulses_four_low_rate_discharges"
    frame["checkpoint_source_sha256"] = sha256_file(source)
    frame["quality_flags"] = "accepted_historical_checkpoint; target_counters_audited_separately"
    folds = physical_folds(frame)
    destination = root / "data/processed/transfer"
    destination.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination / "target_checkpoints.csv", index=False)
    (destination / "target_folds.json").write_text(
        json.dumps([asdict(fold) for fold in folds], indent=2) + "\n"
    )
    provenance = {
        "source_checkpoints_sha256": sha256_file(source),
        "registry_sha256": sha256_file(registry_path),
        "protocol_sha256": sha256_file(protocol_path),
        "target_sha256": sha256_file(destination / "target_checkpoints.csv"),
        "code_sha256": {
            str(path.relative_to(root)): sha256_file(path)
            for path in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/transfer.py",
            ]
        },
        "features": FEATURES,
        "target_rows": len(frame),
        "target_cells": frame.physical_cell_id.nunique(),
        "folds": len(folds),
        "source_training_status": (
            "Full causal source feature and fold audits required before fitting."
        ),
    }
    (destination / "target_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))
    return provenance


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent)
