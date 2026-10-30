"""Derive sealed modeled PV while preserving original benchmark inputs."""

import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.pv_scenario import horizontal_pv_scenario
from second_life_battery.data.solar_resource import align_hourly_resource, parse_nasa_hourly


def prepare(root):
    config_path = root / "configs/india_public_pv_scenario_v1.yaml"
    config = yaml.safe_load(config_path.read_text())
    folder = root / "outputs/india_ci" / config["protocol_id"]
    registration_path = folder / "registration.json"
    registration = json.loads(registration_path.read_text())
    if (
        sha256_file(config_path) != registration["protocol_sha256"]
        or sha256_file(folder / "protocol.yaml") != registration["protocol_sha256"]
        or config["interval_minutes"] != 15
        or config["source_resolution_minutes"] != 60
    ):
        raise ValueError("PV scenario differs from its sealed assumptions")
    input_path = root / config["input"]
    evidence_path = root / config["resource_provenance"]
    if (
        sha256_file(input_path) != config["input_sha256"]
        or sha256_file(evidence_path) != config["resource_provenance_sha256"]
    ):
        raise ValueError("PV scenario source or aligned-resource evidence changed")
    evidence = json.loads(evidence_path.read_text())
    for relative, digest in evidence["code"].items():
        if sha256_file(root / relative) != digest:
            raise ValueError("Resource preparation implementation changed")
    receipt_path = root / "outputs/india_ci/source_audit/nasa_power_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    source_path = root / receipt["path"]
    if (
        sha256_file(receipt_path) != evidence["resource_receipt_sha256"]
        or sha256_file(source_path) != evidence["resource_sha256"]
        or sha256_file(source_path) != receipt["sha256"]
    ):
        raise ValueError("Original NASA source/receipt differs from resource evidence")
    if sha256_file(input_path) != evidence["output_sha256"]:
        raise ValueError("Aligned-resource table differs from its preparation result")
    resource = pd.read_csv(input_path)
    hourly = parse_nasa_hourly(json.loads(source_path.read_text()))
    aligned = align_hourly_resource(hourly, pd.to_datetime(resource.timestamp))
    columns = ["ghi_mean_w_m2", "ghi_wh_m2_interval", "ambient_temperature_c"]
    np.testing.assert_allclose(resource[columns], aligned[columns], rtol=0, atol=1e-10)
    result = horizontal_pv_scenario(resource, config["model"])
    if len(result) != evidence["selected_quarters"]:
        raise ValueError("PV conversion changes benchmark time coverage")
    grouped = result.groupby(result.timestamp.dt.floor("h")).agg(
        power_kw=("modeled_pv_ac_kw", "first"),
        energy_kwh=("modeled_pv_ac_kwh", "sum"),
        quarters=("modeled_pv_ac_kw", "size"),
    )
    balance = grouped.energy_kwh - grouped.power_kw * grouped.quarters * 0.25
    if balance.abs().max() > 1e-9:
        raise ValueError("PV scenario energy is not conserved across source-hour bins")
    output = folder / "conversion"
    data_path = root / "data/processed/india_ci/academic_load_modeled_pv_v1.csv"
    if output.exists() or data_path.exists():
        raise FileExistsError("Preserve completed PV scenarios; use a versioned amendment")
    output.mkdir(exist_ok=False)
    result.to_csv(data_path, index=False)
    dates = result.timestamp.dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
    result.groupby(dates).agg(
        modeled_pv_ac_kwh=("modeled_pv_ac_kwh", "sum"),
        modeled_pv_peak_kw=("modeled_pv_ac_kw", "max"),
    ).to_csv(output / "modeled_daily_totals.csv", index_label="date_ist")
    code_paths = [
        Path(__file__).resolve(),
        root / "src/second_life_battery/data/pv_scenario.py",
        root / "src/second_life_battery/data/solar_resource.py",
    ]
    for path in code_paths:
        (output / path.name).write_bytes(path.read_bytes())
    inputs = {
        str(path.relative_to(root)): sha256_file(path)
        for path in [
            config_path,
            registration_path,
            input_path,
            evidence_path,
            source_path,
            receipt_path,
        ]
    }
    report = {
        "status": "modeled_public_PV_input_prepared; no_forecast_controller_or_bill_validation",
        "inputs": inputs,
        "output": str(data_path.relative_to(root)),
        "output_sha256": sha256_file(data_path),
        "quarter_rows": len(result),
        "source_resolution_minutes": 60,
        "selected_unique_UTC_hour_bins": len(grouped),
        "source_hour_bin_quarter_counts": grouped.quarters.value_counts().sort_index().to_dict(),
        "modeled_pv_total_ac_kwh": float(result.modeled_pv_ac_kwh.sum()),
        "modeled_pv_peak_ac_kw": float(result.modeled_pv_ac_kw.max()),
        "modeled_AC_clipped_quarters": int(result.modeled_pv_ac_clipped.sum()),
        "maximum_hour_bin_energy_balance_error_kwh": float(balance.abs().max()),
        "model": config["model"],
        "limitations": config["limitations"],
        "code": {str(path.relative_to(root)): sha256_file(path) for path in code_paths},
        "runtime": {name: version(name) for name in ["numpy", "pandas"]},
        "artifacts": {path.name: sha256_file(path) for path in output.iterdir()},
    }
    (output / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in [
                    "status",
                    "quarter_rows",
                    "modeled_pv_total_ac_kwh",
                    "modeled_pv_peak_ac_kw",
                    "maximum_hour_bin_energy_balance_error_kwh",
                ]
            },
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parent.parent)
