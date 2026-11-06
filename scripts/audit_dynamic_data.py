"""Export reviewed local-pulse windows; reject incomplete sessions without imputation."""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import yaml

from second_life_battery.data.dynamic import pulse_windows
from second_life_battery.data.parser import merge_exports, read_channel
from second_life_battery.utils.study import begin, complete, write_json


def session(task):
    item, records, settings = task
    try:
        frame, duplicate = merge_exports(
            [
                read_channel(Path(settings["raw_dir"]), r, Path("data/interim/dynamic_v1"))
                for r in records
            ]
        )
        windows = pulse_windows(frame, settings)
        number = int(item["session"].split("_")[-1])
        role = "calibration" if number == 1 else "validation" if number == 2 else "test"
        return {
            "cell_id": item["cell_id"],
            "session": item["session"],
            "role": role,
            "status": "accepted",
            "duplicates_removed": duplicate,
            "source_hashes": {r["source_file"]: r["sha256"] for r in records},
            "windows": windows,
        }
    except (ValueError, KeyError) as error:
        return {
            "cell_id": item["cell_id"],
            "session": item["session"],
            "status": "rejected",
            "reason": str(error),
        }


def run(config, output, smoke=False, workers=3):
    settings = yaml.safe_load(Path(config).read_text())
    record = begin(output, config, [settings["inventory"], settings["sessions"]])
    inventory = json.loads(Path(settings["inventory"]).read_text())
    lookup = {r["source_file"]: r for r in inventory["files"]}
    items = [
        r
        for r in json.loads(Path(settings["sessions"]).read_text())
        if r["test_type"] == "capacity_with_pulses" and r["cell_id"] in settings["cells"]
    ]
    if smoke:
        items = [
            r for r in items if r["cell_id"] == "G1" and r["session"] in {"RPT_1", "RPT_2", "RPT_3"}
        ]
    tasks = [(r, [lookup[f] for f in r["source_files"]], settings) for r in items]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(session, tasks))
    write_json(Path(output) / "sessions.json", results)
    accepted = [r for r in results if r["status"] == "accepted"]
    complete(
        output,
        record,
        accepted_sessions=len(accepted),
        rejected_sessions=len(results) - len(accepted),
        windows=sum(len(r["windows"]) for r in accepted),
        smoke=smoke,
        full_ocv_soc_gate="not established",
        temperature_mapping="unresolved",
        scope=settings["scope"],
    )
    print(f"Audited {len(results)} sessions; {len(accepted)} accepted: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/battery_model_v1.yaml", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    run(args.config, args.output, args.smoke, args.workers)
