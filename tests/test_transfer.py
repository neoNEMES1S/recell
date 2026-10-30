"""Missing features and cross-life identity aliases cannot silently leak into training."""

import pandas as pd
import pytest

from second_life_battery.data.transfer import (
    audit_fold,
    physical_folds,
    split_transfer,
    target_features,
    validate_features,
)


def fixture():
    rows = [
        {
            "cell_id": cell,
            "timestamp": f"2022-01-0{k + 1}",
            "capacity_ah": 5 - k * 0.01,
            "reference_capacity_ah": 5.0,
            "soh": 1 - k * 0.002,
            "elapsed_days": float(k),
            "cumulative_ah": 65 + k * 10,
        }
        for cell in ["A", "B", "C"]
        for k in range(4)
    ]
    registry = {
        "cells": [
            {"second_life_source_id": cell, "physical_cell_id": f"physical-{cell}"}
            for cell in ["A", "B", "C"]
        ]
    }
    target = target_features(pd.DataFrame(rows), registry)
    source = target.copy()
    source["cell_id"] = source.cell_id.map(
        {"A": "source-alias-X", "B": "source-alias-Y", "C": "source-alias-Z"}
    )
    source["life_stage"] = "first_life"
    return source, target


def test_global_identity_is_enforced_across_different_source_labels():
    source, target = fixture()
    fold = physical_folds(target)[0]
    parts = split_transfer(source, target, fold)
    assert fold.test == "physical-A"
    assert set(parts["source_train"].physical_cell_id) == {"physical-C"}
    assert set(parts["source_validation"].physical_cell_id) == {"physical-B"}
    assert all(
        fold.test not in set(part.physical_cell_id)
        for name, part in parts.items()
        if name != "target_test"
    )
    assert target.groupby("cell_id").cumulative_ah_since_stage_start.first().eq(0).all()


def test_missing_source_features_cannot_be_imputed_or_ignored():
    source, target = fixture()
    source.loc[0, "elapsed_days"] = None
    with pytest.raises(ValueError, match="incomplete"):
        split_transfer(source, target, physical_folds(target)[0])


def test_unmapped_target_identity_rejected():
    _, target = fixture()
    original = target.assign(cumulative_ah=target.cumulative_ah_since_stage_start)
    with pytest.raises(ValueError, match="incomplete"):
        target_features(original, {"cells": []})


@pytest.mark.parametrize(
    "column,value,message",
    [
        ("reference_capacity_ah", 5.1, "SOH differs"),
        ("soh", 1.02, "SOH differs"),
        ("cumulative_ah_since_stage_start", 1, "start at zero"),
        ("elapsed_days", 1, "start at zero"),
    ],
)
def test_causal_stage_origin_contract(column, value, message):
    source, _ = fixture()
    source.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        validate_features(source)


def test_age_must_match_native_clocks_and_future_reference_is_rejected():
    source, _ = fixture()
    source.loc[1, "elapsed_days"] = 1.1
    with pytest.raises(ValueError, match="observed stage clocks"):
        validate_features(source)
    source, _ = fixture()
    source.loc[:, "reference_capacity_ah"] = 5.1
    source.loc[:, "soh"] = source.capacity_ah / source.reference_capacity_ah
    with pytest.raises(ValueError, match="first accepted capacity"):
        validate_features(source)


def test_fold_preprocessor_ignores_source_and_held_out_features():
    source, target = fixture()
    # Four checkpoints support H1/min3 here; the registered H2 target needs more.
    protocol = {
        "features": {"primary": ["soh", "elapsed_days", "cumulative_ah_since_stage_start"]},
        "source": {"horizon": 1, "minimum_history": 3},
        "target": {
            "horizon": 1,
            "minimum_history": 3,
            "inference_context_fractions": [0.1, 0.5, 1],
        },
    }
    fold = physical_folds(target)[0]
    before = audit_fold(source, target, fold, protocol)
    source.loc[source.physical_cell_id == fold.validation, "cumulative_ah_since_stage_start"] *= 100
    target.loc[
        (target.physical_cell_id == fold.test) & (target.elapsed_days > 0),
        "cumulative_ah_since_stage_start",
    ] *= 100
    after = audit_fold(source, target, fold, protocol)
    assert before["scaler_mean"] == after["scaler_mean"]
    assert before["scaler_scale"] == after["scaler_scale"]
    assert after["scaler_fit_physical_cells"] == list(fold.training)
    assert after["partitions"]["source_validation"]["origins_by_cell"] == {fold.validation: 1}
    # An entire missing gradient-training history must fail before fitting.
    with pytest.raises(ValueError, match="no usable forecast origin"):
        audit_fold(
            source.drop(source[source.physical_cell_id == fold.training[0]].index[-1]),
            target,
            fold,
            protocol,
        )
