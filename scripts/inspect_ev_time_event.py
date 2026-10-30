"""Inspect one original W10 clock event without sorting, repairing or promoting records."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from second_life_battery.data.inventory import sha256_file


def inspect(root):
    plan_path = root / "outputs/transfer/source_audit/w10_batch2_raw_counter_event_selection.json"
    plan = json.loads(plan_path.read_text())
    entry = plan["files"][0]
    source = root / plan["raw_root"] / entry["path"]
    receipt_path = source.with_suffix(source.suffix + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    if receipt["remote_id"] != entry["remote_id"] or sha256_file(source) != receipt["sha256"]:
        raise ValueError("Raw clock-event workbook differs from acquisition receipt")
    target = 1450150.349228
    book = load_workbook(source, read_only=True, data_only=True)
    window, events, signal_points = [], [], {}
    minimum_native_delta = np.inf
    previous = None
    try:
        channels = [s for s in book if s.title.startswith("Channel_")]
        raw_sheets = [s for s in book if s.title.startswith("RawData_")]
        if len(channels) != 1 or len(raw_sheets) != 1:
            raise ValueError("Unexpected workbook measurement-sheet identities")
        rows = iter(channels[0].values)
        header = next(rows)
        expected = [
            "Date_Time",
            "Test_Time(s)",
            "Step_Time(s)",
            "Step_Index",
            "Cycle_Index",
            "Voltage(V)",
            "Current(A)",
            "Charge_Capacity(Ah)",
            "Discharge_Capacity(Ah)",
        ]
        if list(header[: len(expected)]) != expected:
            raise ValueError("Clock-event channel header/units differ")
        count = 0
        for number, row in enumerate(rows, start=2):
            if not any(value is not None for value in row):
                continue
            count += 1
            point = dict(zip(expected, row[: len(expected)]))
            native = pd.Timestamp(point["Date_Time"])
            time = float(point["Test_Time(s)"])
            if pd.isna(native) or not np.isfinite(time):
                raise ValueError("Missing source event clock")
            point["Date_Time"] = native.isoformat()
            point["source_row"] = number
            if previous is not None:
                native_delta = (native - pd.Timestamp(previous["Date_Time"])).total_seconds()
                minimum_native_delta = min(minimum_native_delta, native_delta)
                difference = time - previous["Test_Time(s)"]
                if difference <= 0:
                    events.append(
                        {
                            "before": previous,
                            "after": point,
                            "test_time_delta_s": difference,
                            "native_time_delta_s": native_delta,
                        }
                    )
            if abs(time - target) <= 2:
                window.append(point)
            previous = point
        print(
            json.dumps({"channel_rows_scanned": count, "time_reversals": len(events)}), flush=True
        )
        if not any(
            np.isclose(e["before"]["Test_Time(s)"], target, rtol=0, atol=1e-4) for e in events
        ):
            raise ValueError("Expected MAT time-reversal event not found in this raw export")
        rows = iter(raw_sheets[0].values)
        raw_header = next(rows)
        selected = {}
        for signal in ["Voltage(V)", "Current(A)", "Charge_Capacity(Ah)", "Discharge_Capacity(Ah)"]:
            matches = [i for i, value in enumerate(raw_header) if value == signal]
            if len(matches) != 1:
                raise ValueError("Independent raw signal field is ambiguous")
            end = matches[0]
            if list(raw_header[end - 4 : end]) != [
                "Test_Time(s)",
                "Step_Time(s)",
                "Cycle_Index",
                "Step_Index",
            ]:
                raise ValueError("Independent raw signal clock/step fields differ")
            selected[signal] = end
            signal_points[signal] = []
        for number, row in enumerate(rows, start=2):
            for signal, end in selected.items():
                if end >= len(row) or row[end - 4] is None or row[end] is None:
                    continue
                time = float(row[end - 4])
                if abs(time - target) <= 2:
                    signal_points[signal].append(
                        {
                            "source_row": number,
                            "test_time_s": time,
                            "step_time_s": row[end - 3],
                            "cycle_index": row[end - 2],
                            "step_index": row[end - 1],
                            "value": row[end],
                        }
                    )
    finally:
        book.close()
    result = {
        "status": "original_clock_event_review; no_recovery_or_feature_promotion",
        "source": str(source.relative_to(root)),
        "source_sha256": receipt["sha256"],
        "receipt_sha256": sha256_file(receipt_path),
        "plan_sha256": sha256_file(plan_path),
        "channel_rows": count,
        "channel_events": events,
        "minimum_native_delta_s": float(minimum_native_delta),
        "channel_event_window": window,
        "independent_signal_windows": signal_points,
        "limitation": "Original record order preserved. No reconstructed timestamps, reset "
        "semantics, exposure value or training permission is inferred.",
    }
    output = root / "outputs/transfer/source_counter_audit_v1/raw_event_probe"
    output.mkdir(exist_ok=False)
    (output / "event.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "code_sha256": sha256_file(Path(__file__).resolve()),
                "artifacts": {
                    p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"events": events, "source": str(source.relative_to(root))}, indent=2))
    return result


if __name__ == "__main__":
    inspect(Path(__file__).resolve().parent.parent)
