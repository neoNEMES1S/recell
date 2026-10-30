"""Describe verified early histories without inventing exposure after a failed interval."""

import numpy as np
import pandas as pd

from second_life_battery.data.ev_exposure import causal_features


def verified_source_prefixes(diagnostics: pd.DataFrame, batches: pd.DataFrame):
    """Capacity labels and complete past feature prefixes are distinct audit products."""
    labels, features, availability = [], [], []
    if diagnostics.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if diagnostics.duplicated(["cell_id", "diagnostic"]).any():
        raise ValueError("Duplicate source capacity diagnostic")
    if diagnostics.groupby("physical_cell_id").cell_id.nunique().gt(1).any():
        raise ValueError("Multiple source labels alias one physical battery")
    if not batches.empty and batches.duplicated(["cell_id", "number"]).any():
        raise ValueError("Duplicate source exposure batch")
    for cell, group in diagnostics.groupby("cell_id"):
        group = group.sort_values("diagnostic").copy()
        if group.physical_cell_id.nunique() != 1:
            raise ValueError("One source cell has conflicting physical identities")
        if group.diagnostic.iloc[0] != 1:
            availability.append(
                {
                    "cell_id": cell,
                    "status": "first_reference_unavailable",
                    "feature_checkpoints": 0,
                    "potential_H1_min3_origins": 0,
                }
            )
            continue
        if not np.isfinite(group.capacity_ah).all() or group.capacity_ah.le(0).any():
            raise ValueError("Source capacity labels are not finite and positive")
        starts = pd.to_datetime(group.diagnostic_start_time, format="ISO8601", errors="raise")
        ends = pd.to_datetime(group.diagnostic_end_time, format="ISO8601", errors="raise")
        if (
            starts.isna().any()
            or ends.isna().any()
            or (ends <= starts).any()
            or any(starts.iloc[i] < ends.iloc[i - 1] for i in range(1, len(group)))
        ):
            raise ValueError("Source diagnostic clocks reverse or overlap")
        group["diagnostic_start_time"] = starts
        group["diagnostic_end_time"] = ends
        group["reference_capacity_ah"] = group.capacity_ah.iloc[0]
        group["soh"] = group.capacity_ah / group.reference_capacity_ah
        group["life_stage"] = "first_life"
        labels.append(group)
        numbers = set(group.diagnostic.astype(int))
        cycle = batches[batches.cell_id.eq(cell)] if not batches.empty else pd.DataFrame()
        if not cycle.empty and "physical_cell_id" in cycle:
            if not cycle.physical_cell_id.eq(group.physical_cell_id.iloc[0]).all():
                raise ValueError("Source exposure has a conflicting physical identity")
        cycle_numbers = set(cycle.number.astype(int)) if not cycle.empty else set()
        end = 1
        current = None
        corridor_failure = None
        while end + 1 in numbers and end in cycle_numbers:
            try:
                candidate = causal_features(
                    group[group.diagnostic.le(end + 1)], cycle[cycle.number.le(end)]
                )
            except ValueError as exc:
                corridor_failure = {"batch": end, "error": str(exc)}
                break
            current = candidate
            end += 1
        if current is not None:
            features.append(current)
        # A later SOH label supplies no future exposure or age to the input history.
        origins = [number for number in range(3, end + 1) if number + 1 in numbers]
        availability.append(
            {
                "cell_id": cell,
                "physical_cell_id": group.physical_cell_id.iloc[0],
                "status": "availability_only_not_training_authorization",
                "accepted_capacity_labels": len(group),
                "last_verified_feature_diagnostic": end,
                "feature_checkpoints": len(current) if current is not None else 0,
                "potential_H1_min3_origins": len(origins),
                "potential_origin_diagnostics": origins,
                "first_unavailable_exposure_batch": end,
                "corridor_failure": corridor_failure,
            }
        )
    return (
        pd.concat(features, ignore_index=True) if features else pd.DataFrame(),
        pd.concat(labels, ignore_index=True) if labels else pd.DataFrame(),
        pd.DataFrame(availability),
    )
