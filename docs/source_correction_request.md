# Dataset clarification request — draft, not sent

To: Professor Simona Onori, sonori@stanford.edu

Contact verified against the [Stanford Energy Control Lab profile](https://onorilab.stanford.edu/simona-onori)
on 27 October 2026 and the corresponding-author address in the dataset paper.

Subject: Clarification on EV real-driving aging dataset exports and time-base discontinuities

Dear Professor Onori,

I am auditing the public INR21700-M50T EV real-driving aging dataset before using
its capacity and cumulative-Ah histories. Could your team help clarify the
following observations or point me to corrected exports?

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

I have retained the original files and can provide the exact filenames, hashes
and minimal numerical examples if helpful. I would appreciate guidance on the
appropriate release or reconstruction method before fitting any models.

Thank you.

---

Approval would authorize sending only the subject and body above to the named
recipient from the connected email account, without attachments. Detailed local
audit files, private project code, model results and client information are not
included in this draft.
