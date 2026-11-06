# Proposal implementation: results and reproducible handoff

Execution began 5 November 2026; delivery checks continued after the session
restart on 6 November. Calendar deadlines are superseded. All feasible local
components are implemented; external scientific/tool requirements remain open.
The earlier phases 14-20 goal remains paused pending evidence. This implementation
does not reopen its failed v2 source gate or contact authors again.

## Measured electrical result

The local pulse audit accepts all 111 diagnostic sessions and 333 windows from
six M50T cells. For each cell, RPT-1 calibrates Rint and one-RC parameters; RPT-2
is validation; 297 later windows test fixed parameters. This is same-cell
chronological testing, not an unseen-cell or full OCV/SOC experiment.

| Model | Equal-cell mean test-window RMSE | Mean test-window MAE |
| --- | ---: | ---: |
| Rint resistance-only | 8.182 mV | 7.237 mV |
| One-RC | 4.400 mV | 3.878 mV |

One-RC minus Rint mean RMSE is -3.7816 mV, descriptive six-cell 95% bootstrap
interval [-4.1239, -3.4322] mV. The initial measured voltage anchors each window
and is excluded from forecast scoring. Constant local OCV and initially stationary
polarization are declared approximations. Physical temperature mapping and an
independently verified equilibrium OCV/SOC map remain unavailable.

## AI selection result

The registered 15-candidate comparison runs 270 CPU validation trials, selecting
separately within each of six physical outer folds across three seeds. It then
scores 2,610 held-out development forecasts. Transforms use training cells only.
No pooled rotating-validation global winner is passed off as an untouched test.

| Method | Next-checkpoint SOH RMSE | Second-checkpoint SOH RMSE |
| --- | ---: | ---: |
| Fixed XGBoost | 0.2187 pp | 0.2078 pp |
| Validation-selected | 0.2465 pp | 0.2284 pp |
| Ridge | 0.2586 pp | 0.2729 pp |
| Fixed GRU | 0.3103 pp | 0.2825 pp |
| Persistence | 0.3465 pp | 0.5152 pp |

Selection minus fixed XGBoost next-checkpoint RMSE is +0.02771 pp, descriptive
six-cell interval [-0.00313, +0.08161] pp. Average error is higher; the interval
spans zero. Tuning does not establish superiority. These six-feature target-only
results are separate from the earlier three-feature first-life transfer study.
Explicit CUDA requests now fail when CUDA is unavailable; the recorded runs are
CPU, not DGX experiments. The familiar cohort is not new independent validation.

## Implementation and evidence states

| Package | Local implementation | Remaining external/application evidence |
| --- | --- | --- |
| C00-C01 | Baseline, fixed protocol/configs and shared units/roles | Full SOL definition and numerical scientific acceptance limits |
| C02-C04 | Waveform audit, general Rint/1-RC engine, local measured calibration/test | Full equilibrium OCV/SOC, mapped temperature, independent cells/packs |
| C05 | Numeric Simscape exporter checked; `.ssc`/`.m` source handoff | Licensed compilation, simulation, solver and orientation checks; sources unexecuted |
| C06 | Bounded CPU selection, saved models and strict CUDA behavior | Authorized DGX allocation and actual hardware-backed execution |
| C07 | Capacity-reference bridge and causal-cutoff/analytic tests | Measured full-OCV coupled comparison |
| C08 | Mapped BMS CSV/quality adapter and 60-record synthetic electrical replay | Real mapped BMS data, required health features and verified live timing |
| C09 | Six-cell history inventory; tested censoring/conditional baseline primitives | Confirmed SOL, threshold and qualifying life/event cohort; no life validation |
| C10 | Independent calculation and saved-model replay | Independent compatible physical cohort; not more rows/seeds of the same cells |
| C11 | Eight dashboard views, 18 lessons, checked snapshot and six-page review | Browser visual QA unavailable after tool failures; full proposal gates remain open |

