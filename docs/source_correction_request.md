# Dataset clarification request - sent

To: Professor Simona Onori, sonori@stanford.edu

Contact rechecked against the [Stanford Energy Control Lab profile](https://onorilab.stanford.edu/simona-onori)
on 30 October 2026 and the corresponding-author address in the dataset paper.
The subject/body below were sent on 30 October 2026 after the user's explicit
"Send both requests" authorization. Gmail readback verifies the exact recipient,
subject and body, with no attachments or CC/BCC. No reply or corrected source
has been obtained by this send operation.

Subject: M50T dataset clarification: export discontinuities and temperature-channel mapping

Dear Professor Onori,

I am developing ReCell, a research project on battery-health forecasting and
second-life solar storage. Our audit of the public INR21700-M50T EV real-driving
aging dataset found discontinuities that prevent a full-history comparison.
We have kept those histories excluded and used only verified input prefixes for
a separately scoped analysis. Could your team clarify these observations or
point me to corrected exports?

1. In Cycling_3/V5/Part1, raw fragment `Channel_1_Wb_26.xlsx` ends on
   22 July 2021 at 11:09:53.037, while fragment 27 starts on 25 June 2021.
   Instrument elapsed time is nearly contiguous, but voltage also changes from
   approximately 4.00 V to 3.48 V. Fragments 1-3 and 14 independently show July
   dates. Which complete export set and test identifiers represent this campaign?
2. W9 Cycling_5's processed MAT repeats identical 214,809-row blocks, whereas
   complete raw exports 16-21 continue into later measurements. The raw data also
   contain a logger event in fragment 15: native time advances 67.14 seconds while
   Test_Time falls 38.477644 seconds, with small capacity-counter rollback. Are
   missing measurements, a corrected time base, or a validated counter-recovery
   method available for this and related W8/W10 discontinuities?
3. W8 and W9 Cycling_6 MAT files contain identical numeric payloads. Their complete
   raw exports reconstruct distinct trajectories that pass the surrounding
   diagnostic-date checks. Is there an updated processed release incorporating
   those original measurements?
4. For the linked second-life M50T release, can your team provide the mapping
   from auxiliary temperature-column indices to physical cell-surface and other
   probes, including any changes by campaign/channel? We also need the native
   timestamp timezone and any recorded between-cycling storage temperatures or
   conditions. We have kept the unmapped temperature channels out of forecasting
   inputs and have not applied a calendar-aging model to these cells.

I have retained the original files and can provide the exact filenames, hashes
and minimal numerical examples if helpful. I would appreciate guidance on a
validated release/reconstruction method and the temperature metadata before
expanding the accepted histories or applying a combined aging model.

Thank you.

Best regards,
ReCell project

---

Only the subject and body above were sent to the named recipient. Detailed local
audit files, private project code, numerical model results and client information
were not attached. The approved source snapshot and private message receipts are
retained under `outputs/integration/author_requests_20261030/`, which is ignored
by Git. Sending does not reopen the failed source gate or establish a sensor map.
