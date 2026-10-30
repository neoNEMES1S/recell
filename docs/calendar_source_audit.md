# Separate calendar-aging source audit

Audit date: 27 October 2026. The independent, preregistered calendar-storage
comparison has completed. It has material prediction failures; no M50T calibration
is established and no calendar term has been added to dispatch wear.

## Pinned source and compatibility

The [authors' repository](https://github.com/viveklam/Joule-Decade-Calendar-Aging)
was pinned at commit `0bc2d6393da223e6d850896b6501153630d393ca`.
`outputs/calendar/source_audit/source_manifest.json` records downloaded metadata
URLs, sizes and SHA-256 hashes. The [OSF release](https://osf.io/ju325/) contains
raw and compact diagnostic-summary folders; the raw archive was not acquired.

The cell inventory has 259 unique IDs, eight base model labels and ten labels
when the two `_v2` variants are kept distinct. Chemistry counts are 107 LFP,
70 LCO, 64 NCA and 18 NMC. The NMC cells are Sony-Murata US18650VTC6; **M50T is
absent**. Storage conditions cover 24, 45, 60 and 85 degrees C, at 50% or 100%
SOC. This supports a separate calendar study, not a direct M50T temperature/SOC
calibration.

The published summary folder contains 232 files. Twenty-seven inventory IDs have
no matching summary file; `summary_coverage.json` lists them explicitly. All
18 NMC IDs have matching filenames, but filename availability alone does not
establish usable longitudinal histories. Eighty-one inventory rows carry author
comments, including removed measurements, possible swaps, short histories and
different lots. Those comments are retained, not silently treated as clean data.

## One summary inspected

`C00103_sum.json` was downloaded and locally hashed; its receipt records any
upstream checksum supplied. Its top-level fields are `meta_data`, `summary_data`
and `comment`. The summary table is itself serialized as a JSON string and has
42 columns. The adapter parses JSON as data and never executes author code.

The prospective capacity definition is `RPT0.2C_2_D_capacity`, the third low-rate
diagnostic discharge. It is distinct from both first-life M50T C/20 capacity and
the second-life capacity-with-pulses measurement. Choosing this field is an audit
decision, not a choice based on predictive model performance. The independent
experiment below subsequently registered this choice before fitting.

The sample has 53 diagnostics spanning 1,945 days, first accepted capacity
2.9549 Ah, and five positive capacity increments. Its date differences agree with
the author's elapsed days. The author's note about deleted M04 data is preserved.
Positive increments remain observations; no monotonic clipping was applied.
The sample table and audit are under `outputs/calendar/source_audit/`.

## Remaining gates

1. The selected summary pool and source hashes are verified. OSF node metadata
   declares no license; intended redistribution/commercial use needs clarification.
2. The standalone protocol below was registered before fitting. Its comparison
   is complete, including grouped `_v2` lots, type-held-out tests and chronological
   extrapolation. Review nonphysical outputs and type failures before application;
   changing model families now requires a new registered study, not silent retuning.
3. Report temperature/SOC and chemistry shifts explicitly. Six M50T target cells
   do not become a calendar validation cohort merely because both sources contain
   some NMC cells.
4. Resolve target temperature channels before any M50T application. The subsequent
   [complete workbook-metadata audit](target_temperature_audit.md) verifies the
   original sources but does not establish probe-to-cell assignments or offline
   storage temperatures. Air temperature from a weather service is not cell temperature.
5. Identify the losses represented by calendar and cycling components before
   combining them. Existing second-life observations and the throughput wear
   proxy already reflect mixed aging; additive use risks double-counting.

The M50T/application phase 19 gates remain open. The separate parser has tests for embedded
JSON, missing capacity exclusions, cell-identity mismatch, observed references and
inconsistent clocks.

## Compact release and full-history audit

The 2,269,469-byte summary archive now matches its upstream SHA-256
`49babeed89739e0850d0da8bf817801889622e1c23c83f357904fe282d0afc78`.
Every one of its 232 JSON members also matches the current folder's per-file
SHA-256; no older archive members were silently mixed with newer folder files.
The existing safe extraction helper verifies paths, rejects links and preserves
the release under `data/raw/stanford_calendar/summary_release_v1/`.

`scripts/prepare_calendar_data.py` produced 9,481 audited checkpoint rows for all
232 available cells. Seven cells each contain two diagnostics sharing an identical
day-only clock. Both ambiguous rows are quarantined in each case, without
inventing dates or discarding the rest of a valid cell history. The report retains
their diagnostic IDs. Thirty-two cells have fewer than four accepted diagnostics;
200 cells meet that descriptive history-length threshold. It is not a fitted-model
eligibility or performance claim. All source third-discharge capacities are
positive and finite; the raw inventory still retains absent and short histories.

Reproduce the local audit with `scripts/prepare_calendar_data.py`. The report,
extraction receipt, input hashes, row exclusions and code hashes are in
`outputs/calendar/source_audit/history_audit.json` and associated metadata. No
M50T/dispatch aging combination has been fitted. The standalone model study is
described below.

## Registered independent comparison

The cohort audit validates 232 physical-cell histories; 218 contain at least one
future observation. Fourteen single-observation cells remain descriptive and do
not receive fabricated zero-aging labels. Thirteen cells have author notes about
deleted potentially swapped points; five have double-bag notes. Flags remain
visible. The primary study retains the author-curated remaining histories; the
registered sensitivity excludes all thirteen swap-note cells from every role.
All alternate `_v2` lots stay grouped with their base type.

[Protocol v1](../configs/calendar_protocol_v1.yaml) was sealed at
2026-10-27T17:53:41.066944+00:00, SHA-256
`7377d66d0867b7500e082ca61382dc807a9d11537e85354cb4223355661c5668`,
before any fit. Eight outer folds hold out one base cell type, reserve the next
sorted type for validation and fit only the other six. Three models compare a
constant reference, a nonnegative square-root-age loss, and a square-root-age loss
conditioned on temperature and storage SOC. First observed capacity defines each
cell's reference. No test-cell parameter fitting, label clipping or interpolation
is used. Training weights balance types, then physical cells, then observations.

The primary regime fits complete permitted training histories. The secondary
regime fits only training ages at or below 180 days and scores held-out-type ages
above 180 days. Unavailable late histories remain unavailable. Six fixed optimizer
starts select by training cost only; validation/test labels never choose parameters.

| Model | Primary mean type RMSE | Primary mean type MAE |
| --- | ---: | ---: |
| Constant first-observed reference | 15.39 percentage points | 14.14 percentage points |
| Age only | 12.16 percentage points | 11.18 percentage points |
| Age + temperature + SOC | 7.29 percentage points | 6.60 percentage points |

Metrics average within physical cells, then equally across the eight held-out
types. The preregistered conditioned-minus-age-only RMSE difference is -4.87
percentage points, with a descriptive 95% type-bootstrap interval of
[-7.17, -2.73]. Only eight types are the bootstrap units; 9,249 held-out future
observations do not become 9,249 independent battery types.

Important failures remain. The conditioned model makes 44 negative predictions on
four K2 Energy LFP18650E cells at 85 degrees C / 100% SOC. Its worst absolute error
is 73.71 percentage points on Tenergy 302030, and the Tenergy mean error exceeds
the constant-reference baseline. These predictions were retained in all metrics.
The 180-day extrapolation RMSE is 10.65 points for the conditioned model versus
17.11 for age-only; excluding swap-note cells gives primary RMSEs of 7.16 versus
11.79 points. These are fixed secondary checks, not settings selected after seeing
the primary outcomes.

The source summaries provide the capacity labels; raw RPT curve completeness was
not independently re-audited for all 9,481 observations. The results concern
apparent loss under storage plus periodic diagnostic cycling. They do not identify
a pure calendar term, a transferable M50T aging law or Indian pack performance.
No model is automatically adopted and no term is added to the existing mixed-aging
wear proxy. The original first-life transfer gate remains unchanged and failed.

Review outputs: [plain-language report](../outputs/calendar/calendar_validation_v1/analysis/review.md),
[cell-type figure](../outputs/calendar/calendar_validation_v1/analysis/held_out_type_errors.png),
and the immutable fit/prediction/metric artifacts under
`outputs/calendar/calendar_validation_v1/validation/`. Saved implementation source,
input hashes, package versions, optimizer records and artifact hashes identify the
completed run. All 141 software tests and lint checks pass.

The additional [five-page review PDF](../output/pdf/recell_calendar_validation_review.pdf)
explains the dataset attributes, implemented equations, fitting objective, metrics,
results and failures. It was generated from verified completed artifacts without
refitting; every page was rendered and visually checked. Its adjacent provenance
JSON records the PDF, builder, protocol and source-result hashes. The original
project mathematical-review PDF is preserved.
