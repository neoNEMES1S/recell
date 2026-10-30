"""Audit original sensor metadata without equating an auxiliary index with a physical probe."""

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from second_life_battery.data.inventory import sha256_file


def global_record(table):
    preview = table["preview"]
    if not table["scan_complete"] or len(preview) != table["nonempty_rows_including_preamble"]:
        raise ValueError("Partial Global_Info preview cannot establish missing assignment fields")
    headers = [
        i
        for i, row in enumerate(preview)
        if "Channel" in row["values"] and "Comments" in row["values"]
    ]
    if len(headers) != 1 or headers[0] + 2 != len(preview):
        raise ValueError("Unreviewed Global_Info channel-record layout")
    index = headers[0]
    row = dict(zip(preview[index]["values"], preview[index + 1]["values"]))
    if "Item ID" not in row:
        raise ValueError("Global_Info omits the expected assignment identifier field")
    return {
        "instrument_channel": row["Channel"],
        "comments": row["Comments"],
        "item_id": row["Item ID"],
        "has_auxiliary_channels": row.get("Has Aux"),
    }


def audit(root):
    manifest_path = root / "outputs/inventory/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    raw = Path(manifest["raw_dir"]).resolve()
    output = root / "outputs/calendar/target_temperature_audit_v1"
    if output.exists():
        raise FileExistsError("Preserve the completed target-temperature audit")
    inputs = {str(manifest_path.relative_to(root)): sha256_file(manifest_path)}
    channels, assignments, scripts = [], [], []
    for entry in manifest["files"]:
        if entry["extension"] not in {".xlsx", ".m"}:
            continue
        path = (raw / entry["source_file"]).resolve()
        if not path.is_relative_to(raw) or sha256_file(path) != entry["sha256"]:
            raise ValueError("Original temperature-metadata source differs from its inventory")
        inputs[str(path.relative_to(root))] = entry["sha256"]
        if entry["extension"] == ".m":
            text = path.read_text(errors="replace")
            hits = [
                number
                for number, line in enumerate(text.splitlines(), 1)
                if re.search(r"temperature|thermocouple|sensor|\baux\b|\bTC\d*\b", line, re.I)
            ]
            scripts.append(
                {"source": entry["source_file"], "temperature_keyword_line_numbers": hits}
            )
            continue
        for table in entry["tables"]:
            if table["name"] == "Global_Info":
                assignments.append({"source": entry["source_file"], **global_record(table)})
            if not table["name"].startswith("Channel_"):
                continue
            if not table["scan_complete"]:
                raise ValueError("Incomplete measurement-table metadata scan")
            temperatures = [
                name
                for name in table["detected_columns"]
                if isinstance(name, str) and "Temperature" in name
            ]
            channels.append(
                {
                    "source": entry["source_file"],
                    "source_sha256": entry["sha256"],
                    "source_cell_id": entry["cell_id"],
                    "test_type": entry["test_type"],
                    "sheet": table["name"],
                    "temperature_columns": temperatures,
                    "auxiliary_column_count": len(temperatures),
                    "observations": table["number_of_observations"],
                    "date_time_coverage": table["date_time_coverage"],
                }
            )
    if len(channels) != 529 or len(assignments) != 529 or len(scripts) != 15:
        raise ValueError("Sensor-metadata audit coverage differs from the inventoried release")
    schemas = Counter(tuple(row["temperature_columns"]) for row in channels)
    populated = [
        row
        for row in assignments
        if row["comments"] not in [None, ""] or row["item_id"] not in [None, ""]
    ]
    output.mkdir(parents=True, exist_ok=False)
    rows = [
        {
            **row,
            "temperature_columns": json.dumps(row["temperature_columns"], ensure_ascii=False),
            "date_time_coverage": json.dumps(row["date_time_coverage"]),
        }
        for row in channels
    ]
    pd.DataFrame(rows).to_csv(output / "channel_inventory.csv", index=False)
    (output / "global_info_records.json").write_text(json.dumps(assignments, indent=2) + "\n")
    (output / "author_script_keyword_review.json").write_text(json.dumps(scripts, indent=2) + "\n")
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "status": "physical_probe_mapping_unresolved; "
        "no_temperature_feature_or_calendar_application",
        "inputs": inputs,
        "xlsx_sources_hash_verified": sum(name.endswith(".xlsx") for name in inputs),
        "measurement_sheets": len(channels),
        "global_info_records": len(assignments),
        "complete_assignment_fields_with_content": populated,
        "temperature_column_schemas": [
            {"columns": list(schema), "measurement_sheets": count}
            for schema, count in schemas.items()
        ],
        "rows_in_sheets_with_temperature_columns": sum(
            r["observations"] for r in channels if r["temperature_columns"]
        ),
        "rows_in_sheets_without_temperature_columns": sum(
            r["observations"] for r in channels if not r["temperature_columns"]
        ),
        "paper_evidence_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11639452/",
        "paper_scope": "Setup describes T-type thermocouples at cell center surfaces; "
        "protocol table temperatures are chamber setpoints, not probe assignments.",
        "unresolved": [
            "No channel/auxiliary-index to physical-cell/probe mapping is established "
            "by reviewed headers and Global_Info",
            "Encoded header unit is preserved; no silent Celsius conversion",
            "Native timestamp timezone and unrecorded storage-period temperature remain unresolved",
            "Opaque MATLAB objects were not decoded; this is not proof no mapping exists anywhere",
            "Nominal chamber settings and outdoor weather do not replace measured cell temperature",
        ],
        "required_external_metadata": [
            "Dated mapping: physical cell, cycler channel, auxiliary index, "
            "probe ID/location and temperature unit",
            "Calibration/status flags and changes across campaign segments",
            "Cell or chamber temperature logs during offline calendar-storage periods",
        ],
        "decision": "Retain temperature exclusion and calendar application gate; "
        "no v3 model, original checkpoint, wear objective or dashboard is changed",
        "artifacts": {path.name: sha256_file(path) for path in output.iterdir()},
    }
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "xlsx_sources_hash_verified",
                    "measurement_sheets",
                    "global_info_records",
                    "temperature_column_schemas",
                ]
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
