"""Persistence and regularized linear/tree residual forecasts share identical sample origins."""

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor


def fit_baseline(name: str, x: np.ndarray, residuals: np.ndarray, config: dict, seed: int):
    """Train deterministic baselines without access to test labels."""
    if name == "persistence":
        return None
    if name == "linear":
        model = Ridge(alpha=config["linear_alpha"])
    elif name == "xgboost":
        model = MultiOutputRegressor(
            XGBRegressor(
                n_estimators=config["tree_estimators"],
                max_depth=config["tree_depth"],
                learning_rate=config["tree_learning_rate"],
                min_child_weight=3,
                objective="reg:squarederror",
                random_state=seed,
                n_jobs=1,
            )
        )
    else:
        raise ValueError(f"Unknown baseline: {name}")
    return model.fit(x, residuals)


def predict_baseline(model, x: np.ndarray, origins: np.ndarray, horizon: int) -> np.ndarray:
    """Persistence is an origin-only forecast; fitted models predict residual capacity loss."""
    residual = np.zeros((len(origins), horizon)) if model is None else model.predict(x)
    return origins[:, None] + np.asarray(residual).reshape(len(origins), horizon)
