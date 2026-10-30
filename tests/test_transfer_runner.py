"""Exercise runner wiring with synthetic tables and mocked fits, never research data."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from second_life_battery.data.inventory import sha256_file

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "transfer_runner", ROOT / "scripts/run_transfer_experiment.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_closed_feature_gate_prevents_training_and_output_creation(tmp_path, monkeypatch):
    def rejected(root):
        raise ValueError("Incomplete causal features")

    monkeypatch.setattr(module, "audit", rejected)
    monkeypatch.setattr(module, "train_gru", lambda *a, **kw: pytest.fail("Training gate bypassed"))
    with pytest.raises(ValueError, match="Incomplete causal features"):
        module.run(tmp_path, smoke=True)
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize("protocol_version", [2, 3])
def test_smoke_wires_six_matched_arms_without_retraining_for_context(
    tmp_path, monkeypatch, protocol_version
):
    protocol_name = f"transfer_protocol_v{protocol_version}.yaml"
    protocol = yaml.safe_load((ROOT / "configs" / protocol_name).read_text())
    prefix = protocol_version == 3
    if prefix:
        protocol["source"]["eligible_gradient_physical_cells"] = [
            f"physical_{cell}" for cell in protocol["target"]["cells"] if cell != "W10"
        ]
        protocol["source"]["validation_physical_cell"] = "physical_W5"
    def execute(**kwargs):
        return module.run(tmp_path, protocol_version=protocol_version, **kwargs)

    config = tmp_path / "configs"
    config.mkdir()
    (config / protocol_name).write_text(yaml.safe_dump(protocol))
    (config / "cell_registry.yaml").write_text("cells: []\n")
    base = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    base_path = tmp_path / "outputs/lobo/config.yaml"
    base_path.parent.mkdir(parents=True)
    base_path.write_text(yaml.safe_dump(base))
    reference = tmp_path / protocol["reference"]["manifest"]
    reference.parent.mkdir(parents=True)
    reference.write_text(
        json.dumps(
            {"files": [{"path": "outputs/lobo/config.yaml", "sha256": sha256_file(base_path)}]}
        )
    )
    registered = tmp_path / "outputs/transfer" / protocol["protocol_id"]
    registered.mkdir()
    (registered / "feature_gate.json").write_text('{"status":"feature_gate_passed"}')
    data = tmp_path / "data/processed/transfer"
    data.mkdir(parents=True)
    for domain, stage, year in [("source", "first_life", 2021), ("target", "second_life", 2022)]:
        cells = protocol["target"]["cells"]
        if prefix and domain == "source":
            cells = [cell for cell in cells if cell != "W10"] + ["W5"]
        rows = [
            {
                "cell_id": cell,
                "physical_cell_id": f"physical_{cell}",
                "life_stage": stage,
                "timestamp": f"{year}-01-{i + 1:02d}",
                "soh": 1 - i * 0.01,
                "capacity_ah": 4.9 * (1 - i * 0.01),
                "reference_capacity_ah": 4.9,
                "elapsed_days": i,
                "cumulative_ah_since_stage_start": i * 10.0,
                "diagnostic": i + 1,
            }
            for cell in cells
            for i in range(7)
        ]
        table = pd.DataFrame(rows)
        path = (
            tmp_path / protocol["data"]["source_features"]
            if prefix and domain == "source"
            else (data / f"{domain}_checkpoints.csv")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)
        if prefix and domain == "source":
            table.drop(columns=["elapsed_days", "cumulative_ah_since_stage_start"]).to_csv(
                tmp_path / protocol["data"]["source_labels"], index=False
            )
    (tmp_path / "data/processed/checkpoints.csv").write_text("frozen synthetic original\n")
    script = tmp_path / "scripts/run_transfer_experiment.py"
    script.parent.mkdir()
    script.write_text("# synthetic implementation identity\n")
    monkeypatch.setattr(module, "__file__", str(script))
    monkeypatch.setattr(module, "audit", lambda root: {"status": "feature_gate_passed"})
    monkeypatch.setattr(module, "audit_prefix", lambda root: {"status": "feature_gate_passed"})
    fitted = []

    def fit(train, validation, scaler, settings, checkpoint, name, *, parent_checkpoint=None):
        contract = settings["transfer"]
        assert {s.cell_id for s in train} == set(contract["gradient_cells"])
        assert {s.cell_id for s in validation} == {contract["validation_cell"]}
        assert contract["test_cell"] not in {s.cell_id for s in train + validation}
        if parent_checkpoint is not None:
            assert parent_checkpoint.exists()
        checkpoint.write_text("synthetic fit placeholder")
        fitted.append((contract["stage"], name, parent_checkpoint))
        return SimpleNamespace()

    def predict(model, samples, scaler):
        median = np.array([[s.origin_soh] * 2 for s in samples])
        return np.stack([median - 0.01, median, median + 0.01], axis=-1)

    monkeypatch.setattr(module, "train_gru", fit)
    monkeypatch.setattr(module, "predict_gru", predict)
    monkeypatch.setattr(module, "fit_baseline", lambda *args: None)
    with pytest.raises(FileNotFoundError):
        execute(smoke=False)
    assert not (registered / "comparison").exists()
    result = execute(smoke=True)
    assert result["status"] == "smoke_passed"
    assert len(fitted) == 6  # Two source fits + four target fits, across all five contexts.
    assert sum(parent is not None for _, _, parent in fitted) == 2
    assert result["prediction_rows"] == 180
    predictions = pd.read_csv(registered / "smoke/predictions.csv")
    assert set(predictions.model) == {"R1", "R2", "R3", "R4", "R5", "R6"}
    keys = ["seed", "history_fraction", "cell_id", "origin_time", "target_time", "horizon"]
    reference_rows = predictions[predictions.model.eq("R1")].sort_values(keys)
    for arm in ["R2", "R3", "R4", "R5", "R6"]:
        rows = predictions[predictions.model.eq(arm)].sort_values(keys)
        assert rows[keys].reset_index(drop=True).equals(reference_rows[keys].reset_index(drop=True))
    assert len(pd.read_csv(registered / "smoke/fit_times.csv")) == 8
    with pytest.raises(FileExistsError):
        execute(smoke=True)
    comparison = execute(smoke=False)
    assert comparison["folds"] == 6
    assert comparison["seeds"] == [42, 43, 44]
    assert comparison["prediction_rows"] == 3240
    assert len(fitted) == 6 + 6 * 3 * 6
    (config / "cell_registry.yaml").write_text("changed registry\n")
    with pytest.raises(ValueError, match="matching successful"):
        execute(smoke=False)
