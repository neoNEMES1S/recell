"""Independently reconstruct saved pulse responses, model selection and all health forecasts."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import yaml

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.sequences import fit_preprocessor, make_sequences, tabular_features
from second_life_battery.models.baselines import predict_baseline
from second_life_battery.models.gru import GRUForecaster
from second_life_battery.models.physics_guided_gru import PhysicsGuidedGRU
from second_life_battery.training.cross_validation import lobo_folds, split_fold
from second_life_battery.training.trainer import predict_gru
from second_life_battery.utils.study import begin, complete, verified, write_json

ECM = Path("outputs/ecm/local_pulse_ecm_v1/comparison")
AUDIT = Path("outputs/ecm/local_pulse_ecm_v1/audit")
AI = Path("outputs/model_selection/health_selection_v1/comparison")


def convolution_voltage(time, current, initial_voltage, p):
    """Direct history convolution, independently of the runner's step recurrence."""
    elapsed = time - time[0]
    initial = p.r1_ohm * current[0]
    prior = np.arange(len(time) - 1)[None, :] < np.arange(len(time))[:, None]
    left = np.exp(-np.maximum(time[:, None] - time[:-1][None, :], 0) / p.tau_s)
    right = np.exp(-np.maximum(time[:, None] - time[1:][None, :], 0) / p.tau_s)
    state = (
        initial * np.exp(-elapsed / p.tau_s) + p.r1_ohm * ((right - left) * prior) @ current[:-1]
    )
    return initial_voltage - p.r0_ohm * (current - current[0]) - (state - initial)


def paired_interval(differences):
    values = np.asarray(differences, float)
    rng = np.random.default_rng(42)
    resampled = values[rng.integers(len(values), size=(10000, len(values)))].mean(axis=1)
    lo, hi = np.quantile(resampled, [0.025, 0.975])
    return {
        "difference": float(values.mean()),
        "low_95": float(lo),
        "high_95": float(hi),
        "units": len(values),
        "method": "descriptive physical-cell bootstrap; not new cells",
    }


