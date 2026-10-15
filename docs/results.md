# Reference research results

Reference artifacts inspected on 2026-10-15. This is a six-cell research prototype;
implementation completion does not establish broad generalization or deployment readiness.
See [methods](methods.md) for the exact protocol and [README](../README.md) to reproduce.

## Dataset and forecasting

There are 111 diagnostic checkpoints across six cells. The reference LOBO experiment
contains 3,132 predictions: six models, three seeds and two future-checkpoint horizons.
The limited-history experiment contains 15,660 predictions over five context fractions.
All fractions retain the same origins and labels. Preprocessing and wear calibration
exclude the held-out battery; validation uses another battery.

Values below average seeds within a cell, then average across cells; SD is across cells.
SOH is a fraction of first observed second-life RPT capacity. The interval target is 80%.

| Model | SOH MAE | SOH RMSE | RMSE SD | P10–P90 coverage |
| --- | ---: | ---: | ---: | ---: |
| xgboost | 0.001514 | 0.002146 | 0.000804 | — |
| linear | 0.001994 | 0.002671 | 0.000927 | — |
| pgp_gru | 0.002001 | 0.002739 | 0.001028 | 86.4% |
| quantile_gru | 0.002096 | 0.002838 | 0.001188 | 84.2% |
| gru | 0.002178 | 0.003018 | 0.001293 | — |
| persistence | 0.003777 | 0.004393 | 0.000720 | — |

XGBoost has the lowest aggregate RMSE. PGP-GRU improves on persistence and vanilla GRU
in this run, but has higher mean error than XGBoost and ridge linear regression. The
physics-penalty ablation has slightly higher mean RMSE; its paired six-cell bootstrap
interval overlaps zero. Do not claim that physics guidance universally outperforms
baselines. PGP-GRU's interval coverage is above nominal, and calibration remains imperfect.

Cell-level metrics, horizon breakdowns, bootstrap comparisons, validation feature
importance and largest errors are in `outputs/lobo/` and `outputs/analysis/`.
Limited-history curves in `outputs/analysis/limited_history.*` measure shortened
inference context while retaining the original SOH reference and exposure metadata.
No measured end-of-life outcome or validated RUL forecast is claimed.

## Solar-storage replay

The replay uses 720 hours of June 2016 OPSD/CoSSMic residential3 meter data, coupled
as an operating scenario to the latest held-out one-checkpoint health forecasts
(seed 42). The selected meter interval has zero upstream interpolation flags;
this is not an independent raw-sensor quality audit. All six cell cases share the
same household replay and are not six independent household trials.

These are monthly scenario means in EUR, not realized savings. Negative electricity
cost is net export revenue. Wear cost is a linear forecast/exposure proxy with assumed
pack replacement cost. A full-horizon optimizer has perfect load/solar foresight.

| Scenario | Net electricity EUR | Estimated wear EUR | Sum EUR | Equivalent full cycles |
| --- | ---: | ---: | ---: | ---: |
| A_no_battery | 33.19 | 0.00 | 33.19 | 0.00 |
| B_conventional | -6.81 | 19.39 | 12.58 | 18.99 |
| C_second_life | -5.00 | 18.13 | 13.13 | 17.81 |
| D_conservative | 29.40 | 3.63 | 33.03 | 1.29 |
| D_degradation_aware | 0.12 | 11.54 | 11.66 | 14.46 |

C and median D use identical health and wear assumptions. At wear multiplier 1, D
reduces modeled electricity-plus-wear cost and cycles at the expense of higher net
electricity cost. The conservative P10 case changes both assumed health and wear;
it is a sensitivity case, not a direct policy comparison. The conventional battery
uses full nominal capacity and the same wear proxy solely as a controlled comparison.

All 42 schedules passed numerical power, SOC and energy-balance checks; the maximum
constraint residual was below 1e-8. Sensitivity plots cover wear multipliers 0, 0.5,
1 and 2. Forecast choices, conversion details, config, package versions and input
hashes are saved under `outputs/dispatch/`. Carbon results are absent because no
carbon-intensity series was supplied.

## Limits and next scientific work

- Only six independent cells and one household replay; overlapping forecast windows
  do not create additional independent batteries.
- RPT target integration and pulse-resistance proxies are protocol dependent; raw
  timestamp timezone and temperature-sensor placement remain unverified.
- Multi-cell/conflicting EIS records are excluded, not assigned to a guessed cell.
- Tariffs, pack size/cost and linear wear conversion are scenario assumptions.
  Health is held constant during dispatch; thermal effects and calendar aging are absent.
- Hardware validation, pack-level aging calibration, solar/load forecast errors and
  closed-loop control remain future research. These results do not establish lifetime
  extension, real-world savings, or a deployable battery controller.
