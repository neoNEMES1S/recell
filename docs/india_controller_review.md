# Public controller comparison: result and mathematical model

30 October 2026. The registered offline comparison is complete. Its central
finding is that slightly lower SOH forecast error did not improve the chosen
scenario objective. **No field savings, physical wear reduction, investment
case or deployment readiness is established.** The published dashboard is unchanged.

## What was compared

Protocol `india_public_controller_v1` was sealed at
2026-10-29T17:15:12.073806 UTC, SHA-256
`5eb1c3b564c66cf96ef3c32a678457a3e7b9e29591cf8ba2d1f80e27c53eef0f`,
before any controller outcome. Existing health-forecast results, demand-forecast
test errors and modeled-PV totals were already known and disclosed in registration.
This is not a new prospective validation cohort.

One IIIT Delhi public active-power meter supplies the 16-day period, 1-16 December
2014. The meter is treated as hypothetical gross load; its existing on-site
PV/net-meter semantics are unverified. The separate [PV scenario](india_pv_source_audit.md)
assumes 40 kWp DC / 32 kW AC, a horizontal array at fixed reference temperature,
and hourly regional NASA resource distributed uniformly over quarters. No
measured inverter series is substituted or inferred.

Six laboratory battery-health states and seeds 42/43/44 supply 18 hypothetical
cases. Each uses the latest matched v3 H1 origin at 10% context. Later laboratory
states are not attributed to the Delhi building in 2014. Within a case, all
policies share the same current physical capacity, actual-origin SOH, power limits,
initial SOC, efficiencies, profiles and recourse. Forecast medians change only
the planning wear coefficient. XGBoost receives no fabricated uncertainty band.

| Policy | Behavior |
| --- | --- |
| A | No battery; direct modeled PV and grid supply |
| B | Greedy current-surplus charging and deficit discharge |
| C | Day-ahead energy/inventory optimization without planning wear |
| D-R1 | Same optimizer with scratch-GRU point-forecast wear |
| D-R2 | Same optimizer with transfer-GRU point-forecast wear |
| D-R5 | Same optimizer with XGBoost point-forecast wear |

There are 1,536 distinct site quarters, replayed across 108 case/policy paths:
165,888 realized rows and 1,728 daily score rows. Baseline paths are reused across
seeds after checking identical physical inputs. There are 960 actual daily
optimizations. Repeated seeds/health cases do not create new sites or independent
weather records.

## How forecasts and actions work

At midnight IST, the controller forecasts 96 quarters. Demand uses the previously
validation-selected 50/50 previous-day/previous-week blend. PV repeats the previous
day's modeled profile. Only quarters ending by that midnight are available. The
PV history is a simulated zero-latency observation feed, not an operational NASA
weather forecast or verified live telemetry service.

The day-ahead plan is followed with ideal interval recourse: each quarter's
requested action is clamped by contemporaneous mean surplus/deficit, power and
SOC limits. Realized energy carries continuously into subsequent quarters and
days. Within-quarter variation, control bandwidth and telemetry timing remain
unvalidated. No hard daily SOC reset or free replacement energy is introduced.

## Implemented mathematical model

Let `L_t` be active load, `S_t` modeled PV, and `c_t`/`d_t` AC charging/discharging
power, all in kW. Time step `dt = 0.25 h`. The assumed pack has nominal energy
`E_nom = 40 kWh`, power limit 20 kW, round-trip efficiency 0.90, and symmetric
one-way efficiency `eta = sqrt(0.90)`.

```text
H_origin = origin_SOH * first_observed_stage_capacity_Ah / 4.85 Ah
E_capacity = E_nom * H_origin
0.1 * E_capacity <= e_t <= 0.9 * E_capacity
e_initial = 0.5 * E_capacity

direct_t = min(L_t, S_t)
surplus_t = max(S_t - L_t, 0)
deficit_t = max(L_t - S_t, 0)
0 <= c_t <= min(20, surplus_t)
0 <= d_t <= min(20, deficit_t)
grid_import_t = deficit_t - d_t
curtailed_PV_t = surplus_t - c_t
grid_export_t = 0
e_(t+1) = e_t + eta*c_t*dt - d_t*dt/eta

internal_throughput_kWh = sum_t[(eta*c_t + d_t/eta)*dt]
EFC = internal_throughput_kWh / (2*E_nom)
```

Charging uses PV only; discharge serves net load. These nonoverlapping surplus
and deficit constraints prevent simultaneous charging/discharging. The model
assumes controllable PV curtailment and unlimited grid imports, not a validated
export connection or backup operation. Capacity is held fixed during the replay;
there is no calibrated pack aging feedback.

Only the four target gradient-training batteries calibrate wear. Target
validation/test histories do not enter those statistics. For each training cell,
the median positive Ah increment divided by `2*4.85 Ah` supplies checkpoint EFC;
the median across four cells supplies expected checkpoint exposure. The planning
coefficient is:

```text
r_planner = max(0,
    (origin_SOH - predicted_median_SOH) * reference_capacity_Ah / 4.85
    / expected_training_EFC_per_checkpoint)
```

For common evaluation, each training cell's median signed nominal-capacity loss
per positive-exposure interval is calculated, then medians are taken across cells
and the pooled result floored at zero. Capacity recoveries remain in the signed
statistics; zero-exposure intervals receive no invented division or cycling-loss
label. This is a mixed-aging throughput proxy, **not measured physical wear**.
No fitted calendar term is added.

