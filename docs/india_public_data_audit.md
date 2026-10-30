# Indian public-data benchmark audit

Source audit: 27 October 2026; load-forecast comparison: 28 October 2026.
The user has no private site data and authorized an
online search. This is preparation for phase 20; the field-validation gate is
still open. Existing dashboard figures and `configs/india_ci.yaml` remain
illustrative.

## Recommended load source

[I-BLEND / Energy dataset of IIITD](https://springernature.figshare.com/articles/dataset/Energy_dataset_of_IIITD/6007637)
is the preferred first candidate. The authors' repository record describes
aggregate electricity consumption for seven campus buildings and publishes a
CC0 release, DOI `10.6084/m9.figshare.6007637.v1`. The associated
[paper](https://doi.org/10.1038/sdata.2019.15) describes a campus dataset spanning
commercial and residential buildings; select the non-residential building meters
after inspecting the archive documentation. An academic campus is an
institutional/commercial demand benchmark, not a measured factory.

The official Figshare API inventory is pinned at
`outputs/india_ci/source_audit/iblend_metadata.json`. It identifies one
589,226,996-byte archive, file ID `10797959`, with upstream MD5
`754d5c8549fd4907a7566b3b82c849ca`. Verified HTTP 206 access allowed selective
acquisition instead of the full archive. `scripts/acquire_iblend.py` acquired the
readme, academic-building mains meter and building availability flags. Their
receipts pin exact ranges, the matching archive ETag, member CRC32 and local
SHA-256 hashes. The full archive MD5 was **not** recomputed; no complete-archive
integrity claim is made. Residential meters were not extracted.

The readme specifies Unix timestamps, Asia/Kolkata (+05:30) conversion and power
in watts. The initial academic-meter audit inspected 2,269,530 rows dated
10 August 2013 through 31 December 2017. There are no duplicate timestamps,
negative power readings or unmatched availability records. Three missing power
values match the author's zero availability flags. Missing timestamps still
exist: the full availability table has 2,311,200 minutes, so these rows must not
be mistaken for continuous four-year coverage.

Power ranges from 0 to approximately 95.786 kW. Requiring every minute of a
15-minute interval to be present, finite, nonnegative and author-flagged as
observed yields 151,059 complete intervals out of 154,080 possible intervals.
The longest complete run has 8,902 intervals, from 16 September 2014 00:30 IST
through 17 December 2014 17:45 IST (interval start times). A proposed first replay
can use whole days inside that span; the evaluation period and forecasts still
need registration. These are initial quality findings, not completed dispatch or
bill validation. Evidence: `iblend_initial_meter_audit.json` and
`iblend_selected_receipt.json` under `outputs/india_ci/source_audit/`.

The separate load gate has now passed. `configs/india_public_data_v1.yaml` fixes
91 whole days (17 September through 16 December 2014), before any forecast fit or
dispatch comparison. It is sealed under `outputs/india_ci/india_iblend_academic_v1/`.
The 8,736 complete quarter-hours are split chronologically into 5,760 training,
1,440 validation and 1,536 test intervals. Estimated energy from the minute power
samples is 44,992.586 kWh; the selected 15-minute peak is 55.773 kW. These are
sample-based energy/load metrics, not a billed kVAh total or billing maximum demand.
The authors downsampled the original 30-second meters to one-minute records.

[COMBED](https://combed.github.io/) is a backup: the authors describe one month of
IIIT Delhi academic-building data sampled every 30 seconds. Its shorter duration
limits seasonal analysis. Its actual download access and file compatibility have
not been verified here.

## Solar and tariff inputs

Use the [NASA POWER historical hourly API](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/)
as a candidate solar-resource source for the same coordinates and dates, once
those are verified. Irradiance and ambient temperature can support an explicitly
modeled PV scenario. They are not measured inverter generation. Pin API response,
units, missing-value conventions, time standard, coordinates and date coverage.
Convert UTC explicitly to Asia/Kolkata; local solar time is not IST. Do not
upsample hourly resource data and describe the result as measured 15-minute PV.

The pinned NASA response now supplies 2,232 complete UTC hours, without fill
values, covering the selected demand period. Its solar units are **Wh/m² per
hour**, as declared in the response, and temperature is ambient air in degrees C.
The approximate regional point is 28.55 N, 77.27 E. `prepare_india_resource.py`
aligns hourly radiant energy to the quarter-hour load grid by uniform division;
the output preserves the 60-minute source-resolution label. No inverter output,
subhourly irradiance measurement or battery temperature is inferred. Load and
resource provenance identify every source and derived file.

Use [DERC's official tariff orders](https://derc.gov.in/tarriff-orders) and the
applicable DISCOM schedule for a declared Delhi scenario. Check effective dates,
consumer class, supply voltage, sanctioned/contract demand, ToD periods, demand
charges, adjustments, taxes and export rules before computing a bill. A recent
true-up publication is not automatically a new retail tariff schedule. Without
the campus connection/bill, a chosen commercial tariff is a counterfactual
scenario, not its observed bill.

The historic schedule effective 1 October 2021 is pinned and its table/notes were
visually reviewed. Commercial energy charges use kVAh. The reviewed 2017 supply
code defines maximum demand over 30 consecutive minutes unless another period
is notified; billing demand is at least the contract/sanctioned demand. Current
amendments, the customer's category/contract and complete billing-cycle data
remain unverified. Do not apply another state's demand floor, treat the 15-minute
load peak as metered demand, or label the 2014/2021 combination as an observed bill.

An electrical-quality audit also found 145 zero power-factor values with positive
active power and 27,368 negative power-factor values in the selected minute data.
The [subsequent semantic review](india_electrical_semantics.md) finds that negative
PF is compatible with the historical EM6400 leading-load convention; it is not
automatically export or a bad reading. Site CSV-to-register mapping and the
release's downsampling operator remain unverified. Zero PF must not be replaced
with unity, or used as a divisor to fabricate apparent energy. No direct kVAh
billing counter is present. The 145 zero-PF/positive-power records span 126
quarters and 59 days; very small nonzero PF values also prevent treating a
zero-only repair as sufficient. The active-load gate therefore does not establish
the apparent-energy billing gate. Original and follow-up audit evidence remain
separate, with unchanged source records.

National/state grid-demand series are useful context but cannot substitute for
one customer's meter when estimating behind-the-meter peak charges or savings.
Monthly PV totals likewise cannot establish interval battery dispatch.

## Integration and evidence gates

1. Complete semantic review of the verified academic-building meter. Keep buildings
   and submeter hierarchies distinct to avoid double-counting demand. The source
   readme, units/timezone and initial availability audit are now established.
2. Establish timestamp timezone, interval semantics, units, gaps, duplicate/conflict
   handling and any cumulative-meter resets. Preserve original records and hashes.
3. Select contiguous usable periods and report coverage before optimization. Never
   fill missing demand or PV with zero silently, or annualize a short replay into
   measured annual savings.
4. Acquire matching solar-resource records and register PV sizing/conversion
   assumptions. Preserve the distinction between measured load and modeled PV.
5. Register a tariff scenario and battery/controller assumptions before comparing
   policies. Preserve historical results and keep public-benchmark results separate.
6. Use identical site inputs and forecast-error assumptions for policy comparisons;
   report energy/demand charges separately and distinguish perfect-foresight replay
   from causal control.
7. Publish a public-data feasibility benchmark only after input, controller and
   provenance checks. Pack quotation, BMS/SOC/temperature telemetry, an actual
   applicable customer bill and supervised operation remain necessary for field
   savings, wear or investment claims.

Load and solar records support dispatch and forecasting of site power. They do
not supply battery SOH labels and will not be appended to the battery-aging GRU
training table. The first-life/second-life research experiment remains separate.

## Registered day-ahead load comparison

The independent [forecast protocol](../configs/india_load_forecast_v1.yaml) was
sealed on 28 October 2026 at 06:22:19.841791 UTC before prediction scoring or blend
selection. SHA-256:
`24c1805e414ca0fd6fcdf07251fdfc3904810797a441f5f876f023186c040486`.
The original data window and chronological partitions remain unchanged. Descriptive
meter-quality findings were known before registration; forecast errors were not
yet scored.

At midnight IST, forecast each of the next 96 quarter-hour mean active-power
values using

```text
predicted_load(day, quarter) =
    w * observed_load(day - 1, quarter)
    + (1 - w) * observed_load(day - 7, quarter)
```

Five weights were fixed in advance: 0, 0.25, 0.5, 0.75 and 1. No GRU or regression
is fitted to these site data. The training period supplies past observed lag
values. Fifteen validation days, 16-30 November 2014, select the weight by pooled
quarter-hour RMSE; ties prefer the smaller daily weight. The selected weight is
saved before scoring the 16 test days, 1-16 December 2014.

Only intervals ending at or before the forecast origin are permitted. This assumes
zero reporting delay at the boundary, not a verified live telemetry service. Past
observed test days may supply lag values to later origins, but their errors never
update the selected weight. Future measured demand, realized weather and modeled
PV do not enter prediction inputs. There is no missing-value filling or clipping.

| Previous-day weight | Validation RMSE (kW) | Test RMSE (kW) |
| ---: | ---: | ---: |
| 0: weekly persistence | 4.585 | 2.846 |
| 0.25 | 3.441 | 2.378 |
| **0.5: selected using validation** | **2.958** | **2.150** |
| 0.75 | 3.429 | 2.235 |
| 1: previous-day persistence | 4.566 | 2.604 |

For each model, pooled RMSE is the square root of the mean squared error across
all 16 x 96 test quarters. The selected model's MAE is 1.448 kW and its signed
prediction-minus-observation bias is +0.617 kW. The selected-minus-weekly RMSE
difference is -0.696 kW; the descriptive 95% paired four-day circular-block
bootstrap interval is [-1.145, -0.265] kW (10,000 replicates, seed 42). One short
seasonal window and serial dependence limit inference; this is not cross-site
or all-season validation.

Lower RMSE does not mean every objective improves. The selected blend overpredicts
daily energy by 14.816 kWh on average, versus 1.850 kWh for the previous-day
baseline. Its mean daily peak magnitude absolute error is 1.597 kW, with an
underestimate on six test days. Its mean absolute peak timing error is 121.875
minutes. These are active-power profile peaks, not a metered billing maximum demand.

On 7 December 2014, the selected model's worst-RMSE day (4.683 kW), daily peak
magnitude is underestimated by only 0.089 kW, but the predicted peak is at 12:45
IST versus the observed 22:15 IST: **570 minutes apart**. Its daily energy error
is +72.860 kWh. A near-correct daily peak magnitude can conceal a large timing
failure; forecast accuracy alone establishes neither peak-shaving effectiveness
nor billed savings. No reason for the demand change is inferred from these traces.

The [daily-error and worst-day figure](../outputs/india_ci/india_load_forecast_v1/analysis/test_errors_and_worst_day.png)
shows these failures. The [run review](../outputs/india_ci/india_load_forecast_v1/forecast/review.md),
all five arms, validation-only selection record, daily metrics, prediction ledger,
implementation snapshot and completion hashes are retained under
`outputs/india_ci/india_load_forecast_v1/`. The postfit figure has separate
provenance; its legend-layout draft is preserved separately, without refitting.

All 155 tests and lint checks pass. An independent integrity check reconstructed
all 14,880 validation/test forecasts from the exact source lag values, recomputed
all RMSEs, reproduced validation selection, checked interval-end cutoffs and
verified protocol/input/code/artifact hashes. Evidence is recorded in
`integrity_recheck.json`. Both run scripts refuse to overwrite completed output
directories; rerunning a scientific comparison requires an explicit versioned
study, not deleting completed evidence.

This advances the separate site-demand forecast component only. A subsequent
[separately declared modeled-PV conversion](india_pv_source_audit.md) now prepares
the public benchmark's hypothetical horizontal PV input; it does not validate
an inverter meter or an operational weather forecast. PV forecast validation,
tariff/apparent-energy semantics, pack calibration and supervised field validation
remain open. The subsequent [registered controller study](india_controller_review.md)
completes a matched offline comparison with past-only planning and ideal
quarter-hour recourse, not verified live causal control or field validation. No first-life
source defect is repaired and no client dashboard result is promoted.

## Registered offline controller comparison

The separately sealed controller protocol uses the frozen load blend and
previous-day modeled PV with explicit observation cutoffs. It compares six
policies over the same 16 days, using 18 hypothetical battery-health/seed cases
with common physical capacity within each case. All 165,888 realized actions,
continuous SOC transitions, common wear coefficients and 108 path scores were
independently reviewed. Transfer-derived control lowers energy charge relative
to scratch-derived control, but increases the common wear/inventory-adjusted
score by INR17.25, descriptive day-block interval [INR0.84, INR32.90].

The active-energy price remains an illustrative INR10/kWh, not a commercial
kVAh bill. Modeled PV, ideal feedback and a training-derived mixed-aging wear
proxy do not validate measured PV, actual pack aging or site savings. See the
[controller mathematical review](india_controller_review.md) and
[remaining gate review](integration_gate_review.md).

## Next data-access lead

The [public-source gap review](india_electrical_semantics.md#additional-public-data-search)
identified a Coimbatore institutional microgrid study describing paired grid,
solar and battery records, with access through the corresponding author on
request. A [concrete data request](india_ci_data_request.md) was sent on
30 October after explicit user instruction; the exact sent message was
read back and verified. No source records or reuse rights are assumed to have
been obtained. The other reviewed solar mapping, capacity-factor
and radiation sources do not supply this building's paired inverter/BMS records.

The additional [Jaipur factory PV workbook audit](india_pv_source_audit.md) acquired
a publisher-checksummed CC BY 4.0 source. Its released data are daily, with missing
inverter outputs and formula-derived zero totals, and do not close the interval
PV or paired-site gate. The preserved source is not merged into the Delhi observations.

## Public-search follow-up: 30 October 2026

A further bounded search reviewed primary publisher/repository records for Indian
microgrid load/PV/BMS data and rechecked the existing request-only lead. These
are metadata-level decisions, not raw-file audits or claims that no other source
exists. No new files were fitted, and no research settings were changed.

| Primary record checked | Observation | Decision for phase 20 |
| --- | --- | --- |
| [Coimbatore smart-building microgrid paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12909795/) | The current data-availability section still directs requests to the corresponding author; no downloadable underlying data were identified there. | Await the requested records; do not treat article tables as interval measurements or infer dataset reuse rights. |
| [Indian demand/solar/wind, version 2](https://data.mendeley.com/datasets/y58jknpgs8/2), DOI 10.17632/y58jknpgs8.2 | Publisher describes hourly demand and renewable generation across India's combined five regional grid networks. | Grid-level scope cannot supply one customer's behind-the-meter load/PV/BMS topology or bill. No large workbook download is needed to resolve this mismatch. |
| [ComErgy 2026 benchmark](https://data.mendeley.com/datasets/fc8tp82hyb/1), DOI 10.17632/fc8tp82hyb.1 | Publisher explicitly describes a hypothetical nine-household community rather than a specific real community. | A further hypothetical benchmark cannot close the measured Indian C&I site gate. |
| [Containerized BESS field operations](https://zenodo.org/records/20094787), DOI 10.5281/zenodo.20094787 | Repository describes eight months of rack/cell electrical, SOC and temperature measurements. Its listed measurement structure does not establish paired Indian customer load/PV, a customer tariff or M50T pack identity. | Potential separate telemetry-method research, not evidence for this site's bill or pack calibration; defer multi-GB acquisition and any new study. |

The next phase-20 dependency is still access to a suitable paired site record and
its equipment/connection metadata. Following explicit user authorization, the
Coimbatore data request and Stanford source/temperature clarification were sent
on 30 October, without attachments. Sending does not supply data or establish
reuse terms. See the
[requirement and acceptance-evidence checklist](integration_gate_review.md).
