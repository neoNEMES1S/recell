"""Explicitly mapped BMS CSV records; quality failures remain visible in source order."""

import numpy as np
import pandas as pd


def prepare_bms(frame, contract):
    required = {"pack_id", "cell_id", "timestamp", "voltage_v", "current_a"}
    columns = contract["columns"]
    if not required.issubset(columns) or not set(columns.values()).issubset(frame.columns):
        raise ValueError("Missing explicitly mapped BMS source columns")
    if contract["voltage_unit"] != "V" or contract["current_unit"] != "A":
        raise ValueError("Convert and document BMS units explicitly before ingestion")
    if contract["current_convention"] not in {"discharge_positive", "charge_positive"}:
        raise ValueError("BMS current convention must be explicit")
    data = frame[list(columns.values())].rename(columns={v: k for k, v in columns.items()}).copy()
    for name in ["pack_id", "cell_id"]:
        if data[name].isna().any() or (data[name].astype(str).str.strip() == "").any():
            raise ValueError("Every BMS row needs physical pack and cell identities")
        data[name] = data[name].astype(str)
    for name in ["timestamp", "arrival_timestamp"]:
        if name not in data:
            continue
        stamp = pd.to_datetime(data[name], errors="raise")
        if stamp.isna().any():
            raise ValueError("Missing BMS timestamp")
        if stamp.dt.tz is None:
            stamp = stamp.dt.tz_localize(
                contract["timezone"], ambiguous="raise", nonexistent="raise"
            )
        data[name] = stamp.dt.tz_convert("UTC")
    for name in ["current_a", "voltage_v"]:
        data[name] = pd.to_numeric(data[name], errors="raise")
    if contract["current_convention"] == "charge_positive":
        data["current_a"] = -data.current_a
    flags = [[] for _ in range(len(data))]
    positions = pd.Series(np.arange(len(data)), index=data.index)

    def flag(mask, reason):
        for index in positions[mask]:
            flags[index].append(reason)

    flag(
        ~np.isfinite(data.voltage_v) | (data.voltage_v <= 0) | ~np.isfinite(data.current_a),
        "invalid_electrical_measurement",
    )
    flag(data.duplicated(["pack_id", "cell_id", "timestamp"], keep=False), "duplicate_event")
    diff = data.groupby(["pack_id", "cell_id"]).timestamp.diff().dt.total_seconds()
    flag(diff < 0, "out_of_order")
    flag(diff > contract["maximum_gap_s"], "gap_before_record")
    if "arrival_timestamp" in data:
        delay = (data.arrival_timestamp - data.timestamp).dt.total_seconds()
        flag(delay < 0, "arrival_before_event")
        flag(delay > contract["maximum_delay_s"], "stale_record")
    data["quality"] = [";".join(items) if items else "ok" for items in flags]
    data["arrival_timing_verified"] = "arrival_timestamp" in data
    return data
