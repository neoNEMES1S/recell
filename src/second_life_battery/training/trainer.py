"""Small-data GRU fitting with battery-disjoint validation and deterministic stopping."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence

from second_life_battery.models.gru import GRUForecaster
from second_life_battery.models.physics_guided_gru import PhysicsGuidedGRU
from second_life_battery.training.losses import physics_guided_loss


def tensors(samples, scaler, device: torch.device) -> tuple[torch.Tensor, ...]:
    """Pad transformed histories without treating padding as observed measurements."""
    history = [
        torch.tensor(scaler.transform(sample.history), dtype=torch.float32) for sample in samples
    ]
    return (
        pad_sequence(history, batch_first=True).to(device),
        torch.tensor([len(row) for row in history]),
        torch.tensor([sample.origin_soh for sample in samples], dtype=torch.float32, device=device),
        torch.tensor(np.stack([sample.target for sample in samples]), device=device),
    )


def train_gru(train, validation, scaler, config: dict, checkpoint: Path, name: str = "gru"):
    """Fit a point/quantile GRU; retain the best independent-validation checkpoint."""
    settings = config["training"]
    requested = settings["device"]
    device = torch.device(
        "cuda" if requested in {"cuda", "auto"} and torch.cuda.is_available() else "cpu"
    )
    model_class = GRUForecaster if name == "gru" else PhysicsGuidedGRU
    model = model_class(len(config["features"]), config["evaluation"]["horizon"], config["gru"]).to(
        device
    )
    x, lengths, origins, target = tensors(train, scaler, device)
    vx, vl, vo, vy = tensors(validation, scaler, device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=settings["learning_rate"], weight_decay=settings["weight_decay"]
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=8)
    best, stale, best_state, best_epoch = float("inf"), 0, None, -1
    history = []
    scale = config["gru"]["output_scale"]
    loss_settings = dict(config.get("physics", {}))
    if name == "quantile_gru":
        loss_settings.update(lambda_monotonic=0, lambda_smooth=0)
    validation_settings = {**loss_settings, "lambda_monotonic": 0, "lambda_smooth": 0}
    for epoch in range(settings["epochs"]):
        model.train()
        optimizer.zero_grad()
        prediction = model(x, lengths, origins)
        components = (
            physics_guided_loss(prediction, target, origins, loss_settings, scale)
            if name != "gru"
            else {}
        )
        loss = (
            components["total"] if components else torch.mean(((prediction - target) / scale) ** 2)
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
        optimizer.step()
        model.eval()
        with torch.no_grad():
            val_prediction = model(vx, vl, vo)
            val_loss = (
                physics_guided_loss(val_prediction, vy, vo, validation_settings, scale)["total"]
                if name != "gru"
                else torch.mean(((val_prediction - vy) / scale) ** 2)
            ).item()
        scheduler.step(val_loss)
        history.append(
            {
                "epoch": epoch,
                "training_loss": loss.item(),
                "validation_loss": val_loss,
                "learning_rate": optimizer.param_groups[0]["lr"],
            }
        )
        history[-1].update({key: value.item() for key, value in components.items()})
        if val_loss < best - settings["minimum_improvement"]:
            best, stale, best_state, best_epoch = val_loss, 0, deepcopy(model.state_dict()), epoch
        else:
            stale += 1
        if stale >= settings["patience"]:
            break
    if best_state is None:
        raise ValueError("Training produced no finite validation checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    torch.save(
        {
            "state_dict": {key: value.cpu() for key, value in best_state.items()},
            "config": config,
            "best_epoch": best_epoch,
            "best_validation_loss": best,
        },
        checkpoint,
    )
    pd.DataFrame(history).to_csv(checkpoint.with_suffix(".history.csv"), index=False)
    return model


def predict_gru(model, samples, scaler) -> np.ndarray:
    """Predict using the selected checkpoint, with dropout disabled."""
    device = next(model.parameters()).device
    x, lengths, origins, _ = tensors(samples, scaler, device)
    model.eval()
    with torch.no_grad():
        return model(x, lengths, origins).cpu().numpy()
