import pytest
import torch

from second_life_battery.training.trainer import resolve_device


def test_explicit_gpu_never_silently_runs_cpu(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="explicitly requested"):
        resolve_device("cuda")
    assert resolve_device("auto").type == "cpu"
    assert resolve_device("cpu").type == "cpu"


def test_unknown_device_rejected():
    with pytest.raises(ValueError):
        resolve_device("gpu-ish")
