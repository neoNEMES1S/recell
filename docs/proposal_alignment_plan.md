# Proposal alignment and missing-work plan

Planning baseline: 5 November 2026. This adds phases 21-28 to ReCell's roadmap;
it does not rename or mark complete phases 1-20. The user requested planning and
inclusion of the missing proposal requirements. New phases are **planned, not
implemented**. The evidence-dependent phases 14-20 goal remains paused until the
user resumes it. This document creates no active execution goal or new experiment.

Execution-policy update: the user has superseded the calendar timeline and wants
completion as soon as dependencies permit. The [Codex implementation plan](codex_implementation_plan.md)
is the governing execution handoff: packages C00-C11 define source changes, tests,
artifacts, dependencies and the instruction for Codex. No Gantt dates govern work.

## Objective-to-deliverable map

The supplied image's right edge is cropped. O1/O2 summarize the visible objectives;
confirm their full approved wording in phase 21. M1-M4 are its methodology items.
SOL is retained verbatim until its meaning is confirmed.

| Proposal requirement | Reusable evidence today | Missing deliverable |
| --- | --- | --- |
| O1: mathematical EV battery model, validation and existing-model comparison | Capacity extraction, SOH equations and statistical model comparisons | Calibrated dynamic cell model and electrical baseline comparison; phases 22-23, independent validation in 27 |
| O2: AI training and optimization with source data | Six forecast methods, grouped evaluation, prefix transfer and three-seed runs | Preregistered tuning budget, selected coupled model and actual DGX execution; phase 24 |
| M1: mathematical model development and validation on Simscape | Audited current/voltage/time records and pulse-resistance proxy | Runnable Simscape project, identified parameters and held-out measured validation; phase 23 |
| M2: AI optimization and selection on NVIDIA DGX | CUDA-capable trainer; completed configuration uses CPU | Compatible pinned DGX environment, actual experiment/resource logs and selection report; phase 24 |
| M3: AI development and integration with BMS data | Offline laboratory preprocessing and saved models | Real-BMS signal mapping, deployable features and timestamped inference replay; phase 25 |
| M4: SOH and SOL validation through computer simulation | Held-out next-checkpoint SOH evaluation and conditional storage simulation | Defined SOL target, reference labels, life model if applicable and independent validation; phases 26-27 |

Transfer learning, uncertainty, calendar aging, Indian demand/PV, storage control
and the dashboard remain useful additional research. They do not substitute for
M1-M4. The physics-guided loss imposes soft trajectory preferences; it is not an
electrical/thermal state model. XGBoost remains a required strong SOH baseline.

## Eight additional phases

| Phase | Work and reviewable output | Dependencies | Completion gate / status today |
| --- | --- | --- | --- |
| 21 | Define proposal scope, SOH/SOL, data contract, baselines and numerical acceptance criteria; freeze new protocols | Full wording, intended application, data and access review | Definitions, physical-cell/site and parameter-identification splits, metrics and thresholds agreed before tuning. Draft plan only; definitions/access unconfirmed. |
| 22 | Formulate and identify a dynamic equivalent-circuit cell model; parameter tables and baseline report | 21; eligible current/voltage/pulse/rest/OCV and capacity data | Identifiable finite parameters, sign/unit checks and held-out dynamic-voltage comparison. Not implemented. |
| 23 | Implement/calibrate in Simscape; model project, parameters and repeatable validation harness | 22; confirmed MATLAB/Simulink/Simscape access and required products | Declared release runs, solver/conservation checks and held-out measured cases meet phase-21 criteria. Not implemented. |
| 24 | Tune/select AI, connect health predictions to the dynamic model, and execute on DGX | 21; eligible health data for selection; 22-23 interfaces for coupling; actual DGX access for hardware execution | Full trial ledger, validation-only selection, frozen scoring, uncertainty and CPU/DGX resource comparison. Local AI work does not wait for Simscape; coupled validation uses the verified ECM. Not implemented. |
| 25 | Integrate real BMS records; adapter, signal dictionary, shadow-inference replay and latency report | 21 schema and eligible frozen model; BMS exports/protocol, sensor map and reference tests | Reader/fault handling can develop before model integration or DGX. Real-data causal replay, parity and timing close the gate. No control actuation in this package. Not implemented. |
| 26 | Implement the defined SOL target; if it means remaining life, add censoring-aware RUL forecasting | 21 definition; eligible health model; adequate longitudinal/end-of-life evidence | Life-data audit and model work do not require BMS completion unless the actual target requires it. Report target-specific errors, uncertainty and censoring. Not implemented; SOL unresolved. |
| 27 | Independently validate the frozen combined model and robustness; separate simulation and measured-data reports | 23-26 candidates; unseen compatible cells/packs and qualified test conditions | Registered SOH/SOL/dynamic errors, sensor-fault/range tests and documented valid limits. Pack/thermal claims need their own measurements. No independent cohort confirmed. |
| 28 | Complete objective-to-evidence review, reproducible handoff and dashboard/PDF updates | 27 and relevant gates; unmet requirements explicitly recorded | Checked equations, model/data versions, measured-versus-simulated labels and supported claims. Proposal attainment requires agreed criteria. Not implemented. |

