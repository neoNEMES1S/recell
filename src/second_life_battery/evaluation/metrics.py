"""Point and probabilistic metrics with explicit zero-target and degenerate-R² handling."""

import numpy as np


def point_metrics(target: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    """MAPE is percentage-valued and omitted when any target is effectively zero."""
    target, prediction = np.asarray(target, dtype=float).ravel(), np.asarray(prediction).ravel()
    if target.shape != prediction.shape or not len(target):
        raise ValueError("Metrics require matching nonempty arrays")
    if not np.isfinite(target).all() or not np.isfinite(prediction).all():
        raise ValueError("Metrics require finite values")
    error = prediction - target
    denominator = np.sum((target - target.mean()) ** 2)
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mape_percent": float(np.mean(np.abs(error / target)) * 100)
        if np.all(np.abs(target) > 1e-8)
        else np.nan,
        "r2": float(1 - np.sum(error**2) / denominator) if denominator > 0 else np.nan,
    }


def probabilistic_metrics(target: np.ndarray, quantiles: np.ndarray) -> dict[str, float]:
    """Evaluate ordered P10/P50/P90; the nominal central interval has 80% coverage."""
    target, quantiles = np.asarray(target), np.asarray(quantiles)
    if quantiles.shape != target.shape + (3,):
        raise ValueError("Quantile shape must equal target shape plus three outputs")
    if not np.isfinite(quantiles).all() or not np.isfinite(target).all():
        raise ValueError("Quantiles and targets must be finite")
    if np.any(np.diff(quantiles, axis=-1) < 0):
        raise ValueError("Quantile predictions cross")
    error = target[..., None] - quantiles
    levels = np.array([0.1, 0.5, 0.9])
    result = {
        "quantile_loss": float(np.maximum(levels * error, (levels - 1) * error).mean()),
        "coverage_80": float(
            ((target >= quantiles[..., 0]) & (target <= quantiles[..., 2])).mean()
        ),
        "interval_width": float((quantiles[..., 2] - quantiles[..., 0]).mean()),
    }
    result.update(
        {
            f"empirical_q{int(q * 100)}": float((target <= quantiles[..., i]).mean())
            for i, q in enumerate(levels)
        }
    )
    return result
