"""Export a hash-verified numeric local-pulse case; does not claim MATLAB execution."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import savemat

from second_life_battery.utils.study import begin, complete, verified, write_json


def run(config, run_dir, output, cell="G1", session="RPT_3", step=10):
    verified(run_dir)
    record = begin(output, config, [run_dir / "completion.json"])
    predictions = pd.read_csv(run_dir / "predictions.csv")
    data = predictions[
        (predictions.cell_id == cell)
        & (predictions.session == session)
        & (predictions.step == step)
        & (predictions.model == "1rc")
    ]
    if data.empty:
        raise ValueError("Requested measured case is absent")
    params = pd.read_csv(run_dir / "parameters.csv")
    p = params[(params.cell_id == cell) & (params.model == "1rc")].iloc[0]
    i0, v0 = data.current_a.iloc[0], data.measured_v.iloc[0]
    arrays = {
        "time_s": data.time_s.to_numpy(),
        "current_a": data.current_a.to_numpy(),
        "measured_v": data.measured_v.to_numpy(),
        "python_v": data.predicted_v.to_numpy(),
        "r0": p.r0_ohm,
        "r1": p.r1_ohm,
        "tau": p.tau_s,
        "ocv": v0 + i0 * (p.r0_ohm + p.r1_ohm),
        "v_initial": i0 * p.r1_ohm,
    }
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("Only finite numeric MATLAB input is supported")
    savemat(output / "case.mat", arrays, oned_as="column")
    data.to_csv(output / "case.csv", index=False)
    write_json(
        output / "case.json",
        {
            "cell": cell,
            "session": session,
            "step": step,
            "scope": "local constant-OCV pulse; no SOC/thermal model validation",
            "current_hold": "left zero-order hold; terminal drop uses current sample",
            "matlab_executed": False,
            "numerical_voltage_tolerance_v": 0.0001,
        },
    )
    complete(output, record, matlab_executed=False, source_kind="measured laboratory pulse")
    print(f"Numeric Simscape handoff exported: {output}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/battery_model_v1.yaml"))
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cell", default="G1")
    p.add_argument("--session", default="RPT_3")
    p.add_argument("--step", type=int, default=10)
    a = p.parse_args()
    run(a.config, a.run, a.output, a.cell, a.session, a.step)
