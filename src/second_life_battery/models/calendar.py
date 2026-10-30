"""Small apparent storage-aging models; no mixed-wear or M50T calibration implied."""

from itertools import product
from time import perf_counter

import numpy as np
from scipy.optimize import least_squares


def features(frame):
    values = frame[["elapsed_days", "storage_temperature_c", "storage_soc_fraction"]].to_numpy(
        float
    )
    age, temperature, soc = values.T
    if (
        not np.isfinite(values).all()
        or (age < 0).any()
        or (temperature <= -273.15).any()
        or ((soc < 0) | (soc > 1)).any()
    ):
        raise ValueError("Calendar prediction conditions are invalid")
    return np.sqrt(age / 365.25), 1000 * (1 / 297.15 - 1 / (temperature + 273.15)), soc - 0.5


def predict_calendar(name, parameters, frame):
    time, temperature, soc = features(frame)
    if name == "C0":
        return np.ones(len(frame))
    if name == "C1":
        return 1 - float(parameters[0]) * time
    if name == "C2":
        alpha, beta_t, beta_s = parameters
        return 1 - np.exp(alpha + beta_t * temperature + beta_s * soc) * time
    raise ValueError("Unknown registered calendar model")


def training_weights(frame):
    if frame.empty or frame.elapsed_days.le(0).any() or not np.isfinite(frame.soh).all():
        raise ValueError("Calendar fitting needs finite positive-time observations")
    if frame.groupby("physical_cell_id").base_type.nunique().gt(1).any():
        raise ValueError("One physical cell cannot describe multiple base models")
    cells = frame[["base_type", "physical_cell_id"]].drop_duplicates().groupby("base_type").size()
    counts = frame.groupby("physical_cell_id").size()
    return 1 / (
        len(cells)
        * frame.base_type.map(cells).to_numpy()
        * frame.physical_cell_id.map(counts).to_numpy()
    )


def fit_calendar(frame, settings):
    weights = training_weights(frame)
    time, _, _ = features(frame)
    coefficient = max(
        0.0, float(np.sum(weights * time * (1 - frame.soh)) / np.sum(weights * time * time))
    )
    models = {
        "C0": {"parameters": [], "fit_seconds": 0.0},
        "C1": {"parameters": [coefficient], "fit_seconds": 0.0},
    }
    lower, upper = np.array(settings["C2_bounds"], dtype=float)
    alpha = float(np.clip(np.log(max(coefficient, 1e-8)), lower[0], upper[0]))
    started = perf_counter()
    fits = []
    for beta_t, beta_s in product(settings["C2_starts_beta_T"], settings["C2_starts_beta_s"]):
        result = least_squares(
            lambda parameters: (
                np.sqrt(weights)
                * (predict_calendar("C2", parameters, frame) - frame.soh.to_numpy())
            ),
            [alpha, beta_t, beta_s],
            bounds=(lower, upper),
            method="trf",
            loss="linear",
            max_nfev=2000,
            x_scale=1.0,
            ftol=1e-8,
            xtol=1e-8,
            gtol=1e-8,
        )
        fits.append(
            {
                "start": [alpha, beta_t, beta_s],
                "converged": bool(result.success),
                "cost": float(result.cost),
                "nfev": int(result.nfev),
                "parameters": result.x.tolist(),
            }
        )
    accepted = [fit for fit in fits if fit["converged"] and np.isfinite(fit["cost"])]
    if not accepted:
        raise ValueError("No registered calendar optimization start converged")
    selected = min(accepted, key=lambda fit: fit["cost"])
    models["C2"] = {
        "parameters": selected["parameters"],
        "training_cost": selected["cost"],
        "fixed_starts": fits,
        "fit_seconds": perf_counter() - started,
        "parameter_at_bound": (
            np.isclose(selected["parameters"], lower, atol=1e-6)
            | np.isclose(selected["parameters"], upper, atol=1e-6)
        ).tolist(),
    }
    return models
