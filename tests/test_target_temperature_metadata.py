"""A truncated metadata preview cannot justify assigning a temperature probe."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "audit_target_temperature",
    Path(__file__).resolve().parents[1] / "scripts/audit_target_temperature.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return {
        "scan_complete": True,
        "nonempty_rows_including_preamble": 3,
        "preview": [
            {"values": ["TEST REPORT"]},
            {"values": ["Channel", "Comments", "Item ID", "Has Aux"]},
            {"values": [2, None, None, 1]},
        ],
    }


def test_auxiliary_presence_flag_does_not_become_a_probe_assignment():
    result = module.global_record(fixture())
    assert result == {
        "instrument_channel": 2,
        "comments": None,
        "item_id": None,
        "has_auxiliary_channels": 1,
    }


def test_partial_metadata_cannot_support_absence_claim():
    table = fixture()
    table["nonempty_rows_including_preamble"] = 4
    with pytest.raises(ValueError, match="Partial"):
        module.global_record(table)


def test_existing_assignment_text_is_preserved():
    table = fixture()
    table["preview"][-1]["values"][1] = "probe A, cell W8"
    assert module.global_record(table)["comments"] == "probe A, cell W8"
