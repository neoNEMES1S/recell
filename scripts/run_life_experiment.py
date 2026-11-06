"""Audit life-data availability; fit conditional baselines only with an explicit target contract."""

import argparse
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.life import life_inventory, threshold_event
from second_life_battery.models.life import remaining_to_threshold
from second_life_battery.utils.study import begin, complete, write_json


def run(config, output, smoke=False):
    protocol = yaml.safe_load(config.read_text())
    record = begin(output, config, [protocol["data"]])
    frame = pd.read_csv(protocol["data"])
    if smoke:
        frame = frame[frame.cell_id == "G1"]
    life_inventory(frame).to_csv(output / "inventory.csv", index=False)
    definition, threshold = protocol["SOL_definition"], protocol["threshold"]
    if definition is None or threshold is None:
        write_json(
            output / "scope.json",
            {
                "SOL": "unconfirmed",
                "threshold": threshold,
                "status": "inventory only",
                "life_validation": False,
                ("reason"): (
                    "No approved life definition, application-specific threshold or event cohort"
                ),
            },
        )
        complete(
            output,
            record,
            scope="inventory only; no SOL/RUL fit",
            smoke=smoke,
            cells=int(frame.cell_id.nunique()),
            life_validation=False,
        )
        print(
            "Life inventory complete; SOL/threshold remain unconfirmed, no lifetime labels invented"
        )
        return
    if definition != "remaining_useful_life" or protocol["axis"] not in {
        "elapsed_days",
        "cumulative_ah",
    }:
        raise ValueError(
            "Only explicitly defined RUL in elapsed days or cumulative Ah is implemented"
        )
    events, predictions = [], []
    for cell, part in frame.groupby("cell_id"):
        part = part.sort_values(protocol["axis"])
        axis, health = part[protocol["axis"]].to_numpy(), part.soh.to_numpy()
        events.append({"cell_id": cell, **threshold_event(axis, health, threshold)})
        for origin in range(2, len(part) - 1):
            estimate = remaining_to_threshold(axis[: origin + 1], health[: origin + 1], threshold)
            predictions.append(
                {
                    "cell_id": cell,
                    "origin": float(axis[origin]),
                    "unit": protocol["axis"],
                    **estimate,
                }
            )
    pd.DataFrame(events).to_csv(output / "events.csv", index=False)
    pd.DataFrame(predictions).to_csv(output / "conditional_predictions.csv", index=False)
    write_json(
        output / "scope.json",
        {
            "SOL": definition,
            "threshold": threshold,
            "life_validation": False,
            "status": "conditional baseline; no independent event scoring",
            "assumption": "future linear trend equals observed past trend",
        },
    )
    complete(output, record, scope="conditional baseline only", life_validation=False, smoke=smoke)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=Path("configs/life_v1.yaml"), type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--smoke", action="store_true")
    a = p.parse_args()
    run(a.config, a.output, a.smoke)
