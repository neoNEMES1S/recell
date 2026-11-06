"""Replay a mapped BMS CSV; synthetic/lab records never become measured BMS evidence."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.bms import prepare_bms
from second_life_battery.models.ecm import Parameters, simulate
from second_life_battery.utils.study import begin, complete, write_json


def run(config, source, output, source_kind, case=None):
    contract = yaml.safe_load(config.read_text())
    inputs = [source, *([case] if case else [])]
    record = begin(output, config, inputs)
    start = time.perf_counter()
    data = prepare_bms(pd.read_csv(source), contract)
    parse_seconds = time.perf_counter() - start
    data["predicted_voltage_v"] = np.nan
    data["electrical_status"] = "unavailable: no verified initial-state/OCV/parameter case"
    data["health_status"] = "unavailable: diagnostic/history features not supplied"
    timings = []
    if case:
        model = json.loads(case.read_text())
        if model["source_kind"] != source_kind:
            raise ValueError("Electrical case and input source-kind declarations disagree")
        for (pack, cell), group in data.groupby(["pack_id", "cell_id"], sort=False):
            if (pack, cell) != (model["pack_id"], model["cell_id"]):
                continue
            if (group.quality != "ok").any() or len(group) < 2:
                data.loc[group.index, "electrical_status"] = "unavailable: invalid/gapped stream"
                continue
            elapsed = (group.timestamp - group.timestamp.iloc[0]).dt.total_seconds().to_numpy()
            start = time.perf_counter()
            try:
                values = simulate(
                    elapsed,
                    group.current_a.to_numpy(),
                    Parameters(**model["parameters"]),
                    **model["electrical"],
                )
            except ValueError as error:
                data.loc[group.index, "electrical_status"] = f"unavailable: {error}"
                continue
            timings.append(
                {
                    "pack_id": pack,
                    "cell_id": cell,
                    "records": len(group),
                    "batch_seconds": time.perf_counter() - start,
                }
            )
            data.loc[group.index, "predicted_voltage_v"] = values["voltage_v"]
            data.loc[group.index, "electrical_status"] = "electrical-only model replay"
    data.to_csv(output / "replay.csv", index=False)
    summary = {
        "source_kind": source_kind,
        "records": len(data),
        "quality_failures": int((data.quality != "ok").sum()),
        "arrival_timing_available": bool(data.arrival_timing_verified.all()),
        "measured_BMS_validation": False,
        "electrical_predictions": int(data.predicted_voltage_v.notna().sum()),
        "health_predictions": 0,
        "parse_seconds": parse_seconds,
        "batch_timings": timings,
        "live_latency": "not established; offline batch timing is not telemetry latency",
    }
    write_json(output / "summary.json", summary)
    complete(output, record, **summary)
    print(
        f"Replayed {len(data)} {source_kind} records; "
        f"{summary['quality_failures']} quality failures"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/bms_v1.yaml"))
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--source-kind", choices=["synthetic", "laboratory", "measured_BMS"], required=True
    )
    p.add_argument("--case", type=Path)
    a = p.parse_args()
    run(a.config, a.input, a.output, a.source_kind, a.case)
