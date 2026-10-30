"""Reconstruct EV cycling exposure using dense current and measured endpoint clocks."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy.io import loadmat, whosmat

from second_life_battery.data.parser import canonical_header, is_channel_sheet


def raw_endpoint(path: Path, *, last: bool = False) -> dict:
    """Read one native endpoint without retaining a large workbook in memory."""
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = [sheet for sheet in book if is_channel_sheet(sheet.title)]
        if len(sheets) != 1:
            raise ValueError("Expected one measurement channel for an EV clock anchor")
        sheets[0].reset_dimensions()
        rows = iter(sheets[0].values)
        header = [canonical_header(name) for name in next(rows)]
        known = [name for name in header if name is not None]
        if len(known) != len(set(known)):
            raise ValueError("Ambiguous equivalent raw endpoint columns")
        point = None
        for row in rows:
            if not any(value is not None for value in row):
                continue
            point = {name: value for name, value in zip(header, row) if name is not None}
            if not last:
                break
        if point is None:
            raise ValueError("Empty clock anchor")
        required = {"Date_Time", "Test_Time(s)", "Voltage(V)", "Current(A)"}
        if not required.issubset(point) or any(point[name] is None for name in required):
            raise ValueError("Raw endpoint lacks reviewed time/current/voltage units")
        return point
    finally:
        book.close()


def integrate_batch(time, current, voltage, first: dict, last: dict) -> dict:
    """Require both raw endpoints to match the processed series before integration."""
    arrays = [np.asarray(a, dtype=float).ravel() for a in (time, current, voltage)]
    time, current, voltage = arrays
    if len(time) < 2 or len({len(a) for a in arrays}) != 1:
        raise ValueError("Incomplete cycling arrays")
    if not all(np.isfinite(a).all() for a in arrays):
        raise ValueError("Nonfinite cycling measurements")
    synthetic = bool(time[0] == 0 and current[0] == 0 and voltage[0] == 0)
    if synthetic:
        time, current, voltage = [a[1:] for a in arrays]
    if len(time) < 2 or (np.diff(time) <= 0).any() or np.diff(time).max() > 5:
        raise ValueError("Cycling time has a reversal or an unaudited sampling gap")
    for index, raw in [(0, first), (-1, last)]:
        for values, key, tolerance in [
            (time, "Test_Time(s)", 1e-4),
            (current, "Current(A)", 1e-4),
            (voltage, "Voltage(V)", 1e-4),
        ]:
            if not np.isclose(values[index], raw[key], rtol=0, atol=tolerance):
                raise ValueError(f"Processed endpoint differs from raw {key}")
    start, end = [pd.Timestamp(raw["Date_Time"]) for raw in (first, last)]
    if pd.isna(start) or pd.isna(end) or end <= start:
        raise ValueError("Missing or reversed native cycling clocks")
    return {
        "batch_start_time": start.isoformat(),
        "batch_end_time": end.isoformat(),
        "observations": len(time),
        "removed_synthetic_zero": synthetic,
        "maximum_gap_seconds": float(np.diff(time).max()),
        "charge_ah": float(np.trapezoid(np.maximum(current, 0), time) / 3600),
        "discharge_ah": float(np.trapezoid(np.maximum(-current, 0), time) / 3600),
        "native_minus_instrument_duration_seconds": float(
            (end - start).total_seconds() - (time[-1] - time[0])
        ),
        "timestamp_basis": "Native workbook Date_Time; timezone unverified",
    }


def batch_arrays(mat: Path):
    names = [name for name, _, _ in whosmat(mat)]
    chosen = []
    for prefix in ["t_full_vec_", "I_full_vec_", "V_full_vec_"]:
        matches = [name for name in names if name.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous processed cycling variable: {prefix}")
        chosen.append(matches[0])
    values = loadmat(mat, variable_names=chosen, squeeze_me=True)
    return [values[name] for name in chosen]


def integrate_segments(time, current, voltage, anchors: list[tuple[dict, dict]]) -> dict:
    """Verify the author's explicit zero-row rebasing using every native restart part."""
    arrays = [np.asarray(a, dtype=float).ravel() for a in (time, current, voltage)]
    if not anchors or len({len(a) for a in arrays}) != 1:
        raise ValueError("Incomplete cycling arrays or source-part anchors")
    time, current, voltage = arrays
    markers = np.flatnonzero((current == 0) & (voltage == 0))
    if not len(markers) and len(anchors) == 1:
        result = integrate_batch(*arrays, *anchors[0])
        return {**result, "removed_synthetic_rows": 0, "source_parts": 1}
    if len(markers) != len(anchors) or markers[0] != 0:
        raise ValueError("Processed restart markers do not match reviewed raw source parts")
    segments, previous_end = [], None
    gaps = []
    for index, (marker, endpoints) in enumerate(zip(markers, anchors)):
        stop = int(markers[index + 1]) if index + 1 < len(markers) else len(time)
        offset = float(time[marker])
        expected_offset = 0 if index == 0 else time[marker - 1]
        if not np.isclose(offset, expected_offset, rtol=0, atol=1e-8):
            raise ValueError("Unverified processed-time rebase at source restart")
        segment = integrate_batch(
            time[marker + 1 : stop] - offset,
            current[marker + 1 : stop],
            voltage[marker + 1 : stop],
            *endpoints,
        )
        start, end = [pd.Timestamp(segment[key]) for key in ["batch_start_time", "batch_end_time"]]
        if previous_end is not None:
            if start < previous_end:
                raise ValueError("Native source restart parts overlap or go backwards")
            gaps.append((start - previous_end).total_seconds())
        previous_end = end
        segments.append({**segment, "segment_index": index + 1, "processed_time_offset_s": offset})
    start = pd.Timestamp(segments[0]["batch_start_time"])
    end = pd.Timestamp(segments[-1]["batch_end_time"])
    instrument_duration = sum(
        (
            pd.Timestamp(row["batch_end_time"]) - pd.Timestamp(row["batch_start_time"])
        ).total_seconds()
        - row["native_minus_instrument_duration_seconds"]
        for row in segments
    )
    return {
        "batch_start_time": start.isoformat(),
        "batch_end_time": end.isoformat(),
        "observations": sum(row["observations"] for row in segments),
        "removed_synthetic_zero": True,
        "removed_synthetic_rows": len(markers),
        "maximum_gap_seconds": max(row["maximum_gap_seconds"] for row in segments),
        "charge_ah": sum(row["charge_ah"] for row in segments),
        "discharge_ah": sum(row["discharge_ah"] for row in segments),
        "native_minus_instrument_duration_seconds": (end - start).total_seconds()
        - instrument_duration,
        "native_inter_part_gaps_seconds": gaps,
        "source_parts": len(segments),
        "segments": segments,
        "timestamp_basis": "Native workbook Date_Time for every part; timezone unverified",
    }


