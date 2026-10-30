# First-life integration: started goal and source audit

Original audit date: 27 October 2026; current status updated 29 October.
The original full-history v2 research remains blocked at its source feature gate.
A separately registered [v3 verified-prefix comparison](transfer_prefix_comparison.md)
has completed source/transfer fits, a successful smoke, the full controlled
comparison and independent prediction review. Earlier dated progress snapshots
below describe v2 and are retained as the audit trail. The published dashboard
remains the reference run.

## Execution status

| Phase | Status | Evidence |
| --- | --- | --- |
| 14: reference freeze and protocol | Complete | 610 files archived, archived bytes checked against hashes; v1 registered before fitting; v2 amendment registered from source availability, not model results |
| 15: selective source audit | Complete | All 266 selected files acquired and hash-verified; all 71 raw capacity diagnostics pass; G1's complete first-life trajectory and cross-life boundary verified |
| 16: common features and physical-cell folds | v2 blocked; separate v3 gate passed | v2 rejects 13 batches; v3 uses verified early prefixes, independent W5 source validation and all unchanged target folds |
| 17-18: transfer fitting and evaluation | v3 complete; v2 not run | v3: 15,660 predictions, paired-cell report and independent replay; small directional transfer result, no promotion |
| 19: separate calendar aging | Independent registered comparison complete; application gates open | 218 cells, eight held-out types; lower mean error but 44 negative predictions and major type failures; see [calendar review](calendar_source_audit.md) |
| 20: Indian C&I validation | Public data and separate load-forecast comparison complete | Registered demand benchmark evaluated causally with failure review; billing, PV/pack, controller, field and promotion gates remain open |

The selective audit is not a declaration that the full source training table is
ready. The machine-readable audit currently says `training_gate: not_ready`.

## Reference preserved

- Archive: `outputs/transfer/reference_20261027/reference.tar.gz`
- Manifest: `outputs/transfer/reference_20261027/manifest.json`
- Archive SHA-256:
  `f5ca605ac35af6dcceab16a52b914f8a3dc81d25c6933e029a3f299eb0fd0c0f`
- Includes actual working source/config files, saved fits, predictions, processed
  reference data, analysis and dashboard assets. A Git revision alone would not
  capture the existing uncommitted changes.
- User notebook edits remain untouched. Original historical input/result/dashboard
  files were rechecked on 29 October: all 539 historical data/result/dashboard
  artifact hashes match. The v3 directory contains the new verification receipt.

## Acquired source and access

