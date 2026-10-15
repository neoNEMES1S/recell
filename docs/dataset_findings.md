# Findings from the downloaded Stanford data

Source: [OSF 8JNR5](https://osf.io/8jnr5/), file `j2ne9`, version 2,
retrieved 2026-10-14. The saved API response is `osf_file_listing.json`.
The 2,153,883,052-byte archive matched OSF SHA-256
`201b21b8e2e9623887d03e9bd6620341e5c91cd28bce34294ccbad2d4e7c6fe3`.
Extraction produced 3,282 archive entries, totaling 2,211,736,139 uncompressed bytes,
including macOS resource metadata. The original archive is retained.

## Observed structure

The actual dataset root is `SL_Dataset_SECL_INR21700-M50T`. Its 777 files comprise
542 XLSX workbooks, 91 MAT files, 15 MATLAB scripts, and 129 `.DS_Store` files.
There are 18 `Cycling_*` directories and 19 `RPT_*` directories. These counts are
observations of this release, not assumptions copied from the article.

The six labels observed in paths are G1, V4, V5, W8, W9, W10. The duty assignments
below come from [Moy et al., Table 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC11639452/#tbl0002).
The article also reports that RPT 2 was conducted at 20 °C due to a chamber setting
error; this must be considered when comparing diagnostic trajectories.

| Cell | Duty cycle |
| --- | --- |
| G1 | Commercial |
| V4 | Residential |
| V5 | Commercial |
| W8 | Commercial |
| W9 | Residential |
| W10 | Residential |

The publication describes an earlier release. Current files extend the folder series;
later operating conditions need validation rather than extrapolation of the article.

## Full structural scan

All 1,408 sheets were read. The 529 Channel sheets contain 10,546,631 nonempty data
rows. These are raw exported records, not independent samples or RPT targets.
Native `Date_Time` values span 2022-10-28 14:58:12.376 through
2025-02-02 23:09:58.084; the timezone is not established.

| Channel-sheet category | Sheets | Raw rows |
| --- | ---: | ---: |
| Cycling | 192 | 223,973 |
| Capacity tests with pulses | 112 | 10,242,453 |
| EIS-associated exports | 225 | 80,205 |

All Channel sheets contain `Discharge_Capacity(Ah)` with no blank cells in that
column, but EIS-associated and cycling counters are not RPT health targets.
`Internal Resistance(Ohm)` is blank in 10,466,426 of the 10,546,631 Channel rows.
The exact `Aux_Temperature(¡æ)_1` column occurs in 510 Channel sheets and has no
blanks across their 9,970,344 rows; physical sensor assignment remains unverified.

Capacity-test files cover 19 RPT folders for G1, V4, V5, W8 and W10, and 16 for W9.
G1 has a split RPT export. V5 has an extra empty workbook:
`diagnostic_tests/RPT_11/Capacity_test_with_pulses/20231030_v5_RPT/Channel_4/_Channel_4.xlsx`.
It is retained and flagged, not interpreted as an observation. Do not impute absent
late-life W9 checkpoints as measured targets.

## Workbook evidence

The first structural inventory found 30 distinct first-row layouts. Most exports
contain `Global_Info` and `Channel_*` sheets; some also contain `RawData_*` sheets.
There are 529 Channel sheets. The same observations may appear in Channel and RawData
representations. RawData sheets repeat time/step/cycle column names in channel blocks.
They must not be concatenated as additional independent measurements.

Observed Channel column labels include:

- `Date_Time`, `Test_Time(s)`, `Step_Time(s)`, `Step_Index`, `Cycle_Index`;
- `Voltage(V)`, `Current(A)`;
- `Charge_Capacity(Ah)`, `Discharge_Capacity(Ah)`;
- `Charge_Energy(Wh)`, `Discharge_Energy(Wh)`;
- `Internal Resistance(Ohm)`, `dV/dt(V/s)`;
- optional auxiliary voltage and `Aux_Temperature(¡æ)_*` columns.

Temperature labels contain an encoding artifact. Do not silently rename those units
or assume every auxiliary channel measures the same cell. A header can exist while
all its values are empty (resistance in initial examples). Missingness counts in
the manifests distinguish this once the header is reviewed.

EIS exports have layouts containing `Device_ID`, `Test_ID`, `Channel_ID`, `Cycle_ID`,
`Step_ID`, `Pt`, `Freq`, `Zmod`, `Zphz`. Twelve aggregate EIS workbooks have multirow,
multi-cell layouts, including `ZCURVE` labels. Their header semantics remain pending.
Thirteen files have no single cell label (those twelve workbooks and `eis_7.mat`).

## MATLAB evidence

Ninety cycling MAT files contain `MatlabOpaque` objects, reported under scipy's
`None` key. Treat this as a MATLAB interoperability issue, not a measurement column.
`diagnostic_tests/RPT_7/eis_7.mat` exposes numeric arrays `EIS_7_326`, `EIS_7_363`,
`EIS_7_400` (43 × 12), `EIS_7_R_HF`, `EIS_7_R_SC` (3 × 6), and cell arrays
`EIS_volts`, `cn_fn_chan_order`. Shapes alone do not establish axis semantics.
Raw XLSX is the simplest initial parser source; MATLAB scripts have not been executed.

## Identity conflicts requiring resolution

Two files have contradictory cell tokens between their parent folder and filename:

```text
diagnostic_tests/RPT_9/EIS_9/20230816_v5_EIS326/Channel_4/20230816_v4_EIS326_Channel_4.xlsx
diagnostic_tests/RPT_9/EIS_9/20230816_w8_EIS400/Channel_2/20230816_w9_EIS400V_EIS_Channel_2.xlsx
```

Their manifest cell ID remains null with `identity_status: ambiguous`. Resolve using
instrument channel/test metadata and neighboring source files before modeling.
Instrument channel numbers also vary across campaign segments, so a channel-to-cell
mapping must not be assumed globally.

## Target readiness

Discharge-capacity, current, time and step columns are present in RPT exports, providing
a viable raw source for a capacity target. A validated target table does **not** yet
exist. Capacity counters can include pulse segments and restart across files/steps.
Phase 3 must identify the intended discharge segments, reconcile split exports,
check signs/units and integrate or extract capacity consistently. Do not take a
workbook maximum as ground-truth capacity without these checks.

SOH reference choice is explicit in base.yaml: first observed second-life RPT.
Alternative nominal/first-life references need separate documented experiments.
No SOH trajectories, RUL labels, model metrics or optimization results were generated.
