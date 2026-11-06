"""Discharge-positive Rint/1-RC models with explicit left-held sampled current."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares


@dataclass(frozen=True)
class Parameters:
    r0_ohm: float
    r1_ohm: float = 0.0
    tau_s: float = 1.0

    def __post_init__(self):
        if not np.isfinite([self.r0_ohm, self.r1_ohm, self.tau_s]).all():
            raise ValueError("ECM parameters must be finite")
        if self.r0_ohm <= 0 or self.r1_ohm < 0 or self.tau_s <= 0:
            raise ValueError("Require R0 > 0, R1 >= 0 and tau > 0")


def trace(time_s, current_a):
    t, current = np.asarray(time_s, float), np.asarray(current_a, float)
    if (
        t.ndim != 1
        or current.shape != t.shape
        or len(t) < 2
        or not np.isfinite(t).all()
        or not np.isfinite(current).all()
        or (np.diff(t) <= 0).any()
    ):
        raise ValueError("Require equal finite 1-D traces and strictly increasing time")
    return t, current


def polarization(time_s, current_a, params: Parameters, initial_v=0.0):
    """v[k] is the pre-update state; current[k-1] drives the preceding interval."""
    t, current = trace(time_s, current_a)
    if not np.isfinite(initial_v):
        raise ValueError("Initial polarization must be finite")
    state = np.empty(len(t))
    state[0] = initial_v
    decay = np.exp(-np.diff(t) / params.tau_s)
    for k, a in enumerate(decay, start=1):
        state[k] = a * state[k - 1] + params.r1_ohm * current[k - 1] * (1 - a)
    return state


def simulate(
    time_s,
    current_a,
    params,
    capacity_ah,
    initial_soc,
    ocv_soc,
    ocv_v,
    initial_polarization_v=0.0,
    charge_efficiency=1.0,
):
    """A measured OCV table is required; no SOC or OCV extrapolation/clipping."""
    t, current = trace(time_s, current_a)
    z, voltage = np.asarray(ocv_soc, float), np.asarray(ocv_v, float)
    if (
        z.ndim != 1
        or len(z) < 2
        or voltage.shape != z.shape
        or not np.isfinite(z).all()
        or not np.isfinite(voltage).all()
        or (np.diff(z) <= 0).any()
        or z[0] < 0
        or z[-1] > 1
        or not np.isfinite([capacity_ah, initial_soc, charge_efficiency]).all()
        or capacity_ah <= 0
        or not 0 < charge_efficiency <= 1
    ):
        raise ValueError("Invalid OCV table, capacity, initial SOC or charge efficiency")
    effective = np.where(current[:-1] < 0, charge_efficiency * current[:-1], current[:-1])
    soc = initial_soc - np.r_[0, np.cumsum(effective * np.diff(t))] / (3600 * capacity_ah)
    if (soc < z[0]).any() or (soc > z[-1]).any():
        raise ValueError("SOC leaves the measured OCV table; extrapolation is unsupported")
    state = polarization(t, current, params, initial_polarization_v)
    return {
        "soc": soc,
        "polarization_v": state,
        "voltage_v": np.interp(soc, z, voltage) - params.r0_ohm * current - state,
    }


def pulse_response(time_s, current_a, initial_voltage_v, params):
    """Local constant-OCV response anchored before a pulse, not a global SOC model.

    Long preceding low-rate discharge is approximated as stationary polarization.
    The measured initial terminal voltage is the only evaluation-voltage input.
    """
    t, current = trace(time_s, current_a)
    if not np.isfinite(initial_voltage_v):
        raise ValueError("Initial voltage must be finite")
    initial = params.r1_ohm * current[0]
    state = polarization(t, current, params, initial)
    return initial_voltage_v - params.r0_ohm * (current - current[0]) - (state - initial)


def fit_pulses(windows, model="1rc", bounds=None):
    """Fit calibration windows only; constant OCV is a declared local approximation."""
    if model not in {"rint", "1rc"} or not windows:
        raise ValueError("Need calibration windows and model rint or 1rc")
    for w in windows:
        t, _ = trace(w["time_s"], w["current_a"])
        v = np.asarray(w["voltage_v"], float)
        if v.shape != t.shape or not np.isfinite(v).all():
            raise ValueError("Measured voltage must match a finite current/time trace")

    def unpack(x):
        return Parameters(x[0], x[1], x[2]) if model == "1rc" else Parameters(x[0])

    def residual(x):
        return np.concatenate(
            [
                (
                    pulse_response(w["time_s"], w["current_a"], w["voltage_v"][0], unpack(x))
                    - w["voltage_v"]
                )[1:]
                / np.sqrt(len(w["time_s"]) - 1)
                for w in windows
            ]
        )

    x0, lower, upper = ([0.03, 0.01, 10], [0.0001, 0.000001, 0.05], [0.3, 0.3, 300])
    if bounds is not None:
        limits = np.asarray([bounds[k] for k in ["r0_ohm", "r1_ohm", "tau_s"]], float)
        if limits.shape != (3, 2) or not np.isfinite(limits).all():
            raise ValueError("Parameter bounds must be three finite lower/upper pairs")
        lower, upper = limits[:, 0], limits[:, 1]
    if model == "rint":
        x0, lower, upper = x0[:1], lower[:1], upper[:1]
    result = least_squares(residual, x0, bounds=(lower, upper), max_nfev=300)
    if not result.success or not np.isfinite(result.x).all():
        raise ValueError(f"Pulse fit failed: {result.message}")
    singular = np.linalg.svd(result.jac, compute_uv=False)
    return unpack(result.x), {
        "success": bool(result.success),
        "nfev": result.nfev,
        "jacobian_condition": float(singular[0] / max(singular[-1], 1e-30)),
        "bound_contact": bool(
            np.any(np.isclose(result.x, lower, rtol=0, atol=1e-5))
            or np.any(np.isclose(result.x, upper, rtol=0, atol=1e-5))
        ),
        "calibration_windows": len(windows),
    }
