# ReCell research methods and decisions

## Capacity and temporal preprocessing

Source: Moy et al., Data in Brief 57 (2024), 111046,
https://doi.org/10.1016/j.dib.2024.111046. The source archive and file hashes are
recorded in the inspection manifest. First-life capacity covariates come from Table 2.

Only reviewed Channel sheets are used for primary measurements. RawData sheets and
processed MATLAB tables duplicate those measurements and are not concatenated.
The raw Arbin exports use **negative discharge current**, verified against voltage
decline and increasing discharge-capacity counters. This differs from the article's
plot sign convention. Source hash checks prevent stale caches after raw-file changes.

RPT capacity is the sum of trapezoidal current integrals over four contiguous low-rate
discharge segments (0.15–0.30 A, at least 300 seconds each). These observed segments
span approximately 4.18 V to 2.5 V. Short pulses, rests and recharge are excluded.
Each integral is checked against that segment's discharge-counter increment. Integration
covers sampled endpoints; the unobserved fraction before a segment's first sample is
not reconstructed. `session_audit.json` preserves durations, currents and capacities.

The overlapping second export of G1 RPT 1 contains 19,709 repeated rows. Exact
duplicates are removed. Millisecond-rounded wall-clock timestamps can legitimately
repeat, so identity uses both wall-clock and instrument test time. Contradictory values
at the same combined key raise an error. The empty V5 workbook is explicitly excluded.
Two conflicting EIS path identities remain quarantined; no cell identity is guessed.

Cycling throughput sums observed charge and discharge capacity-counter increments,
including resets. Initial offsets are excluded, and are zero in this inspected release.
Energy throughput follows the analogous Wh counters. Diagnostic throughput is not
included in this exposure covariate. No overlapping cycling exports were observed.
At each RPT, exposure includes only cycling sessions ending before the RPT starts.
The checkpoint becomes available at the end of the complete diagnostic test.

SOH uses the first observed RPT capacity for each cell, available at every modeled
forecast origin. Fixed positive nominal and documented first-life-end references are
also supported. No future maximum or future mean is used for normalization.

Pulse resistance is an apparent 8-second incremental DC resistance near 3.63 V:
the voltage/current difference between the final low-rate point and the end of the
discharge pulse. It is a protocol-specific proxy, not pure ohmic resistance.
Auxiliary temperature channel 1 is summarized for inspection but excluded from the
initial predictor set because physical sensor mapping is not verified. EIS arrays are
optional and excluded from the initial predictor set because early checkpoints and
aggregate layouts differ. Missing raw `Internal Resistance(Ohm)` is not filled with zero.

The prepared dataset has 111 checkpoints: 19 each for G1, V4, V5, W8 and W10, and
16 for W9. Raw timestamps retain their source's unspecified local timezone; elapsed
durations use instrument time within tests. Calendar intervals use naive wall time.
All results are conditional on this timestamp convention and this six-cell campaign.

## Forecasting and evaluation

Each leave-one-battery-out (LOBO) fold uses four training cells, one separate validation
cell and one held-out test cell. The validation cell rotates deterministically. Median
imputation and scaling fit unique training checkpoints only. Models forecast the next
two RPT checkpoints; checkpoint spacing is irregular, so this is not a fixed-day forecast.
The first origin has three checkpoints. Features are SOH, elapsed days, prior cycling
throughput, pulse-resistance proxy, duty class and documented first-life-end capacity.

Persistence, ridge linear regression and XGBoost predict changes from origin SOH.
Tabular predictors use latest features, within-history slopes and context length. GRU
models use variable-length sequences; padding is excluded by packed recurrence.
PGP-GRU predicts ordered P10/P50/P90 quantiles with point/quantile losses and soft
monotonicity/smoothness penalties. The quantile-GRU ablation omits those penalties.
Training uses validation early stopping, at most 200 epochs and seeds 42, 43 and 44.
Saved checkpoints and preprocessing artifacts accompany each fold/model/seed.