The [Stanford dataset catalogue](https://onorilab.stanford.edu/products/code-and-data-set)
links the EV dataset using an OSF view-only URL. The bare node returned HTTP 401;
the published view-only link provided read access. Its OSF storage folder is empty;
the linked Dropbox provider contains the data. The inventory currently contains
15 diagnostic folders plus processed diagnostics and 14 cycling batch folders.

Selected acquisitions, not the full approximately 249 GB raw release:

- Author README workbook and diagnostic analysis script; the script was read as
  text, never executed.
- `capacity_test.mat`: 78,704,159 bytes; all diagnostic/cell capacity arrays.
- G1 first cycling batch MAT: 105,267,313 bytes; 7,065,192 dense observations.
- G1 raw diagnostic workbooks 1, 2 and 11, plus the first raw export of cycling batch 1.
- First-life paper, downloaded from Stanford to verify protocols and cell labels.

Acquired files live in `data/raw/stanford_ev_first_life/`; response snapshots and
local file hashes are in `outputs/transfer/source_audit/`. The provider does not
expose upstream checksums for these linked files, so local snapshot hashes are
recorded as such, not presented as independently published checksums. Some provider
size metadata is missing or stale; completed files were parsed and workbook ZIP
integrity checked. Download timeouts were resolved using the published direct
file endpoint or bounded resumption. Incomplete `.part` files are not accepted data.

## Physical identities and measurement conventions

The [second-life paper, Table 2](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/97.pdf)
links its named cells to the earlier campaign. The author MATLAB script explicitly
defines the capacity-array cell order; `col_cell_label` and the README agree.
`configs/cell_registry.yaml` records the ten global physical identities and the
six verified cross-life aliases.

The final first-life capacities for the six shared cells agree with the published
transition capacities to the publication's stated precision, except G1's small
approximately 0.00021 Ah difference, retained explicitly in the registry. W3 and W7
have early-termination notes; additional source cells remain excluded from v2.

The paper and author code use a 4.85 Ah nominal specification. The historical
dispatch uses a separate 5 Ah scenario reference; it has not been silently changed.

First-life capacity diagnostics are separate C/20 tests, unlike the four-segment
second-life capacity-with-pulses protocol. The new audit adapter validates the
single discharge and preserves missing calendar/exposure values rather than
fabricating training features.

## Capacity-only potential (not verified-exposure availability)

| Cell | Accepted capacity checkpoints | Source H2 / minimum history 3 origins | Source H1 / minimum history 3 origins |
| --- | ---: | ---: | ---: |
| G1 | 11 | 7 | 8 |
| V4 | 11 | 7 | 8 |
| V5 | 4 | 0 | 1 |
| W10 | 15 | 11 | 12 |
| W8 | 15 | 11 | 12 |
| W9 | 15 | 11 | 12 |
| W3 | 3 | 0 | 0 |
| W4 | 8 | 4 | 5 |
| W5 | 15 | 11 | 12 |
| W7 | 4 | 0 | 1 |

Total: 101 accepted first-life capacity checkpoints, of which 71 belong to the six
target physical batteries. These are more histories, not 101 independent batteries.

The capacity MAT contains `cap`, `curr`, `time`, `vcell`, diagnostic labels and cell
labels. Integrating the supplied current reproduces the supplied capacity curves
exactly; that is a reproduction check, not an independent instrument measurement.
The sampled raw workbooks additionally agree with their instrument discharge
counters, with relative differences below 4e-7.

## Verified G1 interval and counter incompatibility

Native workbook clocks establish:

- Diagnostic 1 ends 2021-01-12 at 14:00:50.384.
- Cycling batch 1 starts 2021-02-03 at 16:01:48.387 and ends approximately
  2021-02-14 at 12:01:15.038.
- Diagnostic 2 starts 2021-02-20 at 14:09:04.101.

The batch clock is anchored by a raw first-export record matched to processed
test time, current and voltage, then advanced using the processed test-time vector.
Its wall-clock interpretation is explicit; timezone and campaign-wide clock drift
are not assumed verified. A synthetic zero initial element in the author's cycling
arrays is not mistaken for the first physical voltage measurement.

The processed batch has strictly increasing test time, a maximum gap of 1.149 s,
121.07485 Ah integrated charge and 119.84559 Ah integrated discharge. Its sum,
**240.92043 Ah**, is therefore available before diagnostic 2. The separate file
`g1_verified_first_interval.csv` contains the first two diagnostic checkpoints
with native diagnostic-end clocks and causal stage-relative exposure.

The historical counter-reset heuristic interprets small decreases in these
first-life MAT counters as resets. On this batch it yields approximately
9,282.52 charge Ah and 68,577.70 discharge Ah, incompatible with the dense-current
integral. Those totals are explicitly diagnostic failures and are never used as
training predictors. The original second-life feature table remains unchanged;
its exposure consistency must also be audited before the common-feature experiment.

## Pre-training protocol amendment

V1 was sealed before fitting, but V5 supplies no source validation samples at
H=2 with three history checkpoints. V2 therefore registers **source H=1** and
**target H=2**, retaining minimum history three, identical target origins, all six
outer target folds, seeds and primary endpoint. No new performance results were
available when making this amendment.

- V1: `configs/transfer_protocol.yaml`; preserved with registration and hash.
- V2: `configs/transfer_protocol_v2.yaml`; active candidate protocol.
- Sealed copies and registration hashes: `outputs/transfer/ev_to_second_life_v1/`
  and `outputs/transfer/ev_to_second_life_v2/`.

Only the encoder and representation transfer; the target prediction head is reset
to two horizons. V5 still has just one source-validation origin, a limitation to
report. With one source horizon the implemented smoothness loss is identically
zero; target H=2 retains the configured smoothness term. No test-cell first-life
history enters source fitting, selection or preprocessing.

## Current feature gate

| Feature | Status |
| --- | --- |
| First-life capacity and relative SOH | Reconstructed for 101 accepted diagnostics |
| Physical identities | Publication linkage and author array columns verified |
| Calendar age | Verified for sampled G1 diagnostics; remaining clocks need raw-source recovery |
| Stage-relative cumulative Ah | First G1 interval verified; remaining campaign batches need reconstruction |
| Resistance | Deferred; HPPC and second-life pulse protocols are not presumed interchangeable |
| Duty and terminal first-life capacity | Excluded from the shared-feature contract |

Missing source age/exposure remains null. The new transfer feature validator rejects
those rows rather than letting median imputation convert them into artificial
training information. The common target table is written separately to
`data/processed/transfer/target_checkpoints.csv` with six physical-cell folds and
input/registry/protocol hashes.

## Next executable work

### Reconstruction implementation and target exposure audit — 2026-10-27

The target audit inspected all 384 charge/discharge counter series in 192
second-life cycling sessions (223,973 observations). No negative counter
increments were found, including resets. The historical target counter rule
therefore does not exhibit the first-life jitter failure on these inputs. The
machine-readable evidence is
`outputs/transfer/source_audit/target_exposure_counter_audit.json`; historical
target features remain unchanged.

`scripts/acquire_ev_transfer.py --download` selects only the six registered cells:
all accepted raw capacity diagnostics, processed cycling batches, and the first
and last raw exports of each batch. Completed files receive local SHA-256
receipts; these are local download pins, not independently supplied upstream
checksums. Metadata pagination now uses bounded curl requests and saves verified
pages so an interrupted listing can resume. Acquisition remains in progress.
Several cycling folders contain numbered `Part` subfolders; selection descends
through those parts and orders exports by part number and numeric fragment,
instead of treating the parent folder as an empty campaign. Unrecognized folder
layouts stop selection for review.

`scripts/reconstruct_ev_transfer.py` implements the complete causal reconstruction
path, but has **not yet passed on the full research campaign**. It requires:

- A matching receipt and hash for every selected file.
- Independent raw capacity-counter agreement and agreement with the author's
  processed capacity curves.
- Matched current, voltage and test-time values at both native workbook
  endpoints of every processed cycling batch.
- Finite dense measurements with increasing instrument time and gaps no larger
  than five seconds; only a proven synthetic initial zero row is removed.
- Exactly the complete numbered batch set, with each measured batch contained
  between its preceding diagnostic end and following diagnostic start.
- Separate stage-relative normalization and first-life clocks preceding the
  corresponding second-life histories.

The output is promoted to `data/processed/transfer/source_checkpoints.csv` only
after those checks. Per-input audit caches include dependency hashes. Native
wall-clock timezones remain unverified; this does not authorize weather or Indian
time-of-use alignment. Passing reconstruction still requires the registered
fold eligibility and feature-range audit before model fitting.

The full local suite passes **81 tests**, including endpoint mismatch, future
exposure, missing batch, changed receipt, cached reconstruction and interrupted
metadata pagination and split-campaign selection checks. These are software
checks, not a claim that source
acquisition or the research comparison is complete.

### Native endpoint evidence and fold audit implementation

The G1 batch-one end export now independently anchors the processed series at
`2021-02-15T00:37:28.061`, rather than the earlier estimate obtained by adding
instrument elapsed time to the first native timestamp. Its native duration exceeds
instrument duration by **45,373.023172 seconds**. Both raw endpoint current,
voltage and test-time measurements match; the dense-current exposure remains
**240.92043479826918 Ah**. The measured interval still lies between diagnostics
1 and 2. This is recorded in `g1_verified_native_endpoints.json`, and the local
sample audit now prefers measured end clocks. The cause of the wall/instrument
duration difference is unverified; no continuous wall-clock assumption is made.

`scripts/build_transfer_target.py` reproducibly derives the separate target table,
preserving diagnostic start/end clocks, source/protocol labels and derivation
hashes. All 111 rows pass stricter normalization checks: SOH equals capacity over
the first accepted stage capacity, age matches native timestamps, and stage age
and exposure begin at zero. All **539** frozen historical data/result/dashboard
files rechecked against the reference manifest remain unchanged.

`scripts/audit_transfer_features.py` is the next gate after complete source
reconstruction. It checks the sealed protocol and current provenance, usable
origins in each declared source/target partition, identical target origins across
context fractions, and a scaler fitted only on unique target training checkpoints.
Its fold report records feature ranges, standardized source shifts, and forecast
spacing in days and Ah. This full-data gate has not passed yet.

1. Finish selective source acquisition for the six eligible physical cells,
   prioritizing direct provider URLs and verified samples over full raw archives.
2. Recover every required diagnostic/batch clock and complete causal stage-relative
   throughput; audit counter/integration consistency for the target as well.
3. Enforce per-fold source/target sample eligibility under v2 and fit the common
   scaler on target training cells only.
4. Only after those gates pass, implement encoder initialization/head reset and run
   one fold/seed smoke test, then the registered comparison matrix.

Reproduce the current local numerical audit with:

```bash
.venv/bin/python scripts/audit_first_life.py
.venv/bin/python scripts/build_transfer_target.py
.venv/bin/python scripts/acquire_ev_transfer.py --download
# After all required acquisitions finish:
.venv/bin/python scripts/reconstruct_ev_transfer.py
.venv/bin/python scripts/audit_transfer_features.py
.venv/bin/python -m pytest -q
```

This audit is an acquisition and compatibility result, not evidence of improved
forecast accuracy or Indian C&I field performance.

### Additional source defects found during complete-unit auditing

All 32 additional restart-part endpoint exports have completed with local hash
receipts. This establishes acquisition of those anchors, not acceptance of their
measurements. The V5 cycling-3 first part begins on 2021-07-09 but its final export
ends on 2021-06-25. Scanning all 421,604 rows in its first export finds increasing
July-9 clocks, so the inconsistency is between exports rather than a reversal
inside that first export. No replacement dates have been inferred.

W8 and W9 cycling-6 processed MAT files have identical bytes after their 128-byte
MAT headers: SHA-256
`86d3156da9a858d0476a7c78f206b7a96fec9e697427fa014c6ea2cb73d31b35`.
An independent download of W8 through the official download permalink reproduces
that same payload. Both processed trajectories start at 3.19839 V, whereas their
respective raw first exports start at 4.03333 V and 4.01838 V. These inputs cannot
be accepted as verified, independent physical-cell histories. Reconstruction from
the complete corresponding raw exports remains to be investigated.

`--audit-available` records rejected cycling units and continues auditing other
complete units. It promotes no feature dataset when any unit is rejected or any
input is missing. Strict reconstruction still fails immediately on a rejected
unit. This does not change the registered scientific acceptance gates.

Several approximately 600-MB MAT downloads exceeded the original 600-second
transport limit on three attempts. Subsequent attempts use a bounded 1,800-second
limit, preserving completed-file hashing and validation. A direct-provider probe
also returned verified HTTP 206 with `Content-Range: bytes 0-1023/612113034`;
resumable range acquisition has not been implemented. No unverified partial files
have been concatenated.

The acquisition-independent trajectory check now hashes decoded time, current
and voltage in canonical little-endian float64 blocks, rather than trusting MAT
file headers or variable names. Reconstruction rejects a verified trajectory
repeated under another physical cell. Tests exercise numerical changes, ordering,
array boundaries and cross-cell rejection. The current full software suite passes
108 tests; this is not evidence that all source histories pass scientific gates.

`scripts/acquire_ev_raw_review.py --download` pins the complete eight-fragment
raw exports for each of W8/W9 cycling 6, reusing four existing endpoint receipts
and selectively acquiring twelve missing middle exports. These are investigation
inputs, not automatically promoted replacements. The selection is immutable once
written and is bound to the original acquisition and protocol hashes.

The first available-unit pass completed with 26 verified cycling batches, ten
rejected cycling batches and 100 pending inputs (including diagnostics not yet
acquired). This pass predates the new numerical fingerprint implementation, so
its caches require revalidation under that code before promotion. The sampling
review in `rejected_batch_sampling_review.json` localizes concrete defects:
W10 cycling 2 has a -0.050132-second step, cycling 3 a 51.9994-second gap, and
cycling 5 a -59.544112-second step. W8 cycling 3 has a 51.2-second gap and two
small backward steps; cycling 5 has a -25.020776-second step. These are not merely
an observation timeout. No sorting, interpolation or acceptance-threshold changes
have been applied to make them pass.

### Complete raw reconstruction of the cycling-6 conflicts

All 16 selected raw exports (eight per cell, including reused endpoints) completed
with verified receipts and no acquisition errors. `scripts/audit_ev_raw_review.py`
checks source/protocol bindings, physical-cell association and each file receipt,
then audits all measurements in original fragment order. It does not sort, fill
gaps or replace dates. The resulting `raw_review_audit.json` records:

| Cell / batch | Observations | Charge Ah | Discharge Ah | Maximum sampling gap |
| --- | ---: | ---: | ---: | ---: |
| W8 / 6 | 1,604,909 | 4.4977055955 | 4.6073538111 | 1.1053 s |
| W9 / 6 | 1,605,446 | 4.5518921581 | 4.6091855599 | 1.1039 s |

The independently reconstructed numeric trajectory hashes differ, resolving the
copied-payload issue at the measurement level. W8 runs from
2021-03-16T11:45:14.307 to 2021-03-18T10:46:55.501; W9 runs from
2021-03-16T11:36:42.371 to 2021-03-18T10:46:40.286. W9 native duration exceeds its
instrument duration by 411.19672 seconds; native endpoints are retained.

These results are still investigation artifacts. An explicit, hash-bound raw
replacement path and the unchanged diagnostic-boundary checks are required before
including either batch in accepted source features. The original conflicting MATs
remain preserved. The full software suite now passes 109 tests, including raw
fragment boundary integration and rejection of reordered, overlapping or gapped
measurements. No transfer fit has been run.

The explicit replacement path is now implemented in
`configs/ev_raw_replacements.yaml` and `reviewed_raw_batches` in the reconstruction
script. Only W8/6 and W9/6 are declared. The configuration pins both the reviewed
report and raw selection hashes; loading verifies their source/protocol bindings,
audit code hashes, exact batch/input coverage, cell association and all 16 raw
file receipts. The complete raw result replaces the conflicting processed batch
only inside reconstruction. Original MATs remain acquired and hashed as evidence.
Replacement configuration, report, selection and individual raw hashes participate
in reconstruction cache/provenance checks. Existing causal diagnostic-boundary,
stage and physical-cell checks still run afterwards. Changed evidence, rejected
reports and changed raw files are tested rejection cases. The current full suite
passes 110 tests.

V5 clock review acquired diagnostic 3 (2021-05-27 to May 28) and diagnostic 4
(2021-09-13 to September 14). Cycling-3 fragment 2 continues fragment 1 normally:
2021-07-09T21:36:42.612 to July 10T09:58:08.012, with test time 51,121.931524 to
95,607.331324 seconds. Thus the first export's July date is independently repeated
by its successor. The final part-1 export's June-25 date remains inconsistent;
the surrounding diagnostic corridor alone does not authorize a replacement date
or acceptance of this potentially mixed raw campaign.

### Available-unit recheck and transfer implementation preparation

The current available-unit audit accepted 33 cycling batches, including both
explicit raw replacements, and rejected eight others; 95 required inputs were
still pending at that audit snapshot. No diagnostic table or feature dataset was
promoted. These counts change as the separate acquisition job progresses.

While acquisition runs, `training/transfer.py` implements strict H1-to-H2,
encoder-only initialization. Source and target must share feature order/units,
stage normalization, scaler hash, source/target dataset hashes, registry/protocol,
seed, quantiles and physical-cell roles. A held-out physical cell cannot be among
the four gradient-training cells. Loading validates the full source state and
architecture before modifying the target, then copies only GRU/representation
weights. Structural checks preserve the target RNG stream and freshly initialized
head. `train_gru` creates a new Adam optimizer and scheduler afterwards and records
the parent hash plus stage-specific optimization time.

The 118-test suite includes synthetic checks of encoder/head separation, ordered
outputs, unchanged RNG, incompatible scaler/features/arm/architecture, overlapping
cell roles, a fresh optimizer and the unchanged legacy trainer call without a
transfer contract. Synthetic unit optimization does not count as
the registered scientific one-fold smoke run. The real feature gate has not passed;
no source or transfer model has been fitted on research data.

### Gated comparison runner

`scripts/run_transfer_experiment.py` reruns the feature audit before creating any
run directory. It verifies reference hyperparameters against the freeze manifest,
fits one target-training-only scaler per physical fold, and creates source H1 and
target H2 configurations sharing the same scaler and dataset/protocol/registry
hashes. Each fold/seed fits two source encoders, four target GRUs and the XGBoost
and persistence baselines. Every fit is reused across all five inference contexts;
the runner rejects changed target origins, invalid prediction shapes and unordered
quantiles. It exports predictions, equal-cell metric summaries, fold identities,
separate source/target fit times and completion evidence into new protocol-specific
directories. Existing run directories cannot be overwritten.

The full matrix requires a successful first-fold/seed smoke run with identical
input and implementation hashes. Multi-input provenance is now supported by
`save_run` without removing its historical checkpoint-data field. Synthetic
tables and mocked fits exercise the smoke and all six folds/three seeds, including
parent routing and equal origins. They are wiring checks, not scientific fits.

The real smoke command was invoked and refused training because
`outputs/transfer/source_audit/feature_provenance.json` is absent. No smoke or
comparison artifacts were created. The current software suite passes 120 tests;
the source feature gate, real smoke run, comparison report and later research
gates remain open.

### Further raw-source localization

Additional V5 part-1 fragments independently show July clocks: fragment 3 runs
July 10, fragment 14 July 16, and fragment 26 July 22. Fragment 26 ends at native
2021-07-22T11:09:53.037, test time 1,136,712.393168 seconds and 4.00000 V. Fragment
27 begins on June 25 at nearly contiguous test time but about 3.48 V. This
localizes a concrete inconsistent export transition; replacing the date alone
would not resolve the voltage/state mismatch. The investigation inputs and hashes
are pinned in `v5_clock_discontinuity_selection.json`.

`w9_batch5_repeated_blocks.json` confirms a separate processed-data assembly
problem: six complete 214,809-row time/current/voltage blocks have the identical
SHA-256 `50992818302a0a3b834596a51a93e63c7e24ff821e40f15f8992fadb18814ddb`.
The corresponding start rows are separated by exactly 214,809 rows. Complete
original raw exports for this batch are being acquired under the immutable
`w9_batch5_raw_selection.json`; no deletion/deduplication of the processed series
has been accepted as a repair.

The local sampling-context review also shows that several small backward time
steps coincide with active current/voltage transitions. For example, W10 cycling
2 changes from approximately -1.54 A / 3.30 V to +14.27 A / 3.76 V at its reversed
step. Treating every reversal as idle noise or simply sorting samples is therefore
not justified. Diagnostic acquisitions have begun, enabling independent capacity
and causal-corridor checks while the remaining files download.

The first independently reconstructed G1 corridor now passes the unchanged causal
feature join: diagnostic 1 ends 2021-01-12T14:00:50.384 at 4.9030311573 Ah;
diagnostic 2 ends 2021-02-21T15:30:03.639 at 4.8379986884 Ah. Cycling batch 1 lies
between the two diagnostic windows and contributes 240.9204347983 Ah of measured
charge-plus-discharge exposure. The derived second checkpoint is at 40.061959
stage days and SOH 0.986736273 relative to the first observed capacity. The bounded
report `g1_verified_partial_causal_trajectory.json` pins all three verified audit
caches; their code and raw input hashes were rechecked before joining. This proves
only that two-diagnostic corridor, not a complete accepted source dataset or a
usable registered source forecast origin.

### Prepared comparison reporting and artifact integrity

The completed-run manifest now hashes every saved checkpoint, scaler, prediction,
metric, timing and fold artifact. Smoke evidence must retain those artifacts before
it authorizes a full run. The results reporter verifies the completed artifacts,
current input hashes and deterministic physical-cell folds without executing model
or scaler files.

`evaluation/transfer.py` rejects incomplete conditions, duplicate or unmatched
origins, changed labels/reference values, wrong retained contexts, future-label
ordering errors and invalid quantiles. Metrics average seeds within cells before
equal-cell aggregation. The primary paired contrast is R2 minus R1 at 10% context,
horizon 1, with the registered 10,000 battery-level bootstrap draws. Secondary
paired contrasts include R4 minus R3, R2 minus R4 and R2 minus R5. Reports include
coverage, width and pinball loss together, cell-level disadvantages, recovery errors,
worst cases and separate fit timing references. No automatic model choice or client
promotion is made.

Synthetic tests with unequal origin counts prove the intended cell-level estimand
and reject incomplete/mismatched predictions. All 127 tests and lint checks pass.
The real `scripts/analyze_transfer_results.py` command correctly stops because no
completed research comparison exists. This is prepared reporting infrastructure,
not completion of phase 18 or evidence of transfer benefit.

### Diagnostic corridor progress and resumable acquisition

The latest completed available-unit pass accepted 39 diagnostics and 51 cycling
batches. Eight cycling batches remain rejected; missing inputs and those failures
still prevent source-feature promotion. A separately hashed G1 preview now passes
the strict causal join for diagnostics 1-8 and batches 1-7: 458.193793 days and
1,288.602111 Ah of stage exposure. Capacity changes from 4.903031 to 4.659582 Ah,
with final stage-relative SOH 0.950347. This bounded preview is not a replacement
for the required complete six-cell training dataset.

Both cycling-6 raw replacements now also pass their native diagnostic corridors.
W8 diagnostic 6 ends February 21, 2021 and diagnostic 7 begins May 27; its verified
March 16-18 raw cycling batch lies fully between them. W9 passes the same ordering
with independently measured clocks and a distinct trajectory. Hashes and exact
clocks are in `raw_replacement_diagnostic_corridors.json`. Other failed batches
remain excluded; these two local repairs do not close the global feature gate.

Repeated whole-file curl failures motivated `scripts/retry_ev_ranges.py`, used
only for confirmed terminal failed selections. It requires exact HTTP 206 ranges,
matching total size, pinned OSF version/modified metadata before and after assembly,
per-chunk hashes, bounded size, file-format validation and a completed local SHA-256.
It refuses ignored ranges and changed source versions, preserves validated chunks
on interruption and does not overwrite another completed acquisition. No upstream
content checksum is claimed. The first W10 cycling-4 retry has verified its initial
32 MiB; completion is still pending.

The bounded source-storage cap is now 32 GiB instead of 25 GiB to accommodate
temporary verified chunks and retries of the same selected files. A free-space
reserve remains enforced. Unit tests cover ignored/mismatched ranges, source
revision changes and an interrupted/restarted workbook assembly with CRC validation.
All 130 tests and lint checks pass.

### Completed diagnostic audit and author mirror recovery

All 71 required raw capacity diagnostics now pass independent low-rate discharge,
counter and author-capacity agreement checks. The completed G1 first-life join
contains all 11 diagnostics and ten cycling batches: 549.939184 days,
1,974.177906 Ah exposure and final stage-relative SOH 0.938139699. Its last
diagnostic (July 16, 2022) precedes its first second-life checkpoint (November 15,
2022). Eight source H1/min3 origins are available for this cell. The full six-cell
gate remains unpassed; this is not a source fit.

The first bulk acquisition ended authoritatively with 259 completed files and
seven terminal failures. Exact ranges recovered the missing V4 diagnostic.
The alternative Dropbox folder linked in the acquired README was verified in a
browser, including its matching processed-file paths and sizes. A bounded prefix
probe and a full W9 cycling-4 download matched the prior OSF response prefix,
total size, pinned opaque mirror ETag and unchanged selected OSF revision. Its
completed local SHA-256 is
`4d7d7d63068e0b287ca382597a5132f32f742794d6a0ab018642a9806fe0c8db`.
`scripts/acquire_ev_mirror.py` now provides this recovery route only for registered
terminal failures, with author-link verification, storage bounds, revision/size
checks, file-format validation and no overwrite of completed inputs. Tests reject
changed prefixes and mirror ETags; all 133 software tests and lint checks pass.

W9 cycling 5's complete 21 raw exports have also been read. They continue into
January 25 instead of repeating processed fragment-15 blocks, but retain an
original logger interruption: inside raw fragment 15, native time advances 67.14
seconds while test time falls 38.477644 seconds, with small counter rollback.
The strict raw audit remains rejected. Corrected assembly alone therefore cannot
close that batch's exposure gate. No missing exposure or replacement dates were
invented. [Prepared source correction questions](source_correction_questions.md)
record the unresolved issues for review; nothing has been sent externally.

## Complete acquisition gate decision

`complete_selected_source_integrity.json` independently rehashes all **266 selected
files** (19,621,718,280 bytes) and verifies their receipt identities and sizes.
There are no pending selected downloads. The final complete-acquisition audit
accepts all **71 capacity diagnostics** and **52 cycling batches**, rejecting **13**:
V5/3; W10/2,3,5,7; W8/3,4,5,7; W9/3,4,5,7. The additional complete raw W9/5
investigation confirms an original logger interruption beyond the processed
assembly problem. Native dates and missing exposure have not been invented.

**Decision: no-go for registered source/transfer fitting pending corrected exports
or validated recovery evidence.** No source checkpoint table or feature-gate pass
has been promoted. The six-cell population, feature contract, target endpoints,
physical-cell exclusions and frozen historical results remain intact. This outcome
does not complete phases 16-20 and is not a null/negative transfer result, since no
scientific transfer comparison has been run.

All 539 frozen historical data/result/dashboard files were rehashed unchanged.
The local [source correction request](source_correction_request.md) is ready for
review; its recipient is verified against the paper and current Stanford lab page.
It has not been sent, and no private project files are attached or uploaded.
