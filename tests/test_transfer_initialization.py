"""Synthetic checks only: no source-data gate is bypassed or research model fitted."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from second_life_battery.models.physics_guided_gru import PhysicsGuidedGRU
from second_life_battery.training.trainer import train_gru
from second_life_battery.training.transfer import initialize_encoder


def config(stage):
    features = ["soh", "elapsed_days", "cumulative_ah_since_stage_start"]
    return {
        "features": features,
        "evaluation": {"horizon": 1 if stage == "first_life" else 2},
        "gru": {"hidden_size": 8, "layers": 1, "dropout": 0.1, "output_scale": 0.02},
        "training": {
            "device": "cpu",
            "epochs": 1,
            "patience": 1,
            "minimum_improvement": 1e-5,
            "learning_rate": 0.003,
            "weight_decay": 1e-4,
        },
        "physics": {
            "lambda_prediction": 1.0,
            "lambda_quantile": 1.0,
            "lambda_monotonic": 0.1,
            "lambda_smooth": 0.1,
            "recovery_tolerance": 0.002,
        },
        "transfer": {
            "stage": stage,
            "seed": 42,
            "protocol_sha256": "a" * 64,
            "registry_sha256": "b" * 64,
            "scaler_sha256": "c" * 64,
            "datasets": {"source": "d" * 64, "target": "e" * 64},
            "feature_order": features,
            "feature_units": ["1", "day", "Ah"],
            "normalization": "first_accepted_stage_capacity",
            "gradient_cells": ["p1", "p2", "p3", "p4"],
            "validation_cell": "p5",
            "test_cell": "p6",
            "quantiles": [0.1, 0.5, 0.9],
        },
    }


def parent_checkpoint(tmp_path):
    settings = config("first_life")
    model = PhysicsGuidedGRU(3, 1, settings["gru"])
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.fill_(0.125)
    path = tmp_path / "synthetic_parent.pt"
    torch.save(
        {"config": settings, "state_dict": model.state_dict(), "model_name": "pgp_gru"}, path
    )
    return path, model


def test_encoder_only_transfer_preserves_head_rng_and_quantile_order(tmp_path):
    parent, source = parent_checkpoint(tmp_path)
    settings = config("second_life")
    target = PhysicsGuidedGRU(3, 2, settings["gru"])
    head = deepcopy(target.head.state_dict())
    rng = torch.get_rng_state().clone()
    evidence = initialize_encoder(target, parent, settings, "pgp_gru")
    assert torch.equal(rng, torch.get_rng_state())
    for key, value in target.state_dict().items():
        if key.startswith("head."):
            assert torch.equal(value, head[key.removeprefix("head.")])
        else:
            assert torch.equal(value, source.state_dict()[key])
    target.eval()
    prediction = target(torch.zeros(2, 3, 3), torch.tensor([1, 3]), torch.tensor([0.9, 0.8]))
    assert prediction.shape == (2, 2, 3)
    assert torch.all(prediction[..., 0] <= prediction[..., 1])
    assert torch.all(prediction[..., 1] <= prediction[..., 2])
    assert not any(key.startswith("head.") for key in evidence["transferred_parameters"])
    assert len(evidence["parent_sha256"]) == 64


@pytest.mark.parametrize("change", ["scaler", "features", "leakage", "arm", "architecture"])
def test_incompatible_parent_rejected_before_target_mutation(tmp_path, change):
    parent, _ = parent_checkpoint(tmp_path)
    settings = config("second_life")
    name = "pgp_gru"
    if change == "scaler":
        settings["transfer"]["scaler_sha256"] = "f" * 64
    elif change == "features":
        settings["features"] = list(reversed(settings["features"]))
    elif change == "leakage":
        settings["transfer"]["gradient_cells"][0] = "p6"
    elif change == "arm":
        name = "quantile_gru"
    else:
        settings["gru"]["hidden_size"] = 16
    target = PhysicsGuidedGRU(3, 2, settings["gru"])
    initial = deepcopy(target.state_dict())
    with pytest.raises(ValueError):
        initialize_encoder(target, parent, settings, name)
    assert all(torch.equal(value, initial[key]) for key, value in target.state_dict().items())


def test_synthetic_fit_uses_fresh_optimizer_and_records_parent(tmp_path, monkeypatch):
    parent, _ = parent_checkpoint(tmp_path)
    settings = config("second_life")
    original = torch.optim.Adam
    created = []

    def adam(*args, **kwargs):
        optimizer = original(*args, **kwargs)
        assert len(optimizer.state) == 0
        created.append(optimizer)
        return optimizer

    monkeypatch.setattr(torch.optim, "Adam", adam)

    def sample(cell):
        return SimpleNamespace(
            cell_id=cell,
            history=np.array([[1.0, 0.0, 0.0], [0.99, 1.0, 10.0]]),
            origin_soh=0.99,
            target=np.array([0.98, 0.97], dtype=np.float32),
        )

    class IdentityScaler:
        def transform(self, values):
            return values

    destination = tmp_path / "synthetic_target.pt"
    train_gru(
        [sample(cell) for cell in settings["transfer"]["gradient_cells"]],
        [sample("p5")],
        IdentityScaler(),
        settings,
        destination,
        "pgp_gru",
        parent_checkpoint=parent,
    )
    saved = torch.load(destination, weights_only=True)
    assert len(created) == 1
    assert saved["initialization"]["optimizer"] == "fresh"
    assert saved["optimization_seconds"] > 0
    assert saved["config"]["transfer"]["stage"] == "second_life"
    with pytest.raises(ValueError, match="Actual samples"):
        train_gru(
            [sample("p6")],
            [sample("p5")],
            IdentityScaler(),
            settings,
            tmp_path / "invalid.pt",
            "pgp_gru",
            parent_checkpoint=parent,
        )


def test_legacy_trainer_call_needs_no_transfer_contract(tmp_path):
    settings = config("second_life")
    del settings["transfer"]
    sample = SimpleNamespace(
        cell_id="legacy",
        history=np.zeros((3, 3)),
        origin_soh=0.99,
        target=np.array([0.98, 0.97], dtype=np.float32),
    )
    scaler = SimpleNamespace(transform=lambda values: values)
    path = tmp_path / "legacy.pt"
    model = train_gru([sample], [sample], scaler, settings, path, "gru")
    assert model.horizon == 2
    assert torch.load(path, weights_only=True)["initialization"] is None


@pytest.mark.parametrize("defect", [None, "source_test", "source_target_validation", "role_map"])
def test_registered_stage_roles_allow_audited_source_subset_only(tmp_path, defect):
    source_config, target_config = config("first_life"), config("second_life")
    roles = {
        "first_life": {"gradient_cells": ["p1", "p2", "p3"], "validation_cell": "extra"},
        "second_life": {"gradient_cells": ["p1", "p2", "p3", "p4"], "validation_cell": "p5"},
    }
    if defect == "source_test":
        roles["first_life"]["gradient_cells"][0] = "p6"
    elif defect == "source_target_validation":
        roles["first_life"]["validation_cell"] = "p5"
    for settings in [source_config, target_config]:
        stage = settings["transfer"]["stage"]
        settings["transfer"].update(deepcopy(roles[stage]))
        settings["transfer"]["stage_roles"] = deepcopy(roles)
        settings["transfer"]["source_labels_sha256"] = "f" * 64
    if defect == "role_map":
        source_config["transfer"]["stage_roles"]["first_life"]["gradient_cells"] = ["p1", "p2"]
        source_config["transfer"]["gradient_cells"] = ["p1", "p2"]
    parent = PhysicsGuidedGRU(3, 1, source_config["gru"])
    path = tmp_path / "synthetic_prefix_parent.pt"
    torch.save(
        {"config": source_config, "state_dict": parent.state_dict(), "model_name": "pgp_gru"}, path
    )
    target = PhysicsGuidedGRU(3, 2, target_config["gru"])
    before = deepcopy(target.state_dict())
    if defect:
        with pytest.raises(ValueError):
            initialize_encoder(target, path, target_config, "pgp_gru")
        assert all(torch.equal(value, before[key]) for key, value in target.state_dict().items())
    else:
        evidence = initialize_encoder(target, path, target_config, "pgp_gru")
        assert evidence["source_contract"]["gradient_cells"] == ["p1", "p2", "p3"]
        assert evidence["source_contract"]["validation_cell"] == "extra"
        assert torch.equal(target.head.weight, before["head.weight"])
