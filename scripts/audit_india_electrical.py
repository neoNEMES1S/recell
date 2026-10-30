"""Audit electrical billing readiness without reconstructing or inventing apparent energy."""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file


def audit(root):
    folder = root / "outputs/india_ci/source_audit/electrical_semantics_v1"
    receipt_path = folder / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    paper_record = next(row for row in receipt["sources"] if row["name"] == "iblend_bioc.xml")
    paper = folder / paper_record["name"]
    if paper_record["status"] != "acquired" or sha256_file(paper) != paper_record["sha256"]:
        raise ValueError("Primary I-BLEND paper text is not pinned")
    document = ET.parse(paper).getroot()
    if document.findtext(".//document/id") != "PMC6422068":
        raise ValueError("Electrical audit received a different paper")
    load_folder = root / "outputs/india_ci/india_iblend_academic_v1"
    evidence_path = load_folder / "load_provenance.json"
    evidence = json.loads(evidence_path.read_text())
    protocol_path = load_folder / "data_protocol.yaml"
    if sha256_file(protocol_path) != evidence["data_protocol_sha256"]:
        raise ValueError("Registered Indian load window changed")
    protocol = yaml.safe_load(protocol_path.read_text())
    source_name = "data/raw/india_iblend/acad_build_mains.csv"
    source = root / source_name
    if sha256_file(source) != evidence["inputs"][source_name]:
        raise ValueError("Audited academic-meter source changed")
    start, end = [pd.Timestamp(protocol[key]).timestamp() for key in ["start", "end_exclusive"]]
    rows = []
    columns = ["timestamp", "power", "power_factor", "voltage", "current"]
    for chunk in pd.read_csv(source, usecols=columns, chunksize=200_000):
        selected = chunk[chunk.timestamp.ge(start) & chunk.timestamp.lt(end)]
        if not selected.empty:
            rows.append(selected)
    frame = pd.concat(rows, ignore_index=True)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, unit="s", utc=True)
    expected = pd.date_range(
        pd.Timestamp(start, unit="s", tz="UTC"),
        pd.Timestamp(end, unit="s", tz="UTC"),
        freq="min",
        inclusive="left",
    )
    if not pd.DatetimeIndex(frame.timestamp).equals(expected):
        raise ValueError("Electrical audit window is not the complete registered minute grid")
    if not np.isfinite(frame[["power", "power_factor", "voltage", "current"]]).all().all():
        raise ValueError("Registered electrical readings include nonfinite values")
    if frame.power.lt(0).any() or frame.power_factor.abs().gt(1).any():
        raise ValueError("Unexpected active-power or power-factor domain")
    zero = frame.power_factor.eq(0) & frame.power.gt(0)
    negative = frame.power_factor.lt(0)
    absolute = frame.loc[frame.power_factor.ne(0), "power_factor"].abs()

    # Counterexamples illustrate information loss, not the release's undocumented resampling rule.
    p_a, pf_a = np.array([1.0, 1.0]), np.array([0.6, 0.6])
    p_b, pf_b = np.array([1.0, 1.0]), np.array([0.3, 0.9])
    assert np.isclose(p_a.mean(), p_b.mean()) and np.isclose(pf_a.mean(), pf_b.mean())
    apparent_a, apparent_b = np.mean(p_a / pf_a), np.mean(p_b / pf_b)
    assert not np.isclose(apparent_a, apparent_b)
    sign_pf = np.array([0.9, -0.9])
    assert sign_pf.mean() == 0 and np.isfinite(np.mean(p_a / abs(sign_pf)))
    voltage_a, current_a = np.array([240, 240, 240]), np.array([10, 10, 10])
    voltage_b, current_b = np.array([250, 240, 230]), np.array([20, 10, 0])
    assert voltage_a.mean() == voltage_b.mean() and current_a.mean() == current_b.mean()
    assert (voltage_a * current_a).sum() != (voltage_b * current_b).sum()
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "active_load_gate_unchanged; apparent_energy_billing_not_verified",
        "selected_minute_rows": len(frame),
        "negative_pf_minutes": int(negative.sum()),
        "zero_pf_positive_power_minutes": int(zero.sum()),
        "quarters_containing_zero_pf_positive_power": int(
            frame.loc[zero, "timestamp"].dt.floor("15min").nunique()
        ),
        "half_hours_containing_zero_pf_positive_power": int(
            frame.loc[zero, "timestamp"].dt.floor("30min").nunique()
        ),
        "days_containing_zero_pf_positive_power": int(
            frame.loc[zero, "timestamp"].dt.tz_convert("Asia/Kolkata").dt.date.nunique()
        ),
        "active_energy_sample_estimate_at_zero_pf_kwh": float(
            frame.loc[zero, "power"].sum() / 60 / 1000
        ),
        "positive_absolute_pf_quantiles": {
            str(q): float(absolute.quantile(q)) for q in [0, 0.01, 0.5, 0.99, 1]
        },
        "mathematical_counterexamples": {
            "scope": "Illustrations only; not inferred source sub-minute values",
            "same_mean_active_kw": float(p_a.mean()),
            "same_mean_pf": float(pf_a.mean()),
            "different_mean_apparent_kva": [float(apparent_a), float(apparent_b)],
            "signed_pf_cancellation_mean_pf": float(sign_pf.mean()),
            "signed_pf_cancellation_mean_apparent_kva": float(np.mean(p_a / abs(sign_pf))),
            "same_phase_mean_voltage_v": float(voltage_a.mean()),
            "same_phase_mean_current_a": float(current_a.mean()),
            "different_arithmetic_phase_apparent_va": [
                int((voltage_a * current_a).sum()),
                int((voltage_b * current_b).sum()),
            ],
        },
        "decision": "Negative PF is compatible with the EM6400 leading-load convention, "
        "not automatically an invalid reading or export. CSV-to-register mapping "
        "and release downsampling operator remain unverified. Neither P/abs(PF) "
        "nor a product of phase averages establishes metered apparent energy. "
        "No PF substitution, clipping, row deletion, synthetic kVAh or bill is produced.",
        "inputs": {
            source_name: sha256_file(source),
            str(evidence_path.relative_to(root)): sha256_file(evidence_path),
            str(protocol_path.relative_to(root)): sha256_file(protocol_path),
            str(paper.relative_to(root)): sha256_file(paper),
            str(receipt_path.relative_to(root)): sha256_file(receipt_path),
        },
        "code_sha256": sha256_file(Path(__file__).resolve()),
    }
    output = folder / "analysis"
    output.mkdir(exist_ok=False)
    frame.loc[zero, columns].to_csv(output / "zero_pf_positive_power_rows.csv", index=False)
    result["artifacts"] = {
        "zero_pf_positive_power_rows.csv": sha256_file(output / "zero_pf_positive_power_rows.csv")
    }
    (output / "billing_readiness.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in ["inputs", "artifacts", "mathematical_counterexamples"]
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
