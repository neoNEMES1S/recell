"""Reviewed Arbin spelling variants preserve field identities and physical units."""

from datetime import datetime, timedelta

import pandas as pd
import pytest
from openpyxl import Workbook

from second_life_battery.data.ev_exposure import raw_endpoint
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.parser import COLUMNS, read_channel


def workbook(path, *, spaced=False, change=None):
    names = list(COLUMNS)[:-1]
    if spaced:
        names = [
            name.replace("_", " ").replace("(", " (") if name != "Date_Time" else name
            for name in names
        ]
    if change:
        names = change(names)
    book = Workbook()
    sheet = book.active
    sheet.title = "Channel3_1" if spaced else "Channel_3_1"
    sheet.append(names)
    for i in range(2):
        row = [
            datetime(2021, 1, 1) + timedelta(seconds=i),
            i + 1,
            i + 1,
            1,
            1,
            3.7,
            0.2,
            0.1,
            0.2,
            0.3,
            0.4,
        ]
        sheet.append(row + ([99] if len(names) > len(row) else []))
    book.save(path)
    return {"source_file": path.name, "sha256": sha256_file(path), "observation_table": sheet.title}


def test_both_reviewed_layouts_have_identical_measurements(tmp_path):
    a = workbook(tmp_path / "a.xlsx")
    b = workbook(tmp_path / "b.xlsx", spaced=True)
    first = read_channel(tmp_path, a, tmp_path / "cache")
    second = read_channel(tmp_path, b, tmp_path / "cache")
    pd.testing.assert_frame_equal(first, second)
    assert raw_endpoint(tmp_path / "b.xlsx")["Test_Time(s)"] == 1
    assert raw_endpoint(tmp_path / "b.xlsx", last=True)["Test_Time(s)"] == 2
    pd.testing.assert_frame_equal(second, read_channel(tmp_path, b, tmp_path / "cache"))


def test_different_units_and_ambiguous_aliases_are_rejected(tmp_path):
    wrong = workbook(
        tmp_path / "wrong.xlsx",
        spaced=True,
        change=lambda names: [n.replace("Time (s)", "Time (ms)") for n in names],
    )
    with pytest.raises(ValueError, match="Required fields"):
        read_channel(tmp_path, wrong, tmp_path / "cache")
    ambiguous = workbook(tmp_path / "ambiguous.xlsx", change=lambda names: names + ["Current (A)"])
    with pytest.raises(ValueError, match="Ambiguous equivalent"):
        read_channel(tmp_path, ambiguous, tmp_path / "cache")
