# Phase status

The documented 13-phase research prototype has been implemented and its reference
artifacts checked on 2026-10-15. This tracks software and experiment completion;
scientific limitations remain explicit in [methods](methods.md) and [results](results.md).

The proposed next extension is documented in the
[dataset integration and validation plan](dataset_integration_plan.md), dated
2026-10-27. Phases 14-18 cover first-life transfer learning, phase 19 covers a
separate calendar-aging investigation, and phase 20 covers Indian C&I validation.
Execution began on 2026-10-27: phase 14 is complete, the phase 15 selective source
audit is complete, and the original v2 phase-16 gate remains blocked by source-data
quality failures. A separately registered [v3 availability-restricted comparison](transfer_prefix_comparison.md)
has passed its feature/smoke gates and completed phases 17-18 for that amendment.
All six target batteries and 87 historical target origins are preserved. Phase 19
has completed an independent comparison, with application gates open.

All 266 selected inputs and 32 additional restart-part endpoints have been
acquired and hash-checked. All 71 capacity diagnostics pass. G1's complete first-life causal trajectory passes, including
its boundary with second life. The duplicated W8/W9 cycling-6 processed payloads
have been replaced by explicitly reviewed complete raw reconstructions; both also
pass their diagnostic-date corridors. The complete audit accepts 52 cycling batches
and rejects 13, including mixed V5 exports and time reversals/gaps. The failures
prevent feature-dataset promotion and training. Acquisition is complete; the
v2 scientific feature gate has failed. The full software suite passes 216 tests.

The extra-cell availability audit acquired 28/30 selected inputs and verified
11 additional capacity diagnostics and four cycling batches; W4 cycling 2 failed
and two W7 inputs remain unavailable. W5 supplies one independent source-validation
origin. The sealed v3 amendment uses verified contiguous input prefixes and separate
measured capacity labels, never future exposure filling. It trains source gradients
on eligible target-training cells only (3-18 origins across three or four cells),
with W5 validation only. The full run produces 15,660 predictions. Primary transfer
minus scratch RMSE is -0.005577 SOH percentage points, descriptive paired-cell
95% interval [-0.012993, -0.000113]. G1 and W8 worsen; XGBoost has the lowest
observed mean error. Independent replay reproduces every saved prediction. This
does not reopen v2, replace the dashboard or close operational validation gates.

An additional [counter-recovery candidate audit](source_counter_audit.md) compared
a fixed step-aware heuristic with 50 clean dense-current reference batches.
Seven exceeded its registered 0.1% agreement tolerance, including an 85.65%
discrepancy. The heuristic is rejected as a global replacement and no source
feature or training gate is changed. Reported revision metadata for 81 selected
inputs associated with all 13 failed batches was rechecked and is unchanged;
this does not certify remote byte identity or rule out private corrections.

The [separate calendar source audit](calendar_source_audit.md) covers 232 cells and
9,481 accepted checkpoints, with ambiguous day-only dates quarantined. Its separate
preregistered comparison evaluates 218 cells across eight held-out base types.
Mean type RMSE falls from 12.16 percentage points for age-only to 7.29 for the
temperature/SOC-conditioned model. However, 44 negative predictions and a worst
absolute error of 73.71 points remain in the metrics. No model has been applied
to M50T operation or combined with dispatch wear. The [Indian public-data
audit](india_public_data_audit.md) covers a registered 91-day IIIT Delhi demand
benchmark and aligned NASA solar/weather resources. A separate registered
day-ahead load comparison selected a 50/50 daily/weekly blend using validation
only: test RMSE is 2.150 kW versus 2.846 kW for weekly persistence. Its mean peak
timing error is about 122 minutes; this does not establish controller effectiveness.
Tariff billing semantics, actual PV/pack calibration and field evidence remain
unresolved. The phase-19 application gates and phase-20 validation gates remain open.

The [target-temperature metadata audit](target_temperature_audit.md) hash-checks
all 542 original workbooks and reviews all 529 complete Global_Info records.
It establishes no physical probe assignment; 19 measurement sheets have no
temperature columns and the rest expose one, three or five auxiliary columns.
Temperature exclusion, storage-temperature and calendar application gates remain open.

