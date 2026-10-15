"""Forecast samples expose past observations only; future rows supply labels, never features."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class Sample:
    """One forecast origin and its strictly subsequent checkpoint targets."""

    cell_id: str
    origin_index: int
    origin_time: str
    target_times: list[str]
    history: np.ndarray
    target: np.ndarray
    origin_soh: float
    reference_capacity_ah: float


def make_sequences(
    frame: pd.DataFrame,
    features: list[str],
    horizon: int,
    fraction: float = 1.0,
    min_history: int = 3,
) -> list[Sample]:
    """Keep a suffix of pre-origin history; evaluate the same origins for every fraction."""
    if not 0 < fraction <= 1 or horizon < 1 or min_history < 1:
        raise ValueError("Invalid history fraction, horizon, or minimum history")
    samples = []
    for cell, group in frame.groupby("cell_id", sort=True):
        group = group.sort_values("timestamp").reset_index(drop=True)
        if group.timestamp.duplicated().any():
            raise ValueError("Duplicate checkpoint timestamps")
        for origin in range(min_history - 1, len(group) - horizon):
            count = max(1, math.ceil((origin + 1) * fraction))
            history = group.loc[origin + 1 - count : origin, features].to_numpy(dtype=np.float32)
            future = group.iloc[origin + 1 : origin + 1 + horizon]
            samples.append(
                Sample(
                    str(cell),
                    origin,
                    str(group.timestamp.iloc[origin]),
                    future.timestamp.astype(str).tolist(),
                    history,
                    future.soh.to_numpy(dtype=np.float32),
                    float(group.soh.iloc[origin]),
                    float(group.reference_capacity_ah.iloc[origin]),
                )
            )
    return samples


def fit_preprocessor(training: pd.DataFrame, features: list[str]):
    """Fit medians/scales on unique training-cell checkpoints, not repeated sequence windows."""
    if training.empty:
        raise ValueError("Cannot fit preprocessing without training checkpoints")
    pipeline = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler()
    )
    pipeline.fit(training[features].to_numpy(dtype=float))
    return pipeline


def tabular_features(samples: list[Sample], preprocessor) -> np.ndarray:
    """Common tabular baseline input: latest features, per-checkpoint slopes and context length."""
    rows = []
    for sample in samples:
        history = preprocessor.transform(sample.history)
        slope = (
            (history[-1] - history[0]) / (len(history) - 1)
            if len(history) > 1
            else np.zeros(history.shape[1])
        )
        rows.append(np.r_[history[-1], slope, len(history)])
    return np.asarray(rows)
