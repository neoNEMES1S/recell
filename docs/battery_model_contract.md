# Battery-model implementation contract v1

Executed local studies: 5 November 2026. This contract describes the implemented
interfaces. It does not claim full completion of the proposal. The
[results and commands](implementation_results.md) distinguish measured research,
software verification and external requirements.

## Electrical inputs and sampling

`models/ecm.py` takes finite one-dimensional time/current arrays of equal length,
at least two samples and strictly positive time increments. Time is elapsed seconds
within one continuous session. Current is discharge-positive in A. The Stanford
adapter negates its verified native negative-discharge current only at the new
interface; the original parser and capacity/SOH definitions remain unchanged.
Raw wall-clock timezone remains unverified; it is not relabelled UTC for this study.

For each interval `[t[k-1], t[k])`, current is the previous sampled value. The RC
state evolves exactly for that hold. Terminal voltage at `t[k]` includes the
instantaneous ohmic drop from `I[k]`. R0 is positive, R1 is nonnegative, and tau is
positive, finite and in seconds. Rint uses R1 = 0. The general SOC engine requires
positive capacity Ah, initial SOC/polarization and an explicit finite OCV/SOC table;
it rejects leaving that table instead of clipping/extrapolating. Charge efficiency
is a declared input in (0,1], not a measured performance claim.

## Registered local measured experiment

`configs/battery_model_v1.yaml` fixes six cells, RPT-1 calibration, RPT-2 validation
and RPT-3 onward testing, before scored fitting. Each diagnostic yields step-6,
step-10 and step-14 discharge/rest/charge windows. Their preceding low-rate point
supplies the observed current/voltage anchor. Native samples are preserved and
gaps above two seconds reject a window/session. Duplicate exports use the existing
reviewed merge; resets/conflicting clocks or incomplete stimulus are rejected.

The local model holds OCV approximately constant over each short window. Initial
polarization is R1 times the observed preceding current, approximating the long
low-rate discharge as stationary. Only the initial measured voltage anchors a test;
it is excluded from scoring. R0/R1/tau are fitted to the three RPT-1 windows only
using fixed positive bounds and least squares. No later voltage refits parameters.
This is a known-cell chronological test, not an unseen-cell parameter test or a
global equilibrium OCV/SOC validation. Sensor mapping/temperature effects remain
unresolved; local fitted parameters are not pack specifications.

Window RMSE/MAE/bias/max error are in mV. Aggregate means first average windows
within each physical cell and role, then weight six cells equally. The primary
comparison is one-RC minus Rint test-window RMSE. Its six-cell bootstrap is
descriptive. Numerical scientific acceptance limits remain unconfirmed; lower
error alone does not declare the proposal performance objective achieved.

## Health selection and capacity bridge

`configs/model_selection_v1.yaml` registers 12 tree/GRU settings plus three fixed
references, six physical outer folds and seeds 42/43/44. The existing six-feature
target table and first-observed second-life SOH reference remain unchanged.
Training transforms fit only that fold's four training cells. Each fold selects
using mean validation next-checkpoint RMSE across its seeds before test scoring.
Rotating validation cells are not pooled to select a global winner and then
reported as untouched test cells. Familiar six-cell results are development
evidence; no new external cohort is inferred. Explicit CUDA requests fail if
CUDA is unavailable. CPU/auto behavior remains documented separately.

`models/health_ecm.py` requires positive finite predicted SOH and matching reference
capacity, the `first_observed_rpt` reference basis and feature/reference timestamps
available at the forecast origin. Effective capacity is SOH times reference Ah.
Nominal/new-cell normalization needs a separately reviewed conversion. Capacity
predictions do not imply identified resistance changes or a joint voltage
uncertainty interval. Coupling has analytic/cutoff tests; a full measured OCV/SOC
coupled comparison remains unavailable.

## BMS, Simscape and life

`data/bms.py` uses explicit CSV field mappings, physical pack/cell IDs, current
sign, V/A units and a declared timestamp timezone. Arrival timestamps are optional;
without them live availability/timing is unverified. Electrical nonfinite values,
duplicates, reversals, gaps and stale records remain flagged in source order.
`scripts/replay_bms.py` accepts an optional declared electrical case with matched
pack/cell identity and initial state. It does not bridge invalid/gapped streams or
fabricate diagnostic features to produce a health forecast. The checked 60-row
fixture is synthetic. Offline batch timing is not end-to-end live latency.

`scripts/export_simscape_case.py` exports numeric CSV/JSON/MAT plus source hashes
for G1/RPT-3/step-10. The Simscape sources target R2025a+ and the Foundation
electrical library. They have not been compiled/executed; see
[the source handoff](../simscape/README.md). Only execution on an actual licensed
installation can establish solver convergence and Python/Simscape agreement.

SOL is unconfirmed. `configs/life_v1.yaml` therefore runs inventory only with no
invented threshold, lifetime labels or fit. Tested event primitives retain left,
interval and right censoring. A conditional linear-to-threshold baseline is
implemented, but not a validated lifetime or uncertainty model. The current
histories' minimum relative SOH is not an end-of-life criterion.

## Artifact and release contract

Each new run uses a fresh directory, sealed inputs/config hashes and completed
artifact hashes; available executed Python source snapshots are retained. A
running/failed run is not publishable. The independent review reconstructs pulse
responses through history convolution and replays every saved health model,
validation selection, transform and reported forecast. The dashboard verifies
completion/review links and exports only saved numeric evidence. It does not fit
models or control a battery. Measured, modeled and synthetic records stay distinct.

No actual DGX, real BMS, full SOC/thermal, lifetime, independent-cohort or Indian
field/billing validation is claimed. Existing phase-19/20 evidence gates remain.
