# Dataset integration: evidence and remaining gates

Review date: 30 October 2026. Governing scope:
[dataset integration plan, phases 14-20](dataset_integration_plan.md).
The evidence-dependent goal is **paused and not complete**. Completed research
comparisons are evidence for their declared questions; they do not waive
calendar-application or site gates.

The [5 November proposal alignment plan](proposal_alignment_plan.md) adds planned
phases 21-28 for missing Simscape/dynamic-model, DGX, BMS and defined SOL/life
requirements. These are separate proposal deliverables; they neither reopen failed
source gates nor close the calendar/site requirements reviewed here. No execution
goal is resumed by this planning addendum.

The subsequent [Codex implementation handoff](codex_implementation_plan.md) replaces
calendar scheduling with earliest feasible execution. Independent code, audit and
interface packages can finish while external gates wait; their software completion
does not waive measured validation, actual Simscape/DGX or real BMS evidence.

Execution update, 5-6 November: [local implementation results](implementation_results.md)
now include a measured same-cell local pulse model, bounded CPU selection and
tested capacity/BMS/life interfaces. The new dashboard and mathematical review
display those scoped results. This does not supply the missing global OCV/SOC,
temperature, independent cohort, SOL, actual BMS/Simscape/DGX or field evidence.

## Decision supported by current evidence

Proceed to a bounded data-access and calibration pilot. Do not present this as
approval for autonomous operation, a pack purchase or guaranteed savings.
No candidate model or controller is promoted for operation. The user-requested
31 October dashboard integration displays the completed studies as separate
research views, with the original reference retained and validation limits visible.
An actual site's success criteria must be agreed and registered before its evaluation;
this review invents no commercial acceptance threshold from already observed results.

## Requirement review

Paths below are relative to the repository root. Reports explain each claim's scope;
run manifests and independently checked ledgers are the underlying evidence.

| Plan requirement | Evidence inspected | Status / interpretation |
| --- | --- | --- |
| 14: preserve reference inputs, results, code and working-tree context | `outputs/transfer/reference_20261027/{manifest.json,reference.tar.gz}`; manifest has 610 files, Git revision/status and archived computational source | Complete reference freeze. The notebook entry is explanatory text, not a notebook hash manifest. |
| 14: historical processed/results/dashboard preservation | The 30 October review verified all 539 frozen paths; the immutable reference archive remains. The 31 October user-requested UI update preserves the old dashboard under `outputs/dashboard/reference_20261023/` and retains all original reference payload values | Historical numerical evidence retained; current frontend assets intentionally change. Do not claim that the updated frontend still matches its historical asset hashes. |
| 14: preregister primary/secondary endpoints, folds, seeds, context and target origins | `configs/transfer_protocol_v2.yaml`; separate sealed `configs/transfer_protocol_v3.yaml`; registrations under the corresponding output roots | Complete registration. v3 explicitly discloses availability-based amendment; it is not v2 completion. |
| 15: selective source acquisition, units/protocol/sign/clock/duplicate audit | `docs/transfer_source_audit.md`; `outputs/transfer/source_audit/`; 266 selected inputs plus 32 restart endpoints verified | Selective audit complete; 71 diagnostics pass, 52 cycling batches pass and 13 fail. No claim that the full raw release is acquired. |
| 15: physical identities, chemistry and nominal conventions | `configs/cell_registry.yaml`; publication mapping and protocol audit | Six linked M50T identities preserved across life stages; 4.85 Ah source nominal distinguished from historical 5 Ah scenario. |
| 15: one capacity/exposure trajectory and other-cell availability | G1 reviewed full trajectory; extra-cell availability audit; source compatibility report | Complete selective evidence. W5 is source validation only; W3/W4/W7 are not silently assumed usable. |
| 16: compatible causal features and quality gate | v2 reconstruction reports; v3 `feature_gate.json`; `data/processed/transfer/ev_to_second_life_v3/{source_features.csv,source_labels.csv,feature_provenance.json}` | Original full-history v2 gate fails. v3 passes only its declared verified-prefix gate: 34 feature rows, 60 labels; future labels never fill missing exposure inputs. |
| 16: physical disjointness, stage boundaries and target-only transforms | `tests/test_prefix_transfer.py`, `tests/test_ev_prefix_sequences.py`; v3 `comparison/folds.json`, saved scalers/fit provenance | v3 passes its declared split contract. Source gradients exclude target test/validation first life; W5 contributes neither gradients nor scaler statistics. All six target cells and 87 origins retained. |
| 17: encoder-only transfer, fresh head/optimizer, ordered quantiles and smoke | `src/second_life_battery/training/transfer.py`; `tests/test_transfer_initialization.py`; v3 accepted `smoke/` and source/target fit artifacts | Complete for v3. Failed native-library smoke is preserved separately; accepted runs pin `OMP_NUM_THREADS=1`. v2 is not fitted. |
| 18: matched R1-R6 matrix without context-dependent refitting | v3 `comparison/{completion.json,predictions.csv,fold_metrics.csv}` and saved fits | Complete for v3: 15,660 predictions, six folds, three seeds, five context fractions and two target horizons. R0 is retained historical context, not a matched transfer arm. |
| 18: calibration, paired uncertainty, negative cases, range/spacing and compute | v3 `comparison/report/` and `comparison/review/verification.json`; `docs/transfer_prefix_comparison.md` | All saved predictions independently replayed; primary metrics/bootstrap reconstructed. Small directional GRU effect, G1/W8 worsen; XGBoost lowest mean. Quantiles are not well calibrated. |
| 19: calendar identities/chemistry/storage metadata and disjoint study | `docs/calendar_source_audit.md`; `outputs/calendar/calendar_validation_v1/{validation,analysis}/` | Separate registered comparison complete: 218 cells, eight held-out types; nonphysical predictions retained. No M50T cells in this source. |
| 19: resolve target temperature assignment before application | `outputs/calendar/target_temperature_audit_v1/`; `docs/target_temperature_audit.md` | Open. All 542 workbooks hash-checked, but auxiliary-channel presence does not establish physical probe mapping or storage temperature. |
| 19: M50T calibration, loss interpretation and intended-use rights | Calendar report; source license/metadata review | Open. Storage plus diagnostic loss is not pure calendar loss; no identifiable additive split from mixed cycling/calendar target loss, no M50T calibration, intended-use clarification remains. Do not add a calendar term to dispatch. |
| 20: independent Indian interval demand and measured paired PV | I-BLEND demand receipts and registered 91-day load ledger; NASA resource; Jaipur PV audit | Partial. Demand is measured; solar is a regional modeled scenario. Jaipur's daily workbook cannot supply interval PV. Delhi gross/net-meter topology is not verified. |
| 20: causal information and realistic forecast errors | Frozen load blend; controller profile forecast ledger and lag cutoffs | Offline implementation complete; load and modeled-PV errors reported. Operational weather forecasts, reporting delay, actual PV accuracy and within-quarter control bandwidth are unvalidated. |
| 20: matched controller and consistent wear accounting | `configs/india_public_controller_v1.yaml`; controller `comparison/` and `comparison/review/verification.json` | Conditional public comparison complete. Six policies, 18 hypothetical cases, 16 days; all 165,888 actions and 108 case scores independently reconstructed. This is one demand window, not 18 independent sites. |
| 20: applicable tariff, ToD, demand, export and actual bill | `docs/india_electrical_semantics.md`; pinned historical DERC order and supply-code review | Open. No customer category/contract, applicable billing-cycle evidence, direct kVAh counter or bill reconciliation. INR10/kWh is illustrative; zero export is an assumed controller constraint. |
| 20: pack specification/quotation, BMS/SOC/temperature and constraints | Declared generic 40 kWh/20 kW pack in controller protocol | Open. No site pack or supplier quotation, measured efficiency/usable capacity, probe assignment or verified operating limits. Lab-cell SOH is a hypothetical scenario input, not plant calibration. |
| 20: supervised closed-loop operation and bounded pilot decision | Offline recourse replay only | Open. No live actuation, operator trial or measured aging/savings. Backup/outage requirements require a separate site specification. |
| 20: conditional dashboard release and mathematical review | User-requested research views include transfer, calendar, Indian demand/modeled PV and controller results, unchanged review PDFs and checked source/review links. Original proxy demonstration remains separately labelled | Research review is available; operational candidate promotion still requires site, billing, pack and supervised field evidence. Displaying the studies does not close those gates. |

