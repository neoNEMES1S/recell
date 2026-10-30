"""Run the separately registered calendar study without modifying transfer or dispatch."""

import json
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.metrics import point_metrics
from second_life_battery.models.calendar import fit_calendar, predict_calendar


def run(root):
    config_path = root / "configs/calendar_protocol_v1.yaml"
    protocol = yaml.safe_load(config_path.read_text())
    folder = root / "outputs/calendar" / protocol["protocol_id"]
    registration = json.loads((folder / "registration.json").read_text())
    if (
        registration["protocol_sha256"] != sha256_file(config_path)
        or sha256_file(folder / "protocol.yaml") != registration["protocol_sha256"]
    ):
        raise ValueError("Calendar protocol differs from sealed registration")
    for name, digest in protocol["inputs"].items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"Registered calendar input changed: {name}")
    cohort_audit = json.loads(
        (root / "outputs/calendar/source_audit/cohort_audit.json").read_text()
    )
    for name, digest in cohort_audit["code"].items():
        if sha256_file(root / name) != digest:
            raise ValueError("Calendar cohort derivation code changed")
    source = pd.read_csv(root / "data/processed/calendar/calendar_checkpoints.csv")
    cohort = pd.read_csv(root / "outputs/calendar/source_audit/calendar_cohort.csv")
    for name, digest in cohort_audit["outputs"].items():
        if sha256_file(root / "outputs/calendar/source_audit" / name) != digest:
            raise ValueError("Audited calendar cohort/folds changed")
    folds = json.loads((root / protocol["splits"]["folds"]).read_text())
    source = source.merge(
        cohort[["physical_cell_id", "base_type", "author_swap_note", "author_double_bag_note"]],
        on="physical_cell_id",
        validate="many_to_one",
    )
    source = source.sort_values(["physical_cell_id", "elapsed_days"])
    source["observed_recovery"] = source.groupby("physical_cell_id").soh.diff().gt(0)
    output = folder / "validation"
    output.mkdir(exist_ok=False)
    code_paths = [
        Path(__file__).resolve(),
        root / "src/second_life_battery/models/calendar.py",
        root / "src/second_life_battery/evaluation/metrics.py",
        root / "src/second_life_battery/data/calendar_validation.py",
    ]
    code = {str(path.relative_to(root)): sha256_file(path) for path in code_paths}
    (output / "implementation_source.json").write_text(
        json.dumps({str(path.relative_to(root)): path.read_text() for path in code_paths}, indent=2)
        + "\n"
    )
    rows, fits, coverage, shifts = [], [], [], []
    for variant in ["primary", "exclude_author_swap_notes"]:
        data = source if variant == "primary" else source[~source.author_swap_note]
        for regime in ["full", "early180"]:
            for fold in folds:
                partitions = {
                    role: data[
                        data.physical_cell_id.isin(fold[f"{role}_cells"]) & data.elapsed_days.gt(0)
                    ].copy()
                    for role in ["training", "validation", "test"]
                }
                if regime == "early180":
                    partitions["training"] = partitions["training"][
                        partitions["training"].elapsed_days.le(180)
                    ]
                    for role in ["validation", "test"]:
                        partitions[role] = partitions[role][partitions[role].elapsed_days.gt(180)]
                identities = {
                    role: set(frame.physical_cell_id) for role, frame in partitions.items()
                }
                if any(
                    identities[a] & identities[b]
                    for a, b in [
                        ("training", "validation"),
                        ("training", "test"),
                        ("validation", "test"),
                    ]
                ):
                    raise ValueError("Calendar physical identities cross split roles")
                train = partitions["training"]
                if train.empty or not set(train.base_type).issubset(fold["training_types"]):
                    raise ValueError("Calendar training type coverage is invalid")
                models = fit_calendar(train, protocol["optimization"])
                context = {"variant": variant, "regime": regime, "test_type": fold["test_type"]}
                fits.append(
                    {
                        **context,
                        "training_cells": sorted(identities["training"]),
                        "validation_cells": sorted(identities["validation"]),
                        "test_cells": sorted(identities["test"]),
                        "models": models,
                    }
                )
                for role, frame in partitions.items():
                    coverage.append(
                        {
                            **context,
                            "role": role,
                            "cells": len(identities[role]),
                            "observations": len(frame),
                            "unavailable_cells": sorted(
                                set(fold[f"{role}_cells"]) - identities[role]
                            ),
                        }
                    )
                for role in ["validation", "test"]:
                    frame = partitions[role]
                    if frame.empty:
                        continue
                    for feature in [
                        "elapsed_days",
                        "storage_temperature_c",
                        "storage_soc_fraction",
                    ]:
                        low, high = train[feature].min(), train[feature].max()
                        shifts.append(
                            {
                                **context,
                                "role": role,
                                "feature": feature,
                                "training_min": float(low),
                                "training_max": float(high),
                                "outside_rows": int(
                                    ((frame[feature] < low) | (frame[feature] > high)).sum()
                                ),
                            }
                        )
                    for name, state in models.items():
                        prediction = predict_calendar(name, state["parameters"], frame)
                        if not np.isfinite(prediction).all():
                            raise ValueError("Calendar model produced nonfinite predictions")
                        selected = frame[
                            [
                                "physical_cell_id",
                                "base_type",
                                "diagnostic",
                                "timestamp",
                                "elapsed_days",
                                "storage_temperature_c",
                                "storage_soc_fraction",
                                "soh",
                                "author_swap_note",
                                "author_double_bag_note",
                                "observed_recovery",
                            ]
                        ].copy()
                        selected["prediction"] = prediction
                        selected["model"], selected["role"] = name, role
                        for key, value in context.items():
                            selected[key] = value
                        rows.append(selected)
                print(
                    json.dumps(
                        {
                            **context,
                            "training_cells": len(identities["training"]),
                            "test_cells": len(identities["test"]),
                        }
                    ),
                    flush=True,
                )
    predictions = pd.concat(rows, ignore_index=True)
    predictions.to_csv(output / "predictions.csv", index=False)
    (output / "fits.json").write_text(json.dumps(fits, indent=2) + "\n")
    pd.DataFrame(coverage).to_json(output / "coverage.json", orient="records", indent=2)
    pd.DataFrame(shifts).to_csv(output / "range_shifts.csv", index=False)
    metrics = []
    keys = ["variant", "regime", "role", "model", "base_type", "physical_cell_id"]
    for key, frame in predictions.groupby(keys):
        values = point_metrics(frame.soh.to_numpy(), frame.prediction.to_numpy())
        metrics.append(
            {
                **dict(zip(keys, key)),
                "observations": len(frame),
                "soh_above_one_observations": int(frame.soh.gt(1).sum()),
                "observed_recovery_observations": int(frame.observed_recovery.sum()),
                "nonphysical_predictions": int(
                    ((frame.prediction < 0) | (frame.prediction > 1)).sum()
                ),
                **values,
            }
        )
    cells = pd.DataFrame(metrics)
    cells.to_csv(output / "cell_metrics.csv", index=False)
    types = cells.groupby(keys[:-1])[["rmse", "mae", "r2"]].mean().reset_index()
    types.to_csv(output / "type_metrics.csv", index=False)
    summary = types.groupby(keys[:4])[["rmse", "mae", "r2"]].mean().reset_index()
    summary.to_csv(output / "summary.csv", index=False)
    primary = types.query("variant=='primary' and regime=='full' and role=='test'").pivot(
        index="base_type", columns="model", values="rmse"
    )
    if len(primary) != 8 or primary.isna().any().any():
        raise ValueError("Calendar primary endpoint lacks all eight held-out types")
    delta = primary.C2 - primary.C1
    settings = protocol["evaluation"]
    rng = np.random.default_rng(settings["bootstrap_seed"])
    draws = rng.choice(
        delta.to_numpy(), size=(settings["bootstrap_repetitions"], len(delta)), replace=True
    ).mean(axis=1)
    interval = np.quantile(draws, [0.025, 0.975])
    comparison = {
        "contrast": "C2 minus C1",
        "types": 8,
        "rmse_difference": float(delta.mean()),
        "bootstrap_low_95": float(interval[0]),
        "bootstrap_high_95": float(interval[1]),
        "interpretation": "inconclusive"
        if interval[0] <= 0 <= interval[1]
        else "descriptive directional difference; independent calibration required",
    }
    (output / "primary_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    note = (
        "# Separate calendar-storage validation\n\nRegistered before fitting; "
        "eight held-out base cell types. Metrics average observations within cells, "
        "then cells within types, then types equally.\n\n"
        f"Primary C2-minus-C1 SOH RMSE: {comparison['rmse_difference']:.6f}; "
        f"descriptive 95% type-bootstrap interval [{interval[0]:.6f}, {interval[1]:.6f}]. "
        f"Interpretation: {comparison['interpretation']}.\n\n"
        "See summary.csv for both regimes and the author-note sensitivity; "
        "cell_metrics.csv for nonphysical predictions and recoveries; "
        "range_shifts.csv and coverage.json for missing or shifted conditions.\n\n"
        "This fits apparent loss under storage plus periodic diagnostic cycling. "
        "Pure calendar and diagnostic losses are not separately identified. "
        "No M50T calibration, field lifetime/savings result, combined dispatch-wear "
        "term or dashboard promotion is established. The OSF node declares no "
        "license; intended redistribution/commercial use remains unresolved.\n"
    )
    (output / "review.md").write_text(note)
    result = {
        "status": "standalone_calendar_comparison_complete; application_gates_open",
        "primary": comparison,
        "protocol_sha256": registration["protocol_sha256"],
        "inputs": protocol["inputs"],
        "code": code,
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ["numpy", "pandas", "scipy"]},
        "artifacts": {
            str(path.relative_to(output)): sha256_file(path)
            for path in sorted(output.iterdir())
            if path.is_file()
        },
    }
    (output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(run(Path(__file__).resolve().parent.parent)["primary"], indent=2))
