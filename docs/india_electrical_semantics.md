# Indian meter semantics and public-data gap review

Review date: 28 October 2026. The registered load-forecast comparison and all
historical research outputs remain unchanged. This audit does not compute a bill.

## What the primary sources establish

The I-BLEND paper identifies Schneider EM6400 meters and says the 30-second logs
were aligned to one-minute records. The reviewed energy-data paragraph does not
specify the release's resampling operator. An analysis helper's later resampling
behavior would not by itself identify the release-construction pipeline.
Source: [I-BLEND paper](https://doi.org/10.1038/sdata.2019.15), Data Cleaning section.
Its BioC XML text is locally pinned under
`outputs/india_ci/source_audit/electrical_semantics_v1/` with acquisition receipt
and SHA-256. The raw paper text is evidence, not executable code.

Schneider's [2011 EM6400 communication chapter](https://ckm-content.se.com/ckmContent/sfc/servlet.shepherd/document/download/0691H00000Dwn4OQAR)
distinguishes registers for total W (3903), total VA (3901), average PF (3907),
average current (3913), line-neutral and line-line voltage averages (3911/3909),
and forward VAh (3959), printed pages 57-58. These addresses do not prove which
registers the released CSV columns came from.

The [2017 EM6400 quick-start guide](https://ckm-content.se.com/ckmContent/sfc/servlet.shepherd/document/download/0691H00000DwmnMQAR)
describes a negative PF as compatible with a leading capacitive load and treats
power direction separately (page 4). Thus negative PF alone is not evidence of
export or an invalid record. This is a model-family convention; the site's
CSV-to-register mapping and configuration still need confirmation.

These PDFs were reviewed through the web tool's extracted text. Direct archival
downloads returned HTTP 503; the receipt records those failures, with no claim
that local PDF bytes or upstream hashes were verified. Newer EM6400NG+ guidance
was not substituted for the historical equipment configuration.

## Quantified limitations in the registered 91-day window

`scripts/audit_india_electrical.py` verifies the pinned source and fixed window,
then inspects all 131,040 selected minute records without changing them.

| Finding | Count / value |
| --- | ---: |
| Negative PF minutes | 27,368 |
| Zero PF with positive active power | 145 minutes |
| Quarter-hours containing those zero-PF readings | 126 |
| Half-hours containing those readings | 122 |
| Local days containing those readings | 59 |
| Active-energy sample estimate associated with those readings | 37.520 kWh |
| Minimum nonzero absolute PF | 0.00001 |
| First percentile of nonzero absolute PF | 0.00027 |

The 37.520 kWh is active energy estimated from the recorded power samples, not
lost energy, apparent energy or a bill discrepancy. Very small nonzero PF also
means a zero-only substitution would not establish a stable or valid apparent-
energy reconstruction. No cause for the readings is assigned without raw logger
and configuration evidence.

## Why dividing averaged columns does not recover a meter register

For illustrative synchronous samples with a verified total PF definition,
instantaneous apparent power could be represented by P/abs(PF). But in general:

```text
mean(P / abs(PF)) != mean(P) / abs(mean(PF))
```

Two hypothetical half-minute histories can both have mean active power 1 kW and
mean PF 0.6. PF values [0.6, 0.6] give mean apparent power 1.667 kVA, whereas
[0.3, 0.9] give 2.222 kVA. Signed PF values [0.9, -0.9] instead have a zero signed
mean while their apparent powers remain finite. These are mathematical
counterexamples, not reconstructions of I-BLEND's missing raw sub-minute samples.

Phase averages also lose information: voltage/current triples [240,240,240] V /
[10,10,10] A and [250,240,230] V / [20,10,0] A have identical means, but different
arithmetic sums of phase VA (7,200 versus 7,400). This illustrates why multiplying
average voltage and current cannot certify total apparent power under unknown
wiring, unbalance and instrument conventions. It does not assert that this
arithmetic definition was the site's configured total-VA method.

Runtime assertions check these counterexamples. The audit saves exact zero-PF
row identities, source/code hashes and counts in
`outputs/india_ci/source_audit/electrical_semantics_v1/analysis/`.

**Decision:** preserve the active-load gate; keep the apparent-energy billing gate
closed. Do not divide by zero, replace PF with unity, clip small values, delete
negative PF rows or manufacture kVAh. Request the original measurement/mapping,
resampling procedure, relevant apparent-energy/demand registers and applicable
customer bill before treating an apparent-energy calculation as verified.

## Additional public-data search

The reviewed search produced a promising access lead, not a downloadable matched
Indian C&I dataset:

- [Coimbatore smart solar microgrid study](https://doi.org/10.1038/s41598-026-36960-x):
  the authors describe 2023 five-minute grid, solar and battery variables from an
  institutional testbed. Its data-availability section routes access through the
  corresponding author on request; no direct dataset link is supplied there.
  Units, usable channels, raw quality, BMS coverage and dataset reuse terms are
  unverified. A [specific request](india_ci_data_request.md) was sent on
  30 October after explicit user authorization; no data access is established.
- [Indian solar-installation map](https://doi.org/10.1038/s41597-022-01499-9):
  geographic installation polygons are not measured PV output or building demand.
- [Historical/modelled Indian renewable production](https://zenodo.org/records/7824872):
  capacity-factor modelling does not supply this campus's inverter meter or
  behind-the-meter battery record.
- [NWIC solar-radiation telemetry](https://nwdp.nwic.gov.in/en/dataset/solar-radiation-telemetry-hourly-bhakra-beas-management-board-chandigarh):
  irradiance observations are not a paired building-load/PV/BMS measurement;
  station/date matching and download contents were not audited here.

This is a bounded search result, not proof that no suitable public dataset exists.
None of these leads is appended to battery-health training or promoted into a
client savings claim. A subsequent [matched offline controller comparison](india_controller_review.md)
is complete with an illustrative active-energy price; it does not close the
pack/thermal, actual tariff/bill or supervised field gates.
