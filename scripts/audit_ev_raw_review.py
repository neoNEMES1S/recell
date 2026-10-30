"""Audit the pinned complete raw exports; do not promote them to training data."""

import json
from pathlib import Path

from openpyxl import load_workbook

from second_life_battery.data.ev_exposure import audit_raw_cycling_fragments
from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.parser import is_channel_sheet, read_channel


def audit_review(root):
    audit = root / "outputs/transfer/source_audit"
    selection_path = audit / "raw_review_selection.json"
    selection = json.loads(selection_path.read_text())
    if selection["source_selection_sha256"] != sha256_file(audit / "source_selection.json"):
        raise ValueError("Raw review differs from pinned source selection")
    if selection["protocol_sha256"] != sha256_file(root / "configs/transfer_protocol_v2.yaml"):
        raise ValueError("Raw review protocol mismatch")
    raw = root / selection["raw_root"]
    entries = {row["path"]: row for row in selection["files"]}
    results, inputs = [], {}
    for batch in selection["batches"]:
        frames = []
        try:
            for name in batch["ordered_paths"]:
                entry = entries[name]
                path = (raw / name).resolve()
                if not path.is_relative_to(raw.resolve()):
                    raise ValueError("Raw review path escapes source directory")
                receipt = json.loads(path.with_suffix(path.suffix + ".receipt.json").read_text())
                if (
                    receipt["remote_id"] != entry["remote_id"]
                    or receipt["sha256"] != sha256_file(path)
                    or entry["cell_id"] != batch["cell_id"]
                    or entry["number"] != batch["number"]
                ):
                    raise ValueError("Raw review identity/hash mismatch")
                inputs[name] = receipt["sha256"]
                book = load_workbook(path, read_only=True, data_only=True)
                try:
                    sheets = [name for name in book.sheetnames if is_channel_sheet(name)]
                finally:
                    book.close()
                if len(sheets) != 1:
                    raise ValueError("Ambiguous raw review measurement channel")
                frame = read_channel(
                    raw,
                    {
                        "source_file": name,
                        "sha256": receipt["sha256"],
                        "observation_table": sheets[0],
                    },
                    root / "data/interim/ev_channel",
                )
                frames.append(frame[["timestamp", "time_s", "current_a", "voltage_v"]])
                print(json.dumps({"fragment_read": name}), flush=True)
            result = {
                "status": "raw_measurements_verified; causal_diagnostic_gate_still_required",
                **audit_raw_cycling_fragments(frames),
            }
        except (ValueError, FileNotFoundError) as error:
            result = {"status": "raw_review_rejected_or_incomplete", "error": str(error)}
        results.append({"cell_id": batch["cell_id"], "number": batch["number"], **result})
        print(json.dumps(results[-1]), flush=True)
    report = {
        "status": "investigation_only; no_training_inputs_promoted",
        "batches": results,
        "selection_sha256": sha256_file(selection_path),
        "inputs": inputs,
        "code": {
            str(p.relative_to(root)): sha256_file(p)
            for p in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/ev_exposure.py",
                root / "src/second_life_battery/data/parser.py",
            ]
        },
    }
    (audit / "raw_review_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    audit_review(Path(__file__).resolve().parent.parent)
