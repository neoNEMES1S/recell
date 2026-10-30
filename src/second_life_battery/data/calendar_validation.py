"""Audit candidate calendar cohorts and type-disjoint folds before model registration."""

import numpy as np
import pandas as pd


def calendar_cohort(frame: pd.DataFrame, inventory: pd.DataFrame):
    """Retain short histories and author flags; do not approve a modelling cohort."""
    if inventory.Cell_id.isna().any() or inventory.Cell_id.duplicated().any():
        raise ValueError("Calendar inventory identities are ambiguous")
    if frame.empty or frame[["cell_id", "physical_cell_id", "timestamp"]].isna().any().any():
        raise ValueError("Calendar histories lack identities or clocks")
    if frame.groupby("physical_cell_id").cell_id.nunique().gt(1).any():
        raise ValueError("Multiple aliases share a physical calendar cell")
    records = []
    mapping = inventory.set_index("Cell_id")
    static = [
        "physical_cell_id",
        "cell_type",
        "chemistry",
        "lot",
        "storage_temperature_c",
        "storage_soc_fraction",
        "source_sha256",
    ]
    for cell, rows in frame.groupby("cell_id", sort=True):
        if cell not in mapping.index or any(
            rows[name].nunique(dropna=False) != 1 for name in static
        ):
            raise ValueError("Calendar identity or storage condition changes within a history")
        meta = mapping.loc[cell]
        ordered = rows.sort_values("timestamp")
        first = ordered.iloc[0]
        if (
            first.physical_cell_id != f"joule_calendar_{cell}"
            or first.cell_type != meta.Cell_type
            or first.chemistry != meta.Cell_chemistry
            or first.lot != meta.Lot
            or first.storage_temperature_c != float(meta.Temperature)
            or first.storage_soc_fraction != float(meta.SOC) / 100
        ):
            raise ValueError("Calendar history differs from its published inventory identity")
        times = pd.to_datetime(ordered.timestamp, errors="raise")
        age = (times - times.iloc[0]).dt.total_seconds() / 86400
        if times.duplicated().any() or not np.allclose(
            ordered.elapsed_days, age, atol=1e-6, rtol=0
        ):
            raise ValueError("Calendar history clocks are ambiguous or inconsistent")
        reference = float(first.capacity_ah)
        if (
            reference <= 0
            or (ordered.capacity_ah <= 0).any()
            or not np.isfinite(ordered[["capacity_ah", "soh"]]).all().all()
            or not np.allclose(ordered.reference_capacity_ah, reference, atol=1e-8, rtol=0)
            or not np.allclose(ordered.soh, ordered.capacity_ah / reference, atol=1e-8, rtol=0)
        ):
            raise ValueError("Calendar normalization uses an invalid or noncausal reference")
        comment = "" if pd.isna(meta.Comment) else str(meta.Comment)
        records.append(
            {
                "cell_id": cell,
                "physical_cell_id": first.physical_cell_id,
                "cell_type": first.cell_type,
                "base_type": first.cell_type.removesuffix("_v2"),
                "chemistry": first.chemistry,
                "lot": first.lot,
                "test_id": meta.Test_id,
                "storage_temperature_c": first.storage_temperature_c,
                "storage_soc_fraction": first.storage_soc_fraction,
                "checkpoints": len(rows),
                "span_days": float(age.max()),
                "has_future_observation": len(rows) >= 2 and age.max() > 0,
                "author_comment": comment,
                "author_swap_note": "swapp" in comment.lower(),
                "author_double_bag_note": "double bag" in comment.lower(),
            }
        )
    cohort = pd.DataFrame(records)
    if cohort.physical_cell_id.duplicated().any():
        raise ValueError("Calendar physical-cell identity is duplicated")
    candidates = cohort[cohort.has_future_observation]
    types = sorted(candidates.base_type.unique())
    if len(types) < 3:
        raise ValueError("Type-held-out preparation needs separate training/validation/test types")
    folds = []
    for index, test_type in enumerate(types):
        validation = types[(index + 1) % len(types)]
        training = [name for name in types if name not in {test_type, validation}]
        parts = {
            "training_cells": sorted(
                candidates[candidates.base_type.isin(training)].physical_cell_id
            ),
            "validation_cells": sorted(
                candidates[candidates.base_type.eq(validation)].physical_cell_id
            ),
            "test_cells": sorted(candidates[candidates.base_type.eq(test_type)].physical_cell_id),
        }
        if any(not cells for cells in parts.values()):
            raise ValueError("A calendar type partition lacks observable future labels")
        folds.append(
            {
                "test_type": test_type,
                "validation_type": validation,
                "training_types": training,
                **parts,
            }
        )
    return cohort, folds
