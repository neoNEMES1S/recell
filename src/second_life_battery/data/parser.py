"""Read the reviewed Stanford Channel exports without executing embedded code."""

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from second_life_battery.data.inventory import sha256_file

COLUMNS = {
    "Date_Time": "timestamp",
    "Test_Time(s)": "time_s",
    "Step_Time(s)": "step_time_s",
    "Step_Index": "step",
    "Cycle_Index": "cycle",
    "Voltage(V)": "voltage_v",
    "Current(A)": "current_a",
    "Charge_Capacity(Ah)": "charge_ah",
    "Discharge_Capacity(Ah)": "discharge_ah",
    "Charge_Energy(Wh)": "charge_wh",
    "Discharge_Energy(Wh)": "discharge_wh",
    "Aux_Temperature(¡æ)_1": "aux_temp_c",
}
REQUIRED = set(COLUMNS.values()) - {"aux_temp_c"}


def read_channel(root: Path, record: dict, cache: Path) -> pd.DataFrame:
    """Validate source hash; cache only numeric arrays and timestamp integers, never pickle."""
    source = root / record["source_file"]
    if sha256_file(source) != record["sha256"]:
        raise ValueError(f"Source changed since inspection: {source}")
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / f"channel-v1-{record['sha256']}.npz"
    if cached.exists():
        with np.load(cached, allow_pickle=False) as arrays:
            frame = pd.DataFrame({name: arrays[name] for name in arrays.files})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        return frame
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        sheet = workbook[record["observation_table"]]
        sheet.reset_dimensions()
        rows = sheet.values
        header = next(rows)
        positions = {i: COLUMNS[name] for i, name in enumerate(header) if name in COLUMNS}
        if not REQUIRED.issubset(positions.values()):
            raise ValueError(f"Required fields absent: {source}")
        frame = pd.DataFrame(
            [
                {name: row[i] if i < len(row) else None for i, name in positions.items()}
                for row in rows
                if any(value is not None for value in row)
            ]
        )
    finally:
        workbook.close()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    for column in frame.columns.drop("timestamp"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if frame[list(REQUIRED)].isna().any().any():
        raise ValueError(f"Missing required measurements: {source}")
    if not np.isfinite(frame[list(REQUIRED - {"timestamp"})]).all().all():
        raise ValueError(f"Nonfinite required measurements: {source}")
    frame["aux_temp_c"] = frame.get("aux_temp_c", np.nan)
    arrays = {name: frame[name].to_numpy() for name in frame}
    arrays["timestamp"] = frame["timestamp"].astype("int64").to_numpy()
    np.savez_compressed(cached, **arrays)
    return frame


def merge_exports(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    """Collapse exact overlapping records; reject contradictory measurements at one timestamp."""
    frame = pd.concat(frames, ignore_index=True)
    count = len(frame)
    frame = frame.drop_duplicates()
    # Wall-clock timestamps are rounded; test time retains sub-millisecond samples.
    key = ["timestamp", "time_s"]
    if frame.duplicated(key).any():
        raise ValueError("Conflicting measurements share timestamp and test time")
    return frame.sort_values(key).reset_index(drop=True), count - len(frame)
