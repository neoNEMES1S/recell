"""Common transfer features require complete causal measurements and global identities."""

import numpy as np
import pandas as pd

from second_life_battery.data.sequences import fit_preprocessor, make_sequences
from second_life_battery.training.cross_validation import Fold, lobo_folds

FEATURES = ["soh", "elapsed_days", "cumulative_ah_since_stage_start"]


def validate_features(frame: pd.DataFrame) -> None:
    """Missing source clocks/exposure are audit findings, never imputed training values."""
    required = {
        "physical_cell_id",
        "cell_id",
        "life_stage",
        "timestamp",
        "capacity_ah",
        "reference_capacity_ah",
        *FEATURES,
    }
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError(
            "Transfer rows require identity, life stage, timestamp and common features"
        )
    if frame[list(required)].isna().any().any():
        raise ValueError("Transfer features or identities are incomplete; finish the source audit")
    if not np.isfinite(frame[FEATURES].to_numpy(dtype=float)).all():
        raise ValueError("Transfer features must be finite")
    capacity = frame[["capacity_ah", "reference_capacity_ah"]].to_numpy(dtype=float)
    if not np.isfinite(capacity).all() or (capacity <= 0).any():
        raise ValueError("Capacity and its observed reference must be positive and finite")
    if not np.allclose(
        frame.soh, frame.capacity_ah / frame.reference_capacity_ah, rtol=0, atol=1e-8
    ):
        raise ValueError("SOH differs from observed capacity/reference")
    if (frame.soh <= 0).any() or (frame[FEATURES[1:]] < 0).any().any():
        raise ValueError("SOH must be positive and age/exposure nonnegative")
    if not set(frame.life_stage).issubset({"first_life", "second_life"}):
        raise ValueError("Unrecognized transfer life stage")
    times = pd.to_datetime(frame.timestamp, errors="raise")
    keys = frame.assign(_time=times)
    if keys.duplicated(["physical_cell_id", "life_stage", "_time"]).any():
        raise ValueError("Duplicate physical-cell/life-stage checkpoint")
    for _, group in keys.groupby(["physical_cell_id", "life_stage"]):
        ordered = group.sort_values("_time")
        if ordered.cell_id.nunique() != 1:
            raise ValueError("Multiple source aliases describe one physical-cell life stage")
        reference = ordered.capacity_ah.iloc[0]
        if not np.allclose(ordered.reference_capacity_ah, reference, rtol=0, atol=1e-8):
            raise ValueError("Stage reference must be its first accepted capacity")
        if not np.allclose(ordered[FEATURES[1:]].iloc[0], 0, rtol=0, atol=1e-8):
            raise ValueError("Stage age and exposure must start at zero")
        age = (ordered._time - ordered._time.iloc[0]).dt.total_seconds() / 86400
        if not np.allclose(ordered.elapsed_days, age, rtol=0, atol=1e-6):
            raise ValueError("Elapsed days differ from the observed stage clocks")
        if (ordered[FEATURES[1:]].diff().iloc[1:] < -1e-8).any().any():
            raise ValueError("Elapsed age and cumulative exposure must not go backwards")


def target_features(checkpoints: pd.DataFrame, registry: dict) -> pd.DataFrame:
    """Derive the common target table without changing the original checkpoint file."""
    aliases = {}
    for cell in registry["cells"]:
        alias = cell.get("second_life_source_id")
        if alias is not None:
            if alias in aliases:
                raise ValueError("Ambiguous second-life alias in physical-cell registry")
            aliases[alias] = cell["physical_cell_id"]
    frame = checkpoints.sort_values(["cell_id", "timestamp"]).copy()
    frame["physical_cell_id"] = frame.cell_id.map(aliases)
    frame["life_stage"] = "second_life"
    frame["cumulative_ah_since_stage_start"] = frame.cumulative_ah - frame.groupby(
        "cell_id"
    ).cumulative_ah.transform("first")
    selected = [
        "physical_cell_id",
        "cell_id",
        "life_stage",
        "timestamp",
        "capacity_ah",
        "reference_capacity_ah",
        *FEATURES,
    ]
    result = frame[selected].reset_index(drop=True)
    validate_features(result)
    return result


def physical_folds(target: pd.DataFrame) -> list[Fold]:
    """Use the existing deterministic fold rule with physical identity as the split key."""
    validate_features(target)
    return lobo_folds(target.assign(cell_id=target.physical_cell_id))


