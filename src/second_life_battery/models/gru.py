"""Small packed-sequence GRU with an origin-relative multi-checkpoint prediction head."""

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


class GRUForecaster(nn.Module):
    """Predict residual SOH; padding cannot affect the final hidden state."""

    def __init__(self, input_size: int, horizon: int, settings: dict):
        super().__init__()
        self.horizon = horizon
        self.output_scale = settings["output_scale"]
        self.gru = nn.GRU(
            input_size,
            settings["hidden_size"],
            settings["layers"],
            batch_first=True,
            dropout=settings["dropout"] if settings["layers"] > 1 else 0,
        )
        self.representation = nn.Sequential(
            nn.Dropout(settings["dropout"]),
            nn.Linear(settings["hidden_size"], settings["hidden_size"]),
            nn.Tanh(),
        )
        self.head = nn.Linear(settings["hidden_size"], horizon)

    def encode(self, history: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """Encode only actual observations, with CPU sequence lengths required by PyTorch."""
        packed = pack_padded_sequence(
            history, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, hidden = self.gru(packed)
        return self.representation(hidden[-1])

    def forward(
        self, history: torch.Tensor, lengths: torch.Tensor, origins: torch.Tensor
    ) -> torch.Tensor:
        return origins[:, None] + self.output_scale * self.head(self.encode(history, lengths))
