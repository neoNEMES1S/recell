"""Forensic counter/integral agreement study; never promote counters to model features."""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.io import loadmat, whosmat

from second_life_battery.data.inventory import sha256_file


def candidate(step, capacity, settings):
    step, capacity = np.asarray(step, float).ravel(), np.asarray(capacity, float).ravel()
    if (
        len(step) != len(capacity)
        or len(step) < 2
        or not np.isfinite(step).all()
        or not np.isfinite(capacity).all()
        or (step < 0).any()
        or (step != np.floor(step)).any()
    ):
        raise ValueError("Counter audit requires matching finite integer-step observations")
    change = np.diff(step) != 0
    delta = np.diff(capacity)
    reset = (
        change
        & (capacity[1:] < settings["new_to_previous_ratio"] * capacity[:-1])
        & (delta < -settings["minimum_drop_ah"])
    )
    return {
        "candidate_total_ah": float(capacity[-1] - capacity[0] + capacity[:-1][reset].sum()),
        "candidate_resets": int(reset.sum()),
        "largest_within_step_decrease_ah": float(max(0, -delta[~change].min()))
        if (~change).any()
        else 0.0,
        "negative_counter_values": int((capacity < 0).sum()),
    }


def run(root):
    config_path = root / "configs/source_counter_audit_v1.yaml"
    protocol = yaml.safe_load(config_path.read_text())
    folder = root / "outputs/transfer" / protocol["audit_id"]
    registration = json.loads((folder / "registration.json").read_text())
    if (
        sha256_file(config_path) != registration["protocol_sha256"]
        or sha256_file(folder / "protocol.yaml") != registration["protocol_sha256"]
    ):
        raise ValueError("Counter candidate protocol changed after registration")
    manifest_path = folder / "reference_batches.json"
    if sha256_file(manifest_path) != protocol["reference_batches_sha256"]:
        raise ValueError("Counter reference batch manifest changed")
    references = json.loads(manifest_path.read_text())["batches"]
    settings = protocol["candidate"]
    toy = candidate([1, 1, 1, 7, 7], [0, 1.2, 1.19999, 0.0001, 0.5], settings)
    assert toy["candidate_resets"] == 1 and np.isclose(toy["candidate_total_ah"], 1.69999)
    ambiguous = candidate([1, 1, 1, 1], [0, 4, 0.1, 1], settings)
    assert ambiguous["candidate_resets"] == 0
    assert np.isclose(ambiguous["largest_within_step_decrease_ah"], 3.9)
    output = folder / "comparison"
    output.mkdir(exist_ok=False)
    rows = []
    verified = {}
    for reference in references:
        cache_path = root / reference["cache"]
        if sha256_file(cache_path) != reference["cache_sha256"]:
            raise ValueError("Dense-current comparison cache changed")
        cache = json.loads(cache_path.read_text())
        for relative, digest in cache["code"].items():
            if sha256_file(root / relative) != digest:
                raise ValueError("Original dense-integral derivation code/provenance changed")
        for relative, digest in cache["inputs"].items():
            path = root / protocol["raw_root"] / relative
            if relative not in verified:
                verified[relative] = sha256_file(path)
            if verified[relative] != digest:
                raise ValueError("Original dense-integral source input changed")
        path = root / reference["mat_path"]
        if sha256_file(path) != reference["mat_sha256"]:
            raise ValueError("Registered MAT counter source changed")
        record = {
            "cell_id": reference["cell_id"],
            "batch": reference["batch"],
            "previously_probed": reference["previously_probed"],
        }
        try:
            names = [name for name, _, _ in whosmat(path)]
            selected = {}
            for key, prefix in [
                ("step", "Step_Index_full_vec_"),
                ("charge", "ch_cap_full_vec_"),
                ("discharge", "dis_cap_full_vec_"),
            ]:
                matches = [name for name in names if name.startswith(prefix)]
                if len(matches) != 1:
                    raise ValueError(f"Counter variable identity is ambiguous: {prefix}")
                selected[key] = matches[0]
            values = loadmat(path, variable_names=list(selected.values()), squeeze_me=True)
            for direction in ["charge", "discharge"]:
                result = candidate(values[selected["step"]], values[selected[direction]], settings)
                expected = cache["result"][direction + "_ah"]
                if expected <= 0:
                    raise ValueError("Reference integral is not positive")
                record.update({direction + "_" + key: value for key, value in result.items()})
                record[direction + "_integral_ah"] = expected
                record[direction + "_relative_difference"] = (
                    abs(result["candidate_total_ah"] - expected) / expected
                )
            record["both_within_registered_tolerance"] = all(
                record[d + "_relative_difference"] <= protocol["agreement_relative_tolerance"]
                for d in ["charge", "discharge"]
            )
            record["status"] = "scored_not_authorized_for_recovery"
            del values
        except (ValueError, KeyError) as exc:
            record["status"] = "candidate_not_evaluable"
            record["error"] = str(exc)
            record["both_within_registered_tolerance"] = False
        rows.append(record)
        print(
            json.dumps(
                {
                    "completed": len(rows),
                    "total": len(references),
                    "cell": record["cell_id"],
                    "batch": record["batch"],
                    "within_tolerance": record["both_within_registered_tolerance"],
                }
            ),
            flush=True,
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "agreement.csv", index=False)
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "status": "forensic_agreement_study_complete; no_recovery_or_feature_promotion",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": registration["protocol_sha256"],
        "reference_batches_sha256": sha256_file(manifest_path),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "reference_batches": len(frame),
        "newly_scored_batches": int((~frame.previously_probed).sum()),
        "within_tolerance_batches": int(frame.both_within_registered_tolerance.sum()),
        "newly_scored_within_tolerance": int(
            ((~frame.previously_probed) & frame.both_within_registered_tolerance).sum()
        ),
        "limitation": "Agreement on clean batches does not identify raw reset semantics, "
        "resolve ambiguous clocks/counter rollbacks, certify corrupt MAT files, "
        "or amend the sealed v2 dense-current feature definition.",
        "verified_reference_inputs": verified,
        "artifacts": {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = run(Path(__file__).resolve().parent.parent)
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "reference_batches",
                    "within_tolerance_batches",
                    "newly_scored_within_tolerance",
                    "status",
                ]
            },
            indent=2,
        )
    )
