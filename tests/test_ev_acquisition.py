"""Acquisition is resumable only for pinned complete files and confines all writes."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

spec = importlib.util.spec_from_file_location(
    "acquire_ev_transfer", Path(__file__).resolve().parents[1] / "scripts/acquire_ev_transfer.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_cell_matching_and_fragment_order():
    records = [
        {"attributes": {"kind": "file", "name": name}}
        for name in [
            "test_W1_Channel_2.10.xlsx",
            "test_W10_Channel_2.1.xlsx",
            "test_W1_Channel_2.1.xlsx",
        ]
    ]
    chosen = module.matching_files(records, "W1")
    assert len(chosen) == 2
    assert (
        min(chosen, key=module.fragment_order)["attributes"]["name"] == "test_W1_Channel_2.1.xlsx"
    )


def test_reviewed_workbook_and_inline_part_names_are_numeric():
    records = [
        {"attributes": {"kind": "file", "name": name}}
        for name in [
            "test_G1_Part3_Channel_3_Wb_10.xlsx",
            "test_G1_Part3_Channel_3_Wb_2.xlsx",
            "test_G10_Part3_Channel_3_Wb_1.xlsx",
            "test_W10_New_Channel_6.1.xlsx",
        ]
    ]
    matches = module.matching_files(records, "G1")
    assert len(matches) == 2
    assert min(matches, key=module.export_order)["attributes"]["name"].endswith("Wb_2.xlsx")
    assert len(module.matching_files(records, "W10")) == 1


def test_download_pins_complete_bytes_and_rejects_tampering(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    calls = []

    def download(command, **kwargs):
        calls.append(command)
        book = Workbook()
        book.active.append(["Test data"])
        book.save(command[-1])
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(module.subprocess, "run", download)
    entry = {
        "path": "diagnostics/test.xlsx",
        "url": "https://files.osf.io/example",
        "remote_id": "example",
        "legacy": None,
    }
    first = module.download_one(raw, entry, {})
    assert first["bytes"] > 0
    assert module.download_one(raw, entry, {}) == first
    assert len(calls) == 1
    (raw / entry["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="pinned receipt"):
        module.download_one(raw, entry, {})


def test_download_rejects_escaping_paths_and_unexpected_origin(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        module.download_one(tmp_path, {"path": "../outside", "url": "https://osf.io/x"}, {})
    with pytest.raises(ValueError, match="origin"):
        module.download_one(tmp_path, {"path": "inside", "url": "https://example.com/"}, {})


def test_numbered_parts_preserve_campaign_order(tmp_path, monkeypatch):
    def file(name):
        return {"attributes": {"kind": "file", "name": name}}

    def folder(n):
        return {
            "attributes": {"kind": "folder", "name": f"Part{n}"},
            "relationships": {"files": {"links": {"related": {"href": str(n)}}}},
        }

    listings = {
        "1": [file("test_G1_Channel_3.20.xlsx"), file("test_G1_Channel_3.1.xlsx")],
        "2": [file("test_G1_Channel_3.10.xlsx"), file("test_G1_Channel_3.1.xlsx")],
    }
    monkeypatch.setattr(module, "inspect_listing", lambda url, path: {"data": listings[url]})
    exports = module.cycling_exports([folder(2), folder(1)], tmp_path, "sample")
    first = min(exports, key=module.export_order)
    last = max(exports, key=module.export_order)
    assert first["part_order"] == (1,)
    assert first["attributes"]["name"].endswith("3.1.xlsx")
    assert last["part_order"] == (2,)
    assert last["attributes"]["name"].endswith("3.10.xlsx")
    channel = folder(5)
    channel["attributes"]["name"] = "Channel_5"
    listings["5"] = listings["2"]
    nested = module.cycling_exports([channel], tmp_path, "channel", parts=(2,), depth=1)
    assert all(row["part_order"] == (2,) for row in nested)
    unknown = folder(1)
    unknown["attributes"]["name"] = "unreviewed"
    with pytest.raises(ValueError, match="Unreviewed"):
        module.cycling_exports([unknown], tmp_path, "sample")
