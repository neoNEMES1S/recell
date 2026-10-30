# Source-data correction questions

Prepared from the acquired Stanford EV first-life release. These questions have
not been sent to the authors. The physical-cell registry and research protocol
remain unchanged; no source or transfer research fit has been run.

The complete selected-source acquisition contains 266 verified files. All 71
capacity diagnostics pass; 52 of 65 cycling batches pass and 13 are rejected:
V5/3; W10/2,3,5,7; W8/3,4,5,7; W9/3,4,5,7. These are measurement/time-base
failures after acquisition, rather than missing downloads. The complete integrity
manifest is `outputs/transfer/source_audit/complete_selected_source_integrity.json`.

## 1. V5 cycling 3, part 1: incompatible exports

Raw fragments 1-3 show July 9-10, 2021; fragment 14 shows July 16; fragment 26
ends July 22 at 11:09:53.037. Fragment 27 instead begins on June 25. Its voltage
also changes from about 4.00 V at fragment 26's end to about 3.48 V at fragment
27's beginning, despite nearly contiguous instrument elapsed time. The processed
MAT contains the same endpoint conflict.

Diagnostic 3 is May 27-28; diagnostic 4 is September 13-14. Those surrounding
windows do not establish which mixed export represents the complete intervening
physical-cell exposure.

**Question:** Which complete export set and test identifiers reconstruct V5's
cycling-3 part-1 campaign? Are corrected or earlier revisions available for the
inconsistent fragments? A corrected date alone would not resolve the state mismatch.

Evidence: `v5_batch3_native_endpoint_review.json`,
`v5_batch3_first_file_clock_scan.json`, `v5_batch3_second_fragment_clocks.json`,
`v5_batch3_intermediate_clocks.json`, `v5_batch3_fragment26_clocks.json` and
`v5_surrounding_native_clocks.json` under `outputs/transfer/source_audit/`.

## 2. Cycling-3 gaps and short time reversals

W10 cycling 3 has a 51.9994-second gap, W8 cycling 3 a 51.2-second gap, and W9
cycling 3 a 50.7994-second gap. Several short negative time steps occur at active
current/voltage transitions, including W10 cycling 2's transition from about
-1.54 A / 3.30 V to +14.27 A / 3.76 V.

**Question:** Do these represent logging interruptions or time-base corrections?
Which clock and independently measured counters should be used across those events?
Are uninterrupted raw measurements available? The current adapter does not sort
measurements, interpolate missing samples or change acceptance thresholds to fit.

Evidence: `rejected_batch_sampling_review.json` and
`rejected_batch_sampling_context.json`.

## 3. Cycling-5 logger interruption and processed assembly

W9 cycling 5's processed MAT contains six complete identical 214,809-row
time/current/voltage blocks. Complete raw exports 16-21 instead continue into later
January-25 measurements. Reading all 21 raw exports avoids accepting those copied
processed blocks, but does not eliminate the original logger interruption.

Inside raw fragment 15, native timestamps advance from January 24, 2021 at
08:32:51.695 to 08:33:58.835, while instrument elapsed time falls from
323,191.08942 to 323,152.611776 seconds. Step 8 / cycle 1 remains indicated, and
both capacity counters also decrease slightly. W8/W10 cycling 5 have related
instrument-time reversals that still need raw localization.

**Question:** What happened during the interruption, and are the missing interval
measurements or a validated counter-recovery method available? Can the corrected
processed assembly be supplied without repeating source fragments?

Evidence: `w9_batch5_repeated_blocks.json`, `w9_batch5_raw_audit.json` and
`w9_batch5_raw_clock_event.json`.

## Resolved locally at the measurement and date-boundary level

W8/W9 cycling-6 MAT files contain identical numeric payloads despite distinct raw
measurements. Complete raw reconstruction yields separate valid trajectories, and
both lie strictly between diagnostics 6 and 7. The original MATs remain preserved;
the explicitly reviewed replacement hashes and audit code are pinned. This local
repair does not resolve the other source issues or pass the complete feature gate.

See [the full source audit](transfer_source_audit.md) for acquisition manifests,
hashes, software validation and the limits on scientific/client claims.
