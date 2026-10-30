"""Verify causal feature provenance, eligible folds and domain shift before any fit."""

import json
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.transfer import audit_fold, physical_folds


def audit(root: Path) -> dict:
    folder = root / "outputs/transfer/source_audit"
    evidence_path = folder / "feature_provenance.json"
    evidence = json.loads(evidence_path.read_text())
    expected = {
        "source_sha256": "data/processed/transfer/source_checkpoints.csv",
        "target_sha256": "data/processed/transfer/target_checkpoints.csv",
        "registry_sha256": "configs/cell_registry.yaml",
        "protocol_sha256": "configs/transfer_protocol_v2.yaml",
        "selection_sha256": "outputs/transfer/source_audit/source_selection.json",
        "segment_selection_sha256": "outputs/transfer/source_audit/source_segments.json",
        "capacity_reference_sha256": (
            "outputs/transfer/source_audit/first_life_capacity_checkpoints.csv"
        ),
        "target_counter_audit_sha256": (
            "outputs/transfer/source_audit/target_exposure_counter_audit.json"
        ),
    }
    for key, path in expected.items():
        if evidence[key] != sha256_file(root / path):
            raise ValueError(f"Feature evidence changed: {path}")
    for path, digest in evidence["code"].items():
        if sha256_file(root / path) != digest:
            raise ValueError(f"Reconstruction code changed: {path}")
    target_provenance_path = root / "data/processed/transfer/target_provenance.json"
    target_evidence = json.loads(target_provenance_path.read_text())
    if (
        target_evidence["source_checkpoints_sha256"]
        != sha256_file(root / "data/processed/checkpoints.csv")
        or target_evidence["target_sha256"] != evidence["target_sha256"]
    ):
        raise ValueError("Target derivation evidence changed")
    for path, digest in target_evidence["code_sha256"].items():
        if sha256_file(root / path) != digest:
            raise ValueError(f"Target derivation code changed: {path}")
    protocol = yaml.safe_load((root / expected["protocol_sha256"]).read_text())
    registered = root / "outputs/transfer" / protocol["protocol_id"]
    registration = json.loads((registered / "registration.json").read_text())
    if (
        registration["protocol_sha256"] != evidence["protocol_sha256"]
        or sha256_file(registered / "protocol.yaml") != evidence["protocol_sha256"]
    ):
        raise ValueError("Current protocol differs from its sealed registration")
    source = pd.read_csv(root / expected["source_sha256"])
    target = pd.read_csv(root / expected["target_sha256"])
    cells = set(protocol["target"]["cells"])
    if set(source.cell_id) != cells or set(target.cell_id) != cells:
        raise ValueError("Source and target cell pools differ from the registration")
    folds = [audit_fold(source, target, fold, protocol) for fold in physical_folds(target)]
    result = {
        "status": "feature_gate_passed",
        "protocol_id": protocol["protocol_id"],
        "inputs": {path: sha256_file(root / path) for path in expected.values()},
        "feature_provenance_sha256": sha256_file(evidence_path),
        "target_provenance_sha256": sha256_file(target_provenance_path),
        "audit_code_sha256": sha256_file(Path(__file__).resolve()),
        "folds": folds,
        "limitations": [
            "Six independent physical cells; validation is not an independent new cohort.",
            "V5 supplies one source H1/min3 validation origin.",
            "First-life and second-life checkpoint horizons represent different time/Ah spacing.",
            "Domain shifts are reported, not corrected using validation/test statistics.",
            "Native timestamp timezones remain unverified.",
        ],
    }
    destination = root / "outputs/transfer" / protocol["protocol_id"] / "feature_gate.json"
    destination.parent.mkdir(exist_ok=True, parents=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "folds": len(folds), "path": str(destination)}))
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
