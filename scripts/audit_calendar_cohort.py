"""Prepare calendar identity/condition coverage and candidate type folds, without fitting."""

import json
from pathlib import Path

import pandas as pd

from second_life_battery.data.calendar_validation import calendar_cohort
from second_life_battery.data.inventory import sha256_file


def audit(root):
    folder = root / "outputs/calendar/source_audit"
    history_path = folder / "history_audit.json"
    history = json.loads(history_path.read_text())
    checkpoint_path = root / "data/processed/calendar/calendar_checkpoints.csv"
    inventory_path = root / "data/raw/stanford_calendar/Joule_cell_id.csv"
    if history["output_sha256"] != sha256_file(checkpoint_path):
        raise ValueError("Calendar checkpoints changed since the source audit")
    manifest_path = folder / "source_manifest.json"
    if history["source_manifest_sha256"] != sha256_file(manifest_path):
        raise ValueError("Calendar source manifest changed")
    for item in json.loads(manifest_path.read_text())["files"]:
        if sha256_file(root / item["path"]) != item["sha256"]:
            raise ValueError("Calendar metadata differs from pinned source")
    for name, digest in history["code"].items():
        if sha256_file(root / name) != digest:
            raise ValueError("Calendar derivation code changed")
    cohort, folds = calendar_cohort(pd.read_csv(checkpoint_path), pd.read_csv(inventory_path))
    cohort.to_csv(folder / "calendar_cohort.csv", index=False)
    (folder / "candidate_type_folds.json").write_text(json.dumps(folds, indent=2) + "\n")
    condition = cohort.groupby(["base_type", "storage_temperature_c", "storage_soc_fraction"]).agg(
        cells=("cell_id", "size"), cells_with_future=("has_future_observation", "sum")
    )
    condition.to_csv(folder / "condition_coverage.csv")
    result = {
        "status": "cohort_and_candidate_folds_audited; predictive_protocol_not_registered",
        "cells": len(cohort),
        "cells_with_future_observations": int(cohort.has_future_observation.sum()),
        "single_observation_cells": cohort[~cohort.has_future_observation].cell_id.tolist(),
        "author_swap_note_cells": cohort[cohort.author_swap_note].cell_id.tolist(),
        "author_double_bag_note_cells": cohort[cohort.author_double_bag_note].cell_id.tolist(),
        "base_types": len(folds),
        "candidate_folds": len(folds),
        "inputs": {
            str(p.relative_to(root)): sha256_file(p)
            for p in [history_path, checkpoint_path, inventory_path]
        },
        "outputs": {
            name: sha256_file(folder / name)
            for name in [
                "calendar_cohort.csv",
                "candidate_type_folds.json",
                "condition_coverage.csv",
            ]
        },
        "code": {
            str(p.relative_to(root)): sha256_file(p)
            for p in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/calendar_validation.py",
            ]
        },
        "limitations": [
            "Author-comment handling and model/temporal validation protocol "
            "require registration before fitting.",
            "Single observations do not establish zero degradation.",
            "Candidate folds group v2 lots with the base model; "
            "no M50T validation or combined wear model established.",
        ],
    }
    (folder / "cohort_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in ["status", "cells", "cells_with_future_observations", "base_types"]
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