def audit_segmented_batch(mat: Path, parts: list[tuple[Path, Path]]) -> dict:
    anchors = [(raw_endpoint(first), raw_endpoint(last, last=True)) for first, last in parts]
    arrays = batch_arrays(mat)
    result = integrate_segments(*arrays, anchors)
    result["numeric_trajectory_sha256"] = trajectory_sha256(arrays)
    return result


def trajectory_sha256(arrays) -> str:
    """Hash actual t/I/V values independently of MAT headers and variable names."""
    digest = hashlib.sha256()
    for label, values in zip(["time_s", "current_a", "voltage_v"], arrays, strict=True):
        values = np.asarray(values).ravel()
        digest.update(f"{label}:{len(values)}:".encode())
        for start in range(0, len(values), 100_000):
            digest.update(np.ascontiguousarray(values[start : start + 100_000], dtype="<f8"))
    return digest.hexdigest()


def audit_raw_cycling_fragments(frames: list[pd.DataFrame]) -> dict:
    """Review complete ordered raw exports without sorting or repairing measurements."""
    if not frames or any(frame.empty for frame in frames):
        raise ValueError("Missing raw cycling fragment")
    columns = ["timestamp", "time_s", "current_a", "voltage_v"]
    frame = pd.concat([part[columns] for part in frames], ignore_index=True)
    clocks = pd.to_datetime(frame.timestamp, errors="raise")
    if clocks.isna().any() or (clocks.diff().dropna() < pd.Timedelta(0)).any():
        raise ValueError("Raw cycling wall clocks reverse within ordered exports")
    arrays = [frame[name].to_numpy() for name in ["time_s", "current_a", "voltage_v"]]

    def endpoint(index):
        row = frame.iloc[index]
        return {
            "Date_Time": row.timestamp,
            "Test_Time(s)": row.time_s,
            "Current(A)": row.current_a,
            "Voltage(V)": row.voltage_v,
        }

    result = integrate_batch(*arrays, endpoint(0), endpoint(-1))
    return {
        **result,
        "numeric_trajectory_sha256": trajectory_sha256(arrays),
        "raw_fragments": len(frames),
        "basis": "Complete raw exports in source fragment order",
    }


def audit_batch(mat: Path, first: Path, last: Path) -> dict:
    return audit_segmented_batch(mat, [(first, last)])


def causal_features(diagnostics: pd.DataFrame, batches: pd.DataFrame) -> pd.DataFrame:
    """Join complete measured intervals; reject missing, overlapping or future batches."""
    result = []
    if set(batches.cell_id) != set(diagnostics.cell_id):
        raise ValueError("Diagnostic and cycling cell coverage differs")
    for cell, group in diagnostics.groupby("cell_id"):
        group = group.sort_values("diagnostic").copy()
        numbers = group.diagnostic.astype(int).tolist()
        if numbers != list(range(1, len(group) + 1)):
            raise ValueError("Noncontiguous accepted diagnostics need a reviewed mapping")
        cycles = batches[batches.cell_id == cell].sort_values("number")
        if cycles.number.astype(int).tolist() != list(range(1, len(group))):
            raise ValueError("Missing or duplicate cycling batch")
        starts = pd.to_datetime(group.diagnostic_start_time).tolist()
        ends = pd.to_datetime(group.diagnostic_end_time).tolist()
        if any(end <= start for start, end in zip(starts, ends)):
            raise ValueError("Invalid diagnostic clocks")
        exposure = [0.0]
        for index, row in enumerate(cycles.itertuples()):
            start, end = pd.Timestamp(row.batch_start_time), pd.Timestamp(row.batch_end_time)
            if not ends[index] <= start < end <= starts[index + 1]:
                raise ValueError("Cycling exposure crosses a diagnostic boundary")
            amount = row.charge_ah + row.discharge_ah
            if not np.isfinite(amount) or amount <= 0:
                raise ValueError("Invalid cycling exposure")
            exposure.append(exposure[-1] + amount)
        group["timestamp"] = [end.isoformat() for end in ends]
        group["elapsed_days"] = [(end - ends[0]).total_seconds() / 86400 for end in ends]
        group["cumulative_ah_since_stage_start"] = exposure
        group["reference_capacity_ah"] = group.capacity_ah.iloc[0]
        group["soh"] = group.capacity_ah / group.reference_capacity_ah
        group["life_stage"] = "first_life"
        result.append(group)
    return pd.concat(result, ignore_index=True)
