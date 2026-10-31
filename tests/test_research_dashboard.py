"""Research exports must preserve evidence, clocks and physical schedule identities."""

import json

import pandas as pd
import pytest

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.dashboard import build_dashboard
from second_life_battery.evaluation.research_dashboard import (
    REPORTS,
    daily_score_summary,
    quarter_grid,
    schedule_payload,
    verified_review,
)


def test_completed_run_needs_its_matching_independent_review(tmp_path):
    run = tmp_path / "run"
    review = run / "review"
    review.mkdir(parents=True)
    data = run / "scores.csv"
    data.write_text("score\n17.25\n")
    completion = run / "completion.json"
    completion.write_text(json.dumps({"artifacts": {"scores.csv": sha256_file(data)}}))
    ledger = review / "checked.json"
    ledger.write_text('{"checked":true}')
    path = review / "verification.json"
    path.write_text(
        json.dumps(
            {
                "completion_sha256": sha256_file(completion),
                "artifacts": {"checked.json": sha256_file(ledger)},
            }
        )
    )
    verified_review(run, path)
    completion.write_text(completion.read_text() + "\n")
    with pytest.raises(ValueError, match="does not match"):
        verified_review(run, path)


def test_changed_reviewed_results_are_rejected(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    data = run / "scores.csv"
    data.write_text("score\n17.25\n")
    (run / "completion.json").write_text(
        json.dumps(
            {
                "artifacts": {"scores.csv": sha256_file(data)},
            }
        )
    )
    path = run / "review.json"
    path.write_text("{}")
    data.write_text("score\n-17.25\n")
    with pytest.raises(ValueError, match="artifact changed"):
        verified_review(run, path)


def test_ist_days_are_not_utc_dates_or_shifted_quarters():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2014-11-30 18:30:00+00:00",
                periods=96,
                freq="15min",
            )
        }
    )
    local = quarter_grid(frame).tz_convert("Asia/Kolkata")
    assert local[0].strftime("%Y-%m-%d %H:%M") == "2014-12-01 00:00"
    assert local[-1].strftime("%H:%M") == "23:45"
    for bad in [
        frame.iloc[:-1],
        pd.concat([frame.iloc[:-1], frame.iloc[:1]]),
        frame.assign(timestamp=frame.timestamp + pd.Timedelta(minutes=30)),
    ]:
        with pytest.raises(ValueError, match="complete chronological"):
            quarter_grid(bad)


def test_representative_paths_keep_one_seed_and_each_capacity():
    grid = pd.date_range("2014-11-30 18:30:00+00:00", periods=96, freq="15min")
    policies = ["A_no_battery", "B_greedy", "C_energy", "D_R1", "D_R2", "D_R5"]
    records, capacities = [], []
    for i in range(6):
        cell, capacity = f"cell{i}", float(30 + i)
        capacities.append({"cell_id": cell, "seed": 42, "capacity_kwh": capacity})
        for policy in policies:
            for timestamp in grid:
                records.append(
                    {
                        "cell_id": cell,
                        "policy": policy,
                        "seed": 42,
                        "timestamp": timestamp,
                        "charge_kw": 0,
                        "discharge_kw": 0,
                        "grid_import_kw": 2,
                        "energy_end_kwh": capacity * 0.5,
                    }
                )
    actions = pd.DataFrame(records)
    other = actions.assign(seed=43, energy_end_kwh=999)
    source = pd.concat([actions, other], ignore_index=True)
    before = source.copy(deep=True)
    result = schedule_payload(source, pd.DataFrame(capacities), grid)
    assert len(result["series"]) == 36
    for path in result["series"]:
        assert path["seed"] == 42
        assert all(row[-1] == path["capacity_kwh"] * 0.5 for row in path["rows"])
    pd.testing.assert_frame_equal(source, before)
    with pytest.raises(ValueError, match="complete chronological"):
        schedule_payload(source.iloc[1:], pd.DataFrame(capacities), grid)


def test_existing_reference_is_reused_without_optimization(tmp_path, monkeypatch):
    import second_life_battery.evaluation.dashboard as dashboard
    import second_life_battery.evaluation.research_dashboard as research

    monkeypatch.setattr(dashboard, "verify_provenance", lambda root: None)

    def unexpected(*args):
        raise AssertionError("Historical optimization must not rerun")

    monkeypatch.setattr(dashboard, "build_payload", unexpected)
    monkeypatch.setattr(research, "build_research_payload", lambda root: {"status": "fixture"})
    source = tmp_path / "config.yaml"
    source.write_text("price: 10\n")
    original = {
        "schema_version": 1,
        "market": {"currency": "INR"},
        "generated_at": "2026-10-23T00:00:00Z",
        "dispatch_summary": [{"score": 12.5}],
        "sources": [{"path": "config.yaml", "sha256": sha256_file(source)}],
    }
    snapshot = tmp_path / "data.js"
    snapshot.write_text("window.RECELL_DATA=" + json.dumps(original) + ";\n")
    original_bytes = snapshot.read_bytes()
    assets = tmp_path / "dashboard"
    assets.mkdir()
    for name in ["index.html", "styles.css", "core.js", "app.js", "lessons.js", "research.js"]:
        (assets / name).write_text("fixture")
    reports = tmp_path / "output/pdf"
    reports.mkdir(parents=True)
    for name in REPORTS.values():
        (reports / name).write_bytes(b"fixture PDF")
    output = tmp_path / "export"
    build_dashboard(tmp_path, output, reference_snapshot=snapshot)
    payload = json.loads(
        (output / "data.js")
        .read_text()
        .removeprefix("window.RECELL_DATA=")
        .strip()
        .removesuffix(";")
    )
    assert payload["schema_version"] == 2
    assert payload["dispatch_summary"] == original["dispatch_summary"]
    assert payload["reference_generated_at"] == original["generated_at"]
    assert snapshot.read_bytes() == original_bytes
    assert {p.name for p in (output / "reports").iterdir()} == set(REPORTS.values())
    source.write_text("price: 999\n")
    with pytest.raises(ValueError, match="Original dashboard input changed"):
        build_dashboard(tmp_path, output, reference_snapshot=snapshot)


def test_daily_scores_weight_cells_not_seed_count_and_exclude_metadata():
    records = []
    for cell, seed, score in [("A", 42, 0), ("B", 42, 0), ("B", 43, 100)]:
        records.append(
            {
                "cell_id": cell,
                "seed": seed,
                "path_computed_seed": seed,
                "date_ist": "2014-12-01",
                "policy": "D_R2",
                "reference_score_inr": score,
                "grid_energy_charge_inr": score,
                "grid_import_kwh": score / 10,
                "reference_wear_cost_inr": 0,
                "inventory_adjustment_inr": 0,
                "internal_throughput_kwh": 0,
                "equivalent_full_cycles": 0,
                "curtailed_pv_kwh": 0,
            }
        )
    result = daily_score_summary(pd.DataFrame(records))
    assert result.reference_score_inr.tolist() == [25]
    assert not {"cell_id", "seed", "path_computed_seed"} & set(result.columns)