The [Indian PV source audit](india_pv_source_audit.md) verifies a licensed Jaipur
factory workbook but finds daily records only, undeclared output units and 27
formula-derived zero totals with both inverter values missing. It is not adopted
for interval forecasting. A separately sealed 40 kWp DC / 32 kW AC horizontal,
reference-temperature PV scenario now supplies 8,736 modeled public-benchmark
intervals with hourly resource labels and verified energy conservation. It is
not measured PV, a weather forecast or a controller/billing validation result.

The subsequent [registered public-controller comparison](india_controller_review.md)
is complete: six policies, 18 hypothetical health/seed cases and 16 test days,
with 165,888 realized action rows independently reconstructed. Forecast cutoffs,
quarter-hour energy balance and continuous SOC pass review. Transfer-derived
planning has a higher common-reference score than scratch-derived planning by
INR17.25 per 16-day scenario, descriptive day-block interval [INR0.84, INR32.90].
The ranking reverses when the unvalidated evaluation-wear coefficient changes.
This completes a conditional public simulation, not the phase-20 field gate.
The [gate review](integration_gate_review.md) separates completed evidence from
the measurements and calibration still required. The published dashboard is unchanged.

A [separate electrical-semantics audit](india_electrical_semantics.md) quantifies
the apparent-energy gap across the fixed load window. A Coimbatore grid/PV/battery
data-access lead and a concrete author request are documented; no records have
been acquired from that lead and the request remains unsent pending instruction.

The phase-17 encoder initialization path validates shared provenance and physical-cell roles,
copies GRU/representation parameters, preserves a fresh H2 head and RNG state,
and starts a new optimizer/scheduler. Checkpoints record parent hashes and
optimization time. Its v3 stage-specific role maps permit the declared source
subset and independent source validation while preserving all target roles.
The accepted v3 one-fold/seed smoke and full six-fold/three-seed comparison have
completed. The original v2 command still stops at its closed feature gate.

The gated comparison runner is prepared: `scripts/run_transfer_experiment.py
--smoke` selects the first registered fold/seed; the full run requires matching
smoke provenance and fits all six candidate/baseline arms once per fold/seed.
Synthetic tables and mocked fits verify both versions. Use `--protocol-version 3`
for the registered follow-up; the default v2 still exits at its closed gate.
Accepted v3 runs require `OMP_NUM_THREADS=1` before Python starts to avoid a
reproduced macOS native-library crash. The failed attempt is preserved separately;
accepted runs pin the runtime, exact code snapshots and individual artifact hashes.

The gated results reporter is also prepared. It checks complete matched origins,
equal-cell aggregation, paired battery bootstrap and negative-transfer cases before
writing a candidate review. Completed fits now pin individual artifact hashes.
The v3 report and independent prediction/primary-metric review are complete. The
default v2 reporter still refuses the absent comparison. No model is promoted.

| Extension phase | Current evidence | Remaining gate |
| --- | --- | --- |
| 14 | Reference archive and registered v2 comparison preserved | Complete |
| 15 | Physical identities, protocols, nominal conventions and complete G1 reconstruction audited | Complete selective audit; source defects explicitly recorded |
| 16 | v2: 71 diagnostics and 52 cycling batches accepted, 13 rejected. Separately registered v3: verified prefixes, separate capacity labels, six physical folds and unchanged target origins pass | v2 remains blocked; v3 passes its declared availability feature gate |
| 17 | v3 encoder-only source/target initialization, physical-role checks and real one-fold/seed smoke complete | Complete for v3; v2 not run |
| 18 | v3 full six-fold/three-seed comparison, matched reporting and independent replay complete; small transfer effect, two negative-transfer cells, XGBoost lowest mean | Complete for v3; independent validation and any operational promotion remain open |
| 19 | Independent registered comparison complete; original target workbook metadata hash-checked, with physical probe mapping still unresolved | Establish target temperature, M50T calibration, loss accounting and intended-use rights before application |
| 20 | Public load forecast, modeled PV conversion and registered matched offline controller comparison complete; adverse primary controller result retained | Paired measured PV/load, operational forecast/timing validation, applicable bill/tariff, pack calibration, supervised field evidence and conditional dashboard release |

