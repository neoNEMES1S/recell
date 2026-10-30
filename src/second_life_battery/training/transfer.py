"""Strict encoder-only initialization for the registered linked-life experiment."""

from pathlib import Path

import torch

from second_life_battery.data.inventory import sha256_file
from second_life_battery.models.physics_guided_gru import PhysicsGuidedGRU


def validate_contract(config: dict, stage: str, name: str) -> dict:
    contract = config.get("transfer", {})
    required = {
        "stage",
        "seed",
        "protocol_sha256",
        "registry_sha256",
        "datasets",
        "feature_order",
        "feature_units",
        "normalization",
        "scaler_sha256",
        "gradient_cells",
        "validation_cell",
        "test_cell",
        "quantiles",
    }
    if (
        not required.issubset(contract)
        or stage not in {"first_life", "second_life"}
        or contract["stage"] != stage
    ):
        raise ValueError("Missing or incompatible transfer contract/stage")
    if name not in {"pgp_gru", "quantile_gru"} or contract["quantiles"] != [0.1, 0.5, 0.9]:
        raise ValueError("Transfer requires the registered ordered-quantile model")
    expected_horizon = 1 if stage == "first_life" else 2
    if config["evaluation"]["horizon"] != expected_horizon or contract["seed"] not in [42, 43, 44]:
        raise ValueError("Transfer stage horizon/seed differs from the registration")
    if (
        contract["feature_order"] != config["features"]
        or len(contract["feature_units"]) != len(config["features"])
        or not contract["normalization"]
        or any(not isinstance(unit, str) or not unit for unit in contract["feature_units"])
    ):
        raise ValueError("Transfer feature order/units/normalization mismatch")
    train = contract["gradient_cells"]
    roles = contract.get("stage_roles")
    expected_count = 4
    if roles is not None:
        if (
            not isinstance(roles, dict)
            or set(roles) != {"first_life", "second_life"}
            or any(
                not isinstance(role, dict)
                or set(role) != {"gradient_cells", "validation_cell"}
                or not isinstance(role["gradient_cells"], list)
                for role in roles.values()
            )
        ):
            raise ValueError("Transfer must declare both stage-specific physical-cell roles")
        source, target = roles["first_life"], roles["second_life"]
        source_cells, target_cells = source["gradient_cells"], target["gradient_cells"]
        if (
            len(target_cells) != 4
            or len(set(target_cells)) != 4
            or not source_cells
            or len(source_cells) != len(set(source_cells))
            or not set(source_cells).issubset(target_cells)
            or source["validation_cell"]
            in {*target_cells, target["validation_cell"], contract["test_cell"]}
            or target["validation_cell"] in target_cells
            or contract["test_cell"] in {*target_cells, target["validation_cell"]}
            or train != roles[stage]["gradient_cells"]
            or contract["validation_cell"] != roles[stage]["validation_cell"]
            or "source_labels_sha256" not in contract
        ):
            raise ValueError("Stage-specific transfer roles overlap or differ from actual roles")
        expected_count = len(roles[stage]["gradient_cells"])
    if (
        len(train) != expected_count
        or len(set(train)) != expected_count
        or contract["validation_cell"] in train
        or contract["test_cell"] in train
        or contract["validation_cell"] == contract["test_cell"]
    ):
        raise ValueError("Transfer physical-cell roles overlap or omit training cells")
    digests = [contract[k] for k in ["protocol_sha256", "registry_sha256", "scaler_sha256"]]
    if set(contract["datasets"]) != {"source", "target"}:
        raise ValueError("Transfer must identify both source and target datasets")
    digests.extend(contract["datasets"].values())
    if roles is not None:
        digests.append(contract["source_labels_sha256"])
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
        for value in digests
    ):
        raise ValueError("Transfer provenance requires SHA-256 digests")
    return contract


def initialize_encoder(model, parent: Path, config: dict, name: str) -> dict:
    """Copy GRU/representation only; reject mismatched provenance before mutation."""
    target = validate_contract(config, "second_life", name)
    saved = torch.load(parent, map_location="cpu", weights_only=True)
    source_config = saved["config"]
    source = validate_contract(source_config, "first_life", saved.get("model_name"))
    if saved["model_name"] != name:
        raise ValueError("Source and target training arms differ")
    shared = set(source) | set(target)
    shared.discard("stage")
    if "stage_roles" in source and "stage_roles" in target:
        shared -= {"gradient_cells", "validation_cell"}
    if any(source.get(key) != target.get(key) for key in shared):
        raise ValueError("Source/target transfer contracts differ")
    if (
        source_config["gru"] != config["gru"]
        or source_config["evaluation"]["horizon"] != 1
        or config["evaluation"]["horizon"] != 2
        or not isinstance(model, PhysicsGuidedGRU)
        or model.horizon != 2
    ):
        raise ValueError("Transfer architecture or H1-to-H2 contract mismatch")
    # Structural verification must not consume the target fit's dropout RNG stream.
    with torch.random.fork_rng(devices=[]):
        source_model = PhysicsGuidedGRU(len(source_config["features"]), 1, source_config["gru"])
        source_model.load_state_dict(saved["state_dict"], strict=True)
    state = model.state_dict()
    encoder = {
        key: value
        for key, value in saved["state_dict"].items()
        if key.startswith(("gru.", "representation."))
    }
    expected = {key for key in state if key.startswith(("gru.", "representation."))}
    if set(encoder) != expected or any(encoder[key].shape != state[key].shape for key in expected):
        raise ValueError("Transfer encoder state is incompatible")
    model.load_state_dict({**state, **encoder}, strict=True)
    return {
        "parent_checkpoint": str(parent),
        "parent_sha256": sha256_file(parent),
        "transferred_parameters": sorted(encoder),
        "head": "fresh_target_initialization",
        "optimizer": "fresh",
        "scheduler": "fresh",
        "source_contract": source,
    }
