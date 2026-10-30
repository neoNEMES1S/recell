"""Report a completed registered transfer comparison without promoting a client model."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.transfer import physical_folds
from second_life_battery.evaluation.transfer import analyze_transfer
from second_life_battery.utils.reproducibility import verify_artifacts


def report(root, *, protocol_version=2):
    if protocol_version not in {2, 3}:
        raise ValueError("Transfer report protocol version must be 2 or 3")
    prefix = protocol_version == 3
    protocol_path = root / f"configs/transfer_protocol_v{protocol_version}.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    registered = root / "outputs/transfer" / protocol["protocol_id"]
    run = registered / "comparison"
    completion_path = run / "completion.json"
    completion = json.loads(completion_path.read_text())
    if completion["status"] != "comparison_fits_complete; report_required":
        raise ValueError("Only the complete comparison matrix may produce a research report")
    verify_artifacts(run, completion["artifacts"])
    if completion["inputs"]["protocol"] != sha256_file(protocol_path):
        raise ValueError("Comparison protocol changed")
    paths = {
        "source": protocol["data"]["source_features"]
        if prefix
        else "data/processed/transfer/source_checkpoints.csv",
        "target": protocol["data"]["target"]
        if prefix
        else "data/processed/transfer/target_checkpoints.csv",
        "registry": "configs/cell_registry.yaml",
        "reference_settings": "outputs/lobo/config.yaml",
    }
    if prefix:
        paths["source_labels"] = protocol["data"]["source_labels"]
    for name, relative in paths.items():
        if completion["inputs"][name] != sha256_file(root / relative):
            raise ValueError(f"Comparison input changed: {name}")
    prediction_path = run / "predictions.csv"
    if completion["predictions_sha256"] != sha256_file(prediction_path):
        raise ValueError("Comparison predictions changed")
    gate_path = registered / "feature_gate.json"
    if completion["inputs"]["feature_gate"] != sha256_file(gate_path):
        raise ValueError("Feature gate changed since fitting")
    gate = json.loads(gate_path.read_text())
    folds = json.loads((run / "folds.json").read_text())
    expected = [asdict(fold) for fold in physical_folds(pd.read_csv(root / paths["target"]))]
    if json.loads(json.dumps(expected)) != folds:
        raise ValueError("Reported folds differ from physical-cell-disjoint construction")
    cells = [fold["test"] for fold in folds]
    results = analyze_transfer(pd.read_csv(prediction_path), protocol, cells)
    output = run / "report"
    output.mkdir(exist_ok=False)
    for name, table in results.items():
        table.to_csv(output / f"{name}.csv", index=False)
    primary = results["paired_comparisons"].iloc[0].to_dict()
    source_limitation = (
        (
            "W5 supplies one source validation origin per fit; source gradients use only "
            "verified prefixes and contain 3–18 origins across three or four cells per fold. "
            "The separately registered v3 expansion is not a result for the blocked v2 protocol. "
        )
        if prefix
        else "V5 provides only one source validation origin. "
    )
    text = (
        "# Registered transfer comparison\n\n"
        "Primary endpoint: equal-cell mean SOH RMSE at 10% context, horizon 1; "
        "seeds averaged within batteries first.\n\n"
        f"R2 minus R1: {primary['rmse_difference']:.8f} SOH; descriptive "
        f"95% paired-cell interval [{primary['bootstrap_low']:.8f}, "
        f"{primary['bootstrap_high']:.8f}]. "
        f"Interpretation: {primary['interpretation']}.\n\n"
        "Six batteries are the independent units. Origins and random seeds do not "
        "increase that sample size. Consult summary.csv for interval coverage, width "
        "and pinball loss together; per_cell_differences.csv for negative transfer; "
        "recovery_errors.csv and failure_cases.csv for failures; ../fit_times.csv for compute.\n\n"
        "Source/target ranges and horizon spacing remain in the pinned feature gate. "
        f"{source_limitation}Previously familiar target "
        "data are not an independent new validation cohort. This report establishes "
        "no measured life extension, Indian site savings or dashboard promotion.\n"
    )
    (output / "review.md").write_text(text)
    evidence = {
        "status": "comparison_report_complete; no_automatic_model_promotion",
        "primary": primary,
        "limitations": gate["limitations"],
        "completion_sha256": sha256_file(completion_path),
        "predictions_sha256": sha256_file(prediction_path),
        "feature_gate_sha256": sha256_file(gate_path),
        "code": {
            str(path.relative_to(root)): sha256_file(path)
            for path in [
                Path(__file__).resolve(),
                root / "src/second_life_battery/evaluation/transfer.py",
                root / "src/second_life_battery/evaluation/metrics.py",
            ]
        },
    }
    (output / "provenance.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-version", type=int, choices=[2, 3], default=2)
    args = parser.parse_args()
    try:
        result = report(
            Path(__file__).resolve().parent.parent, protocol_version=args.protocol_version
        )
        print(json.dumps({"status": result["status"], "primary": result["primary"]}, indent=2))
    except (ValueError, FileNotFoundError) as error:
        raise SystemExit(f"Transfer report gate closed: {error}") from error