The independent review reconstructs all 175,824 pulse rows using direct history
convolution, replays all 270 validation trials and 2,610 test forecasts, checks
scalers/roles and reproduces summaries and intervals. Numeric MAT/CSV round-trip
and synthetic BMS parity are checked. These are independent calculations on the
same underlying cells, not independent physical validation.

## Inputs and reproducible commands

The contract is [battery_model_contract.md](battery_model_contract.md). Existing
package dependencies suffice. Completed run directories are immutable; the commands
below show their original destinations. To rerun, register a new explicit version
and use fresh output directories; do not delete or overwrite the completed runs.

```bash
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_dynamic_data.py --output outputs/ecm/local_pulse_ecm_v1/audit
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/run_ecm_experiment.py --audit outputs/ecm/local_pulse_ecm_v1/audit --output outputs/ecm/local_pulse_ecm_v1/comparison
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/run_model_selection.py --output outputs/model_selection/health_selection_v1/comparison
rtk proxy .venv/bin/python scripts/export_simscape_case.py --run outputs/ecm/local_pulse_ecm_v1/comparison --output outputs/simscape/local_pulse_v1
rtk proxy .venv/bin/python scripts/replay_bms.py --input outputs/bms/synthetic_fixture_v1/input.csv --source-kind synthetic --case outputs/bms/synthetic_fixture_v1/case.json --output outputs/bms/synthetic_replay_v1
rtk proxy .venv/bin/python scripts/run_life_experiment.py --output outputs/life/life_inventory_v1
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/review_implementation.py --output outputs/implementation/proposal_v1/review
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/build_dashboard.py --reference-snapshot outputs/dashboard/reference_20261023/data.js
```

The synthetic BMS input and initial-state case were generated solely as a software
fixture from the documented ECM, with source kind and identities explicitly named
synthetic. They are preserved under `outputs/bms/synthetic_fixture_v1/`, not supplied
by a customer. All generated studies/raw data are separate from Git source.

The PDF builder needs ReportLab in an artifact environment, not a new inference
dependency. The report is `output/pdf/recell_model_implementation_review.pdf`;
its sidecar preserves hashes of the PDF, review completion and executed builder.
An adjacent builder snapshot preserves the executed source before formatting.
All six pages were rendered and visually checked. The four previous review PDFs
and original reference numerical values remain preserved.

Dashboard routes: `#implementation/electrical`, `/ai`, `/gates`, `/interfaces`.
The electrical view has cell/diagnostic/pulse selectors, exact samples and errors.
AI selection has horizon inspection and fold decisions. Proposal progress separates
software checks from external gates, without a readiness percentage. Interface
views identify the synthetic BMS replay and unresolved SOL. Overview, print brief,
source hashes, analysis download and four new lessons include these results.

Checks: 241 Python tests and Ruff passed after implementation; core, research and
implementation JavaScript checks pass. The exported-snapshot rendering check
exercises all main/subroutes, selector fallback, sources and print without a real
browser. This is not visual browser QA; automation failed before a page could be
verified and became unavailable after the server restart. No browser screenshot
or live timing result is fabricated. Publication uses the existing owner-private
Site and does not broaden access.

## Resume work without repeating completed runs

1. Confirm SOL's actual meaning, application threshold/units and acceptance limits.
2. Obtain qualified equilibrium OCV/SOC, temperature mapping, independent capacity/
   life records and real BMS export/clock/topology metadata. Existing author
   requests are leads, not acquired data.
3. Run the prepared Simscape source on licensed R2025a+ products and execute the
   frozen model-selection comparison on an authorized DGX host. Preserve failures.
4. Validate the independent cohort and full measured coupling before declaring
   those requirements achieved. Keep Indian site/pack/bill/field gates separate.

Routine code and numerical work can continue independently, but source files,
synthetic data or CPU runs cannot substitute for those external requirements.
