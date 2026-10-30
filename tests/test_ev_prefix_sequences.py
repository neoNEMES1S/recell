"""Unknown future exposure never enters a source H1 sample."""

import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.ev_prefix_sequences import source_sequences


def tables():
    labels = pd.DataFrame(
        [
            dict(
                physical_cell_id="p1",
                cell_id="W5",
                life_stage="first_life",
                diagnostic=i,
                timestamp=f"2020-01-{i:02d}T00:00:00.000000",
                capacity_ah=5 - i * 0.1,
                reference_capacity_ah=4.9,
                soh=(5 - i * 0.1) / 4.9,
            )
            for i in range(1, 5)
        ]
    )
    features = labels.iloc[:3].assign(
        elapsed_days=[0.0, 1.0, 2.0], cumulative_ah_since_stage_start=[0.0, 10.0, 20.0]
    )
    return features, labels


def test_measured_future_label_without_future_covariates():
    features, labels = tables()
    first = source_sequences(features, labels)
    assert len(first) == 1 and first[0].origin_index == 2
    assert first[0].history.shape == (3, 3)
    assert first[0].cell_id == "p1" and first[0].target_times == [labels.timestamp.iloc[3]]
    labels.loc[3, "capacity_ah"] = 4.1
    labels.loc[3, "soh"] = 4.1 / 4.9
    changed = source_sequences(features, labels)[0]
    np.testing.assert_array_equal(first[0].history, changed.history)
    assert first[0].target[0] != changed.target[0]
    assert "elapsed_days" not in labels and "cumulative_ah_since_stage_start" not in labels


@pytest.mark.parametrize("defect", ["past_capacity", "identity", "clock", "duplicate", "prefix"])
def test_source_sample_rejects_inconsistent_measurements(defect):
    features, labels = tables()
    if defect == "past_capacity":
        labels.loc[1, "capacity_ah"] = 4.2
        labels.loc[1, "soh"] = 4.2 / 4.9
    elif defect == "identity":
        labels["physical_cell_id"] = "test_cell"
    elif defect == "clock":
        labels.loc[3, "timestamp"] = labels.timestamp.iloc[1]
    elif defect == "duplicate":
        labels = pd.concat([labels, labels.iloc[-1:]])
    else:
        features.loc[1, "diagnostic"] = 4
    with pytest.raises(ValueError):
        source_sequences(features, labels)
