"""Inventory usable original-cell prefixes without changing the sealed v2 feature gate."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.ev_prefix import verified_source_prefixes
from second_life_battery.data.inventory import sha256_file


def audit(root):
    folder = root / "outputs/transfer/source_audit"
    progress_path = folder / "reconstruction_progress.json"
    progress = json.loads(progress_path.read_text())
    if progress["pending_inputs"]:
        raise ValueError("Original source acquisition is incomplete")
    inputs = {str(progress_path.relative_to(root)): sha256_file(progress_path)}
    for key, name in [
        ("source_selection_sha256", "source_selection.json"),
        ("segment_selection_sha256", "source_segments.json"),
    ]:
        path = folder / name
        if sha256_file(path) != progress[key]:
            raise ValueError("Original source selection changed")
        inputs[str(path.relative_to(root))] = progress[key]
    for name, digest in progress["code"].items():
        if sha256_file(root / name) != digest:
            raise ValueError("Original reconstruction code or reviewed evidence changed")
        inputs[name] = digest
    registry_path = root / "configs/cell_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    identities = {r["first_life_source_id"]: r["physical_cell_id"] for r in registry["cells"]}
    inputs[str(registry_path.relative_to(root))] = sha256_file(registry_path)
    selection = json.loads((folder / "source_selection.json").read_text())
    raw = (root / selection["raw_root"]).resolve()
    blocked = {(r["cell_id"], r["number"]) for r in progress["failed_cycling_batches"]}
    diagnostics, batches = [], []
    checked_files = {}
    for kind, destination in [("diagnostic", diagnostics), ("cycling", batches)]:
        for path in sorted((folder / "reconstruction_cache").glob(f"{kind}_*.json")):
            _, cell, number = path.stem.split("_")
            number = int(number)
            if kind == "cycling" and (cell, number) in blocked:
                continue
            record = json.loads(path.read_text())
            if record["code"] != progress["code"]:
                raise ValueError("Unit cache differs from the completed reconstruction audit")
            inputs[str(path.relative_to(root))] = sha256_file(path)
            for name, digest in record["inputs"].items():
                source = (raw / name).resolve()
                if not source.is_relative_to(raw):
                    raise ValueError("Unit source escapes the raw dataset")
                if name not in checked_files:
                    receipt_path = source.with_suffix(source.suffix + ".receipt.json")
                    receipt = json.loads(receipt_path.read_text())
                    actual = sha256_file(source)
                    if receipt["sha256"] != actual:
                        raise ValueError("Unit raw file differs from acquisition receipt")
                    checked_files[name] = actual
                    inputs[str(source.relative_to(root))] = actual
                    inputs[str(receipt_path.relative_to(root))] = sha256_file(receipt_path)
                if checked_files[name] != digest:
                    raise ValueError("Unit raw file differs from reconstruction evidence")
            destination.append(
                {
                    **record["result"],
                    "cell_id": cell,
                    "physical_cell_id": identities[cell],
                    "diagnostic" if kind == "diagnostic" else "number": number,
                    "source_hashes": json.dumps(record["inputs"], sort_keys=True),
                }
            )
    if (
        len(diagnostics) != progress["verified_diagnostics"]
        or len(batches) != progress["verified_cycling_batches"]
    ):
        raise ValueError("Accepted cache coverage differs from the completed audit")
    features, labels, availability = verified_source_prefixes(
        pd.DataFrame(diagnostics), pd.DataFrame(batches)
    )
    target_path = root / "data/processed/transfer/target_checkpoints.csv"
    target = pd.read_csv(target_path)
    inputs[str(target_path.relative_to(root))] = sha256_file(target_path)
    for identity, group in labels.groupby("physical_cell_id"):
        following = target[target.physical_cell_id.eq(identity)]
        if (
            following.empty
            or group.diagnostic_end_time.max()
            >= pd.to_datetime(following.timestamp, format="ISO8601").min()
        ):
            raise ValueError("Original source capacity labels overlap the target life stage")
    output = (
        root
        / "outputs/transfer/source_prefix_availability_v1"
        / datetime.now(timezone.utc).strftime("audit_%Y%m%dT%H%M%S%fZ")
    )
    output.mkdir(parents=True, exist_ok=False)
    features.to_csv(output / "verified_feature_prefixes.csv", index=False)
    labels.to_csv(output / "verified_capacity_labels.csv", index=False)
    availability.to_json(output / "availability.json", orient="records", indent=2)
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "status": "availability_only; v2_gate_remains_closed; no_training_authorization",
        "inputs": inputs,
        "prefix_code_sha256": sha256_file(root / "src/second_life_battery/data/ev_prefix.py"),
        "rejected_batches": progress["failed_cycling_batches"],
        "limitations": "Each input history stops at its first unavailable interval. "
        "Later capacity labels remain separate from unavailable future covariates. "
        "No source pool, validation role, protocol or model is changed by this audit.",
        "artifacts": {p.name: sha256_file(p) for p in output.iterdir()},
    }
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(availability.to_json(orient="records", indent=2), flush=True)
    print(json.dumps({"output": str(output.relative_to(root))}), flush=True)
    return result


if __name__ == "__main__":
    audit(Path(__file__).resolve().parent.parent)
