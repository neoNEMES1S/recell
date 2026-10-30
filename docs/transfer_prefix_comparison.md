# Availability-restricted first-life transfer comparison (v3)

Review date: 29 October 2026. The separately registered v3 comparison is complete.
The result supports a small directional improvement over the matched PGP-GRU,
not replacement of the simpler research reference or a client savings claim.
The original full-history v2 experiment remains blocked by 13 rejected cycling
batches. Its gate was not relaxed and it has no fitted comparison.

## Why the experiment changed

The complete linked-cell audit verified 71 capacity diagnostics and 52 cycling
batches, but rejected 13 batches. A global counter-recovery heuristic also failed
its registered agreement criterion. Sorting clocks, imputing missing exposure or
training on a test battery's first life would not solve the research question.

A separate availability audit reconstructed the longest verified input prefix
from each cell's first diagnostic. A later measured capacity can supply a forecast
label without supplying unknown future exposure as an input. This distinction
recovers valid early examples while retaining every original target test battery.

| First-life cell | Verified feature checkpoints used | Measured capacity labels retained | H1 / minimum-history-3 examples | Role in v3 |
| --- | ---: | ---: | ---: | --- |
| G1 | 11 | 11 | 8 | Gradient eligible only when its target cell is in the training fold |
| V4 | 11 | 11 | 8 | Same restriction |
| V5 | 3 | 4 | 1 | Same restriction |
| W8 | 3 | 15 | 1 | Same restriction; later labels cannot create missing input histories |
| W9 | 3 | 15 | 1 | Same restriction |
| W5 | 3 | 4 | 1 | Source validation only; physically independent of all six targets |

The tables contain 34 verified feature rows and 60 measured label rows. Twenty
source examples exist across these six cells, but a fold uses only its permitted
subset. W10 has two verified input checkpoints and zero H1/min3 examples. Its
second-life history remains in the target experiment. Source gradients contain
three or four physical cells and only 3-18 examples per fold; W5 provides one
validation example in every source fit. These are material limitations.

The other reported EV cells were not assumed usable: W3 has only three numeric
capacity checkpoints; W4's second cycling batch fails the original clock/gap
checks; W7 remains acquisition-incomplete. The additional selective acquisition
finished with 28/30 files. Two W7 mirror-recovery attempts also failed at current
OSF metadata access (DNS/timeout), before accepting any mirror file. All three
cells remain excluded from v3 fitting. W5 was chosen using measured availability,
before any source/transfer model result.

## Registration and unchanged target task

`configs/transfer_protocol_v3.yaml` was sealed at
2026-10-28T15:56:48.652221+00:00, before any source or transfer fit. Its SHA-256 is
`1c7f031821378463e43e970eced0b4e69ac27e1ad44418ea5588d5c58ed83fe1`.
The parent v2 remains sealed separately. The availability reports and exact input
hashes are part of the new registration, not chosen after inspecting forecast errors.

The comparison preserves all six target batteries, their deterministic held-out
and validation roles, 87 target origins, two target horizons, seeds 42/43/44,
five context fractions and the primary endpoint. First-life source training uses
only eligible prefixes of target gradient-training batteries. Both target test and
target validation first life are excluded from source gradients. W5 never supplies
gradient updates or preprocessing statistics. Histories never cross life stages.

All arms use the same transform fitted on unique target gradient-training
checkpoints. The source head predicts one future diagnostic; the target head
predicts two. Transfer copies the GRU and representation layers, initializes a
fresh target head and starts a fresh optimizer and scheduler. The model settings,
200-epoch cap and validation stopping rule match the frozen reference.

## Mathematical feature and evaluation model

For accepted diagnostic `j`, let `Q_j` be measured capacity in Ah and `Q_1` the
first observed capacity of that life stage. The model receives:

```text
SOH_j = Q_j / Q_1
d_j = (diagnostic_end_j - diagnostic_end_1) / 86400
A_j = sum of verified cycling charge-plus-discharge Ah before diagnostic j
x_j = [SOH_j, d_j, A_j - A_1]
```

Each cycling integral uses the reviewed dense-current trapezoidal calculation:

```text
Ah = sum_k [(abs(I_k) + abs(I_(k+1))) / 2] * (t_(k+1) - t_k) / 3600
```

Clock ordering, sampling gaps, native endpoints and diagnostic corridors must
pass before that value is available. The v3 source input is `x_1 ... x_j`, with
`j >= 3`, followed by measured label `SOH_(j+1)`. If the next interval is invalid,
`x_(j+1)` remains unavailable: its age/exposure are not filled to create another
input. Future Ah spacing is reported as unavailable where it cannot be measured.
First-observed references and scalers are not calculated from future maxima.

For battery `b`, seed `s` and the same evaluated origins `o`:

