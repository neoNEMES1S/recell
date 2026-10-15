# Phase status

The documented 13-phase research prototype has been implemented and its reference
artifacts checked on 2026-10-15. This tracks software and experiment completion;
scientific limitations remain explicit in [methods](methods.md) and [results](results.md).

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

`python -m pytest -q` passes 41 tests. `ruff check src scripts tests` passes.
Coverage includes archive integrity, conflicting identities, capacity integration,
counter resets, causal SOH, training/test separation, future-feature exclusion, metrics,
quantile ordering, GRU padding, meter differencing and constrained dispatch.

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

Dispatch is a perfect-foresight replay with assumed tariffs and a linear wear proxy.
Pack calibration, dynamic aging, closed-loop operation and hardware validation are not
implemented. There is no claimed carbon benefit, observed RUL, measured lifetime extension
or established real-world dispatch saving. These are research follow-ups rather than
hidden completed deliverables. Reproduction commands are in the README.
