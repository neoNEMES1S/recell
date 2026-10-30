"""Calendar-only diagnostic summaries; never append these rows to cycling histories."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from second_life_battery.data.inventory import sha256_file

CAPACITY = "RPT0.2C_2_D_capacity"


def parse_calendar_summary(path: Path, cell: dict) -> tuple[pd.DataFrame, dict]:
    """Audit the author's third low-rate discharge and preserve exclusions/comments."""
    if path.name != f"{cell.get('Cell_id')}_sum.json":
        raise ValueError("Calendar filename and physical-cell metadata disagree")
    payload = json.loads(path.read_text())
    summary = payload["summary_data"]
    # This release embeds the pandas column-oriented JSON as a JSON string.
    if isinstance(summary, str):
        summary = json.loads(summary)
    if not isinstance(summary, dict):
        raise ValueError("Expected a column-oriented calendar summary")
    frame = pd.DataFrame(summary)
    required = {CAPACITY, "Calendar_Time(date)", "Calendar_DateTime(days)", "diag_num"}
    if frame.empty or not required.issubset(frame):
        raise ValueError("Calendar capacity and clock fields are incomplete")
    frame["diagnostic"] = pd.to_numeric(frame.diag_num, errors="raise")
    if frame.diagnostic.isna().any() or frame.diagnostic.duplicated().any():
        raise ValueError("Calendar diagnostic identifiers must be present and unique")
    frame["timestamp"] = pd.to_datetime(frame["Calendar_Time(date)"], errors="raise")
    frame["author_elapsed_days"] = pd.to_numeric(frame["Calendar_DateTime(days)"], errors="raise")
    frame = frame.sort_values("diagnostic")
    if frame.timestamp.isna().any() or not frame.timestamp.is_monotonic_increasing:
        raise ValueError("Calendar dates must be present and must not go backwards")
    days = (frame.timestamp - frame.timestamp.iloc[0]).dt.total_seconds() / 86400
    author = frame.author_elapsed_days.to_numpy(dtype=float)
    if not np.isfinite(author).all() or not np.allclose(
        author - author[0], days, rtol=0, atol=1e-6
    ):
        raise ValueError("Calendar dates disagree with elapsed-day metadata")
    frame["capacity_ah"] = pd.to_numeric(frame[CAPACITY], errors="raise")
    usable = np.isfinite(frame.capacity_ah) & (frame.capacity_ah > 0)
    excluded = frame.loc[~usable, "diagnostic"].tolist()
    # Day-only clocks cannot establish ordering between distinct diagnostics.
    # Quarantine both ambiguous rows, rather than inventing dates or dropping the cell.
    ambiguous = frame.timestamp.duplicated(keep=False)
    ambiguous_diagnostics = frame.loc[ambiguous, "diagnostic"].tolist()
    frame = frame.loc[usable & ~ambiguous].copy()
    if frame.empty:
        raise ValueError("No usable third low-rate discharge capacities")
    reference = float(frame.capacity_ah.iloc[0])
    frame["reference_capacity_ah"] = reference
    frame["soh"] = frame.capacity_ah / reference
    frame["elapsed_days"] = (frame.timestamp - frame.timestamp.iloc[0]).dt.total_seconds() / 86400
    for key in ["Cell_id", "Cell_type", "Cell_chemistry", "SOC", "Temperature", "Lot"]:
        if key not in cell or pd.isna(cell[key]):
            raise ValueError(f"Missing calendar storage/cell metadata: {key}")
    if not 0 <= float(cell["SOC"]) <= 100 or not -40 <= float(cell["Temperature"]) <= 100:
        raise ValueError("Invalid calendar SOC or temperature units/range")
    frame["physical_cell_id"] = f"joule_calendar_{cell['Cell_id']}"
    frame["cell_id"] = cell["Cell_id"]
    frame["cell_type"] = cell["Cell_type"]
    frame["chemistry"] = cell["Cell_chemistry"]
    frame["lot"] = cell["Lot"]
    frame["storage_soc_fraction"] = float(cell["SOC"]) / 100
    frame["storage_temperature_c"] = float(cell["Temperature"])
    frame["capacity_protocol"] = CAPACITY
    frame["source_sha256"] = sha256_file(path)
    report = {
        "cell_id": cell["Cell_id"],
        "diagnostics": len(frame),
        "excluded_capacity_diagnostics": excluded,
        "ambiguous_same_date_diagnostics": ambiguous_diagnostics,
        "reference_capacity_ah": reference,
        "span_days": float(frame.elapsed_days.iloc[-1]),
        "positive_capacity_increments": int((frame.capacity_ah.diff() > 0).sum()),
        "author_summary_comment": payload.get("comment"),
        "author_inventory_comment": None if pd.isna(cell.get("Comment")) else cell["Comment"],
        "source_sha256": frame.source_sha256.iloc[0],
        "status": "parsed_for_separate_calendar_audit; not_M50T_calibration",
    }
    fields = [
        "physical_cell_id",
        "cell_id",
        "cell_type",
        "chemistry",
        "lot",
        "diagnostic",
        "timestamp",
        "author_elapsed_days",
        "elapsed_days",
        "capacity_ah",
        "reference_capacity_ah",
        "soh",
        "storage_soc_fraction",
        "storage_temperature_c",
        "capacity_protocol",
        "source_sha256",
    ]
    return frame[fields].reset_index(drop=True), report
