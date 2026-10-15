"""Variable-length recurrence must ignore padding and produce deterministic evaluation outputs."""

import torch

from second_life_battery.models.gru import GRUForecaster
from second_life_battery.models.physics_guided_gru import PhysicsGuidedGRU
from second_life_battery.training.losses import physics_guided_loss, pinball_loss
from second_life_battery.utils.reproducibility import seed_everything


def test_gru_prediction_shape_and_padding_invariance() -> None:
    seed_everything(42)
    model = GRUForecaster(
        2, 2, {"hidden_size": 4, "layers": 1, "dropout": 0.1, "output_scale": 0.02}
    )
    model.eval()
    x = torch.randn(2, 5, 2)
    lengths = torch.tensor([2, 5])
    origins = torch.tensor([1.0, 0.9])
    first = model(x, lengths, origins)
    x[0, 2:] = 10000
    second = model(x, lengths, origins)
    assert first.shape == (2, 2)
    torch.testing.assert_close(first, second)


def test_ordered_quantiles_and_soft_penalties_have_gradients() -> None:
    model = PhysicsGuidedGRU(
        2, 2, {"hidden_size": 4, "layers": 1, "dropout": 0, "output_scale": 0.02}
    )
    prediction = model(torch.randn(3, 4, 2), torch.tensor([2, 3, 4]), torch.ones(3))
    assert prediction.shape == (3, 2, 3)
    assert torch.all(prediction[..., 0] <= prediction[..., 1])
    assert torch.all(prediction[..., 1] <= prediction[..., 2])
    loss = pinball_loss(prediction, torch.ones(3, 2))
    loss.backward()
    assert model.head.weight.grad is not None
    q = torch.tensor([[[0.9, 1.01, 1.1], [0.9, 1.03, 1.1]]], requires_grad=True)
    settings = {
        "lambda_prediction": 1,
        "lambda_quantile": 1,
        "lambda_monotonic": 0.1,
        "lambda_smooth": 0.1,
        "recovery_tolerance": 0.002,
    }
    parts = physics_guided_loss(q, torch.ones(1, 2), torch.ones(1), settings, 0.02)
    assert parts["monotonic"] > 0 and parts["smooth"] > 0
    parts["total"].backward()
    assert torch.isfinite(q.grad).all()
    torch.testing.assert_close(
        pinball_loss(torch.tensor([[0.0, 1.0, 2.0]]), torch.tensor([1.0])), torch.tensor(2 / 30)
    )