Limited-history evaluation retains the latest 10%, 25%, 50%, 75% or 100% of each
pre-origin history (rounded up, at least one checkpoint). All fractions share the same
origins and future labels; models train on full training-cell contexts. This measures
inference-time history availability, not retraining with a smaller dataset. SOH reference
and cumulative exposure remain available metadata even when earlier context is removed.

Report metrics for each cell, seed, horizon and unit. Aggregate by averaging seeds
within cells, then report mean and sample SD across six cells. Overlapping origins and
seeds are not independent experimental units. Paired bootstrap intervals resample cells
and are descriptive with only six cells. Feature importance uses validation partitions.
Failure-case analysis and calibration are post-evaluation and do not tune these runs.
No observed end-of-life threshold or validated remaining-life claim is supplied.

## Solar-storage replay

Input source: Open Power System Data (2020), Household Data, version 2020-04-15,
https://data.open-power-system-data.org/household_data/2020-04-15/ (CoSSMic; CC BY 4.0).
The downloaded file hash is pinned in `configs/base.yaml`. Use residential3 PV, grid
import and grid export cumulative kWh counters. Difference adjacent hourly readings
and reconstruct household load as import + PV - export. Assign each difference to
the interval beginning at the earlier reading. Hourly resampling of cumulative meters
limits sub-hour timing accuracy. Preserve upstream interpolation flags from both
endpoints; zero flagged hours does not independently prove every source reading was raw.
The fixed replay covers June 2016 (720 hours). It is unrelated in calendar time to the
battery experiment, and is explicitly a transferable household operating scenario.

Tariffs are assumed: EUR 0.40/kWh from 17:00–21:00 Europe/Berlin, EUR 0.25 otherwise,
and EUR 0.08/kWh export. Pack assumptions: 10 kWh nominal, 3 kW, 90% round-trip
efficiency, 10–90% SOC, 50% initial and terminal SOC, EUR 1,000 replacement cost
and a 20-percentage-point nominal-capacity loss budget. They are not market estimates
or measured pack specifications. No carbon intensity is supplied; no emissions claim.

Use the latest available one-checkpoint PGP-GRU forecast per held-out cell, seed 42;
selection does not inspect target outcomes. Map forecast SOH to nominal health using
the cell's observed reference capacity divided by nominal 5 Ah. Convert predicted
decline to loss per equivalent full cycle using the median positive checkpoint-to-
checkpoint cycling Ah increment of that fold's four training cells, divided by twice
nominal Ah. For multi-checkpoint forecasts, divide by horizon as well. Predicted
recovery yields zero wear. Diagnostics are excluded from exposure, as in preprocessing.
This linear wear coefficient is a scenario proxy, not a validated pack-aging law.

The convex optimizer has perfect knowledge of the whole replay horizon. Only PV
surplus charges the battery; discharge serves remaining load. These restrictions prevent
simultaneous charge/discharge without binary variables and exclude grid arbitrage.
Enforce hourly balance, power and SOC bounds and equal initial/terminal stored energy.
Health is fixed during the replay; estimated wear is reported rather than dynamically
fed back into capacity. Equivalent full cycles use internal charge+discharge throughput
divided by twice nominal energy. Wear cost is replacement cost times predicted nominal
capacity loss divided by the loss budget.

Scenarios A/B/C/D are no battery, full nominal battery, reduced-health second-life
battery, and the same reduced-health battery with wear cost in the objective. B and C
minimize electricity cost; D adds estimated wear. B reuses the same wear coefficient
only for a controlled capacity comparison, not as a measured new-battery aging model.
Sensitivity uses D wear-cost multipliers 0.5, 1 and 2, with C supplying zero. A separate
P10 case changes both health and wear and must not be interpreted as a like-for-like
policy benefit. Negative net electricity cost denotes export revenue exceeding imports.

Only C versus median D at weight 1 compares policies under identical health and wear
assumptions. Lower modeled electricity-plus-wear cost does not establish lower actual
degradation. A real deployment would require pack calibration, load/solar forecasts and
closed-loop evaluation. Schedules, forecast selections, conversions, source hashes and
solver residuals are exported to `outputs/dispatch/`.
