"""Reload every v3 fit, reproduce predictions and independently verify the primary estimand."""

import json
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
import torch
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from second_life_battery.data.inventory import sha256_file
from second_life_battery.data.sequences import make_sequences, tabular_features
from second_life_battery.data.transfer import FEATURES, physical_folds
from second_life_battery.models.baselines import predict_baseline
from second_life_battery.models.physics_guided_gru import PhysicsGuidedGRU
from second_life_battery.training.trainer import predict_gru
from second_life_battery.training.transfer import validate_contract
from second_life_battery.utils.reproducibility import seed_everything, verify_artifacts


def review(root):
    protocol_path = root / "configs/transfer_protocol_v3.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    registered = root / "outputs/transfer" / protocol["protocol_id"]
    run = registered / "comparison"
    completion = json.loads((run / "completion.json").read_text())
    if completion["status"] != "comparison_fits_complete; report_required":
        raise ValueError("Only the complete v3 comparison can be reviewed")
    verify_artifacts(run, completion["artifacts"])
    for relative, digest in completion["code"].items():
        if (
            sha256_file(root / relative) != digest
            or sha256_file(run / "code_snapshot" / relative) != digest
        ):
            raise ValueError("Current or archived model implementation differs from the fit")
    target = pd.read_csv(root / protocol["data"]["target"])
    if sha256_file(root / protocol["data"]["target"]) != completion["inputs"]["target"]:
        raise ValueError("Target prediction inputs changed")
    predictions = pd.read_csv(run / "predictions.csv")
    checked = 0
    seed_everything(42)
    for fold in physical_folds(target):
        folder = run / fold.test
        scaler_path = folder / "scaler.joblib"
        scaler = joblib.load(scaler_path)
        held_out = target[target.physical_cell_id.eq(fold.test)]
        contexts = {
            fraction: make_sequences(
                held_out.assign(cell_id=held_out.physical_cell_id), FEATURES, 2, fraction, 3
            )
            for fraction in protocol["target"]["inference_context_fractions"]
        }
        for seed in protocol["target"]["seeds"]:
            parents = {}
            for name in ["pgp_gru", "quantile_gru"]:
                path = folder / f"source_{name}_{seed}.pt"
                saved = torch.load(path, map_location="cpu", weights_only=True)
                contract = validate_contract(saved["config"], "first_life", name)
                if (
                    contract["scaler_sha256"] != sha256_file(scaler_path)
                    or contract["test_cell"] != fold.test
                    or contract["validation_cell"] != "secl_m50t_W5"
                ):
                    raise ValueError("Saved source fit has incorrect roles or scaling")
                parents[name] = (path, saved)
            for arm in ["R1", "R2", "R3", "R4", "R5", "R6"]:
                if arm in {"R1", "R2", "R3", "R4"}:
                    path = folder / f"{arm}_{seed}.pt"
                    saved = torch.load(path, map_location="cpu", weights_only=True)
                    name = "pgp_gru" if arm in {"R1", "R2"} else "quantile_gru"
                    contract = validate_contract(saved["config"], "second_life", name)
                    if (
                        contract["gradient_cells"] != list(fold.training)
                        or contract["validation_cell"] != fold.validation
                        or contract["scaler_sha256"] != sha256_file(scaler_path)
                    ):
                        raise ValueError("Saved target fit has incorrect roles or scaling")
                    parent_path, parent = parents[name]
                    if arm in {"R2", "R4"}:
                        initialization = saved["initialization"]
                        if (
                            initialization["parent_sha256"] != sha256_file(parent_path)
                            or any(
                                key.startswith("head.")
                                for key in initialization["transferred_parameters"]
                            )
                            or initialization["head"] != "fresh_target_initialization"
                        ):
                            raise ValueError("Saved transfer initialization is not encoder-only")
                        if contract["stage_roles"] != parent["config"]["transfer"]["stage_roles"]:
                            raise ValueError("Source/target declared stage roles differ")
                    elif saved["initialization"] is not None:
                        raise ValueError("A scratch model has an unexpected parent")
                    model = PhysicsGuidedGRU(3, 2, saved["config"]["gru"])
                    model.load_state_dict(saved["state_dict"], strict=True)
                    model.eval()
                else:
                    model = joblib.load(folder / f"{arm}_{seed}.joblib")
                for fraction, samples in contexts.items():
                    expected = (
                        predict_gru(model, samples, scaler)
                        if arm in {"R1", "R2", "R3", "R4"}
                        else predict_baseline(
                            model,
                            tabular_features(samples, scaler),
                            np.array([s.origin_soh for s in samples]),
                            2,
                        )
                    )
                    rows = predictions[
                        (predictions.model.eq(arm))
                        & predictions.seed.eq(seed)
                        & predictions.cell_id.eq(fold.test)
                        & predictions.history_fraction.eq(fraction)
                    ].sort_values(["origin_index", "horizon"])
                    if len(rows) != len(samples) * 2:
                        raise ValueError(
                            "Saved prediction matrix has missing or duplicated origins"
                        )
                    columns = ["q10", "q50", "q90"] if expected.ndim == 3 else ["q50"]
                    np.testing.assert_allclose(
                        rows[columns].to_numpy(),
                        expected.reshape(-1, len(columns)),
                        rtol=0,
                        atol=1e-12,
                    )
                    np.testing.assert_allclose(
                        rows.y_true,
                        np.stack([s.target for s in samples]).ravel(),
                        rtol=0,
                        atol=1e-12,
                    )
                    checked += len(rows)
    if checked != 15660 or checked != len(predictions):
        raise ValueError("Independent model replay did not cover every registered prediction")
    primary = predictions[predictions.history_fraction.eq(0.1) & predictions.horizon.eq(1)].copy()
    primary["squared_error"] = (primary.q50 - primary.y_true) ** 2
    primary["absolute_error"] = abs(primary.q50 - primary.y_true)
    per_seed = primary.groupby(["model", "cell_id", "seed"]).agg(
        mse=("squared_error", "mean"), mae=("absolute_error", "mean")
    )
    per_seed["rmse"] = np.sqrt(per_seed.mse)
    per_cell = per_seed.groupby(["model", "cell_id"])[["rmse", "mae"]].mean()
    summary = per_cell.groupby("model").mean()
    reported = pd.read_csv(run / "report/summary.csv").query(
        "history_fraction == .1 and horizon == 1"
    )
    for row in reported.itertuples():
        np.testing.assert_allclose(
            [row.rmse_mean, row.mae_mean],
            summary.loc[row.model, ["rmse", "mae"]],
            rtol=0,
            atol=1e-12,
        )
    difference = per_cell.xs("R2").rmse - per_cell.xs("R1").rmse
    rng = np.random.default_rng(protocol["evaluation"]["bootstrap_seed"])
    bootstrap = rng.choice(difference.to_numpy(), size=(10000, 6), replace=True).mean(axis=1)
    interval = np.quantile(bootstrap, [0.025, 0.975])
    reported_primary = pd.read_csv(run / "report/paired_comparisons.csv").iloc[0]
    np.testing.assert_allclose(
        [difference.mean(), *interval],
        [
            reported_primary.rmse_difference,
            reported_primary.bootstrap_low,
            reported_primary.bootstrap_high,
        ],
        rtol=0,
        atol=1e-12,
    )
    output = run / "review"
    output.mkdir(exist_ok=False)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.25, 1]})
    names = [
        "PGP scratch",
        "PGP transfer",
        "Quantile scratch",
        "Quantile transfer",
        "XGBoost",
        "Persistence",
    ]
    rmse = summary.loc[[f"R{i}" for i in range(1, 7)], "rmse"] * 100
    bars = axes[0].barh(
        names, rmse, color=["#789481", "#264c38", "#aa99b0", "#80618c", "#527a99", "#a5aba5"]
    )
    axes[0].invert_yaxis()
    axes[0].set_xlabel("RMSE (SOH percentage points; lower is better)")
    axes[0].set_xlim(0, float(rmse.max()) * 1.25)
    axes[0].bar_label(bars, fmt="%.4f", padding=4, fontsize=9)
    delta = difference * 100
    bars = axes[1].barh(
        [name.removeprefix("secl_m50t_") for name in delta.index],
        delta,
        color=["#ac6055" if value > 0 else "#264c38" for value in delta],
    )
    axes[1].invert_yaxis()
    axes[1].axvline(0, color="#444", lw=0.8)
    axes[1].set_xlabel("Transfer minus scratch RMSE (SOH points)")
    axes[1].set_title("Negative favors transfer; two cells worsen", fontsize=10)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.15)
        ax.set_axisbelow(True)
    fig.suptitle("Availability-restricted transfer (v3): primary endpoint", fontsize=14, y=0.97)
    fig.text(
        0.5,
        0.88,
        "10% target history | horizon 1 | six target cells | three seeds",
        ha="center",
        fontsize=10,
    )
    fig.text(
        0.02,
        0.035,
        "W5 source validation: one origin. Familiar target cohort; "
        "no field validation or model promotion.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.16, right=0.98, bottom=0.20, top=0.76, wspace=0.5)
    fig.savefig(output / "primary_comparison.png", dpi=180)
    fig.savefig(output / "primary_comparison.pdf")
    plt.close(fig)
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "status": "independent_prediction_and_primary_review_passed; no_promotion",
        "checked_prediction_rows": checked,
        "source_fits": 36,
        "target_torch_fits": 72,
        "primary_difference_soh": float(difference.mean()),
        "primary_difference_soh_percentage_points": float(difference.mean() * 100),
        "primary_interval_soh": interval.tolist(),
        "negative_transfer_cells": difference[difference > 0].index.tolist(),
        "completion_sha256": sha256_file(run / "completion.json"),
        "report_artifacts": {
            str(p.relative_to(run)): sha256_file(p) for p in sorted((run / "report").iterdir())
        },
        "artifacts": {p.name: sha256_file(p) for p in output.iterdir()},
    }
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "checked_prediction_rows",
                    "primary_difference_soh_percentage_points",
                    "negative_transfer_cells",
                ]
            },
            indent=2,
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    review(Path(__file__).resolve().parent.parent)