Execute the [Codex dependency graph](codex_implementation_plan.md#shortest-path-and-dependency-graph),
not a sequential wait through all eight phases. Electrical modelling, Simscape
source preparation, AI selection, BMS ingestion and life-data work can advance
independently after their contracts exist. Complete all feasible local work while
external gates are waiting. Reserve the independent validation set in phase 21.
Phase 20 remains the separate
requirement for Indian field/billing claims; a phase-28 dashboard update does not
close it. The original full-history v2 gate stays failed; v3 is a separate study.

## Mathematical model to implement

Start with an open-circuit voltage plus series-resistance baseline (Rint), then a
one resistance-capacitance branch (1-RC Thevenin) model. Consider 2-RC only if
permitted validation data justify its extra parameters. Fix baseline, operating
range and model-order selection rules before fitting; compare error and runtime.

For normalized SOC z, discharge-positive current I in A, time t in seconds,
effective capacity Q_eff in Ah and polarization voltage v1:

```text
dz/dt  = -eta(I) * I / (3600 * Q_eff)
dv1/dt = -v1 / (R1 * C1) + I / C1
V_hat  = OCV(z, T) - I * R0 - v1
```

`eta(I)` is the documented coulombic-efficiency convention: discharge unity and
a separately calibrated charge factor initially. SOC/temperature/health-dependent
parameter tables require measurements identifying those dependencies. Review rest
and relaxation before treating voltage as equilibrium OCV. The existing 8-second
resistance proxy alone does not identify R0, R1, C1 or an OCV curve. Audit the
available pulse records before treating them as adequate HPPC calibration data.

Define the AI-to-model bridge with explicit units, reference and timing. For a
matching `SOH = Q_eff / Q_ref` definition, use `Q_eff = SOH_hat * Q_ref` with Q_ref
available at the prediction origin. Existing SOH is relative to first observed
second-life capacity, not automatically nominal/new-cell SOH. Preserve the old
definition; register any conversion separately. Never parameterize an earlier
prediction using future measured capacity. Any AI parameter/residual correction
is a registered ablation against the identified ECM and existing health models.

A normal-operation lumped thermal extension is conditional on mapped cell sensors,
ambient/cooling data and parameter-identification evidence. A restricted proposed
balance is `C_th*dT/dt = I^2*R0 + v1^2/R1 - (T-T_ambient)/R_th`; reversible heat and
spatial gradients are excluded from that simple form. Otherwise restrict electrical
validation to the measured temperature range. This model does not establish
thermal-runaway/fire prediction or prevention. Such claims require separately
confirmed scope, qualified safety experiments and independent event evidence.

## Data and resource requirements

| Input | Current limitation | Action before execution |
| --- | --- | --- |
| Dynamic electrical measurements | Raw Stanford waveforms exist; continuity, pulse/rest coverage, initial SOC and OCV sufficiency need a new audit | Verify cell identity, clocks, units, resolution and identifiability; acquire compatible missing tests |
| Temperature/thermal boundaries | Auxiliary channels exist but physical probe mapping is unresolved | Obtain sensor map, calibration, ambient/cooling and storage-temperature evidence; weather is not cell temperature |
| Real BMS records | No accepted BMS integration dataset | Obtain authorized export, sampling rates, signs/units, cell/pack topology, clocks, firmware and quality flags |
| Independent SOH reference | Six familiar target cells; no reserved external cohort | Acquire compatible unseen cells with independently measured capacity; BMS-estimated SOH is not automatically ground truth |
| SOL/end-of-life reference | SOL undefined; two-checkpoint forecasts do not establish observed lifetime | Confirm target, application-specific end-of-life rule, reference basis, future duty and censoring; obtain qualifying histories |
| MATLAB/Simscape | Access, products and release unconfirmed | Record licensed products/release, check API support and run the validation harness |
| NVIDIA DGX | No recorded DGX run or confirmed allocation | Confirm actual DGX model, architecture, GPUs, drivers, scheduler/storage/access; pin compatible software/image digest |
| Indian field application | Demand measured; PV modeled; site/pack/bill gates open | Retain phase-20 measured paired PV/load/BMS, billing, pack-calibration and supervised-operation requirements |

Existing author requests are access leads, not acquired records. No new outreach
or access check is performed by writing this plan. Additional training sources need
rights, compatibility and physical-identity review. Do not invent missing exposure,
sensor measurements or failure dates, or merge unrelated chemistries as equivalent.

## Acceptance and experimental design

Phase 21 fixes numerical pass/fail limits with the research owner using intended
use and measurement precision. Limits below remain **TBD before fitting**, rather
than targets chosen after inspecting test errors. A generic 95% accuracy claim
must be replaced with a defined quantity, tolerance and evaluation population.

| Area | Proposed metrics and checks |
| --- | --- |
| Electrical dynamics | Voltage RMSE/MAE in mV, bias/max error, pulse/relaxation residuals, operating-range coverage and baseline difference |
| Simscape verification | Identical-input Python/Simscape differences, solver-step convergence, charge/energy residuals and initial-state/unit agreement |
| SOC / thermal, if claimed | SOC error in percentage points against an independent reference; temperature RMSE/max error in deg C against mapped sensors |
| SOH | Capacity error in Ah, SOH RMSE/MAE in percentage points with matched reference/test method, per-cell failures and paired cell-level uncertainty |
| Uncertainty | Coverage together with interval width and pinball loss; validation-only calibration; interval coverage is distinct from prediction accuracy |
| SOL, if RUL | Error in agreed days/cycles/Ah to the defined observed threshold, origin rules, uncertainty and censoring-aware scoring; report noncrossing histories |
| BMS runtime | Tail/end-to-end latency versus sampling deadline, causal arrival cutoffs, resource use, stale/missing/duplicate/out-of-order records and sensor bias/dropout |
| AI/DGX | Finite preregistered search budget, all trials/failures, fit time, inference latency, memory and seed variability under the same splits; do not presume GPU speedup |

Split physical batteries across all life stages, and sites where relevant. Distinguish
allowed early same-cell calibration from unseen-cell testing. Fit OCV/ECM parameters,
scalers, tuning and uncertainty calibration only in permitted roles. New tuning on
the familiar six-cell benchmark is development evidence, not independent validation.
Keep BMS features available at inference: no future RPT, missing pulse test or
unmeasured channel may be a required hidden input. Freeze the selected model before
independent scoring and do not repeatedly select on its final test set.

Python/Simscape agreement verifies implementation; held-out measured data validate
physical predictions. Synthetic labels assess agreement with their generator, not
an independent battery population. If SOL means RUL, start with a transparent
degradation-to-threshold baseline and a registered probabilistic candidate. State
future duty assumptions. Irregular two-checkpoint predictions cannot simply be
multiplied into a validated lifetime. Right-censored cells receive no invented
failure date. If SOL means another quantity, replace that conditional work package
with its confirmed definition and labels in phase 21.

## Execution priority; timeline superseded

The user explicitly chose earliest feasible completion instead of the proposed
calendar schedule. The local Gantt PDF remains an unchanged historical planning
artifact, not a deadline or dependency authority. Use C00-C11 in the
[Codex implementation plan](codex_implementation_plan.md). Prioritize one measured
electrical-model slice, then expand verified components and independent branches.
Do not wait for dates or hold local implementation behind unavailable runtimes.

Software-in-the-loop is the initial integration target. Hardware-in-the-loop and
supervised actuation require separately specified equipment, limits and operator
approval; neither is already delivered by offline replay.

## Implementation and publication touchpoints

Reuse parsers, grouped folds, metrics, model classes and provenance helpers. Create
only needed adapters and versioned outputs when implementation starts: proposed
roots are `outputs/ecm/<protocol>/`, `outputs/simscape/<protocol>/`,
`outputs/dgx/<protocol>/`, `outputs/bms/<protocol>/` and `outputs/life/<protocol>/`.
Keep Simscape source, parameters, product/release requirements and the validation
harness in a dedicated source directory. Pin data/code/config/protocol hashes;
preserve completed studies, historical definitions and benchmark folds.

Phase 28 adds dynamic voltage/SOC comparisons, DGX evidence, BMS quality/latency
and defined SOL results to the dashboard as verified artifacts become available.
Planned items must say planned; distinguish simulated, measured and independently
validated results. Update mathematical PDFs to implemented equations, not merely
this proposal. This planning update changes no frontend or hosted deployment.

Immediate execution package when requested: complete the phase-21 definitions and
acceptance worksheet; audit eligible waveforms and BMS/life-data availability;
confirm Simscape/DGX access. No new dependency or placeholder simulation is needed
to include these commitments in the roadmap.

## Technical references checked on 5 November 2026

- [MathWorks: HPPC-based ECM parameter estimation](https://www.mathworks.com/help/simscape-battery/ug/estimate-battery-model-parameters-from-hppc-data.html): pulse current/voltage/time inputs, parameter fitting and block parameterization; verify installed-release support.
- [MathWorks: remaining useful life models](https://www.mathworks.com/help/predmaint/ug/models-for-predicting-remaining-useful-life.html): explicit life units, threshold and uncertainty; this does not resolve SOL's meaning in the proposal.
- [NVIDIA: running PyTorch containers](https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/running.html): GPU runtime prerequisites; choose a compatible pinned environment after inspecting the allocated DGX.