def review(output):
    for root in [
        ECM,
        AUDIT,
        AI,
        Path("outputs/simscape/local_pulse_v1"),
        Path("outputs/bms/synthetic_replay_v1"),
        Path("outputs/life/life_inventory_v1"),
    ]:
        verified(root)
    record = begin(
        output,
        Path("configs/battery_model_v1.yaml"),
        [
            ECM / "completion.json",
            AUDIT / "completion.json",
            AI / "completion.json",
            Path("outputs/simscape/local_pulse_v1/completion.json"),
            Path("outputs/bms/synthetic_replay_v1/completion.json"),
            Path("outputs/life/life_inventory_v1/completion.json"),
        ],
    )
    params = pd.read_csv(ECM / "parameters.csv")
    predicted = pd.read_csv(ECM / "predictions.csv")
    scores = []
    max_error, n = 0.0, 0
    for key, group in predicted.groupby(
        ["cell_id", "session", "role", "step", "model"], sort=False
    ):
        cell, session, role, step, model = key
        p = params[(params.cell_id == cell) & (params.model == model)].iloc[0]
        group = group.sort_values("time_s")
        reconstructed = convolution_voltage(
            group.time_s.to_numpy(), group.current_a.to_numpy(), group.measured_v.iloc[0], p
        )
        discrepancy = float(abs(reconstructed - group.predicted_v.to_numpy()).max())
        max_error = max(max_error, discrepancy)
        if discrepancy > 1e-9:
            raise ValueError("Independent pulse convolution disagrees with saved predictions")
        error = (reconstructed[1:] - group.measured_v.to_numpy()[1:]) * 1000
        scores.append(
            {
                "cell_id": cell,
                "session": session,
                "role": role,
                "step": step,
                "model": model,
                "rmse_mv": float(np.sqrt(np.mean(error**2))),
                "mae_mv": float(np.mean(abs(error))),
                "bias_mv": float(error.mean()),
                "max_error_mv": float(abs(error).max()),
            }
        )
        n += len(group)
    score = pd.DataFrame(scores)
    metrics = ["rmse_mv", "mae_mv", "bias_mv", "max_error_mv"]
    per_cell = score.groupby(["cell_id", "model", "role"])[metrics].mean().reset_index()
    summary = per_cell.groupby(["model", "role"])[metrics].mean().reset_index()
    old = pd.read_csv(ECM / "summary.csv").sort_values(["model", "role"])
    np.testing.assert_allclose(
        summary.sort_values(["model", "role"])[metrics], old[metrics], atol=1e-8
    )
    matrix = per_cell[per_cell.role == "test"].pivot(
        index="cell_id", columns="model", values="rmse_mv"
    )
    pulse_primary = paired_interval(matrix["1rc"] - matrix.rint)
    per_cell.to_csv(output / "ecm_per_cell.csv", index=False)
    summary.to_csv(output / "ecm_summary.csv", index=False)
    write_json(output / "ecm_primary.json", pulse_primary)

    protocol = yaml.safe_load(Path("configs/model_selection_v1.yaml").read_text())
    base = yaml.safe_load(Path(protocol["base_config"]).read_text())
    frame = pd.read_csv(protocol["data"], parse_dates=["timestamp"])
    selections = json.loads((AI / "selections.json").read_text())
    trials = pd.read_csv(AI / "trials.csv")
    health = pd.read_csv(AI / "predictions.csv")
    replay_error, validation_error = 0.0, 0.0
    for fold in lobo_folds(frame):
        train, validation, test = split_fold(frame, fold)
        roles = json.loads((AI / fold.test / "roles.json").read_text())
        assert roles["training"] == list(fold.training) and roles["test"] == fold.test
        assert roles["validation"] == fold.validation and roles["scaler_cells"] == list(
            fold.training
        )
        scaler = joblib.load(AI / fold.test / "scaler.joblib")
        fresh = fit_preprocessor(train, base["features"])
        np.testing.assert_allclose(
            scaler.transform(train[base["features"]].to_numpy()),
            fresh.transform(train[base["features"]].to_numpy()),
        )
        vs, ts = [
            make_sequences(
                p,
                base["features"],
                base["evaluation"]["horizon"],
                min_history=base["evaluation"]["minimum_history"],
            )
            for p in [validation, test]
        ]
        rank = []
        model_cache = {}
        for candidate in protocol["candidates"]:
            values = []
            for seed in protocol["seeds"]:
                prefix = AI / fold.test / f"{candidate['id']}_{seed}"
                if candidate["model"] in {"gru", "pgp_gru", "quantile_gru"}:
                    checkpoint = torch.load(
                        prefix.with_suffix(".pt"), map_location="cpu", weights_only=False
                    )
                    cls = GRUForecaster if candidate["model"] == "gru" else PhysicsGuidedGRU
                    c = checkpoint["config"]
                    model = cls(len(c["features"]), c["evaluation"]["horizon"], c["gru"])
                    model.load_state_dict(checkpoint["state_dict"])
                else:
                    model = joblib.load(prefix.with_suffix(".joblib"))
                model_cache[(candidate["id"], seed)] = model
                q = predict(model, candidate["model"], vs, scaler, base)
                rmse = float(np.sqrt(np.mean((q[:, 0, 1] - [s.target[0] for s in vs]) ** 2)))
                saved = trials[
                    (trials.test_cell == fold.test)
                    & (trials.candidate == candidate["id"])
                    & (trials.seed == seed)
                ]
                assert len(saved) == 1
                validation_error = max(
                    validation_error, abs(rmse - saved.validation_rmse_soh.iloc[0])
                )
                values.append(rmse)
            rank.append((np.mean(values), candidate["id"]))
        winner = min(rank)[1]
        chosen = next(s for s in selections if s["test_cell"] == fold.test)
        assert chosen["selected"] == winner and not chosen["test_scored_at_selection"]
        candidates = {c["id"]: c for c in protocol["candidates"]}
        for label in [*protocol["fixed_comparators"], "selected"]:
            identifier = winner if label == "selected" else label
            for seed in protocol["seeds"]:
                q = predict(
                    model_cache[(identifier, seed)],
                    candidates[identifier]["model"],
                    ts,
                    scaler,
                    base,
                )
                saved = health[
                    (health.cell_id == fold.test) & (health.model == label) & (health.seed == seed)
                ].sort_values(["origin_time", "horizon"])
                np.testing.assert_allclose(
                    saved.y_true, np.stack([s.target for s in ts]).reshape(-1), atol=1e-10
                )
                delta = float(abs(saved[["q10", "q50", "q90"]].to_numpy() - q.reshape(-1, 3)).max())
                replay_error = max(replay_error, delta)
    if max(replay_error, validation_error) > 1e-8:
        raise ValueError("Health selection/model replay differs from saved forecasts")
    hmetrics = []
    for (cell, model, seed, horizon), part in health.groupby(
        ["cell_id", "model", "seed", "horizon"]
    ):
        error = (part.q50 - part.y_true) * 100
        hmetrics.append(
            {
                "cell_id": cell,
                "model": model,
                "seed": seed,
                "horizon": horizon,
                "rmse_pp": float(np.sqrt(np.mean(error**2))),
                "mae_pp": float(np.mean(abs(error))),
            }
        )
    hcell = (
        pd.DataFrame(hmetrics)
        .groupby(["cell_id", "model", "horizon"])[["rmse_pp", "mae_pp"]]
        .mean()
        .reset_index()
    )
    hsummary = hcell.groupby(["model", "horizon"])[["rmse_pp", "mae_pp"]].mean().reset_index()
    np.testing.assert_allclose(
        hsummary[["rmse_pp", "mae_pp"]],
        pd.read_csv(AI / "summary.csv")[["rmse_pp", "mae_pp"]],
        atol=1e-10,
    )
    hm = hcell[hcell.horizon == 1].pivot(index="cell_id", columns="model", values="rmse_pp")
    health_primary = paired_interval(hm.selected - hm.xgb_d2_lr03)
    hsummary.to_csv(output / "health_summary.csv", index=False)
    write_json(output / "health_primary.json", health_primary)
    bms = pd.read_csv("outputs/bms/synthetic_replay_v1/replay.csv")
    np.testing.assert_allclose(bms.predicted_voltage_v, bms.voltage_v, atol=1e-12)
    sim = Path("outputs/simscape/local_pulse_v1")
    from scipy.io import loadmat

    matlab = loadmat(sim / "case.mat")
    csv = pd.read_csv(sim / "case.csv")
    np.testing.assert_allclose(matlab["python_v"].ravel(), csv.predicted_v, atol=1e-12)
    write_json(
        output / "verification.json",
        {
            "ecm_rows_checked": n,
            "ecm_max_replay_difference_v": max_error,
            "health_rows_checked": len(health),
            "validation_trials_checked": len(trials),
            "health_max_replay_difference": replay_error,
            "validation_max_replay_difference": validation_error,
            "selection_is_per_fold": True,
            "synthetic_bms_rows_checked": len(bms),
            "simscape_numeric_roundtrip_checked": True,
            "matlab_executed": False,
            "independent_external_cohort": False,
            "completion_hashes": {
                str(p): sha256_file(p / "completion.json") for p in [ECM, AUDIT, AI]
            },
        },
    )
    complete(output, record, scope="independent calculation/model replay; no independent cohort")
    print(f"Verified {n} pulse rows, {len(health)} forecasts and {len(trials)} validation trials")


def predict(model, name, samples, scaler, base):
    if name in {"gru", "pgp_gru", "quantile_gru"}:
        q = predict_gru(model, samples, scaler)
        return q if q.ndim == 3 else np.stack([q, q, q], axis=-1)
    q = predict_baseline(
        model,
        tabular_features(samples, scaler),
        np.array([s.origin_soh for s in samples]),
        base["evaluation"]["horizon"],
    )
    return np.stack([q, q, q], axis=-1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    review(args.output)
