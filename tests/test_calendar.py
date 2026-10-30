"""Calendar summaries retain native clocks, observed references and author warnings."""

import json

import pytest

from second_life_battery.data.calendar import CAPACITY, parse_calendar_summary


def fixture(tmp_path):
    path = tmp_path / "C00103_sum.json"
    summary = {
        CAPACITY: {"0": 3.0, "1": None, "2": 2.9},
        "Calendar_Time(date)": {"0": "2020-01-01", "1": "2020-01-02", "2": "2020-01-04"},
        "Calendar_DateTime(days)": {"0": 0, "1": 1, "2": 3},
        "diag_num": {"0": 0, "1": 1, "2": 2},
    }
    cell = {
        "Cell_id": "C00103",
        "Cell_type": "Sony",
        "Cell_chemistry": "NMC",
        "SOC": 50,
        "Temperature": 24,
        "Lot": "L1",
        "Comment": "author warning",
    }
    path.write_text(json.dumps({"summary_data": json.dumps(summary), "comment": "kept"}))
    return path, cell, summary


def test_embedded_json_missing_capacity_and_observed_reference(tmp_path):
    path, cell, _ = fixture(tmp_path)
    frame, report = parse_calendar_summary(path, cell)
    assert frame.elapsed_days.tolist() == [0, 3]
    assert frame.soh.tolist() == pytest.approx([1, 2.9 / 3])
    assert report["excluded_capacity_diagnostics"] == [1]
    assert report["author_inventory_comment"] == "author warning"
    assert frame.storage_soc_fraction.eq(0.5).all()


def test_mismatched_cell_and_clock_rejected(tmp_path):
    path, cell, summary = fixture(tmp_path)
    with pytest.raises(ValueError, match="physical-cell"):
        parse_calendar_summary(path, {**cell, "Cell_id": "C00104"})
    summary["Calendar_DateTime(days)"]["2"] = 4
    path.write_text(json.dumps({"summary_data": summary}))
    with pytest.raises(ValueError, match="elapsed-day"):
        parse_calendar_summary(path, cell)


def test_same_day_diagnostics_quarantined_without_fabricating_dates(tmp_path):
    path, cell, summary = fixture(tmp_path)
    summary[CAPACITY] = {"0": 3.0, "1": 2.99, "2": 2.98, "3": 2.9}
    summary["diag_num"] = {str(i): i for i in range(4)}
    summary["Calendar_Time(date)"] = {
        "0": "2020-01-01",
        "1": "2020-01-02",
        "2": "2020-01-02",
        "3": "2020-01-04",
    }
    summary["Calendar_DateTime(days)"] = {"0": 0, "1": 1, "2": 1, "3": 3}
    path.write_text(json.dumps({"summary_data": summary}))
    frame, report = parse_calendar_summary(path, cell)
    assert frame.diagnostic.tolist() == [0, 3]
    assert frame.elapsed_days.tolist() == [0, 3]
    assert report["ambiguous_same_date_diagnostics"] == [1, 2]