| Phase | Deliverable | Evidence and status |
| --- | --- | --- |
| 1 | Repository and reproducible environment | Python package, locked dependencies, config and logging implemented |
| 2 | Dataset acquisition and inspection | Verified OSF archive; 777 files inventoried; 633 supported files scanned |
| 3 | Parsing and capacity/SOH targets | 111 checkpoints; source hashes, segment audits, exclusions and duplicate checks |
| 4 | Exploratory analysis | Capacity/SOH, exposure, resistance, missingness and duty plots; descriptive tables |
| 5 | Baselines | Persistence, ridge linear regression and XGBoost fitted per fold and seed |
| 6 | Vanilla GRU | Packed variable-length sequences, deterministic training and validation stopping |
| 7 | Leave-one-battery-out evaluation | Six folds, separate validation cells, training-only preprocessing; three seeds |
| 8 | Physics-guided probabilistic GRU | Ordered quantiles, soft penalties and quantile-GRU ablation; calibration outputs |
| 9 | Limited-history experiments | Five fractions with matched origins; 15,660 prediction rows |
| 10 | Failure and comparative analysis | Per-cell/horizon metrics, recovery errors, validation importance and paired bootstrap |
| 11 | Solar/load data interface | Pinned OPSD cumulative meters; hourly conversion, validation and provenance |
| 12 | Degradation-aware dispatch | Four planned scenarios, P10 case and wear sensitivity; 42 solved schedules |
| 13 | Reproducible tables and figures | CSV tables, PNG/PDF figures, source-reading notebooks and reference results report |

## Validation and provenance

The original reference passed 41 tests. The extended suite now passes 216 tests;
`ruff check src scripts tests` passes.
Coverage includes archive integrity, conflicting identities, capacity integration,
counter resets, causal SOH, training/test separation, future-feature exclusion, metrics,
quantile ordering, GRU padding, meter differencing and constrained dispatch.
New load-forecast checks cover observation cutoffs, exact lag clocks, invalid or
missing history, matched forecast arms, validation-only selection and paired day
bootstrap. All 14,880 saved demand predictions were independently reconstructed.
New prefix checks cover optional fractional ISO clocks, physical identity,
separate future labels, unchanged target folds, held-out first-life exclusion,
stage-specific transfer roles and fresh-process PyTorch/XGBoost compatibility.
All 15,660 v3 battery-health predictions were independently replayed.
Additional checks preserve missing inverter output despite spreadsheet zero totals,
reject partial sensor-metadata absence claims, and verify PV units, clipping,
timezones, hourly resolution and energy conservation. All 8,736 modeled PV rows
were independently recomputed; this is calculation verification, not meter validation.
Quarter-hour controller checks additionally cover energy units, SOC carryover,
current-interval recourse, future-profile and future-health-label exclusion,
training-only wear calibration, terminal inventory and nonfinite-ledger rejection.
The independent controller review checks every realized action and all 108 case
scores; these are offline calculation checks, not hardware or billing validation.

The saved forecasting configurations match current modeling settings. Both forecasting
runs' recorded input hashes match `data/processed/checkpoints.csv`. Each run has 216
checkpoint/preprocessing/training-history files. Prediction targets follow their origins;
probabilistic quantiles are ordered. The latest dispatch run used these checked forecasts
and a hash-pinned household file, with maximum solver residual below 1e-8.

Reference artifacts:

- `outputs/inventory/`: source identities, hashes, columns, row counts and missingness.
- `data/processed/`: checkpoints, cycling summaries, per-session audit and exclusions.
- `outputs/figures/eda/`, `outputs/tables/`: exploratory figures and dataset tables.
- `outputs/lobo/`, `outputs/limited_history/`: predictions, fold metrics and saved models.
- `outputs/analysis/`: calibration, comparison, failure cases and limited-history plots.
- `outputs/dispatch/`: schedules, scenario summaries, wear conversion and figures.

## Deliberate scientific boundaries

Temperature channel mapping and naive timestamp timezone remain unresolved. Temperature
and EIS are excluded from forecast features; conflicting EIS identities remain quarantined.
SOH references use past observations only. Six independent cells limit statistical claims.
XGBoost, not PGP-GRU, has the lowest aggregate error in the reference run.

The original dispatch is a perfect-foresight replay with assumed tariffs and a
linear wear proxy. The separate public controller uses past-only day-ahead
forecasts with ideal quarter-hour feedback. Pack calibration, dynamic aging,
live closed-loop operation and hardware validation remain unimplemented.
There is no claimed carbon benefit, observed RUL, measured lifetime extension
or established real-world dispatch saving. These are research follow-ups rather than
hidden completed deliverables. Reproduction commands are in the README.