The illustrative active-energy price is INR10/kWh. Replacement cost is assumed
INR400,000 and the nominal capacity-loss budget is 0.20. These are scenario
inputs, not a DISCOM tariff, observed customer bill or supplier quotation.

```text
wear_cost(r) = 400000 * r * EFC / 0.20
terminal_value = 10 * eta  [INR per internal kWh]

J_plan = 10 * predicted_grid_import_kWh + wear_cost(r_planner)
         - terminal_value*(e_end - e_start)
         + 1e-6 * sum_t[(c_t^2 + d_t^2)*dt]

J_reference = 10 * realized_grid_import_kWh + wear_cost(r_reference)
              - terminal_value*(e_final - e_initial)
```

The inventory adjustment prevents using initial stored energy as free savings
and values unequal final inventories consistently. It is an assumed accounting
value, not a utility payment or a full future wear/value model. The small planning
preference is excluded from reported reference scores. Its maximum is INR0.0192
per day at the declared limits; that is not an error bound on realized replay.

## Results and interpretation

Amounts below are mean scenario INR per 16-day replay, averaging seeds within
each health case and then six cases equally. Lower reference score is better.

| Policy | Energy charge | Common wear proxy | Inventory adjustment | Reference score |
| --- | ---: | ---: | ---: | ---: |
| A: no battery | 43,392.82 | 0.00 | 0.00 | **43,392.82** |
| B: greedy | 41,586.79 | 1,962.68 | 136.42 | 43,685.89 |
| C: energy-only plan | 42,450.09 | 1,003.95 | 107.61 | 43,561.65 |
| D-R1: scratch-GRU wear | 42,716.26 | 781.53 | -31.67 | 43,466.11 |
| D-R2: transfer-GRU wear | 42,628.10 | 875.11 | -19.85 | 43,483.36 |
| D-R5: XGBoost wear | 43,129.87 | 314.60 | -33.04 | 43,411.43 |

The registered primary D-R2-minus-D-R1 difference is **+INR17.2473**, with a
descriptive paired four-day circular-block interval of **[+0.8410, +32.9049]**.
Transfer-derived planning lowers energy charge by INR88.16 but adds INR93.58 in
reference wear and INR11.82 in inventory adjustment. The net result is unfavorable
under this fixed proxy. W10 and W8 contribute approximately +INR51.76 and
+INR51.72 respectively before averaging across six health cases; the other four
case differences are below INR0.006 and numerically small.

D-R2-minus-D-R5 is +INR71.93, interval [-INR30.08, +INR172.57], and remains
inconclusive. No storage has the lowest observed mean reference score. This does
not establish that storage is uneconomic at an actual Indian site: demand/ToD
charges, billing kVAh/PF, taxes, fixed costs, financing, installation, O&M, backup
and calibrated aging are unmodeled.

The preregistered score sensitivities retain the same actions and rescale only
evaluation wear. D-R2-minus-D-R1 is -INR76.34 at zero reference wear, -INR29.54
at half wear, +INR17.25 at the primary coefficient and +INR110.83 at double wear.
The ranking changes with this unvalidated coefficient. These are fixed-path score
sensitivities, not newly optimized policies or evidence of physical wear reduction.

The common load forecast has RMSE 2.14968 kW, matching its earlier independent
benchmark. Previous-day modeled PV has RMSE 2.05432 modeled kW; it is not a
measured-plant PV forecast accuracy result. Nine of 18 D-R5 paths are idle under
the declared 0.0001 kWh throughput threshold; all 18 no-battery paths are idle
by definition. Other very small case effects require numerical qualification.

## Verification and remaining gates

All 216 software tests and lint checks pass. The one-cell/seed/day smoke passes
before the full matrix. Maximum planner constraint residual is 1.95e-8; maximum
realized balance/SOC residual is 3.56e-15 kWh. Independent review reconstructs all
165,888 actions from their requests/current states and inputs, confirms continuous
SOC, verifies every case score, rederives all wear coefficients from permitted
training cells, checks forecast cutoffs/lag values, and reproduces primary
aggregation and the 10,000-replicate paired block bootstrap.

The [comparison figure](../outputs/india_ci/india_public_controller_v1/comparison/figures/energy_and_reference_score.png)
separates lower energy charges from the reference score. Its layout draft is
retained separately; no model or policy was changed for the figure.

Decision: retain the published research reference. The result supports further
validation of data, wear accounting and controller assumptions, not operational
or investment approval. Measured paired load/PV, actual bill/category/export
evidence, pack/BMS/temperature calibration, sensor mapping, real telemetry timing
and supervised operation remain open. Phase 19 application and phase 20 field
release gates are not closed by this simulation.

The five-page [mathematical-review supplement](../output/pdf/recell_public_controller_mathematical_review.pdf)
explains the input attributes, forecast evaluation, quarter-hour energy equations,
wear/inventory objective and remaining acceptance evidence. It preserves the
original attributes/model PDF. The [integration gate review](integration_gate_review.md)
maps these findings back to every phase and holds the candidate dashboard release.

Artifacts and executed code are preserved under
`outputs/india_ci/india_public_controller_v1/`. New commands refuse existing
completed run directories:

```bash
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/run_public_controller.py --smoke
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/run_public_controller.py
rtk proxy env OMP_NUM_THREADS=1 .venv/bin/python scripts/review_public_controller.py
```