The independent controller comparison's transfer-minus-scratch score is
**+INR17.25** per 16-day scenario, descriptive interval [INR0.84, INR32.90].
Lower energy charges are outweighed by the common wear proxy and inventory
adjustment. Changing only the evaluation wear coefficient reverses the ranking.
This is useful evidence against claiming that the small SOH error improvement
already establishes operating value. It is not proof that Indian storage is
uneconomic. See the complete [controller review](india_controller_review.md).

## Minimum evidence to move the open gates

1. **Acquire a real paired site record.** Preserve load/PV/battery meter topology,
   raw units/signs, native timezone and interval meaning, quality flags, reporting
   delays and reuse terms. Confirm gross load versus net grid flow before balancing
   energy. A different site's PV trace cannot validate the Delhi building's PV.
2. **Establish the connection and bill.** Obtain a redacted bill and contract,
   category/voltage, applicable tariff and amendments, billing interval, import/
   export agreement and apparent-energy channels. Reconcile a complete billing
   period before publishing savings. Keep energy, demand, tax and inventory/wear
   accounting separate.
3. **Calibrate the actual pack.** Obtain equipment/chemistry/second-life identity,
   quotation, measured usable capacity and efficiency, BMS channels and sensor map,
   operational limits and operator-approved constraints. Establish what any loss
   model measures before combining cycling and calendar contributions.
4. **Register and run an independent replay.** Seal site/time split, predictors,
   causal cutoffs, forecast availability, policy arms, objectives, wear assumptions,
   uncertainty and acceptance criteria before scoring. Include failure cases and
   reference policies. Current familiar public-window results cannot select these.
5. **Validate operation before release.** Reconcile telemetry/action timing and
   physical constraints, then perform supervised operation under the site's agreed
   constraints. Evaluate billed costs and observed health separately; a short pilot
   may not identify lifetime effects. Release only claims supported by that evidence.

## Data-access status

The [Coimbatore request](india_ci_data_request.md) and
[Stanford export/temperature clarification](source_correction_request.md) were
sent on 30 October after the user's explicit authorization. Exact Gmail sent
records were read back: approved recipients, subjects and bodies, no attachments
or CC/BCC. This does not establish recipient delivery, replies or data access.
The [30 October public-search follow-up](india_public_data_audit.md#public-search-follow-up-30-october-2026)
rechecks the request-only route and rejects newly reviewed nonmatching records as
substitutes for the missing site evidence. A bounded search does not prove that
no suitable public source exists. No source corrections, sensor assignments,
site records or new reuse rights are inferred from sending these requests.

Current calculation/artifact rechecks are recorded under
`outputs/integration/gate_review_20261030/`. The new mathematical supplement is
`output/pdf/recell_public_controller_mathematical_review.pdf`; the original
attributes/model, transfer and calendar PDFs are preserved.
