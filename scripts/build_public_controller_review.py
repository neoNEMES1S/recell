"""Create a mathematical-review supplement from immutable reviewed results; no refits."""

import json
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from second_life_battery.data.inventory import sha256_file
from second_life_battery.utils.reproducibility import verify_artifacts


def build(root):
    run = root / "outputs/india_ci/india_public_controller_v1/comparison"
    review = run / "review"
    check_path = review / "verification.json"
    check = json.loads(check_path.read_text())
    complete = json.loads((run / "completion.json").read_text())
    verify_artifacts(run, complete["artifacts"])
    verify_artifacts(review, check["artifacts"])
    if check["completion_sha256"] != sha256_file(run / "completion.json"):
        raise ValueError("Independent controller review no longer matches the run")
    figure = run / "figures"
    picture = json.loads((figure / "provenance.json").read_text())
    verify_artifacts(figure, picture["artifacts"])
    if picture["verification_sha256"] != sha256_file(check_path):
        raise ValueError("Figure no longer matches reviewed results")
    audit = root / "outputs/integration/gate_review_20261030"
    integrity = json.loads((audit / "evidence.json").read_text())
    verify_artifacts(root, integrity["original_pdfs_before_addendum"])
    if integrity["reviews"]["controller"]["sha256"] != sha256_file(check_path):
        raise ValueError("Integration audit no longer matches the controller review")
    summary = pd.read_csv(review / "policy_summary.csv").set_index("policy")
    expected = ["A_no_battery", "B_greedy", "C_energy", "D_R1", "D_R2", "D_R5"]
    if summary.index.tolist() != expected or not np.isfinite(summary.to_numpy()).all():
        raise ValueError("Incomplete or nonfinite policy score table")
    primary = check["primary"]
    difference = summary.loc["D_R2"] - summary.loc["D_R1"]
    if not np.isclose(difference.reference_score_inr, primary["difference_inr"], atol=1e-7):
        raise ValueError("Primary result and policy summary disagree")
    battery_report = root / "outputs/transfer/ev_to_second_life_v3/comparison/report"
    battery_check_path = (
        root / "outputs/transfer/ev_to_second_life_v3/comparison/review/verification.json"
    )
    battery_check = json.loads(battery_check_path.read_text())
    verify_artifacts(battery_report.parent, battery_check["report_artifacts"])
    health = pd.read_csv(battery_report / "summary.csv")
    health = health[(health.history_fraction == 0.1) & (health.horizon == 1)].set_index("model")
    sensitivity = pd.read_csv(review / "fixed_score_sensitivities.csv").pivot(
        index="reference_wear_multiplier",
        columns="policy",
        values="inventory_adjusted_reference_score_inr",
    )
    out = root / "output/pdf/recell_public_controller_mathematical_review.pdf"
    provenance = audit / "mathematical_supplement"
    if out.exists() or provenance.exists():
        raise FileExistsError("Completed supplement outputs are immutable; use a new version")

    fonts = Path("/System/Library/Fonts/Supplemental")
    for name, filename in [
        ("Review", "Arial.ttf"),
        ("ReviewBold", "Arial Bold.ttf"),
        ("ReviewMono", "Courier New.ttf"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily("Review", normal="Review", bold="ReviewBold")
    styles = getSampleStyleSheet()
    for name, changes in {
        "BodyReview": {"fontSize": 9.4, "leading": 13.2, "spaceAfter": 8},
        "TitleReview": {"fontName": "ReviewBold", "fontSize": 23, "leading": 27, "spaceAfter": 12},
        "HeadingReview": {
            "fontName": "ReviewBold",
            "fontSize": 15,
            "leading": 19,
            "spaceAfter": 10,
        },
        "SmallReview": {"fontSize": 8, "leading": 11, "spaceAfter": 7},
        "FormulaReview": {
            "fontName": "ReviewMono",
            "fontSize": 8.1,
            "leading": 12,
            "backColor": colors.HexColor("#edf3ef"),
            "borderPadding": 7,
            "spaceBefore": 5,
            "spaceAfter": 13,
        },
        "CellReview": {"fontSize": 8.4, "leading": 11, "spaceAfter": 0},
        "HeadReview": {
            "fontName": "ReviewBold",
            "fontSize": 8.4,
            "leading": 11,
            "textColor": colors.white,
        },
    }.items():
        defaults = {"fontName": "Review", "textColor": colors.HexColor("#263a31")}
        styles.add(ParagraphStyle(name, **(defaults | changes)))
    story = []

    def p(text, style="BodyReview"):
        story.append(Paragraph(text, styles[style]))

    def formula(text):
        p(escape(text).replace("\n", "<br/>"), "FormulaReview")

    def table(rows, widths):
        cells = [
            [
                Paragraph(escape(str(value)), styles["HeadReview" if i == 0 else "CellReview"])
                for value in row
            ]
            for i, row in enumerate(rows)
        ]
        item = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#254334")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#edf3ef"), colors.white],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([item, Spacer(1, 8)])

    p("ReCell | Public controller<br/>Mathematical review supplement", "TitleReview")
    p("30 October 2026 | India C&I research | Registered offline scenario", "SmallReview")
    p(
        "<b>Review decision:</b> advance data access and calibration for a validation pilot. "
        "The experiment does not support autonomous operation, an investment approval or "
        "guaranteed savings. The published research dashboard remains unchanged."
    )
    p(
        f"Transfer-based planning changes the 16-day common-reference score by "
        f"<b>+INR{primary['difference_inr']:.2f}</b> versus scratch-based planning; "
        "higher is worse. "
        f"Descriptive 95% day-block interval: [{primary['descriptive_low_95_inr']:.2f}, "
        f"{primary['descriptive_high_95_inr']:.2f}] INR."
    )
    names = [
        "No battery",
        "Greedy",
        "Energy-only plan",
        "Scratch-GRU wear",
        "Transfer-GRU wear",
        "XGBoost wear",
    ]
    table(
        [["Policy", "Energy charge", "Wear proxy", "Inventory", "Reference score"]]
        + [
            [
                label,
                *(
                    f"{summary.loc[policy, column]:,.2f}"
                    for column in [
                        "grid_energy_charge_inr",
                        "reference_wear_cost_inr",
                        "inventory_adjustment_inr",
                        "reference_score_inr",
                    ]
                ),
            ]
            for policy, label in zip(expected, names, strict=True)
        ],
        [142, 92, 86, 78, 112],
    )
    p(
        "Mean scenario INR per 16 days: average three seeds within each health case, then "
        "six health cases equally. All policies within a case share physical capacity and limits. "
        "Amounts are not measured utility bills or observed physical wear.",
        "SmallReview",
    )
    story.append(Image(str(figure / "energy_and_reference_score.png"), width=510, height=246.5))
    p(
        "Lower grid energy charges do not automatically improve the complete objective. "
        "No battery has the lowest mean reference score here; demand/ToD charges, actual "
        "pack calibration and investment costs remain outside this scenario.",
        "SmallReview",
    )

    story.append(PageBreak())
    p("1. Data, attributes and prediction", "HeadingReview")
    table(
        [
            ["Attribute", "Use and boundary"],
            [
                "Diagnostic discharge capacity Q (Ah)",
                "Measured health target; Q_ref is the first accepted capacity of that life "
                "stage, not a future maximum.",
            ],
            [
                "Past SOH, elapsed stage days, cumulative Ah",
                "Three shared GRU/XGBoost predictors. Only accepted history available "
                "at an origin enters the sequence.",
            ],
            [
                "Physical battery, life stage, hashes and protocol",
                "Split/provenance keys. Histories do not cross life stages; a held-out "
                "cell's first life cannot train its second-life predictor.",
            ],
            [
                "Delhi academic-building demand (kW)",
                "Measured active-power benchmark: 91 complete days, chronological "
                "60/15/16-day split. Gross/net-meter topology remains unverified.",
            ],
            [
                "Regional hourly GHI and modeled PV (kW)",
                "NASA historical resource; 40 kWp DC/32 kW AC horizontal scenario. "
                "Quarter-hour values retain 60-minute source resolution; not measured PV.",
            ],
            [
                "Temperature, resistance, duty and future metadata",
                "Not predictors in the three-feature transfer comparison. Ambient air "
                "is not battery temperature. Future labels/exposure never fill past inputs.",
            ],
        ],
        [186, 324],
    )
    formula(
        "SOH_j = Q_j / Q_ref\n"
        "age_j = (diagnostic_end_j - diagnostic_end_1) / 86400\n"
        "Ah = sum_k[0.5*(abs(I_k)+abs(I_(k+1)))*delta_t_k/3600]\n"
        "x_j = [SOH_j, age_j, verified_Ah_j - verified_Ah_1]"
    )
    p(
        "The registered v3 amendment uses verified first-life prefixes and separate later "
        "measured capacity labels. The original full-history v2 gate remains failed. A future "
        "label can supervise a valid earlier input; it cannot create a missing input history."
    )
    p(
        "Source training predicts the next checkpoint; the target model outputs the next two "
        "checkpoints. Transfer copies the GRU/representation, resets the head and optimizer, "
        "and fine-tunes on permitted target-training cells. Scaling uses target-training "
        "checkpoints only. Six physical test folds retain 87 origins and three seeds."
    )
    formula(
        "RMSE_b,s = sqrt(mean_origins[(predicted_SOH - measured_SOH)^2])\n"
        "Reported RMSE = mean_cells(mean_seeds(RMSE_b,s)) * 100"
    )
    table(
        [["10% context, next checkpoint", "RMSE (SOH percentage points)"]]
        + [
            [name, f"{health.loc[arm, 'rmse_mean'] * 100:.4f}"]
            for arm, name in [
                ("R1", "Scratch PGP-GRU"),
                ("R2", "Transfer PGP-GRU"),
                ("R5", "XGBoost"),
            ]
        ],
        [270, 240],
    )
    p(
        "Transfer's small average health-error improvement has negative cases (G1/W8). "
        "Nominal 80% intervals are not well calibrated. XGBoost has the lowest observed "
        "mean error. Six familiar cells do not establish population superiority.",
        "SmallReview",
    )

    story.append(PageBreak())
    p("2. Scheduling physics and information", "HeadingReview")
    p(
        "The comparison replays one public demand window, 1-16 December 2014. Six "
        "later laboratory health states with three model seeds create 18 hypothetical "
        "cases, not 18 sites. The lab states are not attributed to the building in 2014."
    )
    p(
        "Let L_t and S_t be interval mean load and modeled PV (kW); c_t and d_t are AC "
        "charging/discharging power. e_t is stored internal energy (kWh). eta is one-way "
        "efficiency. The 40 kWh/20 kW battery is generic, with constant health during replay."
    )
    formula(
        "dt = 0.25 h; eta = sqrt(0.90); E_nom = 40 kWh\n"
        "H_origin = origin_SOH * Q_ref / 4.85 Ah\n"
        "E_capacity = E_nom * H_origin\n"
        "0.1*E_capacity <= e_t <= 0.9*E_capacity\n"
        "e_initial = 0.5*E_capacity\n"
        "e_(t+1) = e_t + eta*c_t*dt - d_t*dt/eta"
    )
    formula(
        "surplus_t = max(S_t-L_t, 0); deficit_t = max(L_t-S_t, 0)\n"
        "0 <= c_t <= min(20, surplus_t)\n"
        "0 <= d_t <= min(20, deficit_t)\n"
        "direct_PV_t = min(L_t,S_t)\n"
        "grid_import_t = deficit_t - d_t\n"
        "curtailed_PV_t = surplus_t - c_t; grid_export_t = 0\n"
        "throughput = sum_t[(eta*c_t+d_t/eta)*dt]\n"
        "EFC = throughput / (2*E_nom)"
    )
    p(
        "Charging is PV-only; discharge serves net load. Nonoverlapping surplus and "
        "deficit prohibit simultaneous charge/discharge. Residual PV is curtailed; grid "
        "imports are unlimited. Export permission, backup operation and physical curtailment "
        "capability have not been validated at a site."
    )
    p(
        "<b>Planning at midnight IST:</b> forecast the next 96 quarters using completed "
        "past intervals. Demand is the frozen 50/50 previous-day/previous-week blend; "
        "PV repeats the previous day's modeled profile. No future realized load, "
        "resource or SOH label enters the plan."
    )
    formula("Lhat(day,q) = 0.5*L(day-1,q) + 0.5*L(day-7,q)\nShat(day,q) = S(day-1,q)")
    p(
        "<b>Execution:</b> ideal current-quarter feedback clamps requested power to "
        "realized mean surplus/deficit, power and energy bounds. Realized SOC carries "
        "between quarters and days without a hard daily reset. A zero-latency modeled "
        "observation feed and interval-mean feedback are not a verified live controller."
    )
    p(
        "<b>Unit example:</b> charging at 10 kW for 15 minutes consumes 2.5 AC kWh and "
        "adds approximately 2.372 internal kWh at eta = sqrt(0.90). Energy is not kW "
        "multiplied by 15 without converting minutes to hours."
    )

    story.append(PageBreak())
    p("3. Wear, costs and the objective", "HeadingReview")
    p(
        "Only four target gradient-training cells calibrate wear for each held-out "
        "case. Validation/test histories and future SOH labels never calibrate it. "
        "Let delta_Ah be accepted interval exposure, and Q_ref the cell's stage reference."
    )
    formula(
        "EFC_b,j = delta_Ah_b,j / (2*4.85 Ah)\n"
        "loss_b,j = (SOH_(j-1)-SOH_j)*Q_ref_b/4.85 Ah\n"
        "expected_EFC = median_b(median_j(EFC_b,j))\n"
        "r_reference = max(0, median_b(median_j(loss_b,j/EFC_b,j)))\n"
        "r_planner = max(0, (origin_SOH-predicted_median_SOH)\n"
        "                  * Q_ref/4.85 Ah / expected_EFC)"
    )
    p(
        "The medians use only exposure increments above the audited 1e-6 Ah tolerance. "
        "Signed capacity recoveries remain in reference-loss statistics; zero-exposure "
        "intervals receive no invented rate. XGBoost supplies a point forecast, without "
        "fabricated quantiles. This mixed-aging throughput proxy is not physical wear truth; "
        "no calendar term is added."
    )
    formula(
        "price = 10 INR/kWh; replacement = 400000 INR; loss_budget = 0.20\n"
        "Wear(r) = replacement * r * EFC / loss_budget\n"
        "v = price*eta  [INR/internal kWh]\n"
        "J_plan = price*forecast_grid_kWh + Wear(r_planner)\n"
        "         - v*(e_end-e_start) + 1e-6*sum_t[(c_t^2+d_t^2)*dt]\n"
        "J_reference = price*realized_grid_kWh + Wear(r_reference)\n"
        "              - v*(e_final-e_initial)"
    )
    p(
        "Terminal inventory prevents free use of initial energy and accounts for unequal "
        "final SOC. The credit is an assumed energy-service value, not a utility payment "
        "or full future wear/value model. The fixed quadratic planning preference is "
        "excluded from evaluation; its maximum INR0.0192/day is not a replay error bound."
    )
    table(
        [["Transfer minus scratch component", "Scenario INR / 16 days"]]
        + [
            [name, f"{difference[key]:+.2f}"]
            for name, key in [
                ("Energy charge", "grid_energy_charge_inr"),
                ("Common reference wear", "reference_wear_cost_inr"),
                ("Inventory adjustment", "inventory_adjustment_inr"),
                ("Total reference score", "reference_score_inr"),
            ]
        ],
        [330, 180],
    )
    table(
        [["Evaluation-wear multiplier", "Transfer minus scratch score (INR)"]]
        + [[f"{scale:g}", f"{row.D_R2 - row.D_R1:+.2f}"] for scale, row in sensitivity.iterrows()],
        [230, 280],
    )
    p(
        "These fixed-action score sensitivities do not reoptimize policies. The ranking "
        "changes with an unvalidated coefficient. Totals are calculated before rounding. "
        "W10/W8 dominate the primary difference; "
        "four other case differences are below INR0.006. No result is a measured saving.",
        "SmallReview",
    )

    story.append(PageBreak())
    p("4. Evidence gates and review decision", "HeadingReview")
    table(
        [
            ["Evidence", "Current finding / next required evidence"],
            [
                "Reference and transfer",
                "539 frozen processed/result/dashboard paths unchanged. v3 comparison "
                "complete; v2 source defects remain. Keep all physical splits and exclusions.",
            ],
            [
                "Calendar application",
                "Separate study complete, including 44 negative predictions. M50T "
                "calibration, probe mapping, loss decomposition and intended-use "
                "clarification remain open.",
            ],
            [
                "Paired site measurements",
                "Measured load plus modeled PV only. Obtain actual paired load/PV/battery "
                "records, meter topology, units, timezone, quality flags and reuse terms.",
            ],
            [
                "Connection and bill",
                "Obtain category, voltage, contract demand, applicable DISCOM amendments, "
                "ToD/demand/export rules and complete bills. Reconcile kVAh/PF where required.",
            ],
            [
                "Pack and BMS",
                "Obtain chemistry/identity, quotation, measured usable capacity/efficiency, "
                "SOC/temperature channels, sensor map and operating constraints.",
            ],
            [
                "Forecasts and operation",
                "Seal independent site split, forecast availability, delay, policy arms "
                "and success criteria before scoring. Verify timing and perform supervised "
                "operation.",
            ],
            [
                "Dashboard release",
                "Hold candidate release until provenance, selection and field/claim gates "
                "pass. Current public simulation cannot approve deployment or establish "
                "lifetime extension.",
            ],
        ],
        [143, 367],
    )
    p(
        "<b>Verification:</b> the latest recorded software suite has 216 passing tests. "
        "Independent reviews replayed all 15,660 health predictions and reconstructed "
        "all 165,888 controller actions and 108 case scores. Forecast cutoffs, SOC "
        "continuity, wear coefficients and primary bootstrap were checked. Maximum "
        "planner residual is 1.95e-8; realized balance/SOC residual is 3.56e-15 kWh. "
        "The new integration audit checks saved artifact bytes and review links, not hardware."
    )
    p(
        "<b>Uncertainty:</b> the primary controller 95% interval uses 10,000 paired circular "
        "four-day block resamples over 16 days, after averaging seeds then health cases. "
        "It is conditional on one short site window, modeled PV, fixed pack and wear "
        "assumptions. It is not cross-site or population evidence."
    )
    p("Sources and reproducibility", "HeadingReview")
    for text in [
        "Demand: I-BLEND, DOI 10.6084/m9.figshare.6007637.v1 (CC0); modeled solar resource: "
        "NASA POWER, approximate point 28.55 N / 77.27 E. Detailed source/units audits: "
        "docs/india_public_data_audit.md and docs/india_pv_source_audit.md.",
        "Registered controller protocol: configs/india_public_controller_v1.yaml. "
        "Sealed 29 October 2026, 17:15:12 UTC, before controller outcomes. Health results, "
        "load errors and PV totals were already known; no new prospective cohort is claimed.",
        "Equations/results: docs/india_controller_review.md. Complete requirement review: "
        "docs/integration_gate_review.md. Executed runs, ledgers and independent "
        "verification: outputs/india_ci/india_public_controller_v1/.",
        "Review provenance: outputs/integration/gate_review_20261030/. The original "
        "attributes/model, transfer and calendar PDFs are preserved. This supplement "
        "documents the separate quarter-hour controller; it does not rewrite the hourly "
        "historical optimizer.",
    ]:
        p(escape(text), "SmallReview")
    p(
        "<b>Decision boundary:</b> discuss a validation pilot for missing data and calibration. "
        "An actual site's acceptance criteria require agreement before evaluation. "
        "The full phases 14-20 goal remains incomplete."
    )

    def page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#c5d4c9"))
        canvas.line(42, 39, A4[0] - 42, 39)
        canvas.setFont("Review", 8)
        canvas.setFillColor(colors.HexColor("#52665a"))
        canvas.drawString(
            42, 25, "ReCell | Research review | Scenario INR; no verified field savings"
        )
        canvas.drawRightString(A4[0] - 42, 25, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=39,
        bottomMargin=52,
        title="ReCell Public Controller Mathematical Review",
        author="ReCell",
    )
    doc.build(story, onFirstPage=page, onLaterPages=page)
    provenance.mkdir()
    (provenance / "implementation.py").write_bytes(Path(__file__).read_bytes())
    result = {
        "status": "mathematical_supplement_created; visual_QA_required; no_model_change",
        "review_sha256": sha256_file(check_path),
        "integration_evidence_sha256": sha256_file(audit / "evidence.json"),
        "battery_review_sha256": sha256_file(battery_check_path),
        "figure_sha256": sha256_file(figure / "energy_and_reference_score.png"),
        "output": str(out.relative_to(root)),
        "output_sha256": sha256_file(out),
        "implementation_sha256": sha256_file(provenance / "implementation.py"),
    }
    (provenance / "provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent)
