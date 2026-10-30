"""Inspect the licensed factory PV workbook without inventing interval power or units."""

import json
from datetime import date
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from second_life_battery.data.inventory import sha256_file


def daily_ledger(measurements, formulas, year):
    if list(measurements[6][:5]) != ["Month", "Date", "Inv-1", "Inv-2", "Main"]:
        raise ValueError("Unreviewed Jaipur output schema")
    records, excluded = [], []
    for number, row in enumerate(measurements[7:], start=8):
        if row[0] is None and row[1] is None:
            if any(value is not None for value in row):
                excluded.append(number)
            continue
        if any(
            not isinstance(value, (float, int)) or not np.isfinite(value) or value != int(value)
            for value in row[:2]
        ):
            raise ValueError("Jaipur month/day must be measured integer calendar identifiers")
        clock = date(year, int(row[0]), int(row[1])).isoformat()
        first, second, main = row[2:5]
        for value in [first, second, main]:
            if value is not None and (
                not isinstance(value, (int, float)) or not np.isfinite(value)
            ):
                raise ValueError("Jaipur reported output has a nonnumeric/nonfinite value")
        both_missing = first is None and second is None
        formula = formulas[number - 1][4]
        records.append(
            {
                "source_row": number,
                "date": clock,
                "inv1_reported_daily_output": first,
                "inv2_reported_daily_output": second,
                "main_reported_daily_output": main,
                "main_formula": formula if isinstance(formula, str) else None,
                "both_inverters_missing": both_missing,
                "main_zero_with_both_missing": both_missing and main == 0,
                "main_is_sum_formula": formula == f"=SUM(C{number}:D{number})",
            }
        )
    ledger = pd.DataFrame(records)
    if ledger.empty or ledger.date.duplicated().any():
        raise ValueError("Jaipur dates are absent or duplicated")
    return ledger, excluded


def audit(root):
    folder = root / "outputs/india_ci/pv_source_audit_20261029"
    source = root / "data/raw/india_jaipur_pv_v1/Solar_Panel_Data_Set.xlsx"
    listing_path = folder / "jaipur_files.json"
    entry = json.loads(listing_path.read_text())[0]
    receipt_path = source.with_suffix(".xlsx.receipt.json")
    receipt = json.loads(receipt_path.read_text())
    if (
        sha256_file(source) != entry["content_details"]["sha256_hash"]
        or receipt["verified_sha256"] != sha256_file(source)
        or source.stat().st_size != entry["content_details"]["size"]
    ):
        raise ValueError("Jaipur source differs from its published checksum/size")
    landing_path = folder / "jaipur_landing.html"
    text = landing_path.read_text().split("window.INITIAL_STATE = ", 1)[1]
    state, _ = json.JSONDecoder().raw_decode(text)
    snapshot = state["dataset"]["snapshot"]
    if (
        snapshot["id"] != "82jswfyz5p"
        or snapshot["version"] != 1
        or snapshot["licence"]["short_name"] != "CC BY 4.0"
    ):
        raise ValueError("Jaipur metadata identity/version/licence changed")
    books = [load_workbook(source, read_only=True, data_only=value) for value in [True, False]]
    try:
        if any(book.sheetnames != ["Sheet1", "Sheet2", "Sheet3"] for book in books):
            raise ValueError("Unreviewed Jaipur worksheet set")
        measurements, formulas = [list(book["Sheet1"].values) for book in books]
        other_rows = {
            name: sum(any(value is not None for value in row) for row in books[0][name].values)
            for name in ["Sheet2", "Sheet3"]
        }
    finally:
        for book in books:
            book.close()
    with ZipFile(source) as workbook:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheet = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        cell = next(cell for cell in sheet.findall(".//m:c", ns) if cell.attrib["r"] == "C4")
        raw_year = cell.find("m:v", ns).text
    if raw_year != "2022" or measurements[3][1] != "Year":
        raise ValueError("Jaipur metadata year is not the reviewed stored numeric year")
    ledger, excluded = daily_ledger(measurements, formulas, int(raw_year))
    expected = pd.date_range("2022-01-01", "2022-12-31", freq="D").strftime("%Y-%m-%d").tolist()
    if ledger.date.tolist() != expected or any(other_rows.values()):
        raise ValueError("Jaipur date coverage/empty-sheet expectations changed")
    complete = ledger.inv1_reported_daily_output.notna() & ledger.inv2_reported_daily_output.notna()
    differences = (
        ledger.main_reported_daily_output
        - ledger.inv1_reported_daily_output
        - ledger.inv2_reported_daily_output
    )[complete]
    output = folder / "workbook_audit"
    output.mkdir(exist_ok=False)
    ledger.to_csv(output / "reported_daily_output_ledger.csv", index=False)
    (output / "publisher_snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    missing_zero = ledger[ledger.main_zero_with_both_missing]
    result = {
        "status": "not_eligible_for_interval_PV_or_paired_controller_validation",
        "source_doi": snapshot["doi"],
        "licence": snapshot["licence"]["short_name"],
        "source_sha256": sha256_file(source),
        "source_bytes": source.stat().st_size,
        "inputs": {
            str(path.relative_to(root)): sha256_file(path)
            for path in [source, receipt_path, listing_path, landing_path]
        },
        "days": len(ledger),
        "date_range": [ledger.date.iloc[0], ledger.date.iloc[-1]],
        "within_day_timestamps": 0,
        "other_sheet_nonempty_rows": other_rows,
        "output_headers": list(measurements[6][2:5]),
        "inverter_units": "Not declared in the daily output headers; "
        "do not label kW or kWh by inference",
        "missing_inv1_days": int(ledger.inv1_reported_daily_output.isna().sum()),
        "missing_inv2_days": int(ledger.inv2_reported_daily_output.isna().sum()),
        "main_zero_with_both_inverters_missing_days": len(missing_zero),
        "these_zeros_have_explicit_sum_formula": bool(missing_zero.main_is_sum_formula.all()),
        "main_zero_missing_dates": missing_zero.date.tolist(),
        "complete_output_days": int(complete.sum()),
        "main_vs_inverter_sum_mismatch_days_at_1e_minus_7": int((differences.abs() > 1e-7).sum()),
        "year_cell": {
            "raw_numeric_value": raw_year,
            "date_formatted_reader_value": measurements[3][2].isoformat(),
            "basis": "Stored year plus explicit Month/Date columns, corroborated "
            "by publisher year; no invented within-day time",
        },
        "nondate_trailing_rows_preserved_as_exclusions": excluded,
        "duplicate_header_labels": sorted(
            {name for name in measurements[6] if measurements[6].count(name) > 1}
        ),
        "gaps": [
            "No subdaily generation records are released in this workbook",
            "No paired site demand, battery/BMS, tariff or export agreement",
            "Publisher describes 06:00-15:00 sampling; full-day interval coverage is unestablished",
            "Weather columns describe realized conditions, "
            "not forecasts available at an earlier origin",
        ],
        "decision": "Preserve as a dated C&I solar data-access lead; do not upsample, "
        "infer units, fill missing inverter output with Main=0, fit an interval forecast "
        "or replace the Delhi benchmark",
        "artifacts": {path.name: sha256_file(path) for path in output.iterdir()},
    }
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "days",
                    "complete_output_days",
                    "missing_inv1_days",
                    "missing_inv2_days",
                    "main_zero_with_both_inverters_missing_days",
                ]
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
