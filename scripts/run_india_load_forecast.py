"""Run sealed day-ahead demand baselines, selecting weights before test scoring."""

import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.load_forecast import (
    load_error_tables,
    paired_load_interval,
    select_load_candidate,
)
from second_life_battery.models.load_forecast import seasonal_day_ahead


def run(root):
    config_path = root / "configs/india_load_forecast_v1.yaml"
    protocol = yaml.safe_load(config_path.read_text())
    run_dir = root / "outputs/india_ci" / protocol["protocol_id"]
    registration = json.loads((run_dir / "registration.json").read_text())
    if (
        sha256_file(config_path) != registration["protocol_sha256"]
        or sha256_file(run_dir / "protocol.yaml") != registration["protocol_sha256"]
    ):
        raise ValueError("Day-ahead forecast protocol differs from sealed registration")
    for name, digest in protocol["inputs"].items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"Registered demand input changed: {name}")
    load_dir = root / "outputs/india_ci/india_iblend_academic_v1"
    load_evidence = json.loads((load_dir / "load_provenance.json").read_text())
    for name, digest in {
        **load_evidence["inputs"],
        **load_evidence["outputs"],
        **load_evidence["code"],
    }.items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"Audited demand derivation changed: {name}")
    receipt_path = root / "outputs/india_ci/source_audit/iblend_selected_receipt.json"
    if sha256_file(receipt_path) != load_evidence["source_receipt_sha256"]:
        raise ValueError("Audited demand source receipt changed")
    receipt = json.loads(receipt_path.read_text())
    for name, field in [
        ("iblend_metadata.json", "metadata_sha256"),
        ("iblend_remote_directory.json", "directory_sha256"),
    ]:
        if sha256_file(receipt_path.parent / name) != receipt[field]:
            raise ValueError("Pinned demand source inventory changed")
    data_protocol = yaml.safe_load((load_dir / "data_protocol.yaml").read_text())
    data = pd.read_csv(root / "data/processed/india_ci/academic_benchmark_load_15min.csv")
    data["timestamp"] = pd.to_datetime(data.timestamp, utc=True, errors="raise")
    expected = pd.date_range(
        data_protocol["start"], data_protocol["end_exclusive"], freq="15min", inclusive="left"
    ).tz_convert("UTC")
    if (
        not pd.DatetimeIndex(data.timestamp).equals(expected)
        or not data.complete.eq(True).all()
        or data.load_kw.isna().any()
        or data.load_kw.lt(0).any()
        or len(data) != load_evidence["selected_intervals"]
    ):
        raise ValueError("Registered demand period is incomplete or invalid")
    for split, bounds in data_protocol["splits"].items():
        first, last = [
            pd.Timestamp(bounds[k]).tz_convert("UTC") for k in ["start", "end_exclusive"]
        ]
        selected = data.timestamp.ge(first) & data.timestamp.lt(last)
        if not data.loc[selected, "split"].eq(split).all():
            raise ValueError("Demand chronological labels differ from registered splits")
    candidates = protocol["forecast"]["candidates"]
    history = data.set_index("timestamp").load_kw

    def predict_partition(split):
        bounds = data_protocol["splits"][split]
        origins = pd.date_range(
            bounds["start"], bounds["end_exclusive"], freq="D", inclusive="left"
        )
        if len(origins) != protocol["evaluation"][f"{split}_days"]:
            raise ValueError("Registered evaluation day count differs")
        rows = []
        for origin in origins:
            predictions = seasonal_day_ahead(history[history.index < origin], origin, candidates)
            predictions = predictions.merge(
                data[["timestamp", "load_kw", "split"]], on="timestamp", validate="many_to_one"
            )
            if len(predictions) != 96 * len(candidates) or not predictions.split.eq(split).all():
                raise ValueError("Forecast labels are missing or cross partitions")
            if (predictions.latest_feature_interval_end > predictions.origin).any():
                raise ValueError("Day-ahead forecast uses an unavailable measurement")
            rows.append(predictions)
        return pd.concat(rows, ignore_index=True)

    output = run_dir / "forecast"
    output.mkdir(exist_ok=False)
    code_paths = [
        Path(__file__).resolve(),
        *[
            root / "src/second_life_battery" / name
            for name in [
                "models/load_forecast.py",
                "evaluation/load_forecast.py",
                "evaluation/metrics.py",
            ]
        ],
    ]
    code = {str(p.relative_to(root)): sha256_file(p) for p in code_paths}
    (output / "implementation_source.json").write_text(
        json.dumps({str(p.relative_to(root)): p.read_text() for p in code_paths}, indent=2) + "\n"
    )
    validation = predict_partition("validation")
    validation.to_csv(output / "validation_predictions.csv", index=False)
    val_scores, val_daily = load_error_tables(validation)
    val_scores.to_csv(output / "validation_summary.csv", index=False)
    val_daily.to_csv(output / "validation_daily.csv", index=False)
    selected = select_load_candidate(val_scores, candidates)
    decision = {
        "selected_model": selected,
        "day_weight": candidates[selected],
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "test_errors_scored_at_selection": False,
        "criterion": protocol["selection"],
        "validation_predictions_sha256": sha256_file(output / "validation_predictions.csv"),
        "validation_summary_sha256": sha256_file(output / "validation_summary.csv"),
    }
    (output / "selection.json").write_text(json.dumps(decision, indent=2) + "\n")
    test = predict_partition("test")
    test.to_csv(output / "test_predictions.csv", index=False)
    test_scores, test_daily = load_error_tables(test)
    test_scores.to_csv(output / "test_summary.csv", index=False)
    test_daily.to_csv(output / "test_daily.csv", index=False)
    settings = protocol["evaluation"]
    comparison = paired_load_interval(
        test_daily,
        selected,
        block_days=settings["bootstrap_block_days"],
        repetitions=settings["bootstrap_repetitions"],
        seed=settings["bootstrap_seed"],
    )
    (output / "paired_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    scores = test_scores.set_index("model")
    chosen, weekly, previous_day = [
        scores.loc[name] for name in [selected, "weekly", "previous_day"]
    ]
    note = (
        "# Indian public-building day-ahead forecast review\n\n"
        f"Validation selected **{selected}**, previous-day weight {candidates[selected]:g}, "
        "using only the 15 registered validation days. Its weight was saved before test "
        "scoring. At each local midnight, the next 96 quarters use only completed past "
        "intervals; observed past test days may supply later lag inputs.\n\n"
        f"Over 16 test days, selected RMSE is **{chosen.rmse_kw:.3f} kW**, "
        f"MAE {chosen.mae_kw:.3f} kW and bias {chosen.bias_kw:.3f} kW. Weekly "
        f"RMSE is {weekly.rmse_kw:.3f} kW; previous-day RMSE is "
        f"{previous_day.rmse_kw:.3f} kW. All five candidate scores are retained.\n\n"
        f"Selected-minus-weekly RMSE is {comparison['rmse_difference_kw']:.3f} kW; "
        "the descriptive 95% paired four-day circular-block bootstrap interval is "
        f"[{comparison['descriptive_low_95_kw']:.3f}, "
        f"{comparison['descriptive_high_95_kw']:.3f}] kW. One short seasonal "
        "window and serial dependence limit inference.\n\n"
        f"Selected mean daily peak absolute error is {chosen.mean_peak_absolute_error_kw:.3f} "
        f"kW; it underestimates peak magnitude on {int(chosen.underestimated_peak_days)} "
        "of 16 days. These are active-power profile peaks, not billing maximum demand.\n\n"
        "This is a historical one-building forecast benchmark with assumed zero measurement "
        "reporting delay. It is not live-controller, solar-forecast, customer bill, pack/BMS, "
        "battery-aging, field-savings or national generalization validation. No dashboard "
        "promotion or first-life gate change occurs.\n"
    )
    (output / "review.md").write_text(note)
    result = {
        "status": "load_forecast_benchmark_complete; controller_and_field_gates_open",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": registration["protocol_sha256"],
        "inputs": protocol["inputs"],
        "registration_sha256": sha256_file(run_dir / "registration.json"),
        "selected_model": selected,
        "primary": comparison,
        "code": code,
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ["numpy", "pandas"]},
        "artifacts": {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"selected": selected, "test_rmse_kw": chosen.rmse_kw, "primary": comparison}, indent=2
        )
    )
    return result


if __name__ == "__main__":
    run(Path(__file__).resolve().parent.parent)
