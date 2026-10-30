"""Build a review PDF from the completed calendar study, without refitting models."""

import json
from pathlib import Path
from xml.sax.saxutils import escape

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
    run = root / "outputs/calendar/calendar_validation_v1"
    fit = run / "validation"
    analysis = run / "analysis"
    completion = json.loads((fit / "completion.json").read_text())
    review = json.loads((analysis / "provenance.json").read_text())
    verify_artifacts(fit, completion["artifacts"])
    verify_artifacts(analysis, review["artifacts"])
    assert review["completion_sha256"] == sha256_file(fit / "completion.json")
    assert completion["protocol_sha256"] == sha256_file(run / "protocol.yaml")
    summary = pd.read_csv(fit / "summary.csv")
    types = (
        pd.read_csv(fit / "type_metrics.csv")
        .query("variant=='primary' and regime=='full' and role=='test'")
        .pivot(index="base_type", columns="model", values="rmse")
    )
    assert types.shape == (8, 3) and not types.isna().any().any()
    means = types.mean() * 100
    primary = completion["primary"]
    invalid = pd.read_csv(analysis / "nonphysical_predictions.csv")
    assert len(invalid) == review["nonphysical_predictions"]
    worst = pd.read_csv(analysis / "worst_cases_by_type.csv").absolute_error.max() * 100

    fonts = Path("/System/Library/Fonts/Supplemental")
    pdfmetrics.registerFont(TTFont("Review", str(fonts / "Arial.ttf")))
    pdfmetrics.registerFont(TTFont("ReviewBold", str(fonts / "Arial Bold.ttf")))
    pdfmetrics.registerFont(TTFont("ReviewMono", str(fonts / "Courier New.ttf")))
    pdfmetrics.registerFontFamily("Review", normal="Review", bold="ReviewBold")
    style = getSampleStyleSheet()
    style.add(
        ParagraphStyle(
            "BodyReview",
            fontName="Review",
            fontSize=10,
            leading=14,
            spaceAfter=9,
            textColor=colors.HexColor("#263a31"),
        )
    )
    style.add(
        ParagraphStyle(
            "TitleReview",
            parent=style["BodyReview"],
            fontName="ReviewBold",
            fontSize=25,
            leading=29,
            spaceAfter=15,
        )
    )
    style.add(
        ParagraphStyle(
            "HeadingReview",
            parent=style["BodyReview"],
            fontName="ReviewBold",
            fontSize=15,
            leading=19,
            spaceBefore=9,
            spaceAfter=10,
        )
    )
    style.add(
        ParagraphStyle(
            "SmallReview", parent=style["BodyReview"], fontSize=8.3, leading=11, spaceAfter=7
        )
    )
    style.add(
        ParagraphStyle(
            "FormulaReview",
            parent=style["BodyReview"],
            fontName="ReviewMono",
            fontSize=9,
            leading=13,
            backColor=colors.HexColor("#f0f4f1"),
            borderPadding=8,
            spaceBefore=5,
            spaceAfter=13,
        )
    )
    style.add(
        ParagraphStyle(
            "TableReview", parent=style["BodyReview"], fontSize=9, leading=12, spaceAfter=0
        )
    )
    style.add(
        ParagraphStyle(
            "TableHeadReview",
            parent=style["TableReview"],
            fontName="ReviewBold",
            textColor=colors.white,
        )
    )
    story = []

    def para(text, kind="BodyReview"):
        story.append(Paragraph(text, style[kind]))

    def heading(text):
        para(text, "HeadingReview")

    def formula(text):
        para(escape(text).replace("\n", "<br/>"), "FormulaReview")

    def table(rows, widths):
        content = [
            [
                Paragraph(escape(str(value)), style["TableHeadReview" if i == 0 else "TableReview"])
                for value in row
            ]
            for i, row in enumerate(rows)
        ]
        item = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#254334")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#f0f4f1"), colors.white],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.extend([item, Spacer(1, 11)])

    para("ReCell | Calendar-aging research review", "TitleReview")
    para("27 October 2026 | Independent study | Protocol calendar_validation_v1", "SmallReview")
    para(
        "<b>Review decision:</b> retain this as a research comparison. Average prediction "
        "error improved, but severe failures prevent adoption as a battery-life or dispatch model."
    )
    table(
        [
            ["Held-out-type RMSE", "Age only", "Age + temperature + SOC"],
            ["Percentage points", f"{means.C1:.2f}", f"{means.C2:.2f}"],
        ],
        [245, 100, 165],
    )
    para(
        "The primary test covers <b>218 physical cells, eight held-out cell types and "
        "9,249 future capacity observations</b>. Types receive equal weight in the final score."
    )
    story.append(Image(str(analysis / "held_out_type_errors.png"), width=510, height=306))
    para(
        f"<b>Failure evidence:</b> {len(invalid)} impossible negative SOH predictions across "
        f"{invalid.physical_cell_id.nunique()} cells; worst absolute error {worst:.2f} percentage "
        "points. Every failure remains in the reported metrics."
    )
    para(
        "This is separate from the first-life transfer experiment. No result here establishes "
        "M50T calibration, Indian pack performance, measured life extension or customer savings.",
        "SmallReview",
    )

    story.append(PageBreak())
    heading("1. Data and attributes")
    para(
        "The pinned Stanford calendar release supplies storage experiments across eight base "
        "cell types and four chemistries. It contains Sony VTC6 NMC cells, but no LG M50T cells."
    )
    table(
        [
            ["Attribute", "Role in this study"],
            [
                "Third C/5 discharge capacity (Ah)",
                "RPT0.2C_2_D_capacity supplies the measured target "
                "and each cell's first reference.",
            ],
            [
                "Elapsed storage days",
                "Predictor in C1 and C2; clock/reference consistency is audited.",
            ],
            ["Storage temperature (degrees C)", "C2 predictor; source settings: 24, 45, 60 or 85."],
            ["Storage SOC (fraction)", "C2 predictor; source settings: 0.5 or 1.0."],
            [
                "Physical-cell identity and base type",
                "Split and weighting keys, not predictive inputs.",
            ],
            [
                "Chemistry, lot and author comments",
                "Compatibility review and predefined sensitivity; "
                "alternate _v2 lots stay grouped with their base type.",
            ],
        ],
        [192, 318],
    )
    para(
        "<b>Coverage:</b> 259 inventory IDs; 232 published summary files; 27 missing summaries. "
        "The parser accepts 9,481 checkpoints and quarantines 14 ambiguous day-only clock rows "
        "across seven cells. Fourteen single-observation cells remain descriptive; they do not "
        "receive invented future labels. The other 218 support predictive evaluation."
    )
    heading("What is fitted, and what is held back?")
    para(
        "Each of eight outer folds holds out one complete base cell type for testing. The next "
        "sorted type is reserved for validation; the other six supply parameter fitting. "
        "No physical battery appears in multiple roles within a fold. Test cells provide only "
        "their initial observed capacity reference, with no parameter updates."
    )
    para(
        "<b>Primary cohort:</b> all eligible author-curated histories. <b>Sensitivity:</b> remove "
        "all 13 cells with notes about deleted potentially swapped measurements from every "
        "role. Recoveries, above-reference capacities and double-bag notes remain visible."
    )
    para(
        "Summary capacities are source-provided labels. All underlying raw diagnostic curves "
        "were not independently audited. This limitation applies to every model.",
        "SmallReview",
    )

    story.append(PageBreak())
    heading("2. Mathematical model and fitting")
    para(
        "For cell c, Q(c,0) is the first accepted measured capacity and Q(c,i) is a later "
        "capacity. Elapsed age d is measured from that first accepted reference. SOH is a "
        "fraction of this reference, not manufacturer nominal capacity."
    )
    formula(
        "y(c,i) = Q(c,i) / Q(c,0)\nu = sqrt(d / 365.25)\n"
        "zT = 1000 * [1/297.15 - 1/(T_C + 273.15)]\nzS = s - 0.5"
    )
    table(
        [
            ["Model", "Predicted SOH", "Interpretation"],
            ["C0", "1", "Constant initial-reference baseline"],
            ["C1", "1 - a*u, with a >= 0", "Shared square-root-age loss"],
            [
                "C2",
                "1 - exp(alpha + beta_T*zT + beta_s*zS)*u",
                "Age loss conditioned on storage temperature and SOC",
            ],
        ],
        [46, 281, 183],
    )
    para(
        "The temperature transform is centered at 24 degrees C (297.15 K); SOC is centered "
        "at 50%. C2 is a fixed empirical model family, not an identified electrochemical law. "
        "Its exponential coefficient is positive, but predictions can fall below zero."
    )
    heading("Training objective")
    formula(
        "minimize sum_(k,c,i) w(k,c,i) * [yhat(c,i) - y(c,i)]^2\nw(k,c,i) = 1 / [K * C_k * N_c]"
    )
    para(
        "K is the number of represented training types, C_k their training-cell count and N_c "
        "a cell's permitted positive-age observations. Thus each type, then cell, receives "
        "equal weight. The reference observation at age zero is excluded from fitting and scoring."
    )
    formula("C1: a = max(0, sum(w*u*(1-y)) / sum(w*u*u))")
    para(
        "C2 uses bounded nonlinear least squares: alpha in [-20, 2], beta_T in [0, 20], "
        "beta_s in [-10, 10]. Six fixed starts combine beta_T = 0, 2, 5 with beta_s = 0, 1; "
        "initial alpha is log(max(a, 1e-8)), restricted to optimizer bounds. The converged "
        "solution with lowest training cost wins. Validation/test labels never select it."
    )
    para(
        "SciPy trf, linear loss, at most 2,000 evaluations per start, x_scale=1, "
        "ftol=xtol=gtol=1e-8. No label or prediction clipping; no interpolation.",
        "SmallReview",
    )

    story.append(PageBreak())
    heading("3. Metrics, uncertainty and failures")
    formula(
        "RMSE_c = sqrt(mean_i[(yhat(c,i) - y(c,i))^2])\n"
        "RMSE_type = mean_cells(RMSE_c)\nReported RMSE = mean_8_test_types(RMSE_type)"
    )
    para(
        "Multiply a SOH-fraction error by 100 to obtain percentage points. A one-point error "
        "equals 1% of that cell's first measured capacity. MAE follows the same cell/type "
        "aggregation using absolute errors. Lower error is better."
    )
    table(
        [["Held-out base type", "C0", "C1", "C2"]]
        + [
            [name, f"{row.C0 * 100:.2f}", f"{row.C1 * 100:.2f}", f"{row.C2 * 100:.2f}"]
            for name, row in types.iterrows()
        ],
        [282, 76, 76, 76],
    )
    para(
        f"<b>Primary contrast:</b> C2 minus C1 = {primary['rmse_difference'] * 100:.2f} points; "
        f"descriptive 95% bootstrap interval [{primary['bootstrap_low_95'] * 100:.2f}, "
        f"{primary['bootstrap_high_95'] * 100:.2f}]. Ten thousand paired resamples use the "
        "eight types as units, seed 42. Overlapping training folds and eight types limit "
        "the inference; the observations are not thousands of independent battery types."
    )
    secondary = []
    for variant, regime, label in [
        ("primary", "early180", "Train age <=180d, test >180d"),
        ("exclude_author_swap_notes", "full", "Exclude swap-note cells, full age"),
    ]:
        selected = summary[
            (summary.variant == variant) & (summary.regime == regime) & (summary.role == "test")
        ].set_index("model")
        secondary.append(
            [
                label,
                f"{selected.loc['C1', 'rmse'] * 100:.2f}",
                f"{selected.loc['C2', 'rmse'] * 100:.2f}",
            ]
        )
    table([["Registered secondary check", "C1 RMSE", "C2 RMSE"]] + secondary, [310, 100, 100])
    para(
        "<b>Do not hide failures:</b> the 44 negative C2 outputs occur on four K2 Energy "
        "LFP18650E cells at 85 degrees C / 100% SOC. Tenergy's C2 error exceeds the "
        f"constant baseline; its worst single absolute error is {worst:.2f} points. "
        "No source-data explanation is assumed without further raw evidence."
    )

    story.append(PageBreak())
    heading("4. What this supports, and what remains open")
    for text in [
        "<b>Supported:</b> a reproducible comparison of three preregistered apparent "
        "storage-loss models on unseen cell types, including chronological extrapolation "
        "and a predefined author-note sensitivity. The conditioned model has lower average error.",
        "<b>Model limit:</b> severe type errors and physically impossible forecasts prevent "
        "automatic adoption. Any changed family needs a new registered comparison, not "
        "retuning on these test results.",
        "<b>Aging accounting:</b> storage experiments include periodic diagnostic cycling. "
        "Pure calendar loss and diagnostic loss are not separately identified. Adding this "
        "curve to existing mixed-aging wear would risk double-counting.",
        "<b>Application gap:</b> M50T cells are absent. Measured target-cell temperature, "
        "independent calibration and pack/BMS evidence are still needed. Ambient weather "
        "is not cell temperature. This study does not validate Indian customer savings.",
        "<b>Source gate:</b> first-life transfer remains blocked by 13 rejected cycling batches. "
        "This calendar study neither repairs that data nor demonstrates "
        "positive or negative transfer.",
        "<b>Release gap:</b> the reviewed OSF node metadata declares no license. This records "
        "a missing declaration; intended redistribution/commercial use still needs clarification.",
    ]:
        para(text)
    heading("Sources and reproducibility")
    para(
        'Author source: <link href="https://github.com/viveklam/Joule-Decade-Calendar-Aging" '
        'color="#2e637d">Joule-Decade-Calendar-Aging</link>, commit '
        "0bc2d6393da223e6d850896b6501153630d393ca; "
        '<link href="https://osf.io/ju325/" color="#2e637d">OSF ju325 release</link>. '
        "Third-discharge summaries are pinned by archive and member hashes.",
        "SmallReview",
    )
    para(
        "Sealed before fitting: 2026-10-27T17:53:41.066944+00:00. Protocol SHA-256:", "SmallReview"
    )
    formula(completion["protocol_sha256"][:32] + "\n" + completion["protocol_sha256"][32:])
    para(
        "Review evidence: docs/calendar_source_audit.md; "
        "configs/calendar_protocol_v1.yaml; outputs/calendar/calendar_validation_v1/. "
        "The validation folder retains fit coefficients, all predictions, cell/type metrics, "
        "optimizer records, implementation source and input/artifact hashes.",
        "SmallReview",
    )
    para(
        "Verification: 141 software tests and lint pass. An independent saved-output check "
        "reproduced all scores and predictions across 32 fold configurations, verified "
        "physical/type separation, and checked 200,628 saved prediction rows and artifact "
        "hashes. Software checks do not establish field validity.",
        "SmallReview",
    )
    para(
        "Historical forecasting, dispatch and dashboard results remain preserved. "
        "This PDF is an additional review artifact; no model was refitted to produce it.",
        "SmallReview",
    )

    output = root / "output/pdf/recell_calendar_validation_review.pdf"
    if output.exists():
        raise FileExistsError("Preserve the existing PDF; use an explicit review revision")

    def page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dbe3dc"))
        canvas.line(42, 34, A4[0] - 42, 34)
        canvas.setFont("Review", 8)
        canvas.setFillColor(colors.HexColor("#617168"))
        canvas.drawString(42, 21, "ReCell | Research review - application gates open")
        canvas.drawRightString(A4[0] - 42, 21, f"{doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=40,
        bottomMargin=45,
        title="ReCell calendar validation review",
        author="ReCell research",
        pageCompression=1,
    )
    doc.build(story, onFirstPage=page, onLaterPages=page)
    provenance = {
        "pdf_sha256": sha256_file(output),
        "builder_sha256": sha256_file(Path(__file__).resolve()),
        "completion_sha256": sha256_file(fit / "completion.json"),
        "postfit_review_sha256": sha256_file(analysis / "provenance.json"),
        "protocol_sha256": completion["protocol_sha256"],
        "purpose": "additional review artifact; no refit or model promotion",
    }
    output.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent)
