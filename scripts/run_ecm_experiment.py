"""Fit RPT-1 local pulse models and score strictly later same-cell diagnostics."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.models.ecm import fit_pulses, pulse_response
from second_life_battery.utils.study import begin, complete, verified, write_json


def run(config, audit, output, smoke=False):
    audited = verified(audit)
    settings = yaml.safe_load(Path(config).read_text())
    from second_life_battery.data.inventory import sha256_file

    if audited["inputs"][str(config.resolve().relative_to(Path.cwd()))] != sha256_file(config):
        raise ValueError("Pulse protocol differs from the sealed audit")
    record = begin(output, config, [audit / "completion.json"])
    sessions = json.loads((audit / "sessions.json").read_text())
    accepted = [r for r in sessions if r["status"] == "accepted"]
    if smoke:
        accepted = [r for r in accepted if r["cell_id"] == "G1"]
    scores, predictions, parameters = [], [], []
    for cell in sorted({r["cell_id"] for r in accepted}):
        training = [r for r in accepted if r["cell_id"] == cell and r["role"] == "calibration"]
        if len(training) != 1:
            raise ValueError(f"Missing unique preregistered RPT-1 calibration for {cell}")
        for model in settings["model_order"]:
            p, fit = fit_pulses(training[0]["windows"], model, settings["parameter_bounds"])
            parameters.append({"cell_id": cell, "model": model, **asdict(p), **fit})
            for item in accepted:
                if item["cell_id"] != cell:
                    continue
                for w in item["windows"]:
                    actual = np.asarray(w["voltage_v"])
                    predicted = pulse_response(w["time_s"], w["current_a"], actual[0], p)
                    # The measured initial anchor is an input, not a scored forecast.
                    error = (predicted[1:] - actual[1:]) * 1000
                    key = {
                        "cell_id": cell,
                        "session": item["session"],
                        "role": item["role"],
                        "step": w["step"],
                        "model": model,
                    }
                    scores.append(
                        {
                            **key,
                            "n": len(error),
                            "rmse_mv": float(np.sqrt(np.mean(error**2))),
                            "mae_mv": float(np.mean(abs(error))),
                            "bias_mv": float(error.mean()),
                            "max_error_mv": float(abs(error).max()),
                        }
                    )
                    predictions.extend(
                        {
                            **key,
                            "time_s": t,
                            "current_a": i,
                            "measured_v": v,
                            "predicted_v": y,
                            "scored": j > 0,
                        }
                        for j, (t, i, v, y) in enumerate(
                            zip(w["time_s"], w["current_a"], actual, predicted)
                        )
                    )
    out = Path(output)
    pd.DataFrame(scores).to_csv(out / "window_metrics.csv", index=False)
    pd.DataFrame(predictions).to_csv(out / "predictions.csv", index=False)
    pd.DataFrame(parameters).to_csv(out / "parameters.csv", index=False)
    numeric = ["rmse_mv", "mae_mv", "bias_mv", "max_error_mv"]
    per_cell = (
        pd.DataFrame(scores).groupby(["cell_id", "model", "role"])[numeric].mean().reset_index()
    )
    per_cell.to_csv(out / "per_cell.csv", index=False)
    summary = per_cell.groupby(["model", "role"])[numeric].mean().reset_index()
    summary.to_csv(out / "summary.csv", index=False)
    write_json(
        out / "scope.json",
        {
            "scope": settings["scope"],
            "ocv": settings["ocv_assumption"],
            "initial_state": settings["initial_state"],
            "acceptance": settings["numeric_acceptance"],
            "excluded_anchor": True,
            "temperature_mapping": "unresolved",
            "smoke": smoke,
            "independent_cells": False,
            "full_soc_validation": False,
        },
    )
    complete(
        out,
        record,
        physical_cells=len({r["cell_id"] for r in accepted}),
        scope=settings["scope"],
        prediction_rows=len(predictions),
        smoke=smoke,
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=Path("configs/battery_model_v1.yaml"), type=Path)
    p.add_argument("--audit", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--smoke", action="store_true")
    a = p.parse_args()
    run(a.config, a.audit, a.output, a.smoke)