def split_transfer(source: pd.DataFrame, target: pd.DataFrame, fold: Fold) -> dict:
    """Exclude every first-life test-cell row and every unregistered extra source cell."""
    validate_features(source)
    validate_features(target)
    if set(source.life_stage) != {"first_life"} or set(target.life_stage) != {"second_life"}:
        raise ValueError("Source and target life stages are inconsistent")
    if fold.test == fold.validation or set(fold.training) & {fold.test, fold.validation}:
        raise ValueError("Physical-cell fold roles overlap")
    parts = {
        "source_train": source[source.physical_cell_id.isin(fold.training)].copy(),
        "source_validation": source[source.physical_cell_id == fold.validation].copy(),
        "target_train": target[target.physical_cell_id.isin(fold.training)].copy(),
        "target_validation": target[target.physical_cell_id == fold.validation].copy(),
        "target_test": target[target.physical_cell_id == fold.test].copy(),
    }
    if any(part.empty for part in parts.values()):
        raise ValueError("Every declared transfer partition needs measured rows")
    for name in ["source_train", "target_train"]:
        if set(parts[name].physical_cell_id) != set(fold.training):
            raise ValueError("A declared training battery lacks source or target history")
    return parts


def audit_fold(source: pd.DataFrame, target: pd.DataFrame, fold: Fold, protocol: dict) -> dict:
    """Check usable histories and record domain shift using target-training scales only."""
    if protocol["features"]["primary"] != FEATURES:
        raise ValueError("Registered feature order differs from the common contract")
    parts = split_transfer(source, target, fold)
    scaler = fit_preprocessor(parts["target_train"], FEATURES)
    result = {
        "test": fold.test,
        "validation": fold.validation,
        "training": list(fold.training),
        "features": FEATURES,
        "scaler_fit_physical_cells": sorted(parts["target_train"].physical_cell_id.unique()),
        "scaler_medians": scaler[0].statistics_.tolist(),
        "scaler_mean": scaler[1].mean_.tolist(),
        "scaler_scale": scaler[1].scale_.tolist(),
        "partitions": {},
    }
    minimum = parts["target_train"][FEATURES].min().to_numpy()
    maximum = parts["target_train"][FEATURES].max().to_numpy()
    for name, rows in parts.items():
        domain = protocol["source" if name.startswith("source") else "target"]
        histories = rows.assign(cell_id=rows.physical_cell_id)
        samples = make_sequences(
            histories, FEATURES, domain["horizon"], min_history=domain["minimum_history"]
        )
        counts = {
            cell: sum(sample.cell_id == cell for sample in samples)
            for cell in sorted(rows.physical_cell_id.unique())
        }
        if any(count == 0 for count in counts.values()):
            raise ValueError(f"A declared {name} battery has no usable forecast origin")
        baseline_origins = [(s.cell_id, s.origin_time, s.target_times) for s in samples]
        if name == "target_test":
            for fraction in protocol["target"]["inference_context_fractions"]:
                reduced = make_sequences(
                    histories, FEATURES, domain["horizon"], fraction, domain["minimum_history"]
                )
                if [
                    (s.cell_id, s.origin_time, s.target_times) for s in reduced
                ] != baseline_origins:
                    raise ValueError("Context fractions change the held-out forecast origins")
        gaps = []
        exposure_lookup = {
            (row.cell_id, str(row.timestamp)): row.cumulative_ah_since_stage_start
            for row in histories.itertuples()
        }
        for sample in samples:
            for horizon, target_time in enumerate(sample.target_times, 1):
                days = (
                    pd.Timestamp(target_time) - pd.Timestamp(sample.origin_time)
                ).total_seconds() / 86400
                if days <= 0:
                    raise ValueError("Forecast labels must strictly follow their origin")
                ah = (
                    exposure_lookup[(sample.cell_id, target_time)]
                    - exposure_lookup[(sample.cell_id, sample.origin_time)]
                )
                if ah < 0:
                    raise ValueError("Forecast exposure must not precede its origin")
                gaps.append({"horizon": horizon, "days": days, "ah": ah})
        spacing = pd.DataFrame(gaps).groupby("horizon").days.agg(["min", "median", "max"])
        values = rows[FEATURES].to_numpy(dtype=float)
        result["partitions"][name] = {
            "checkpoint_rows": len(rows),
            "origins_by_cell": counts,
            "feature_min": values.min(axis=0).tolist(),
            "feature_max": values.max(axis=0).tolist(),
            "outside_target_training_range_rows_by_feature": (
                (values < minimum) | (values > maximum)
            )
            .sum(axis=0)
            .tolist(),
            "max_abs_standardized_by_feature": np.abs(scaler.transform(values))
            .max(axis=0)
            .tolist(),
            "forecast_spacing_days": spacing.to_dict(orient="index"),
            "forecast_spacing_ah": pd.DataFrame(gaps)
            .groupby("horizon")
            .ah.agg(["min", "median", "max"])
            .to_dict(orient="index"),
        }
    return result
