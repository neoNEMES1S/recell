"""Dimensionless prediction/quantile losses and configurable soft trajectory preferences."""

import torch


def pinball_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Mean quantile loss for P10/P50/P90; accepts any leading batch/horizon dimensions."""
    if prediction.shape != target.shape + (3,):
        raise ValueError("Expected three quantiles per target")
    levels = prediction.new_tensor([0.1, 0.5, 0.9])
    error = target[..., None] - prediction
    return torch.maximum(levels * error, (levels - 1) * error).mean()


def physics_guided_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    origins: torch.Tensor,
    settings: dict,
    scale: float,
) -> dict:
    """Penalize sustained upward moves and checkpoint-space curvature without hard monotonicity."""
    if scale <= 0 or any(settings[key] < 0 for key in settings if key.startswith("lambda_")):
        raise ValueError("Loss scale must be positive and weights nonnegative")
    median = prediction[..., 1]
    point = torch.mean(((median - target) / scale) ** 2)
    quantile = pinball_loss(prediction, target) / scale
    path = torch.cat((origins[:, None], median), dim=1)
    increments = path[:, 1:] - path[:, :-1]
    monotonic = torch.mean(torch.relu((increments - settings["recovery_tolerance"]) / scale) ** 2)
    smooth = (
        torch.mean(((increments[:, 1:] - increments[:, :-1]) / scale) ** 2)
        if increments.shape[1] > 1
        else median.sum() * 0
    )
    total = (
        settings["lambda_prediction"] * point
        + settings["lambda_quantile"] * quantile
        + settings["lambda_monotonic"] * monotonic
        + settings["lambda_smooth"] * smooth
    )
    return {
        "total": total,
        "prediction": point,
        "quantile": quantile,
        "monotonic": monotonic,
        "smooth": smooth,
    }
