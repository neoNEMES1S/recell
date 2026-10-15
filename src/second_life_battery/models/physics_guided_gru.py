"""Ordered quantile GRU; physical preferences are soft training penalties, never output clipping."""

import torch
from torch import nn
from torch.nn import functional as F

from second_life_battery.models.gru import GRUForecaster


class PhysicsGuidedGRU(GRUForecaster):
    """P10/P50/P90 around a median residual, ordered by positive learned spacings."""

    def __init__(self, input_size: int, horizon: int, settings: dict):
        super().__init__(input_size, horizon, settings)
        self.head = nn.Linear(settings["hidden_size"], horizon * 3)

    def forward(
        self, history: torch.Tensor, lengths: torch.Tensor, origins: torch.Tensor
    ) -> torch.Tensor:
        raw = self.head(self.encode(history, lengths)).reshape(-1, self.horizon, 3)
        median = origins[:, None] + self.output_scale * raw[..., 0]
        lower = median - self.output_scale * F.softplus(raw[..., 1])
        upper = median + self.output_scale * F.softplus(raw[..., 2])
        return torch.stack((lower, median, upper), dim=-1)
