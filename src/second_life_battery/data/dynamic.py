"""Audited local diagnostic-pulse windows, without manufacturing an OCV/SOC map."""

import numpy as np


def pulse_windows(frame, settings):
    if frame.empty or (np.diff(frame.time_s.to_numpy()) <= 0).any():
        raise ValueError("Session clock resets, duplicates or reverses")
    result = []
    for step in settings["pulse_steps"]:
        indices = np.flatnonzero(frame.step.to_numpy() == step)
        if not len(indices) or indices[0] == 0:
            raise ValueError(f"Pulse {step} has no preceding voltage/current anchor")
        following = np.flatnonzero(frame.step.to_numpy() == step + settings["following_steps"])
        if not len(following):
            raise ValueError(f"Pulse {step} lacks following rest/charge")
        start, end = indices[0] - 1, following[-1] + 1
        part = frame.iloc[start:end].copy()
        t = part.time_s.to_numpy() - part.time_s.iloc[0]
        if np.diff(t).max() > settings["maximum_sample_gap_s"]:
            raise ValueError(f"Pulse {step} has an unresolved sample gap")
        current = -part.current_a.to_numpy()
        voltage = part.voltage_v.to_numpy()
        if not np.isfinite(np.c_[t, current, voltage]).all() or not 0 < current[0] < 0.4:
            raise ValueError("Missing finite low-rate pre-pulse anchor")
        if current[1:].max() <= current[0] or not (current[1:] < 0).any():
            raise ValueError("Expected discharge/rest/charge stimulus is incomplete")
        result.append(
            {
                "step": int(step),
                "time_s": t.tolist(),
                "current_a": current.tolist(),
                "voltage_v": voltage.tolist(),
                "anchor_voltage_v": float(voltage[0]),
                "rows": len(part),
                "max_gap_s": float(np.diff(t).max()),
            }
        )
    return result
