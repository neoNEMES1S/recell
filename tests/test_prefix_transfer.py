"""The availability amendment preserves every target test role and held-out first life."""

from copy import deepcopy

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from second_life_battery.data.prefix_transfer import split_prefix_transfer
from second_life_battery.data.transfer import physical_folds


def data():
    def frame(cells, stage):
        return pd.DataFrame(
            [
                dict(
                    cell_id=cell,
                    physical_cell_id=cell,
                    life_stage=stage,
                    timestamp=f"2020-01-{i:02d}T00:00:00",
                    capacity_ah=5 - i * 0.01,
                    reference_capacity_ah=4.99,
                    soh=(5 - i * 0.01) / 4.99,
                    elapsed_days=float(i - 1),
                    cumulative_ah_since_stage_start=float((i - 1) * 10),
                )
                for cell in cells
                for i in range(1, 5)
            ]
        )

    target = frame([f"p{i}" for i in range(1, 7)], "second_life")
    source = frame([f"p{i}" for i in range(1, 6)] + ["extra"], "first_life")
    protocol = {
        "target": {"cells": sorted(target.cell_id.unique())},
        "source": {
            "eligible_gradient_physical_cells": [f"p{i}" for i in range(1, 6)],
            "validation_physical_cell": "extra",
        },
    }
    return source, target, protocol


def test_all_six_target_folds_remain_with_audited_source_subset():
    source, target, protocol = data()
    folds = physical_folds(target)
    assert len(folds) == 6
    for fold in folds:
        parts = split_prefix_transfer(source, target, fold, protocol)
        assert set(parts["target_train"].physical_cell_id) == set(fold.training)
        assert set(parts["target_test"].physical_cell_id) == {fold.test}
        assert set(parts["target_validation"].physical_cell_id) == {fold.validation}
        assert set(parts["source_validation"].physical_cell_id) == {"extra"}
        assert set(parts["source_train"].physical_cell_id) == set(fold.training) - {"p6"}


def test_held_out_first_life_cannot_change_source_gradient_data():
    source, target, protocol = data()
    fold = physical_folds(target)[0]
    before = split_prefix_transfer(source, target, fold, protocol)
    held_out = source.physical_cell_id.isin([fold.test, fold.validation])
    source.loc[held_out, "cumulative_ah_since_stage_start"] *= 100
    after = split_prefix_transfer(source, target, fold, protocol)
    assert_frame_equal(before["source_train"], after["source_train"])
    assert_frame_equal(before["source_validation"], after["source_validation"])
    assert_frame_equal(before["target_train"], after["target_train"])


@pytest.mark.parametrize("defect", ["extra_gradient", "test_validation", "pool", "target_pool"])
def test_unregistered_or_overlapping_roles_are_rejected(defect):
    source, target, protocol = data()
    fold = physical_folds(target)[0]
    protocol = deepcopy(protocol)
    if defect == "extra_gradient":
        protocol["source"]["eligible_gradient_physical_cells"].append("extra")
    elif defect == "test_validation":
        protocol["source"]["validation_physical_cell"] = fold.test
    elif defect == "pool":
        source = source[source.physical_cell_id.ne("p3")]
    else:
        protocol["target"]["cells"] = ["p1", "p2"]
    with pytest.raises(ValueError):
        split_prefix_transfer(source, target, fold, protocol)
