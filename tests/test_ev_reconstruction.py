"""Exercise the complete promotion path without network access or research fitting."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from openpyxl import Workbook

from second_life_battery.data.inventory import sha256_file

spec = importlib.util.spec_from_file_location(
    "reconstruct_ev_transfer",
    Path(__file__).resolve().parents[1] / "scripts/reconstruct_ev_transfer.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(root, monkeypatch):
    audit = root / "outputs/transfer/source_audit"
    audit.mkdir(parents=True)
    config = root / "configs"
    config.mkdir()
    protocol = config / "transfer_protocol_v2.yaml"
    protocol.write_text(yaml.safe_dump({"target": {"cells": ["G1"]}}))
    (config / "cell_registry.yaml").write_text(
        yaml.safe_dump(
            {
                "cells": [
                    {
                        "first_life_source_id": "G1",
                        "physical_cell_id": "physical_G1",
                    }
                ]
            }
        )
    )
    # The pipeline hashes its implementation dependencies alongside the source files.
    for name in ["ev_exposure", "first_life", "parser", "features", "transfer", "sequences"]:
        path = root / f"src/second_life_battery/data/{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic dependency\n")
    script = root / "scripts/reconstruct_ev_transfer.py"
    script.parent.mkdir()
    script.write_text("# synthetic entry point\n")
    monkeypatch.setattr(module, "__file__", str(script))
    raw = root / "raw"
    raw.mkdir()
    entries = []
    for n in [1, 2, 3]:
        for kind in (
            ["diagnostic", "cycling_mat", "cycling_anchor", "cycling_end_anchor"]
            if n < 3
            else ["diagnostic"]
        ):
            path = raw / f"{kind}_{n}.xlsx"
            book = Workbook()
            book.active.title = "Channel_1_1"
            book.save(path)
            entry = {
                "path": path.name,
                "kind": kind,
                "number": n,
                "cell_id": "G1",
                "remote_id": path.name,
            }
            entries.append(entry)
            path.with_suffix(".xlsx.receipt.json").write_text(
                json.dumps(
                    {
                        "remote_id": path.name,
                        "sha256": sha256_file(path),
                    }
                )
            )
    (audit / "source_selection.json").write_text(
        json.dumps(
            {
                "protocol_sha256": sha256_file(protocol),
                "raw_root": "raw",
                "files": entries,
            }
        )
    )
    (audit / "source_segments.json").write_text(
        json.dumps(
            {
                "protocol_sha256": sha256_file(protocol),
                "source_selection_sha256": sha256_file(audit / "source_selection.json"),
                "extra_files": [],
                "batches": [
                    {
                        "cell_id": "G1",
                        "number": n,
                        "mat_path": f"cycling_mat_{n}.xlsx",
                        "segments": [
                            {
                                "segment_index": 1,
                                "first_path": f"cycling_anchor_{n}.xlsx",
                                "last_path": f"cycling_end_anchor_{n}.xlsx",
                            }
                        ],
                    }
                    for n in [1, 2]
                ],
            }
        )
    )
    pd.DataFrame(
        {"cell_id": ["G1"] * 3, "diagnostic": [1, 2, 3], "capacity_ah": [4.9, 4.8, 4.7]}
    ).to_csv(audit / "first_life_capacity_checkpoints.csv", index=False)
    target = root / "data/processed/transfer/target_checkpoints.csv"
    target.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "physical_cell_id": ["physical_G1"],
            "cell_id": ["G1"],
            "life_stage": ["second_life"],
            "timestamp": ["2022-01-01"],
            "soh": [1],
            "capacity_ah": [4.6],
            "reference_capacity_ah": [4.6],
            "elapsed_days": [0],
            "cumulative_ah_since_stage_start": [0],
        }
    ).to_csv(target, index=False)
    (audit / "target_exposure_counter_audit.json").write_text("{}")
    monkeypatch.setattr(
        module,
        "read_channel",
        lambda root, record, cache: pd.DataFrame(
            {
                "timestamp": [f"2021-01-0{record['source_file'].split('_')[-1][0]}"],
                "time_s": [0],
            }
        ),
    )

    def capacity(frame):
        assert isinstance(frame, pd.DataFrame)
        n = int(frame.timestamp.iloc[0][-1])
        return {
            "capacity_ah": [4.9, 4.8, 4.7][n - 1],
            "diagnostic_start_time": f"2021-01-0{n}",
            "diagnostic_end_time": f"2021-01-0{n}T01:00:00",
        }

    def batch(mat, parts):
        n = int(mat.stem[-1])
        return {
            "batch_start_time": f"2021-01-0{n}T02:00:00",
            "batch_end_time": f"2021-01-0{n}T03:00:00",
            "charge_ah": 10,
            "discharge_ah": 9,
            "numeric_trajectory_sha256": f"synthetic-trajectory-{n}",
        }

    monkeypatch.setattr(module, "audit_raw_capacity", capacity)
    monkeypatch.setattr(module, "audit_segmented_batch", batch)
    return audit, raw, target.parent


def test_complete_reconstruction_and_cached_resume(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    result = module.reconstruct(tmp_path)
    assert result["source_rows"] == 3
    source = pd.read_csv(output / "source_checkpoints.csv")
    assert source.cumulative_ah_since_stage_start.tolist() == [0, 19, 38]
    monkeypatch.setattr(
        module, "audit_segmented_batch", lambda *args: pytest.fail("cache not reused")
    )
    assert module.reconstruct(tmp_path)["source_sha256"] == result["source_sha256"]


def test_incomplete_or_changed_input_never_promoted(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    (raw / "cycling_mat_1.xlsx").write_bytes(b"modified")
    with pytest.raises(ValueError, match="pinned receipt"):
        module.reconstruct(tmp_path)
    assert not (output / "source_checkpoints.csv").exists()
    assert not (audit / "feature_provenance.json").exists()


def test_part_anchor_cannot_cross_its_declared_batch(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    path = audit / "source_segments.json"
    plan = json.loads(path.read_text())
    plan["batches"][0]["segments"][0]["last_path"] = "cycling_end_anchor_2.xlsx"
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="crosses a cell/batch"):
        module.reconstruct(tmp_path)
    assert not (output / "source_checkpoints.csv").exists()


def test_partial_audit_caches_completed_units_without_promoting_features(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    (raw / "cycling_mat_2.xlsx").unlink()
    result = module.reconstruct(tmp_path, audit_available=True)
    assert result["status"] == "acquisition_incomplete; no_feature_dataset_promoted"
    assert result["verified_cycling_batches"] == 1
    assert result["verified_diagnostics"] == 3
    assert result["pending_inputs"] == ["cycling_mat_2.xlsx"]
    assert not (output / "source_checkpoints.csv").exists()
    assert not (audit / "feature_provenance.json").exists()
    assert (audit / "reconstruction_cache/cycling_G1_1.json").exists()


def test_partial_audit_records_rejection_and_continues_without_promotion(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    original = module.audit_segmented_batch

    def reject_first(mat, parts):
        if mat.stem.endswith("1"):
            raise ValueError("Native clocks reverse")
        return original(mat, parts)

    monkeypatch.setattr(module, "audit_segmented_batch", reject_first)
    with pytest.raises(ValueError, match="Native clocks reverse"):
        module.reconstruct(tmp_path)
    result = module.reconstruct(tmp_path, audit_available=True)
    assert result["status"] == "source_validation_failed; no_feature_dataset_promoted"
    assert result["verified_cycling_batches"] == 1
    assert result["failed_cycling_batches"] == [
        {"cell_id": "G1", "number": 1, "error": "Native clocks reverse"}
    ]
    assert (audit / "reconstruction_cache/cycling_G1_2.json").exists()
    assert not (output / "source_checkpoints.csv").exists()
    assert not (audit / "feature_provenance.json").exists()


def test_identical_numeric_histories_cannot_be_two_physical_cells(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    protocol = tmp_path / "configs/transfer_protocol_v2.yaml"
    protocol.write_text(yaml.safe_dump({"target": {"cells": ["G1", "G2"]}}))
    registry = tmp_path / "configs/cell_registry.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "cells": [
                    {"first_life_source_id": cell, "physical_cell_id": f"physical_{cell}"}
                    for cell in ["G1", "G2"]
                ]
            }
        )
    )
    selection_path = audit / "source_selection.json"
    selection = json.loads(selection_path.read_text())
    additions = []
    for entry in selection["files"]:
        path = raw / f"G2_{entry['path']}"
        path.write_bytes((raw / entry["path"]).read_bytes())
        path.with_suffix(".xlsx.receipt.json").write_text(
            json.dumps(
                {
                    "remote_id": path.name,
                    "sha256": sha256_file(path),
                }
            )
        )
        additions.append({**entry, "cell_id": "G2", "path": path.name, "remote_id": path.name})
    selection["files"].extend(additions)
    selection["protocol_sha256"] = sha256_file(protocol)
    selection_path.write_text(json.dumps(selection))
    plan_path = audit / "source_segments.json"
    plan = json.loads(plan_path.read_text())
    plan["batches"].extend(
        [
            {
                **batch,
                "cell_id": "G2",
                "mat_path": f"G2_{batch['mat_path']}",
                "segments": [
                    {
                        **part,
                        "first_path": f"G2_{part['first_path']}",
                        "last_path": f"G2_{part['last_path']}",
                    }
                    for part in batch["segments"]
                ],
            }
            for batch in list(plan["batches"])
        ]
    )
    plan.update(
        protocol_sha256=sha256_file(protocol), source_selection_sha256=sha256_file(selection_path)
    )
    plan_path.write_text(json.dumps(plan))
    reference_path = audit / "first_life_capacity_checkpoints.csv"
    reference = pd.read_csv(reference_path)
    pd.concat([reference, reference.assign(cell_id="G2")]).to_csv(reference_path, index=False)
    with pytest.raises(ValueError, match="duplicates another physical cell"):
        module.reconstruct(tmp_path)
    result = module.reconstruct(tmp_path, audit_available=True)
    assert len(result["failed_cycling_batches"]) == 2
    assert not (output / "source_checkpoints.csv").exists()


def test_reviewed_raw_replacement_requires_pinned_verified_evidence(tmp_path, monkeypatch):
    audit, raw, output = fixture(tmp_path, monkeypatch)
    source = json.loads((audit / "source_selection.json").read_text())
    entry = next(row for row in source["files"] if row["kind"] == "cycling_anchor")
    plan = {
        "source_selection_sha256": sha256_file(audit / "source_selection.json"),
        "protocol_sha256": source["protocol_sha256"],
        "raw_root": "raw",
        "files": [entry],
        "batches": [{"cell_id": "G1", "number": 1, "ordered_paths": [entry["path"]]}],
    }
    plan_path = audit / "raw_review_selection.json"
    plan_path.write_text(json.dumps(plan))
    report_path = audit / "raw_review_audit.json"
    report = {
        "selection_sha256": sha256_file(plan_path),
        "code": {},
        "inputs": {entry["path"]: sha256_file(raw / entry["path"])},
        "batches": [
            {
                "cell_id": "G1",
                "number": 1,
                "raw_fragments": 1,
                "status": "raw_measurements_verified; causal_diagnostic_gate_still_required",
            }
        ],
    }
    config = {
        "selection_sha256": sha256_file(plan_path),
        "batches": [{"cell_id": "G1", "number": 1}],
    }
    config_path = tmp_path / "configs/ev_raw_replacements.yaml"

    def pin():
        report_path.write_text(json.dumps(report))
        config["report_sha256"] = sha256_file(report_path)
        config_path.write_text(yaml.safe_dump(config))

    pin()
    replacements, inputs, bindings = module.reviewed_raw_batches(tmp_path)
    assert set(replacements) == {("G1", 1)}
    assert len(inputs) == 1 and len(bindings) == 3
    report_path.write_text("{}")
    with pytest.raises(ValueError, match="evidence changed"):
        module.reviewed_raw_batches(tmp_path)
    report["batches"][0]["status"] = "rejected"
    pin()
    with pytest.raises(ValueError, match="not verified"):
        module.reviewed_raw_batches(tmp_path)
    report["batches"][0]["status"] = (
        "raw_measurements_verified; causal_diagnostic_gate_still_required"
    )
    pin()
    (raw / entry["path"]).write_bytes(b"changed raw source")
    with pytest.raises(ValueError, match="source receipt changed"):
        module.reviewed_raw_batches(tmp_path)
