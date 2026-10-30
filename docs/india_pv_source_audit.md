# Indian PV source audit and declared public scenario

29 October 2026. A factory PV data source was acquired and audited. It does not
supply interval generation suitable for the planned controller validation.
A separate modeled scenario now prepares public-benchmark inputs; it does not
replace measured-PV, tariff, pack or field evidence.

## Jaipur factory workbook

Source: Parashar and Verma (2024), [Solar Panel Data, version 1](https://data.mendeley.com/datasets/82jswfyz5p/1),
DOI 10.17632/82jswfyz5p.1, CC BY 4.0. The publisher identifies a Jaipur textile-factory
rooftop with 20 kW and 100 kW inverters. The 92,705-byte workbook matches the
publisher SHA-256 `0d5d2b8a3c9c4af56e7e78d57cda35a3b0afa16a8f2a164cceff024ac7341a94`.
Public-page metadata and its anonymous file-list response are pinned separately.

The released workbook contains 365 daily rows for 2022, with no within-day
timestamps; the two other sheets are empty. Its `Inv-1`, `Inv-2` and `Main` output
headers do not declare kW or kWh. The description's subdaily collection cadence
does not make those underlying records available in this workbook.

There are 338 days with both inverter outputs present. On 5-31 December, both
inverter values are missing while `Main` is zero from an explicit SUM formula.
These 27 values are retained with missing-input flags, never treated as observed
zero generation. A separate arithmetic discrepancy occurs on 25 June: the reported
inverters total 550.4, while `Main` is 570.4. Source values are not repaired.

The year metadata cell stores numeric 2022 with a date format that a standard
reader displays as 14 July 1905. The audit reads that literal stored year and
explicit month/day columns, corroborated by the publisher's year. It invents no
time of day. Seven nondate trailing rows and duplicate flare/CME header labels
remain documented. Realized weather columns are not day-ahead forecast inputs.

Decision: do not upsample this daily series, infer output units, manufacture
missing inverter generation, attach it to the unrelated Delhi load, or use it
to train an interval PV forecast. It remains a concrete C&I data-access lead.
The raw source and receipt are under `data/raw/india_jaipur_pv_v1/`; the daily
ledger, exclusions, publisher metadata and executed audit are under
`outputs/india_ci/pv_source_audit_20261029/workbook_audit/`.

## Separate Delhi public-data PV scenario

The [declared conversion protocol](../configs/india_public_pv_scenario_v1.yaml)
was sealed before deriving PV totals at 2026-10-29T11:51:56.671663 UTC, SHA-256
`6e64f96aab365485c0e7f61ceb32a833303391e9703e02b700450bf4d94c8ca0`.
It uses the existing 91-day load/resource benchmark and round assumed ratings,
with no sizing optimization or supplier quotation:

```text
DC nameplate = 40 kWp; AC limit = 32 kW; constant inverter efficiency = 0.96
Pdc[kW] = 40 * GHI_mean[W/m2] / 1000
Pac[kW] = min(32, 0.96 * Pdc)
Eac[kWh per quarter] = Pac * 0.25 h
```

This is a horizontal, reference-temperature irradiance-linear scenario. The
[PVWatts V5 technical reference](https://pvwatts.nrel.gov/downloads/pvwattsv5.pdf)
documents the irradiance-linear DC relation with a temperature factor. Here the
PV cell temperature is explicitly fixed at its 25 C reference. This small
conversion is not a complete PVWatts implementation or performance validation.
Ambient NASA T2M is not relabelled as PV cell or battery temperature. Tilt,
reflection, shading, soiling, thermal loss, part-load efficiency, degradation,
standby consumption and outage effects are uncalibrated/excluded.

The 8,736 quarter-hour rows retain their **60-minute resource resolution**.
There are 2,183 complete UTC source-hour bins and two endpoint bins with two
quarters each. Quarter values are piecewise constant derivatives of hourly
resource, not subhourly measurements. Unit tests cover darkness, clipping, exact
Wh-to-W and kW-to-kWh conversion, timezones, continuity, immutable inputs and
rejection of unsupported tilt/temperature assumptions.

The 91-day scenario totals 14,895.759744 modeled AC kWh, reaches the assumed
32 kW AC limit and clips 60 quarters. The source-hour-bin energy balance error
is zero. All rows were also recomputed from the direct formula, with maximum
power disagreement below 8e-15 kW. These verify the implemented calculation,
not its agreement with a real plant or an annual production estimate.

New data: `data/processed/india_ci/academic_load_modeled_pv_v1.csv`.
Registration, daily modeled totals, code snapshots, source/output hashes and
integrity review: `outputs/india_ci/india_public_pv_scenario_v1/`.
Reproduction is `rtk proxy .venv/bin/python scripts/prepare_public_pv_scenario.py`;
completed outputs are immutable. Existing source/load/forecast results and the
published dashboard are preserved.

## Remaining operational gate

Historical realized resource is an offline simulation input, not a weather
forecast available at the decision origin. The subsequent separately registered
[controller comparison](india_controller_review.md) now implements observation
cutoffs, previous-day modeled-PV forecasts, frozen load forecasts, continuous
SOC, ideal interval recourse and matched wear/inventory objectives under an
illustrative active-energy price. Its adverse primary result is retained.
This completes that offline comparison, not operational forecast validation.
Measured paired site PV/load, bill/category/export evidence,
pack/BMS/temperature calibration and supervised operation remain necessary for
field claims. This conversion alone establishes neither financial savings nor
controller effectiveness.
