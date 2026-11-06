"""Only checked implementation artifacts enter the client snapshot."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from second_life_battery.data.inventory import sha256_file
from second_life_battery.utils.study import verified

STUDIES = {
    "audit": "outputs/ecm/local_pulse_ecm_v1/audit",
    "ecm": "outputs/ecm/local_pulse_ecm_v1/comparison",
    "selection": "outputs/model_selection/health_selection_v1/comparison",
    "simscape": "outputs/simscape/local_pulse_v1",
    "bms": "outputs/bms/synthetic_replay_v1",
    "life": "outputs/life/life_inventory_v1",
    "review": "outputs/implementation/proposal_v1/review",
}

# Software and external evidence are deliberately different columns, not a readiness percentage.
PACKAGES = [
    (
        "C00",
        "Baseline and resources",
        "software_verified",
        "222 baseline tests; local CPU",
        "MATLAB/DGX access unconfirmed",
    ),
    (
        "C01",
        "Contracts and protocols",
        "software_verified",
        "Versioned units, roles and bounded candidate settings",
        "SOL and scientific acceptance thresholds unconfirmed",
    ),
    (
        "C02",
        "Waveform audit",
        "evidence_verified",
        "111 laboratory sessions; 333 local pulse windows",
        "No global equilibrium OCV/SOC map or probe mapping",
    ),
    (
        "C03",
        "Dynamic electrical model",
        "software_verified",
        "Rint/1-RC with analytic and independent ODE tests",
        "Full SOC/thermal physical validation open",
    ),
    (
        "C04",
        "Measured pulse comparison",
        "evidence_verified",
        "RPT-1 calibration; RPT-2 validation; later same-cell tests",
        "Not an unseen-cell or pack test; numerical target not agreed",
    ),
    (
        "C05",
        "Simscape counterpart",
        "waiting_external",
        "Numeric exporter checked; source handoff prepared",
        "MATLAB/Simscape source has not been compiled or executed",
    ),
    (
        "C06",
        "AI optimization and DGX",
        "software_verified",
        "270 CPU trials; per-fold validation selection; 2,610 test forecasts",
        "Actual DGX run and independent cohort remain unavailable",
    ),
    (
        "C07",
        "Health-to-model bridge",
        "software_verified",
        "Capacity-reference and causal-cutoff tests",
        "Measured full-OCV coupled comparison not established",
    ),
    (
        "C08",
        "BMS adapter and replay",
        "software_verified",
        "60 explicitly synthetic electrical replay records; quality tests",
        "No real BMS integration or validated live timing; no health output",
    ),
    (
        "C09",
        "SOL and life",
        "waiting_external",
        "Six-cell inventory; tested threshold/censoring primitives",
        "SOL/threshold/event cohort unconfirmed; no lifetime validation",
    ),
    (
        "C10",
        "Independent checks",
        "software_verified",
        "175,824 pulse rows and all health trials/predictions replayed",
        "Calculation review is not an independent physical cohort",
    ),
    (
        "C11",
        "Dashboard and handoff",
        "software_verified",
        "Saved evidence, formulas, source hashes and review report",
        "External proposal requirements remain explicitly open",
    ),
]


def build_implementation_payload(root: Path):
    sources, completions = [], {}
    for name, relative in STUDIES.items():
        folder = root / relative
        complete = verified(folder, input_root=root)
        completions[name] = complete
        sources.append(
            {
                "path": f"{relative}/completion.json",
                "sha256": sha256_file(folder / "completion.json"),
            }
        )

    def read(name, filename):
        path = root / STUDIES[name] / filename
        sources.append({"path": str(path.relative_to(root)), "sha256": sha256_file(path)})
        return json.loads(path.read_text())

    def table(name, filename):
        path = root / STUDIES[name] / filename
        frame = pd.read_csv(path)
        sources.append(
            {"path": str(path.relative_to(root)), "sha256": sha256_file(path), "rows": len(frame)}
        )
        return json.loads(frame.to_json(orient="records", double_precision=12))

    check = read("review", "verification.json")
    for name in ["ecm", "audit", "selection"]:
        path = root / STUDIES[name]
        if check["completion_hashes"][str(Path(STUDIES[name]))] != sha256_file(
            path / "completion.json"
        ):
            raise ValueError("Implementation review belongs to a different completed study")
    predictions = pd.read_csv(root / STUDIES["ecm"] / "predictions.csv")
    test = predictions[predictions.role == "test"]
    paths = []
    for (cell, session, step), part in test.groupby(["cell_id", "session", "step"]):
        a = part[part.model == "rint"].sort_values("time_s")
        b = part[part.model == "1rc"].sort_values("time_s")
        if (
            not np.array_equal(a.time_s, b.time_s)
            or len(a) < 2
            or not np.isfinite(a[["time_s", "measured_v", "current_a", "predicted_v"]]).all().all()
        ):
            raise ValueError("Displayed pulse paths must have identical complete finite clocks")
        values = np.c_[a.time_s, a.current_a, a.measured_v, a.predicted_v, b.predicted_v]
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite candidate path")
        paths.append(
            {
                "cell_id": cell,
                "session": session,
                "step": int(step),
                "rows": values.round(10).tolist(),
            }
        )
    if len(paths) != 297 or check["ecm_rows_checked"] != len(predictions):
        raise ValueError("Implementation evidence does not cover the registered pulse study")
    audit = completions["audit"]
    if audit["accepted_sessions"] != 111 or audit["windows"] != 333:
        raise ValueError("Implementation status no longer matches reviewed waveform coverage")
    return {
        "packages": [
            dict(zip(["id", "name", "status", "implemented", "remaining"], row)) for row in PACKAGES
        ],
        "audit": {k: audit[k] for k in ["accepted_sessions", "rejected_sessions", "windows"]},
        "ecm": {
            "summary": table("review", "ecm_summary.csv"),
            "per_cell": table("review", "ecm_per_cell.csv"),
            "parameters": table("ecm", "parameters.csv"),
            "primary": read("review", "ecm_primary.json"),
            "paths": paths,
            "columns": ["time_s", "current_a", "measured_v", "rint_v", "one_rc_v"],
        },
        "selection": {
            "summary": table("review", "health_summary.csv"),
            "per_cell": table("selection", "per_cell.csv"),
            "selections": read("selection", "selections.json"),
            "primary": read("review", "health_primary.json"),
            "runtime": read("selection", "runtime.json"),
            "trials": completions["selection"]["trials"],
        },
        "bms": read("bms", "summary.json"),
        "life": {"inventory": table("life", "inventory.csv"), "scope": read("life", "scope.json")},
        "verification": check,
        "sources": sources,
        "report": "reports/recell_model_implementation_review.pdf",
    }
