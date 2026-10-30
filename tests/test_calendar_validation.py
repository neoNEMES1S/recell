"""Calendar type splits cannot leak alternate lots or fabricate short-cell labels."""

import pandas as pd
import pytest

from second_life_battery.data.calendar_validation import calendar_cohort


def tables():
    metadata, observations = [], []
    for index, name in enumerate(["A", "A_v2", "B", "C", "D"]):
        cell = f"C{index}"
        metadata.append(
            {
                "Cell_id": cell,
                "Cell_type": name,
                "Cell_chemistry": "NMC",
                "Lot": f"L{index}",
                "Temperature": 24,
                "SOC": 50,
                "Test_id": f"T{index}",
                "Comment": "Week 10 data deleted, potentially swapped" if index == 0 else "",
            }
        )
        for day in [0] if name == "D" else [0, 7]:
            capacity = 3.0 if day == 0 else 3.01  # Observed recovery stays in the source table.
            observations.append(
                {
                    "cell_id": cell,
                    "physical_cell_id": f"joule_calendar_{cell}",
                    "cell_type": name,
                    "chemistry": "NMC",
                    "lot": f"L{index}",
                    "storage_temperature_c": 24.0,
                    "storage_soc_fraction": 0.5,
                    "source_sha256": str(index) * 64,
                    "timestamp": f"2021-01-{day + 1:02d}",
                    "elapsed_days": day,
                    "capacity_ah": capacity,
                    "reference_capacity_ah": 3.0,
                    "soh": capacity / 3.0,
                }
            )
    return pd.DataFrame(observations), pd.DataFrame(metadata)


def test_type_folds_group_lots_and_keep_short_histories_descriptive():
    frame, metadata = tables()
    before = frame.copy(deep=True)
    cohort, folds = calendar_cohort(frame, metadata)
    assert frame.equals(before)
    assert len(cohort) == 5 and cohort.has_future_observation.sum() == 4
    assert cohort.author_swap_note.sum() == 1
    assert len(folds) == 3
    first = next(fold for fold in folds if fold["test_type"] == "A")
    assert set(first["test_cells"]) == {"joule_calendar_C0", "joule_calendar_C1"}
    all_test = []
    for fold in folds:
        train, validation, test = [
            set(fold[name]) for name in ["training_cells", "validation_cells", "test_cells"]
        ]
        assert not (train & validation or train & test or validation & test)
        assert "joule_calendar_C4" not in train | validation | test
        all_test.extend(test)
    assert len(all_test) == len(set(all_test)) == 4


@pytest.mark.parametrize(
    "defect", ["physical_id", "storage_condition", "reference", "duplicate_clock"]
)
def test_conflicting_identity_conditions_or_clocks_rejected(defect):
    frame, metadata = tables()
    if defect == "physical_id":
        frame.loc[frame.cell_id.eq("C0"), "physical_cell_id"] = "joule_calendar_C1"
    elif defect == "storage_condition":
        frame.loc[0, "storage_soc_fraction"] = 1.0
    elif defect == "reference":
        frame.loc[1, "reference_capacity_ah"] = 3.01
    else:
        frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
    with pytest.raises(ValueError):
        calendar_cohort(frame, metadata)
