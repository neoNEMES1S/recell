"""Verify the compact calendar release and audit histories without fitting an aging model."""

import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from extract_dataset import extract_verified

from second_life_battery.data.calendar import parse_calendar_summary
from second_life_battery.data.inventory import sha256_file


def prepare(root: Path) -> dict:
    audit = root / "outputs/calendar/source_audit"
    raw = root / "data/raw/stanford_calendar"
    manifest = json.loads((audit / "source_manifest.json").read_text())
    for row in manifest["files"]:
        if sha256_file(root / row["path"]) != row["sha256"]:
            raise ValueError("Pinned calendar metadata changed")
    metadata = pd.read_csv(raw / "Joule_cell_id.csv")
    if metadata.Cell_id.isna().any() or metadata.Cell_id.duplicated().any():
        raise ValueError("Calendar identities are incomplete or ambiguous")
    listing = json.loads((audit / "osf_root.json").read_text())
    archive_record = next(
        r for r in listing["data"] if r["attributes"]["name"] == "joule_declass_sum.zip"
    )
    selected_metadata = audit / "summary_archive_metadata.json"
    selected_metadata.write_text(json.dumps({"data": [archive_record]}, indent=2) + "\n")
    archive = raw / "joule_declass_sum.zip"
    destination = raw / "summary_release_v1"
    expected = archive_record["attributes"]["extra"]["hashes"]["sha256"]
    if (
        archive.stat().st_size != archive_record["attributes"]["size"]
        or sha256_file(archive) != expected
    ):
        raise ValueError("Calendar archive size or upstream SHA256 differs")
    with ZipFile(archive) as source:
        if sum(row.file_size for row in source.infolist()) > 100 * 1024**2:
            raise ValueError("Calendar summary archive exceeds the 100 MiB extraction budget")
    if not destination.exists():
        extraction = extract_verified(archive, selected_metadata, destination)
        (audit / "summary_extraction_receipt.json").write_text(
            json.dumps(extraction, indent=2) + "\n"
        )
    folder = json.loads((audit / "summary_files.json").read_text())["data"]
    expected_files = {r["attributes"]["name"]: r for r in folder}
    actual = list(destination.rglob("*_sum.json"))
    if len(actual) != len(expected_files) or {p.name for p in actual} != set(expected_files):
        raise ValueError("Calendar archive and current summary-folder file sets differ")
    tables, reports, exclusions, inputs = [], [], [], []
    for path in sorted(actual):
        digest = sha256_file(path)
        reference = expected_files[path.name]["attributes"]["extra"]["hashes"]["sha256"]
        if not reference or digest != reference:
            raise ValueError(f"Calendar member differs from upstream folder hash: {path.name}")
        cell_id = path.name.removesuffix("_sum.json")
        identity = metadata[metadata.Cell_id.eq(cell_id)]
        if len(identity) != 1:
            raise ValueError("Calendar summary lacks a unique inventory identity")
        inputs.append({"path": str(path.relative_to(root)), "sha256": digest})
        try:
            frame, report = parse_calendar_summary(path, identity.iloc[0].to_dict())
        except (ValueError, KeyError, TypeError) as error:
            exclusions.append({"cell_id": cell_id, "reason": str(error), "source_sha256": digest})
            continue
        tables.append(frame)
        reports.append(report)
    if not tables:
        raise ValueError("No accepted calendar histories")
    result = pd.concat(tables, ignore_index=True)
    output = root / "data/processed/calendar"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "calendar_checkpoints.csv"
    result.to_csv(path, index=False)
    audit_result = {
        "status": "summary_histories_audited; registration_and_predictive_validation_pending",
        "inventory_cells": len(metadata),
        "archive_cells": len(actual),
        "parsed_cells": len(reports),
        "parsed_checkpoint_rows": len(result),
        "inventory_without_summary": sorted(
            set(metadata.Cell_id) - set(result.cell_id) - {row["cell_id"] for row in exclusions}
        ),
        "parse_exclusions": exclusions,
        "cells_with_fewer_than_four_diagnostics": [
            r["cell_id"] for r in reports if r["diagnostics"] < 4
        ],
        "cell_audits": reports,
        "inputs": inputs,
        "archive_sha256": expected,
        "output_sha256": sha256_file(path),
        "source_manifest_sha256": sha256_file(audit / "source_manifest.json"),
        "code": {
            str(p.relative_to(root)): sha256_file(p)
            for p in [
                Path(__file__).resolve(),
                root / "scripts/extract_dataset.py",
                root / "src/second_life_battery/data/calendar.py",
            ]
        },
        "limitation": (
            "Calendar-only source. No M50T cell, mixed-aging decomposition "
            "or field calibration established."
        ),
    }
    (audit / "history_audit.json").write_text(json.dumps(audit_result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: audit_result[k]
                for k in [
                    "status",
                    "inventory_cells",
                    "archive_cells",
                    "parsed_cells",
                    "parsed_checkpoint_rows",
                    "parse_exclusions",
                ]
            },
            indent=2,
        )
    )
    return audit_result


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parent.parent)
