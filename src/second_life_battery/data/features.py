"""Physical summaries with explicit current convention and diagnostic selection."""

import numpy as np
import pandas as pd


def counter_throughput(values: np.ndarray) -> float:
    """Sum recorded counter increments, including observed resets; omit unknown initial offset."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2 or not np.isfinite(values).all() or (values < -1e-8).any():
        raise ValueError("Throughput requires at least two finite nonnegative counter values")
    delta = np.diff(values)
    return float(np.where(delta >= -1e-8, np.maximum(delta, 0), values[1:]).sum())


def integrate_current(time_s: np.ndarray, current_a: np.ndarray) -> float:
    """Trapezoidal signed Ah; time must increase strictly within a continuous segment."""
    time_s, current_a = np.asarray(time_s), np.asarray(current_a)
    if len(time_s) < 2 or not np.isfinite(time_s).all() or not np.isfinite(current_a).all():
        raise ValueError("Integration needs finite arrays with at least two observations")
    if np.any(np.diff(time_s) <= 0):
        raise ValueError("Integration time must strictly increase")
    return float(np.trapezoid(current_a, time_s) / 3600)


def diagnostic_summary(frame: pd.DataFrame, settings: dict) -> dict:
    """Integrate contiguous low-rate discharge segments; exclude short pulses and rests."""
    frame = frame.copy()
    # Raw Arbin exports are negative on discharge, unlike the article's plot convention.
    frame["segment"] = (frame["step"].diff().fillna(1) != 0).cumsum()
    capacity = counter_capacity = 0.0
    segments = []
    pulse_resistances = []
    for _, segment in frame.groupby("segment", sort=False):
        duration = float(segment.time_s.iloc[-1] - segment.time_s.iloc[0])
        current = float(segment.current_a.median())
        if (
            settings["discharge_current_min_a"] <= -current <= settings["discharge_current_max_a"]
            and duration >= settings["minimum_segment_seconds"]
        ):
            if np.diff(segment.time_s).max() > settings["maximum_sample_gap_seconds"]:
                raise ValueError("Gap inside a capacity discharge segment")
            measured = -integrate_current(segment.time_s.to_numpy(), segment.current_a.to_numpy())
            counter = float(segment.discharge_ah.iloc[-1] - segment.discharge_ah.iloc[0])
            if measured <= 0 or counter <= 0:
                raise ValueError("Discharge sign or capacity-counter direction is inconsistent")
            capacity += measured
            counter_capacity += counter
            segments.append(
                {
                    "step": int(segment.step.iloc[0]),
                    "seconds": duration,
                    "current_a": current,
                    "capacity_ah": measured,
                    "start_voltage_v": float(segment.voltage_v.iloc[0]),
                    "end_voltage_v": float(segment.voltage_v.iloc[-1]),
                }
            )
        if current < -0.4 and 5 <= duration <= 12:
            index = segment.index[0]
            if index > 0:
                previous = frame.loc[index - 1]
                delta_i = float(segment.current_a.iloc[-1] - previous.current_a)
                resistance = float((segment.voltage_v.iloc[-1] - previous.voltage_v) / delta_i)
                if abs(previous.voltage_v - 3.63) < 0.05 and 0 < resistance < 1:
                    pulse_resistances.append(resistance)
    if len(segments) != 4:
        raise ValueError(f"Expected four low-rate discharge segments; found {len(segments)}")
    if segments[0]["start_voltage_v"] < 4.1 or segments[-1]["end_voltage_v"] > 2.55:
        raise ValueError("Capacity test does not span the reviewed full-discharge voltage window")
    if abs(capacity - counter_capacity) / capacity > settings["counter_relative_tolerance"]:
        raise ValueError("Integrated capacity disagrees with the instrument counter")
    if not settings["capacity_min_ah"] <= capacity <= settings["capacity_max_ah"]:
        raise ValueError(f"Capacity outside configured plausibility bounds: {capacity}")
    return {
        "capacity_ah": capacity,
        "counter_capacity_ah": counter_capacity,
        "counter_relative_error": abs(capacity - counter_capacity) / capacity,
        "pulse_resistance_ohm": float(np.mean(pulse_resistances)) if pulse_resistances else np.nan,
        "rpt_aux_temp_c": float(frame.aux_temp_c.median())
        if frame.aux_temp_c.notna().any()
        else np.nan,
        "segments": segments,
        "start_time": frame.timestamp.iloc[0].isoformat(),
        "end_time": frame.timestamp.iloc[-1].isoformat(),
        "observations": len(frame),
    }


def cycling_summary(frame: pd.DataFrame) -> dict:
    """Summarize a recorded cycling export; counters preserve sparse-logging throughput."""
    dt = np.diff(frame.time_s.to_numpy())
    if (dt <= 0).any():
        raise ValueError("Cycling timestamps must increase after deduplication")
    return {
        "start_time": frame.timestamp.iloc[0].isoformat(),
        "end_time": frame.timestamp.iloc[-1].isoformat(),
        "observations": len(frame),
        "charge_ah": counter_throughput(frame.charge_ah.to_numpy()),
        "discharge_ah": counter_throughput(frame.discharge_ah.to_numpy()),
        "charge_wh": counter_throughput(frame.charge_wh.to_numpy()),
        "discharge_wh": counter_throughput(frame.discharge_wh.to_numpy()),
        "aux_temp_mean_c": float(frame.aux_temp_c.mean()),
        "aux_temp_max_c": float(frame.aux_temp_c.max()),
        "elevated_temp_hours": float(np.sum(dt * (frame.aux_temp_c.to_numpy()[1:] > 30)) / 3600),
        "initial_charge_counter_ah": float(frame.charge_ah.iloc[0]),
        "initial_discharge_counter_ah": float(frame.discharge_ah.iloc[0]),
        "voltage_mean_v": float(frame.voltage_v.mean()),
        "current_abs_mean_a": float(frame.current_a.abs().mean()),
    }


def add_soh(frame: pd.DataFrame, reference: dict) -> pd.DataFrame:
    """Normalize by a declared reference available at the first forecast origin."""
    frame = frame.sort_values(["cell_id", "timestamp"]).copy()
    method = reference["method"]
    if method == "first_observed_rpt":
        denominator = frame.groupby("cell_id").capacity_ah.transform("first")
    elif method == "fixed":
        denominator = reference["fixed_capacity_ah"]
        if denominator is None or denominator <= 0:
            raise ValueError("A positive fixed_capacity_ah is required")
    elif method == "first_life_end":
        denominator = frame.cell_id.map(reference["first_life_capacity_ah"])
    else:
        raise ValueError(f"Unknown SOH reference method: {method}")
    if np.any(pd.isna(denominator)) or np.any(np.asarray(denominator) <= 0):
        raise ValueError("SOH reference must be finite and positive for every cell")
    frame["reference_capacity_ah"] = denominator
    frame["soh"] = frame.capacity_ah / denominator
    return frame
