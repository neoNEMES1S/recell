"""Illustrate energy-charge reductions and the registered common-reference score separately."""

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from second_life_battery.data.inventory import sha256_file
from second_life_battery.utils.reproducibility import verify_artifacts


def plot(root):
    run = root / "outputs/india_ci/india_public_controller_v1/comparison"
    review = run / "review"
    verification_path = review / "verification.json"
    verification = json.loads(verification_path.read_text())
    verify_artifacts(review, verification["artifacts"])
    if verification["completion_sha256"] != sha256_file(run / "completion.json"):
        raise ValueError("Controller completion changed after independent review")
    summary = pd.read_csv(review / "policy_summary.csv").set_index("policy")
    cells = pd.read_csv(review / "per_cell_differences.csv")
    primary = cells[cells.candidate.eq("D_R2") & cells.reference.eq("D_R1")].copy()
    primary = primary.sort_values("cell_id")
    base = summary.loc["A_no_battery"]
    policies = ["B_greedy", "C_energy", "D_R1", "D_R2", "D_R5"]
    names = ["Greedy", "Energy-only plan", "Scratch-GRU wear", "Transfer-GRU wear", "XGBoost wear"]
    energy = base.grid_energy_charge_inr - summary.loc[policies, "grid_energy_charge_inr"]
    score = base.reference_score_inr - summary.loc[policies, "reference_score_inr"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8), gridspec_kw={"width_ratios": [1.4, 1]})
    y = np.arange(len(policies))
    first = axes[0].barh(y - 0.18, energy, height=0.32, color="#527a99", label="Energy charge only")
    second = axes[0].barh(
        y + 0.18, score, height=0.32, color="#ad665b", label="Common-reference score"
    )
    axes[0].set_yticks(y, names)
    axes[0].invert_yaxis()
    axes[0].axvline(0, color="#444", lw=0.8)
    axes[0].bar_label(first, fmt="%.1f", padding=3, fontsize=8)
    axes[0].bar_label(second, fmt="%.1f", padding=3, fontsize=8)
    axes[0].set_xlim(-650, 2150)
    axes[0].set_xlabel("No-storage minus policy (scenario INR / 16 days)")
    axes[0].set_title("Positive = lower charge or score", fontsize=11)
    axes[0].legend(loc="lower right", fontsize=9, frameon=False)
    values = primary.seed_mean_difference_inr
    bars = axes[1].barh(
        primary.cell_id.str.removeprefix("secl_m50t_"),
        values,
        color=["#ad665b" if value > 0 else "#264c38" for value in values],
    )
    axes[1].invert_yaxis()
    axes[1].axvline(0, color="#444", lw=0.8)
    for bar, value in zip(bars, values, strict=True):
        axes[1].text(
            max(value, 0) + 0.8,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            fontsize=9,
        )
    axes[1].set_xlim(-5, 65)
    axes[1].set_xlabel("Transfer minus scratch score (scenario INR)")
    axes[1].set_title("Two health cases drive the difference", fontsize=11)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.15)
        ax.set_axisbelow(True)
    fig.suptitle(
        "Lower SOH forecast error did not improve this scenario objective", fontsize=14, y=0.97
    )
    p = verification["primary"]
    fig.text(
        0.5,
        0.88,
        f"Primary mean: +{p['difference_inr']:.2f} INR; descriptive day-block interval "
        f"[{p['descriptive_low_95_inr']:.2f}, {p['descriptive_high_95_inr']:.2f}]",
        ha="center",
        fontsize=11,
    )
    fig.text(
        0.02,
        0.06,
        "One site, 16 days, six hypothetical battery-health cases, three model seeds. "
        "Hourly modeled PV and ideal interval recourse.",
        fontsize=9,
    )
    fig.text(
        0.02,
        0.025,
        "Reference score includes training-derived wear and terminal inventory. "
        "These are not measured bills, physical wear or field savings.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.20, top=0.75, wspace=0.45)
    output = run / "figures"
    output.mkdir(exist_ok=False)
    fig.savefig(output / "energy_and_reference_score.png", dpi=180)
    plt.close(fig)
    (output / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "verification_sha256": sha256_file(verification_path),
        "primary": p,
        "artifacts": {path.name: sha256_file(path) for path in output.iterdir()},
        "status": "postfit_visualization_only; no_model_or_policy_change",
    }
    (output / "provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    plot(Path(__file__).resolve().parent.parent)