```text
RMSE_b,s = sqrt(mean_o[(predicted_SOH - measured_SOH)^2])
M_arm = mean_b[mean_s[RMSE_b,s]]
primary_difference = M_R2 - M_R1
```

The primary setting is 10% target context, horizon 1. A negative difference favors
transfer. Bootstrap draws resample six paired battery differences, not origins or
seeds: 10,000 draws, seed 42, percentile 95% interval. These are descriptive
intervals from six familiar batteries, not strong population evidence.

## Results

The complete run contains 15,660 predictions. RMSE below is SOH percentage points:
stored SOH-fraction RMSE multiplied by 100, not a percentage accuracy score.

| Arm | Method | Primary RMSE (SOH points) |
| --- | --- | ---: |
| R1 | PGP-GRU from scratch | 0.2972 |
| R2 | PGP-GRU with first-life pretraining | 0.2916 |
| R3 | Quantile GRU from scratch | 0.3137 |
| R4 | Quantile GRU with pretraining | 0.2968 |
| R5 | XGBoost | **0.2534** |
| R6 | Persistence | 0.3465 |

Primary R2-minus-R1 difference: **-0.005577 SOH points**; descriptive paired-cell
95% interval **[-0.012993, -0.000113]** points. The observed effect is small.
G1 and W8 worsen; four cells improve. The point estimate for R2-minus-R5 is
+0.0382 points, with an interval spanning zero. XGBoost has the lowest observed
mean, but these six batteries do not establish population superiority.

R2's nominal 80% interval has 93.70% equal-cell mean coverage and mean width
1.3617 SOH points. Its empirical P10/P50/P90 frequencies are approximately
4.44% / 60.28% / 98.15%, rather than 10% / 50% / 90%. Read width, pinball loss
and coverage together; ordered quantiles are not proof of calibrated uncertainty.
The R2-versus-R4 physical-guidance contrast is inconclusive under its descriptive
interval. No hyperparameters, thresholds or origins were changed after scoring.

All per-cell/context/horizon metrics, recovery and worst-error cases, range-shift
and horizon-spacing audits remain available. No cell or negative-transfer case is
removed from the report.

## Runtime, verification and decision

The first smoke attempt completed six Torch fits and then crashed in the native
PyTorch/XGBoost combination. A standalone synthetic reproduction isolated this
combination; starting Python with `OMP_NUM_THREADS=1` passed. A corresponding
[upstream macOS OpenMP issue](https://github.com/dmlc/xgboost/issues/11500) describes
the same class of conflict. No library binary or model setting was changed.
The failed attempt, six fits, histories and hash-verified executed code were
preserved in `smoke_failed_native_20261029T033524Z`; it is not a successful result.

The accepted smoke and full comparison record the runtime setting and complete
code snapshots. The full comparison has 36 source GRU fits, 72 target GRU fits,
18 XGBoost fits and 18 persistence artifacts. Recorded fit wall time totals
3.63 seconds for source fits and 17.42 seconds for target arms on this machine;
these exclude acquisition/audit/reporting overhead and additional smoke attempts.
The failed attempt's saved optimization-time lower bound is recorded separately.

Independent review reloaded every registered model, reproduced all 15,660
prediction rows, checked source/target roles and parent initialization, and
recalculated the primary mean and paired bootstrap. The full software suite
passes 188 tests, including the fresh-process native-runtime regression; lint
passes. All 539 historical input/result/dashboard artifacts match their reference
hashes; the original archive remains intact and user notebook edits are untouched.

Decision: retain the simpler research reference and the published dashboard.
Treat v3 as a small directional transfer result requiring independent validation.
It does not validate Indian site savings, calendar/cycling loss decomposition,
pack behavior or closed-loop control. Phase-19 application and phase-20 field,
PV, billing and controller gates remain open.

## Reproduction and artifacts

```bash
# Existing outputs are immutable; these fitting commands refuse existing run folders.
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/run_transfer_experiment.py --protocol-version 3 --smoke
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/run_transfer_experiment.py --protocol-version 3
rtk proxy .venv/bin/python scripts/analyze_transfer_results.py --protocol-version 3
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/review_prefix_transfer.py
```

- `data/processed/transfer/ev_to_second_life_v3/`: separate source features, labels and provenance.
- `outputs/transfer/ev_to_second_life_v3/`: sealed protocol, registration, feature gate and historical rechecks.
- `comparison/report/`: matched metrics, paired comparisons, negative-transfer and failure tables.
- `comparison/review/`: independent verification, executed review code and primary comparison figure.
- `comparison/code_snapshot/`: exact model implementation used for accepted fits.
- `output/pdf/recell_transfer_v3_primary_comparison.pdf`: exported primary comparison figure, rendered and visually reviewed.
