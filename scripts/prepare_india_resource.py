"""Align pinned historical resource to the fixed load grid without generating PV claims."""

import json
from pathlib import Path

import pandas as pd

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.solar_resource import align_hourly_resource, parse_nasa_hourly


def prepare(root: Path) -> dict:
    receipt_path = root / "outputs/india_ci/source_audit/nasa_power_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    source = root / receipt["path"]
    if sha256_file(source) != receipt["sha256"]:
        raise ValueError("NASA source response changed")
    run = root / "outputs/india_ci/india_iblend_academic_v1"
    load_evidence_path = run / "load_provenance.json"
    evidence = json.loads(load_evidence_path.read_text())
    load_path = root / "data/processed/india_ci/academic_benchmark_load_15min.csv"
    if evidence["outputs"][str(load_path.relative_to(root))] != sha256_file(load_path):
        raise ValueError("Registered benchmark load changed")
    protocol = run / "data_protocol.yaml"
    if evidence["data_protocol_sha256"] != sha256_file(protocol):
        raise ValueError("Registered load window changed")
    for path, digest in evidence["code"].items():
        if sha256_file(root / path) != digest:
            raise ValueError("Load preparation code changed; revalidate before alignment")
    hourly = parse_nasa_hourly(json.loads(source.read_text()))
    load = pd.read_csv(load_path)
    load["timestamp"] = pd.to_datetime(load.timestamp, utc=True, errors="raise")
    aligned = align_hourly_resource(hourly, load.timestamp)
    combined = load.merge(aligned, on="timestamp", validate="one_to_one")
    output = root / "data/processed/india_ci/academic_load_resource_15min.csv"
    combined.to_csv(output, index=False)
    result = {
        "status": "load_resource_aligned; no_PV_generation_or_bill_validation_yet",
        "resource_sha256": sha256_file(source),
        "resource_receipt_sha256": sha256_file(receipt_path),
        "load_sha256": sha256_file(load_path),
        "load_provenance_sha256": sha256_file(load_evidence_path),
        "data_protocol_sha256": sha256_file(protocol),
        "output_sha256": sha256_file(output),
        "resource_hours": len(hourly),
        "selected_quarters": len(combined),
        "source_resolution_minutes": 60,
        "units": receipt["parameters"],
        "coordinate_basis": receipt["coordinate_basis"],
        "alignment": (
            "Each hourly Wh/m^2 value is split equally across four quarters. "
            "The same value divided by 1 h gives mean W/m^2; no subhourly observations exist."
        ),
        "code": {
            str(path.relative_to(root)): sha256_file(path)
            for path in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/data/solar_resource.py",
            ]
        },
    }
    (run / "resource_provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({key: result[key] for key in ["status", "resource_hours", "selected_quarters"]})
    )
    return result


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parent.parent)
