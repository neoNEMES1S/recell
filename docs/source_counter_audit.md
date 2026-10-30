# Step-aware counter candidate audit

28 October 2026. This forensic study rejects the tested counter heuristic as a
global replacement for the registered dense-current exposure method. It is not
a transfer-learning experiment, and no feature dataset or model is promoted.

## Fixed comparison

The legacy rule treats every negative counter difference as a reset and produces
implausible first-life throughput. An exploratory alternative counts a reset only
when Step_Index changes, the counter drops by more than 0.0001 Ah, and its new
value is below 10% of the preceding value. The candidate total is its last value
minus its first, plus the preceding counter value at each candidate reset. Other
signed differences are preserved; within-step decreases remain visible. These
thresholds are a heuristic under audit, not established instrument semantics.

G1 cycling 1 and rejected-clock W10 cycling 2 were probed before registration.
The first G1 result agreed closely with the accepted current integral; that result
is disclosed as development evidence, not an independent validation case.

Protocol `source_counter_audit_v1` was sealed at
2026-10-28T07:58:48.442360+00:00, SHA-256
`946e8c7d25be27a1da260099a7aacdca6e60fa4ec3119ad60f3254e14f12e8f3`,
before scoring the remaining 49 clean-reference batches. Both charge and discharge
were compared with previously accepted dense-current integrals at a fixed 0.1%
relative-agreement tolerance. There are 50 reference batches including the known
G1 case. The two explicit raw replacements are excluded: their rejected MAT files
are retained in provenance and cannot serve as reference counter measurements.

## Result and failures

43 of 50 batches meet the tolerance for both directions, including 42 of the 49
newly scored batches. Seven fail; no thresholds were changed and no failures
were deleted after scoring. The largest difference is 85.652%, on G1 cycling 3
discharge exposure. Agreement in the initial G1 case did not generalize to all
clean reference batches.

| Cell / cycling batch | Charge difference (%) | Discharge difference (%) |
| --- | ---: | ---: |
| G1 / 2 | 26.803 | 39.777 |
| G1 / 3 | 77.260 | 85.652 |
| G1 / 4 | 80.939 | 0.002 |
| V4 / 4 | 80.636 | 0.002 |
| V5 / 2 | 0.314 | 0.324 |
| W10 / 4 | 0.142 | 0.172 |
| W10 / 6 | 0.583 | 0.597 |

Relative difference is abs(candidate - current integral) / current integral. These
are measurement-method discrepancies, not battery-health prediction errors.

A separate original RawData-sheet example in W10 cycling 2 export 70 records
current at Test_Time 1,895,843.196676 s and capacity counters at 1,895,844.096376 s,
a difference of 0.8997 s. Signal-specific time and step columns therefore need
independent review before a current-aligned Step_Index is treated as a counter
reset identifier. This one example does not establish the cause of all seven
failures or a universal alignment correction. Its original workbook hash and
signal-specific values are saved in `raw_signal_clock_example.json`.

## Original W10 clock-event evidence

The acquired cycling-2 export 53 contains the previously rejected MAT event in
its original Channel and RawData sheets. At source rows 192358–192359,
Test_Time decreases from 1,450,150.349228 to 1,450,150.299096 seconds
(-0.050132 s), while native Date_Time advances from
2020-07-21 04:10:05.190 to 04:10:05.348 (+0.158 s). Current switches from
-1.541916 A to +14.269653 A at the step-14 to step-7 transition. This is an active
transition, so deleting the interval or treating it as an idle reset is unsupported.

All 205,439 Channel records in this workbook were scanned in original order.
There is one nonpositive instrument-time transition; the minimum native-time
increment is positive at 0.001 s. The independent current, voltage and capacity
signal windows also retain their own clocks and step identifiers. Native time is
therefore a possible measurement basis to investigate, not a validated replacement
for the complete batch. This workbook alone does not establish full-batch native
clock quality, exposure agreement or a recovery rule for other failures.

The completed 49,578,391-byte workbook has SHA-256
`402db7f2ce7ce8de327311a3b5467a820754e0bc5ec195046ed0189a8e8decb6`.
Its first 10,051,584 bytes match the retained interrupted permalink download.
The same OSF remote ID was acquired through its listed direct provider endpoint;
the original partial and transport amendment are preserved. Exact events, signal
windows, source/receipt/plan hashes and the executed implementation are pinned in
`outputs/transfer/source_counter_audit_v1/raw_event_probe/`. No time sorting,
repair, exposure replacement or source-feature promotion was performed.

## Consequence for the goal

The candidate is not accepted as a global recovery rule. Even close numeric
agreement would not certify clocks, ambiguous resets, corrupt trajectories or
physical diagnostic corridors. The sealed v2 feature contract remains unchanged:
first-life exposure requires its validated dense-current integral. No source
checkpoint, fold, registered model setting, historical result or dashboard output
is replaced by these candidate totals.

The separate 81-file revision recheck covering inputs associated with all 13
failed cycling batches found unchanged reported version/name/modified-date/size
metadata after retrying three interrupted lookups. This does not certify remote
byte identity or rule out private corrections. The default v2 transfer smoke command
still exits at its closed scientific gate because verified feature provenance is
missing.

The separately registered [v3 verified-prefix comparison](transfer_prefix_comparison.md)
has since completed without using this rejected heuristic or changing v2's gate.

Full counter results, implementation snapshot, reference input hashes, protocol,
registration and artifact hashes are under
`outputs/transfer/source_counter_audit_v1/`. The audit's synthetic assertions and
real-data hash checks passed. Corrected exports or an independently validated
measurement recovery are still required; the 13-batch rejection list is unchanged.
