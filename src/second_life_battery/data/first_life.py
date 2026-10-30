"""Audit the author's processed EV capacity arrays without inventing missing clocks."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

from second_life_battery.data.features import integrate_current
from second_life_battery.data.inventory import sha256_file


def audit_raw_capacity(frame: pd.DataFrame) -> dict:
    """Recover the real diagnostic clock and independently check its discharge counter."""
    if (
        frame.empty
        or frame.timestamp.isna().any()
        or frame.duplicated(["timestamp", "time_s"]).any()
    ):
        raise ValueError("Raw diagnostic timestamp/test-time pairs must be present and unique")
    if not frame.timestamp.is_monotonic_increasing:
        raise ValueError("Raw diagnostic timestamps must increase")
    groups = (frame.step.diff().fillna(1) != 0).cumsum()
    selected = []
    for _, section in frame.groupby(groups):
        duration = section.time_s.iloc[-1] - section.time_s.iloc[0]
        if duration >= 300 and 0.15 <= -section.current_a.median() <= 0.30:
            selected.append(section)
    if len(selected) != 1:
        raise ValueError("Expected one separate first-life C/20 capacity discharge")
    section = selected[0]
    if (
        np.diff(section.time_s).max() > 5
        or section.voltage_v.iloc[0] < 4.1
        or section.voltage_v.iloc[-1] > 2.55
    ):
        raise ValueError("Raw capacity protocol has a gap or incomplete voltage span")
    capacity = -integrate_current(section.time_s.to_numpy(), section.current_a.to_numpy())
    counter = float(section.discharge_ah.iloc[-1] - section.discharge_ah.iloc[0])
    if not 2 <= capacity <= 5.5 or counter <= 0 or abs(counter - capacity) / capacity > 0.01:
        raise ValueError("Raw integrated capacity disagrees with its discharge counter")
    return {
        "diagnostic_start_time": frame.timestamp.iloc[0].isoformat(),
        "diagnostic_end_time": frame.timestamp.iloc[-1].isoformat(),
        "discharge_start_time": section.timestamp.iloc[0].isoformat(),
        "discharge_end_time": section.timestamp.iloc[-1].isoformat(),
        "capacity_ah": capacity,
        "instrument_discharge_ah": counter,
        "counter_relative_error": abs(counter - capacity) / capacity,
        "timestamp_basis": "Native workbook Date_Time; timezone unverified",
    }


def reconstruct_capacities(source: Path, registry: dict) -> pd.DataFrame:
    """Validate named cell columns and integrate each single C/20 discharge test."""
    data = loadmat(source, squeeze_me=False)
    labels = [str(np.asarray(value).ravel()[0]) for value in data["col_cell_label"].ravel()]
    identities = {row["first_life_source_id"]: row for row in registry["cells"]}
    expected = sorted(identities.values(), key=lambda row: row["first_life_mat_column_zero_based"])
    if labels != [row["first_life_source_id"] for row in expected]:
        raise ValueError("MAT cell column order differs from the reviewed identity registry")
    diagnostics = np.asarray(data["row_diag_number"]).ravel()
    if len(set(diagnostics)) != len(diagnostics) or np.any(np.diff(diagnostics) <= 0):
        raise ValueError("Diagnostic labels must be unique and increasing")
    shape = (len(diagnostics), len(labels))
    if any(data[name].shape != shape for name in ["cap", "curr", "time", "vcell"]):
        raise ValueError("Capacity MAT arrays do not share the diagnostic/cell grid")
    digest = sha256_file(source)
    records = []
    for column, label in enumerate(labels):
        for index, diagnostic in enumerate(diagnostics):
            capacity = np.asarray(data["cap"][index, column], dtype=float).ravel()
            if len(capacity) == 1 and np.isnan(capacity[0]):
                continue
            time, current, voltage = [
                np.asarray(data[name][index, column], dtype=float).ravel()
                for name in ["time", "curr", "vcell"]
            ]
            if (
                len(time) != len(capacity)
                or len(current) != len(capacity)
                or len(voltage) != len(capacity)
                or not all(
                    np.isfinite(values).all() for values in [capacity, time, current, voltage]
                )
            ):
                raise ValueError(f"Incomplete or nonfinite diagnostic: {label}/{diagnostic}")
            if (
                time[-1] - time[0] < 300
                or not 0.15 <= -np.median(current) <= 0.30
                or current.max() > 0.01
                or voltage[0] < 4.1
                or voltage[-1] > 2.55
            ):
                raise ValueError(f"Unexpected EV capacity-discharge protocol: {label}/{diagnostic}")
            value = -integrate_current(time, current)
            reported = float(capacity[-1] - capacity[0])
            if not 2 <= value <= 5.5 or reported <= 0:
                raise ValueError(f"Implausible discharge capacity: {label}/{diagnostic}")
            error = abs(value - reported) / value
            if error > 0.01:
                raise ValueError(f"Capacity curve disagrees with current: {label}/{diagnostic}")
            records.append(
                {
                    "physical_cell_id": identities[label]["physical_cell_id"],
                    "cell_id": label,
                    "life_stage": "first_life",
                    "diagnostic": int(diagnostic),
                    "capacity_ah": value,
                    "reported_capacity_ah": reported,
                    "relative_agreement_error": error,
                    "observations": len(time),
                    "diagnostic_duration_seconds": time[-1] - time[0],
                    "timestamp": None,
                    "elapsed_days": None,
                    "cumulative_ah_since_stage_start": None,
                    "source_sha256": digest,
                    "feature_status": (
                        "capacity_verified; absolute_clock_and_complete_exposure_pending"
                    ),
                }
            )
    if not records:
        raise ValueError("No accepted first-life capacity tests")
    result = pd.DataFrame(records).sort_values(["cell_id", "diagnostic"])
    result["reference_capacity_ah"] = result.groupby("cell_id").capacity_ah.transform("first")
    result["soh"] = result.capacity_ah / result.reference_capacity_ah
    return result.reset_index(drop=True)
