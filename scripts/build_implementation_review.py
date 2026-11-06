"""Build a review PDF from checked numeric artifacts, without refitting any model."""

import csv
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build():
    root = Path.cwd()
    review = root / "outputs/implementation/proposal_v1/review"
    complete = json.loads((review / "completion.json").read_text())

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    for name, expected in complete["artifacts"].items():
        if digest(review / name) != expected:
            raise ValueError(f"Checked review artifact changed: {name}")

    def load(name):
        return json.loads((review / name).read_text())

    def table_rows(path):
        with path.open() as stream:
            return list(csv.DictReader(stream))

    es = table_rows(review / "ecm_summary.csv")
    ec = table_rows(review / "ecm_per_cell.csv")
    hs = table_rows(review / "health_summary.csv")
    ep, hp, check = load("ecm_primary.json"), load("health_primary.json"), load("verification.json")
    params = table_rows(root / "outputs/ecm/local_pulse_ecm_v1/comparison/parameters.csv")
    selected = json.loads(
        (
            root / "outputs/model_selection/health_selection_v1/comparison/selections.json"
        ).read_text()
    )
    inventory = table_rows(root / "outputs/life/life_inventory_v1/inventory.csv")
    output = root / "output/pdf/recell_model_implementation_review.pdf"
    if output.exists():
        raise FileExistsError("Preserve completed PDF; choose a new version")
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleR",
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            textColor=colors.HexColor("#1a3c2b"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeadingR",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=9,
        )
    )
    styles.add(
        ParagraphStyle(name="BodyR", fontName="Helvetica", fontSize=9.5, leading=13.4, spaceAfter=9)
    )
    styles.add(
        ParagraphStyle(name="SmallR", fontName="Helvetica", fontSize=8, leading=10.5, spaceAfter=7)
    )
    styles.add(
        ParagraphStyle(
            name="MonoR", fontName="Courier", fontSize=8.6, leading=12, spaceBefore=6, spaceAfter=12
        )
    )
    story = []

    def p(text, style="BodyR"):
        story.append(Paragraph(text, styles[style]))

    def title(text, subtitle):
        p(text, "TitleR")
        p(subtitle, "SmallR")

    def tab(headers, rows, widths):
        data = [
            [Paragraph(escape(str(v)), styles["SmallR"]) for v in row] for row in [headers, *rows]
        ]
        t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eee2")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f6f8f4")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#9aae96")),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 10))

    def formula(text):
        story.append(Preformatted(text, styles["MonoR"]))

    def new():
        story.append(PageBreak())

    def f(value, digits=3):
        return f"{float(value):.{digits}f}"

    def e(model):
        return next(x for x in es if x["model"] == model and x["role"] == "test")

    title(
        "ReCell model implementation",
        "Research and mathematical review | 5 November 2026 | Version 1",
    )
    p(
        (
            "The local mathematical-model and AI implementation is now "
            "reviewable. This report distinguishes measured comparisons, "
            "software checks and requirements that still depend on external "
            "evidence."
        )
    )
    tab(
        ["Evidence", "Result", "Boundary"],
        [
            [
                "Measured local pulse test",
                f"One-RC RMSE {f(e('1rc')['rmse_mv'])} mV; Rint {f(e('rint')['rmse_mv'])} mV",
                "Later diagnostics of the same six cells; constant OCV over short windows",
            ],
            [
                "Bounded CPU AI selection",
                "270 validation trials; 2,610 independently replayed test forecasts",
                "Selected models do not outperform fixed XGBoost on average; no independent cohort",
            ],
            [
                "Simscape source/export",
                "Numeric CSV/JSON/MAT case exported and round-trip checked",
                "MATLAB source not compiled or executed",
            ],
            [
                "BMS and capacity bridge",
                "Mapped CSV/quality handling; 60-record synthetic electrical replay",
                "No actual BMS validation or live health output",
            ],
            [
                "SOL/life",
                "Six-cell observed-history inventory; censoring and baseline primitives",
                "SOL and lifetime threshold unconfirmed; no life validation",
            ],
        ],
        [115, 190, 200],
    )
    p("Interpretation", "HeadingR")
    p(
        (
            "The pulse result supports local electrical-response modelling. It"
            " does not establish a complete SOC/temperature model, "
            "unseen-battery generalization, pack calibration, thermal-runaway "
            "prediction, lifetime extension or Indian site savings. Software "
            "verification and measured validation are separate requirements."
        )
    )
    p(
        (
            "Work continues by available dependency, without calendar "
            "deadlines. The next external inputs are a confirmed SOL "
            "definition and acceptance criteria, verified OCV/SOC and sensor "
            "mapping, real BMS/lifetime records, independent batteries, and "
            "actual Simscape/DGX access."
        )
    )

    new()
    title("Equations and conventions", "General engine versus the restricted measured benchmark")
    formula(
        (
            "Discharge-positive current I [A]; elapsed time t [s]\ndSOC/dt = "
            "-eta(I) * I / (3600 * Qeffective[Ah])\ndv1/dt = (R1 * I - v1) / "
            "tau\nVterminal = OCV(SOC) - R0 * I - v1\ntau = R1 * C1"
        )
    )
    p(
        (
            "The general engine needs a finite measured OCV/SOC table, "
            "positive capacity, declared initial SOC and polarization, and an "
            "explicit charge-efficiency convention. It rejects unsupported SOC"
            " extrapolation instead of clipping invalid states. Current is "
            "held at its preceding sampled value over each interval; the ohmic"
            " term uses the current at the output sample."
        )
    )
    formula("a[k] = exp(-(t[k]-t[k-1])/tau)\nv1[k] = a[k]*v1[k-1] + R1*I[k-1]*(1-a[k])")
    p("Local pulse benchmark", "HeadingR")
    formula(
        (
            "v1[0] = R1 * I[0]  (stationary pre-pulse approximation)\nVhat[k] ="
            " Vmeasured[0] - R0*(I[k]-I[0])\n          - (v1[k]-v1[0])"
        )
    )
    p(
        (
            "The local benchmark holds OCV approximately constant during the "
            "pulse/rest/charge sequence. Only the measured initial voltage "
            "anchors the test. It is excluded from error scoring. The "
            "preceding long low-rate discharge motivates the "
            "initial-polarization approximation; this assumption is not a "
            "measured equilibrium OCV map."
        )
    )
    p("Capacity-reference bridge", "HeadingR")
    formula("Qeffective = predicted relative SOH * matching reference Ah")
    p(
        (
            "The historical SOH reference is the first observed second-life "
            "capacity, not nominal new-cell capacity. The bridge requires that"
            " reference and all features to exist at the forecast origin. It "
            "does not infer resistance changes from a capacity forecast or "
            "claim calibrated joint voltage uncertainty."
        )
    )
    p(
        (
            "No mapped thermal model is fitted. The available "
            "auxiliary-temperature channels do not establish physical probe "
            "assignments. A weather temperature is not a cell-temperature "
            "measurement."
        ),
        "SmallR",
    )

    new()
    title(
        "Measured electrical comparison",
        "111 diagnostics | 333 pulse windows | six cells | same-cell chronological testing",
    )
    p(
        (
            "Each cell's RPT-1 calibrates Rint and one-RC from three pulse "
            "windows. RPT-2 is validation. RPT-3 onward supplies 297 untouched"
            " test windows. No later pulse fits parameters. Native instrument "
            "clocks, current sign, duplicate removal and within-window gaps "
            "are audited; no measurements are imputed."
        )
    )
    cells = sorted({x["cell_id"] for x in ec})
    rows = []
    for cell in cells:
        a = next(
            x for x in ec if x["cell_id"] == cell and x["model"] == "rint" and x["role"] == "test"
        )
        b = next(
            x for x in ec if x["cell_id"] == cell and x["model"] == "1rc" and x["role"] == "test"
        )
        rows.append(
            [cell, f(a["rmse_mv"]), f(b["rmse_mv"]), f(float(b["rmse_mv"]) - float(a["rmse_mv"]))]
        )
    tab(["Cell", "Rint RMSE mV", "One-RC RMSE mV", "Difference mV"], rows, [65, 145, 150, 145])
    p(
        "Mean within cells, then equally across six cells: "
        f"one-RC {f(e('1rc')['rmse_mv'])} mV versus Rint {f(e('rint')['rmse_mv'])} mV. "
        f"One-RC minus Rint is {f(ep['difference'])} mV, with descriptive six-cell "
        f"bootstrap interval [{f(ep['low_95'])}, {f(ep['high_95'])}] mV. "
        "Repeated windows do not create independent batteries."
    )
    tab(
        ["Cell", "R0 mOhm", "R1 mOhm", "tau seconds", "Bound contact"],
        [
            [
                x["cell_id"],
                f(float(x["r0_ohm"]) * 1000),
                f(float(x["r1_ohm"]) * 1000),
                f(x["tau_s"]),
                x["bound_contact"],
            ]
            for x in params
            if x["model"] == "1rc"
        ],
        [65, 110, 110, 110, 110],
    )
    p(
        (
            "Fits retain Jacobian conditioning and parameter-bound indicators "
            "for identifiability review. The eight-second resistance proxy "
            "alone is not used as a full model parameterization. These fitted "
            "values concern the declared local protocol, not a supplier "
            "specification."
        ),
        "SmallR",
    )
    p(
        f"Independent history convolution reconstructed all {check['ecm_rows_checked']:,} "
        "saved voltage rows; maximum disagreement "
        f"{check['ecm_max_replay_difference_v']:.3g} V. "
        "This verifies calculation, not an independent cell cohort.",
        "SmallR",
    )

    new()
    title(
        "AI selection and an adverse result",
        "15 registered candidates | six outer folds | three seeds | CPU execution",
    )
    p(
        (
            "Twelve tree/GRU settings and three fixed references are "
            "evaluated. Each fold fits transforms on its four training cells, "
            "selects using its own validation cell's mean next-checkpoint "
            "error across seeds, then seals selection before scoring the test "
            "cell. Rotating validation identities are not pooled into a global"
            " winner."
        )
    )
    labels = {
        "selected": "Validation-selected",
        "xgb_d2_lr03": "Fixed XGBoost",
        "gru_reference": "Fixed GRU",
        "linear": "Ridge",
        "persistence": "Persistence",
    }
    tab(
        ["Method", "H1 RMSE pp", "H2 RMSE pp"],
        [
            [
                label,
                *[
                    f(
                        next(x for x in hs if x["model"] == model and int(x["horizon"]) == h)[
                            "rmse_pp"
                        ],
                        4,
                    )
                    for h in [1, 2]
                ],
            ]
            for model, label in labels.items()
        ],
        [215, 145, 145],
    )
    p(
        f"Selected minus fixed XGBoost H1 RMSE: {f(hp['difference'], 4)} SOH percentage points, "
        f"descriptive six-cell interval [{f(hp['low_95'], 4)}, {f(hp['high_95'], 4)}]. "
        "The interval spans zero. The selected models have higher mean error; "
        "tuning does not establish superiority."
    )
    tab(
        ["Outer test", "Validation", "Selected candidate"],
        [[x["test_cell"], x["validation_cell"], x["selected"]] for x in selected],
        [95, 100, 310],
    )
    p(
        (
            "All 270 validation trials and 2,610 reported test forecasts were "
            "independently replayed from saved model/scaler files. These are "
            "target-only six-feature models, distinct from the earlier "
            "three-feature transfer experiment. The six cells remain familiar "
            "development data."
        )
    )
    p(
        (
            "The trainer now rejects an explicitly requested CUDA run when "
            "CUDA is unavailable. The recorded runs are CPU runs; no actual "
            "DGX allocation or execution is claimed. A hardware-backed receipt"
            " and independent validation remain necessary."
        ),
        "SmallR",
    )

    new()
    title(
        "BMS, Simscape and life evidence",
        "Interfaces implemented; application validation remains conditional",
    )
    p("Simscape handoff", "HeadingR")
    p(
        (
            "A numeric G1/RPT-3/step-10 case preserves the original clock, "
            "measured voltage, Python prediction and fixed RPT-1 parameters. "
            "CSV/MAT round-tripping is checked. Source targets "
            "MATLAB/Simulink/Simscape R2025a+ and a physical one-RC cell/load "
            "network. Source compilation, solver convergence and numerical "
            "execution are unverified until run on a licensed host."
        )
    )
    p("BMS shadow replay", "HeadingR")
    p(
        (
            "The CSV adapter explicitly maps pack/cell identity, timestamp, "
            "current convention and units. It retains invalid, duplicate, "
            "out-of-order, stale and gapped measurements. A 60-record "
            "synthetic fixture verifies electrical replay parity; it is not a "
            "real BMS dataset. Offline batch execution time does not establish"
            " live telemetry or tail latency. Health output remains "
            "unavailable when required diagnostic/history features are absent."
        )
    )
    p("Observed life-data inventory", "HeadingR")
    tab(
        ["Cell", "Checkpoints", "Observed days", "Minimum relative SOH %"],
        [
            [
                x["cell_id"],
                x["checkpoints"],
                f(x["observed_days"], 1),
                f(float(x["minimum_observed_relative_soh"]) * 100, 2),
            ]
            for x in inventory
        ],
        [65, 100, 145, 195],
    )
    p(
        (
            "SOL's meaning and an application-specific threshold remain "
            "unconfirmed. No lifetime labels or performance claims are "
            "generated. Tested primitives distinguish left-, interval- and "
            "right-censored observations. A first below-threshold test "
            "identifies an interval since the prior test, not an exact failure"
            " time. A linear-to-threshold baseline is conditional on future "
            "trend assumptions."
        )
    )
    p("Full proposal and operational gates", "HeadingR")
    p(
        (
            "Agree scientific definitions/acceptance limits; obtain "
            "equilibrium OCV/SOC and mapped temperature, real BMS and "
            "qualifying life records, an independent compatible cell/pack "
            "cohort, and actual Simscape/DGX runs. Indian paired PV/load, pack"
            " calibration, applicable bill/tariff and supervised operation "
            "remain separate phase-20 requirements."
        )
    )

    new()
    title(
        "Reproducibility and review decision", "Evidence locations, independent checks and sources"
    )
    p("What can be reviewed now", "HeadingR")
    tab(
        ["Artifact root", "Contents"],
        [
            [
                "outputs/ecm/local_pulse_ecm_v1/",
                "Immutable audit, calibration/test ledgers, parameters and predictions",
            ],
            [
                "outputs/model_selection/health_selection_v1/",
                "Smoked and full CPU selection, every trial, models, transforms and decisions",
            ],
            [
                "outputs/implementation/proposal_v1/review/",
                "Independent voltage convolution, model replay, metrics and descriptive intervals",
            ],
            [
                "outputs/simscape/local_pulse_v1/",
                "Checked numeric export; explicitly no MATLAB execution",
            ],
            [
                "outputs/bms/ and outputs/life/",
                "Explicitly synthetic replay and observed-history inventory",
            ],
        ],
        [240, 265],
    )
    p(
        (
            "Every completed study records registration, input/config/code "
            "hashes and numeric artifact hashes; computational source "
            "snapshots preserve the executed version. The dashboard verifies "
            "completions/review links and selects saved results. It never "
            "retrains models in a browser. Original research data and "
            "numerical reference results remain separate."
        )
    )
    p("Review recommendation", "HeadingR")
    p(
        (
            "Continue the missing-data and tool-execution work. The measured "
            "local pulse comparison is a useful milestone; it does not warrant"
            " declaring the entire EV-battery proposal complete or approving "
            "autonomous control. Keep the fixed XGBoost reference and retain "
            "the adverse selection result. There is no timeline-based "
            "completion or invented readiness percentage."
        )
    )
    p("Technical references", "HeadingR")
    for text in [
        (
            "MathWorks: HPPC-based ECM parameter estimation. "
            "https://www.mathworks.com/help/simscape-battery/ug/estimate-battery-model-parameters-from-hppc-data.html"
        ),
        (
            "MathWorks: Simscape physical connection API (R2025a+). "
            "https://www.mathworks.com/help/simscape/ref/simscape.addconnection.html"
        ),
        (
            "NVIDIA: Running PyTorch containers. "
            "https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/running.html"
        ),
        (
            "ReCell: docs/battery_model_contract.md; "
            "docs/codex_implementation_plan.md; checked study manifests. "
            "Source datasets: Stanford second-life M50T (OSF 8JNR5)."
        ),
    ]:
        p(escape(text), "SmallR")

    def footer(canvas, document):
        canvas.setStrokeColor(colors.HexColor("#cbd5c6"))
        canvas.line(45, 39, A4[0] - 45, 39)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            45, 25, "ReCell | Research implementation review | No field/lifetime claim"
        )
        canvas.drawRightString(A4[0] - 45, 25, str(document.page))

    SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=45,
        rightMargin=45,
        topMargin=43,
        bottomMargin=53,
        title="ReCell model implementation review",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    provenance = {
        "pdf_sha256": digest(output),
        "review_completion_sha256": digest(review / "completion.json"),
        "builder_sha256": digest(Path(__file__)),
        "source": str(review.relative_to(root)),
    }
    (output.with_suffix(".provenance.json")).write_text(json.dumps(provenance, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    build()
