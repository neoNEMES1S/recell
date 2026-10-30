"""Descriptive review of immutable calendar-study outputs; no refitting or promotion."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from second_life_battery.data.inventory import sha256_file
from second_life_battery.evaluation.plots import plt
from second_life_battery.utils.reproducibility import verify_artifacts


def review(root):
    folder = root / "outputs/calendar/calendar_validation_v1/validation"
    completion = json.loads((folder / "completion.json").read_text())
    verify_artifacts(folder, completion["artifacts"])
    frame = pd.read_csv(folder / "predictions.csv")
    selected = frame.query(
        "variant=='primary' and regime=='full' and role=='test' and model=='C2'"
    ).copy()
    selected["absolute_error"] = abs(selected.prediction - selected.soh)
    invalid = selected[(selected.prediction < 0) | (selected.prediction > 1)]
    worst = (
        selected.sort_values("absolute_error", ascending=False)
        .groupby("base_type", sort=False)
        .head(3)
    )
    summary = pd.read_csv(folder / "type_metrics.csv").query(
        "variant=='primary' and regime=='full' and role=='test'"
    )
    table = summary.pivot(index="base_type", columns="model", values="rmse") * 100
    output = folder.parent / "analysis"
    output.mkdir(exist_ok=False)
    invalid.to_csv(output / "nonphysical_predictions.csv", index=False)
    worst.to_csv(output / "worst_cases_by_type.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(table))
    for offset, name, label, color in [
        (-0.25, "C0", "Constant reference", "#969f99"),
        (0, "C1", "Age only", "#ac823d"),
        (0.25, "C2", "Age + temperature + SOC", "#527c99"),
    ]:
        ax.barh(y + offset, table[name], height=0.23, label=label, color=color)
    ax.set_yticks(y, table.index)
    ax.invert_yaxis()
    ax.set_xlabel("SOH RMSE (percentage points of first observed capacity); lower is better")
    ax.set_title("Separate calendar-storage study: held-out cell-type errors")
    ax.legend(loc="lower right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(
        0.02,
        0.015,
        f"218 cells / 8 types. C2 has {len(invalid)} negative predictions; no M50T calibration.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    figure = output / "held_out_type_errors.png"
    fig.savefig(figure, dpi=160)
    plt.close(fig)
    primary = completion["primary"]
    means = table.mean()
    worst_row = selected.loc[selected.absolute_error.idxmax()]
    text = (
        "# Calendar validation review\n\n"
        "This is the independently registered storage-protocol study, "
        "not the first-life transfer experiment.\n\n"
        f"Average held-out-type RMSE: constant reference {means['C0']:.2f}, "
        f"age-only {means['C1']:.2f}, temperature/SOC-conditioned {means['C2']:.2f} "
        "percentage points. Errors average within cells, then types equally.\n\n"
        f"The C2-minus-C1 difference is {primary['rmse_difference'] * 100:.2f} "
        "percentage points, with descriptive 95% type-bootstrap interval "
        f"[{primary['bootstrap_low_95'] * 100:.2f}, "
        f"{primary['bootstrap_high_95'] * 100:.2f}].\n\n"
        f"C2 produces {len(invalid)} physically impossible negative predictions "
        f"across {invalid.physical_cell_id.nunique()} cells. "
        f"The worst absolute error is {worst_row.absolute_error * 100:.2f} "
        f"percentage points on {worst_row.base_type}. "
        "Tenergy's conditioned-model error also exceeds the constant-reference baseline. "
        "These failures were retained in the metrics; predictions were not clipped.\n\n"
        "An error of 1 percentage point means a capacity error equal to 1% "
        "of that cell's first accepted measured capacity, "
        "not 1% of manufacturer nominal capacity.\n\n"
        "The curves represent apparent loss under storage plus periodic diagnostic cycling. "
        "They are not a pure calendar-loss component and cannot be added "
        "to mixed-aging dispatch wear. No M50T, Indian-pack, lifetime-extension, "
        "billed-savings or deployment validation is established.\n"
    )
    (output / "review.md").write_text(text)
    evidence = {
        "status": "postfit_descriptive_review; no_refit_or_model_promotion",
        "completion_sha256": sha256_file(folder / "completion.json"),
        "nonphysical_predictions": len(invalid),
        "worst_absolute_error": float(worst_row.absolute_error),
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "artifacts": {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "provenance.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "figure": str(figure),
                "nonphysical_predictions": len(invalid),
                "worst_absolute_error": float(worst_row.absolute_error),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    review(Path(__file__).resolve().parent.parent)
