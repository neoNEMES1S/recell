# Target temperature metadata audit

29 October 2026. The audit verifies source metadata but does not establish a
physical probe assignment. Temperature remains excluded from the forecasting
features, and the M50T calendar-model application gate remains open.

All 542 original XLSX files and 15 author MATLAB scripts match the inventoried
source hashes. The 529 measurement sheets have these temperature-column schemas:

| Auxiliary temperature columns | Measurement sheets |
| ---: | ---: |
| None | 19 |
| Index 1 | 400 |
| Indices 1, 2, 3 | 104 |
| Indices 1 through 5 | 6 |

The sheets containing temperature columns have 9,970,344 rows; the remaining
19 sheets contain 576,287 rows. Header spelling and its encoded unit are
preserved. An auxiliary index is not promoted to a physical sensor identity.

Every `Global_Info` table has five nonempty rows, all present in its full recorded
preview. All 529 channel records have empty `Comments` and `Item ID` fields.
The presence flag `Has Aux` supplies no probe-to-cell mapping. The author scripts'
temperature-keyword search supplies no assignment either. Opaque MATLAB objects
were not decoded; this audit does not prove that a mapping exists nowhere else.

The [source paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11639452/)
describes T-type thermocouples at cell center surfaces. Its protocol temperatures
are chamber setpoints. Neither fact assigns a particular exported auxiliary index
to a physical probe throughout changing cycler-channel configurations. Outdoor
air temperature and nominal setpoints cannot fill that gap or the unrecorded
offline-storage temperature history.

Required evidence is a dated table of physical cell, cycler channel, auxiliary
index, probe ID/location, temperature unit and calibration/status flags, plus
changes across campaign segments and storage-period cell/chamber logs. These are
measurement-metadata requirements, not parameters to infer by choosing the column
that best predicts test SOH. No new temperature model or combined aging loss is fitted.

Reproduction: `rtk proxy .venv/bin/python scripts/audit_target_temperature.py`.
The command refuses an existing completed output directory. Input hashes,
per-sheet inventory, all channel records, keyword-search results and executed
source are preserved under `outputs/calendar/target_temperature_audit_v1/`.
