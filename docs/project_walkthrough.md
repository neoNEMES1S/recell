# ReCell: from measurements to a pilot decision

The dashboard now targets **Indian commercial and industrial (C&I) storage** and
reports costs in **INR**, with Indian digit grouping. Its dispatch is re-optimized
using `configs/india_ci.yaml`: ₹10/kWh flat grid energy, ₹0 export credit and
₹1,00,000 replacement cost for the 10 kWh / 3 kW reference system. These are
illustrative inputs, not a DISCOM tariff or a supplier quotation. No FX conversion
is used. The current German household solar/load profile remains a research proxy,
not an Indian industrial measurement or a sized C&I installation.

The original EUR experiment discussed below is preserved as the historical research
reference. Do not use its percentages as the new INR scenario results; the dashboard
computes those from the new dispatch. For an Indian pilot, collect the site's
interval demand and solar, applicable DISCOM tariff, sanctioned demand, ToD slots,
export agreement and pack quotation. The reference objective excludes demand/fixed
charges, power-factor penalties, duties, taxes, installation, O&M, financing,
subsidies and backup value. It therefore does not estimate the complete C&I bill.
Backup reliability, outage operation and demand-charge savings are not modeled.

[Ministry of Power's 2023 ToD implementation reference](https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=1945236)
provides policy context; the site's applicable tariff order must determine its rates
and time slots. The dashboard's flat ₹10/kWh input is explicitly an assumption.

Use this guide alongside the dashboard's **Learn the method** view. The objective is
to understand what we calculate, why we calculate it, and what each result supports.
The project has two separate optimization problems: learning accurate health forecasts,
then choosing storage operation under assumed electricity and wear costs.

## 1. What question are we answering?

A used EV battery can still store energy. We investigate whether its recorded history
helps predict future capacity, and whether incorporating that forecast changes the
way a solar-storage system should operate. This research prototype supplies evidence
for a validation pilot. It does not establish field savings or lifetime extension.

Our evidence consists of six battery cells, 111 diagnostic checkpoints, and one
720-hour household solar/load replay. Thousands of forecast rows are repeated
experiments on those six cells, not thousands of independently tested batteries.

## 2. How do measurements become capacity?

Capacity in ampere-hours (Ah) measures how much electric charge the battery can deliver.
The raw instrument records time and current. Discharge current is negative in this
release. We integrate four reviewed low-current discharge segments:

`capacity_Ah = −Σ[(I[j] + I[j+1]) / 2 × (t[j+1] − t[j])] / 3600`

The trapezoidal formula estimates the area under the current-versus-time curve. The
3600 converts seconds to hours. A constant 2 A discharge lasting 2 hours delivers
4 Ah. That is an illustrative example, not a replacement for the actual test protocol.

We exclude pulses, rests and recharge from this capacity measurement. The four segments
must span the reviewed voltage window, have acceptable sample gaps, and agree with
the instrument's capacity counters. Hash checks, duplicate removal and identity checks
prevent using altered, double-counted or incorrectly assigned measurements.

## 3. What does battery health mean here?

`SOH = measured_capacity_Ah / first_observed_second_life_capacity_Ah`

For example, a battery with a 4.5 Ah starting reference and a later measurement of
4.32 Ah has SOH 0.96, displayed as 96%. The denominator is available before forecasting;
we never normalize using a future best measurement.

This 96% is relative to the battery's second-life starting point. It is not necessarily
96% of its factory specification. To compare with nominal capacity we must change the
reference explicitly: 4.32 Ah / 5 Ah = 86.4% of nominal.

SOH is also different from **SOC**, state of charge. SOH describes the size of the
remaining energy container; SOC describes how full that container is at a moment.

## 4. What do we show the forecasting models?

At each forecast origin we supply only information available up to that checkpoint:
SOH, elapsed days, previous cycling throughput, a pulse-resistance proxy, duty class,
and documented first-life-end capacity. Diagnostic throughput is excluded from the
cycling exposure feature. Temperature and EIS are excluded from the initial predictors
because sensor mapping and some identities remain unresolved.

Persistence repeats the last SOH. Ridge regression learns a regularized linear relation.
XGBoost combines small decision trees. A GRU learns patterns in a sequence of earlier
checkpoints. Point models predict one value; quantile models predict P10, P50 and P90.

We forecast the next one and two diagnostic checkpoints. Their calendar spacing is
irregular, so a two-checkpoint horizon must not be presented as a fixed number of days.

## 5. How do we test an unseen battery fairly?

For each of six folds: train on four cells, use a fifth for validation and stopping,
and evaluate once on the sixth. Rotate the held-out cell. Fit missing-value replacement
and scaling only on training cells. Test battery outcomes do not choose the model fit.

Repeat with three random seeds. Limited-history experiments retain the most recent
10%, 25%, 50%, 75% or 100% of the available pre-origin checkpoints, rounded up to at
least one. Forecast origins and targets stay identical. Models still train on full
training histories; SOH reference and accumulated exposure remain available metadata.

Metrics are calculated per cell and seed, then seeds are averaged within each cell,
then cells receive equal weight. We do not pool every row and call the result six-cell
generalization. Error bars in the reference summary are SD across cells, not confidence
intervals or prediction intervals.

## 6. What do the forecast metrics mean?

Let `e = prediction − observation`, with `n` evaluated predictions.

| Metric | Calculation | Meaning |
| --- | --- | --- |
| MAE | `Σ abs(e) / n` | Typical absolute error; lower is better |
| RMSE | `sqrt(Σ e² / n)` | Emphasizes large misses; lower is better |
| MAPE | `100 × mean(abs(e / observation))` | Relative error; undefined near zero targets |
| R² | `1 − Σe² / Σ(observation − mean(observation))²` | Fit relative to the observed-mean benchmark; can be negative, not “accuracy” |
| P10–P90 coverage | `count(P10 ≤ observation ≤ P90) / n` | Fraction covered by the interval; target 80% |
| Interval width | `mean(P90 − P10)` | How broad the uncertainty range is; read together with coverage |
| Empirical quantile | `mean(observation ≤ predicted quantile)` | Calibration: ideally 10%, 50% or 90% for P10/P50/P90 |

SOH metrics are stored as fractions. Multiply MAE/RMSE/width by 100 to display SOH
**percentage points**. RMSE 0.002146 is 0.2146 percentage points, not 99.7854% accuracy.
Capacity metrics instead multiply the target and forecast by that cell's reference Ah
before computing the error.

Worked example: actual SOH `[98, 97, 96]%`, predicted `[97.8, 97.4, 95.9]%` gives errors
`[−0.2, +0.4, −0.1]` percentage points. MAE is 0.2333 pp and RMSE is 0.2646 pp.
The larger +0.4 miss affects RMSE more strongly.

For quantile level `q`, let `u = observed − predicted_quantile`. **Pinball loss** is
`max(q × u, (q − 1) × u)`. We average this across P10, P50, P90 and targets. It penalizes
under- and over-prediction differently, so the model learns a distribution rather than
three identical means. Coverage alone is insufficient: very wide intervals can cover
almost everything without being useful.

In the reference run, XGBoost has the lowest aggregate RMSE. PGP-GRU beats persistence
and vanilla GRU on average, but not XGBoost or ridge. Its 86.4% P10–P90 coverage is above
the nominal 80%; uncertainty is not perfectly calibrated. The small six-cell sample
limits claims about general superiority.

## 7. What objective trains PGP-GRU?

The model predicts changes relative to origin SOH. Positive spacings keep P10 ≤ P50 ≤ P90.
The training objective combines four terms, with `s = 0.02` and tolerance `r = 0.002`:

`L = λp × mean(((P50 − y)/s)²) + λq × pinball/s + λm × monotonic + λs × smooth`

`path = [origin_SOH, predicted_P50_at_horizon_1, predicted_P50_at_horizon_2]`

`increments = consecutive differences in path`

`monotonic = mean(max((increment − r)/s, 0)²)`

`smooth = mean((consecutive differences in increments / s)²)`

The reference weights are 1, 1, 0.1 and 0.1. The first terms reward accurate central
and quantile predictions. The last terms softly discourage large recovery and abrupt
curvature; they do not enforce a mechanistic electrochemical law. Small recovery is
allowed. Smoothness is across checkpoints, not equal-duration time intervals.

Vanilla GRU uses scaled squared point error only. The quantile-GRU ablation sets both
physics penalty weights to zero. Validation selects the best epoch using prediction
loss without physics penalties. Training loss is not the same as the reported RMSE.

## 8. How do forecasts enter dispatch?

Use each cell's selected held-out one-checkpoint forecast, seed 42. The median case uses
P50; the conservative case uses P10. Selection is by latest origin, not smallest test error.

`nominal_health = forecast_SOH × reference_capacity_Ah / nominal_cell_capacity_Ah`

`available_energy_kWh = nominal_pack_energy_kWh × nominal_health`

For G1 in the saved run: nominal health is approximately 0.88244, so a nominal 10 kWh
pack is represented by 8.8244 kWh. The 10–90% SOC operating window permits a 7.0595 kWh
swing before conversion losses. The exported “usable_energy_capacity_kwh” field is the
full health-adjusted capacity; the dashboard distinguishes it from the SOC window.

Training-cell throughput estimates exposure between diagnostics:

`expected_EFC_per_checkpoint = median(positive training-cell ΔAh) / (2 × nominal_cell_Ah)`

`wear_per_EFC = max(0, (origin_SOH − forecast_SOH) × reference_Ah / nominal_Ah
                         / (expected_EFC_per_checkpoint × horizon))`

This is a linear calibration proxy. It attributes forecast decline to cycling exposure,
omits a separate calendar-aging model, and transfers cell behavior to a pack scenario.
It needs physical validation. Predicted recovery is mapped to zero wear, not negative wear.

## 9. How do we calculate the operating objective?

Household meters report cumulative energy. Difference adjacent readings to obtain
hourly energy; over one hour the numeric kWh difference equals average kW. Reconstruct
load as `grid_import + PV − grid_export`. The June 2016 household replay is a separate
operating scenario, not the historical operation of these test batteries.

The optimizer chooses hourly charge/discharge, grid import/export and curtailment.
It minimizes:

`objective = net_electricity_cost + wear_weight × estimated_wear_cost`

`net_electricity_cost = Σ(import_kWh × import_price − export_kWh × export_price)`

`internal_throughput_kWh = Σ(η × charge_kW + discharge_kW / η) × 1 hour`

`equivalent_full_cycles = internal_throughput_kWh / (2 × nominal_pack_kWh)`

`estimated_capacity_loss = wear_per_EFC × equivalent_full_cycles`

`estimated_wear_cost = replacement_cost × estimated_capacity_loss / loss_budget`

Here `η = sqrt(0.90)`, replacement cost EUR1,000 and loss budget 0.20. EFC uses nominal
pack energy, not the reduced health-adjusted capacity. Wear is an estimated economic
allowance, not an observed repair bill. A carbon-cost term is supported but disabled
because no carbon-intensity data are supplied.

Constraints enforce energy conservation, power bounds, SOC limits, and equal initial
and final stored energy. `E[t+1] = E[t] + η × charge[t] − discharge[t]/η` for hourly data.
Only solar surplus charges the battery; discharge serves remaining household load.
The optimizer has perfect knowledge of the entire replay. Health stays fixed during it.

Solar self-consumption is `(direct solar + solar charged into battery) / total solar`.
This includes energy later lost in battery conversion. It is not the same as the
fraction of household demand supplied by solar.

## 10. How should a client interpret the comparison?

Scenario C optimizes electricity cost only (`wear_weight = 0`). Median D adds the wear
proxy (`wear_weight = 1`) using identical battery health and wear assumptions. Read
electricity cost and estimated wear separately before comparing their sum.

Across six cell scenarios, C has EUR−5.00 net electricity cost plus EUR18.13 modeled
wear, or EUR13.13 total. Median D has EUR0.12 plus EUR11.54, or EUR11.66 total. D raises
the electricity bill but lowers modeled cycling cost enough to improve the combined
objective. Negative electricity cost means export revenue exceeds import cost.

`relative modeled improvement = (mean C total − mean D total) / mean C total × 100`

`relative cycling reduction = (mean C EFC − mean D EFC) / mean C EFC × 100`

Use unrounded means for those percentages. Do not confuse ratio-of-means with mean
of cell-level percentage changes. At wear weights 0.5 or 2, the solver objective differs
from the unweighted electricity-plus-wear sum displayed for comparison. The dashboard
selects precomputed scenarios; moving a selector does not re-solve the optimization.

The P10 conservative case changes assumed health and wear. It is not a fair direct
policy comparison with C. Scenario B assumes full nominal capacity but uses the same
wear proxy, so it does not independently validate new-battery economics.

## 11. What are we asking the client to approve?

A bounded validation pilot, with acceptance thresholds agreed before collecting new
test outcomes. Proposed work: acquire additional independent cells/packs; calibrate
wear against observed aging; test realistic load/solar forecast errors; compare against
a conventional controller; verify safety and operational constraints on the target system.

Agree the evidence and threshold for forecasting error, interval coverage/width,
constraint violations and measured economic outcomes. No deployment-readiness score,
ROI guarantee, lifetime extension or arbitrary numeric approval threshold is asserted.
The dashboard review checklist is a discussion aid, not a signature or authorization.

Calculation sources: `data/features.py`, `evaluation/metrics.py`, `training/losses.py`,
`training/experiments.py`, `optimization/degradation.py`, and `optimization/solar_dispatch.py`
under `src/second_life_battery/`. Snapshot sources and hashes are exposed in the dashboard.
