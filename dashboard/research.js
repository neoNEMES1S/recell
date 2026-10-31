/* Completed research studies, deliberately separate from the historical reference. */
(function (root) {
  "use strict";
  const studies = {transfer: "First-life transfer", calendar: "Calendar aging", india: "Indian demand & PV", controller: "Controller comparison"};
  const arms = {R1: "Scratch PGP-GRU", R2: "Transfer PGP-GRU", R3: "Scratch quantile GRU", R4: "Transfer quantile GRU", R5: "XGBoost", R6: "Persistence"};
  const policies = {A_no_battery: "A · No battery", B_greedy: "B · Greedy", C_energy: "C · Energy-only plan", D_R1: "D-R1 · Scratch-GRU wear", D_R2: "D-R2 · Transfer-GRU wear", D_R5: "D-R5 · XGBoost wear"};
  const loadNames = {weekly: "Previous week", blend25: "25% day / 75% week", blend50: "50% day / 50% week · frozen choice", blend75: "75% day / 25% week", previous_day: "Previous day"};
  const cleanCell = s => s.replace("secl_m50t_", "");
  const clock = h => `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.round(h * 60) % 60).padStart(2, "0")}`;
  const signed = (u, v, digits = 3) => `${v > 0 ? "+" : ""}${u.fmt(v, digits)}`;
  const money = (u, v) => `${v > 0 ? "+" : ""}${u.rupees(v)}`;
  const report = (u, path, label) => `<a class="button secondary" href="${u.esc(path)}" target="_blank" rel="noopener">${label} ↗</a>`;
  const quarterOptions = {min: 0, xTicks: [0, 6, 12, 18, 23.75], xFormat: clock, xlabel: "Local time · IST (UTC+05:30)"};

  function overview(D, u) {
    const r = D.extensions;
    if (!r) return "";
    return u.panel("Research extensions are ready to review", "Completed comparisons · field validation remains open", `
      <div class="research-cards">
        <a href="#research/transfer"><strong>First-life transfer</strong><span>Small GRU error improvement; XGBoost has the lowest observed mean.</span></a>
        <a href="#research/calendar"><strong>Calendar aging</strong><span>Average error improves, with ${r.calendar.nonphysical_predictions} impossible negative predictions retained.</span></a>
        <a href="#research/india"><strong>Indian demand & modeled PV</strong><span>Measured Delhi load; solar generation remains an explicit scenario.</span></a>
        <a href="#research/controller"><strong>Better forecasts, different decisions</strong><span>Transfer minus scratch score: ${money(u, r.controller.primary.difference_inr)}. Higher is worse under this proxy.</span></a>
      </div><p class="chart-caption mt">The original six-cell / German-household demonstration below is retained as a reference. These newer studies have separate datasets, assumptions and objectives; their cost figures must not be combined.</p><div class="mt">${report(u, r.reports.method, "Open dataset attributes and model review PDF")}</div>`);
  }

  function transfer(D, u, s) {
    const r = D.extensions.transfer;
    const chosen = r.summary.filter(x => x.history_fraction === s.researchFraction && x.horizon === s.researchHorizon).sort((a, b) => a.rmse_mean - b.rmse_mean);
    const r2 = chosen.find(x => x.model === "R2");
    const primary = r.paired.find(x => x.comparison === "R2 minus R1");
    const cells = [...new Set(r.per_cell.map(x => x.cell_id))].sort();
    const series = ["R1", "R2", "R5"].map((model, i) => ({name: arms[model], color: ["#527d9a", "#1a3c2b", "#a97728"][i], points: r.summary.filter(x => x.model === model && x.horizon === s.researchHorizon).map(x => ({x: x.history_fraction * 100, y: x.rmse_mean * 100})).sort((a, b) => a.x - b.x)}));
    return u.title("Research / First-life transfer", "Can earlier battery life help?", "Pretrain on verified first-life histories, then test future second-life health on a physically held-out battery. This v3 study preserves the original six test cells; it is not a new independent cohort.")
      + u.note("Registered primary result · 10% history, next checkpoint", `Transfer minus scratch RMSE is ${signed(u, primary.rmse_difference * 100, 6)} SOH percentage points; descriptive six-cell 95% interval [${u.fmt(primary.bootstrap_low * 100, 6)}, ${u.fmt(primary.bootstrap_high * 100, 6)}]. Lower favors transfer. The improvement is small; G1 and W8 worsen. XGBoost has the lowest observed mean error.`, true)
      + `<div class="filters">${u.select("researchFraction", "Retained history", [0.1, .25, .5, .75, 1].map(v => [v, `${v * 100}%`]), s.researchFraction)}${u.select("researchHorizon", "Forecast horizon", [[1, "Next checkpoint"], [2, "Second checkpoint"]], s.researchHorizon)}<p class="filter-note">Selectors inspect saved results. They do not tune the study or change its registered primary result.</p></div>`
      + `<div class="grid-main"><div class="stack">${u.panel("Matched model comparison", "Same features, folds and evaluated origins · errors in SOH percentage points", u.bars(chosen.map(x => ({label: arms[x.model], value: x.rmse_mean * 100}))) + u.table(["Arm", "MAE (pp)", "RMSE (pp)", "80% coverage", "Width (pp)"], chosen.map(x => [arms[x.model], u.fmt(x.mae_mean * 100, 4), u.fmt(x.rmse_mean * 100, 4), u.percent(x.coverage_80_mean), x.interval_width_mean === null ? "—" : u.fmt(x.interval_width_mean * 100, 3)])))}
      ${u.panel("How much history is enough?", "Models train once per fold/seed; only inference history changes", u.chart(series, {title: "Transfer, scratch and XGBoost across retained histories", xTicks: [10, 25, 50, 75, 100], xFormat: v => `${v}%`, xlabel: "Retained past checkpoint history", ylabel: "Equal-cell SOH RMSE (percentage points)"}))}</div>
      <div class="stack">${u.panel("What the model receives", "Three shared predictors; no joined life-stage sequence", `<div class="formula">x = [past SOH, elapsed stage days, cumulative stage Ah]\nSOH = capacity / first accepted stage capacity</div><p>Only target-training batteries' eligible first-life prefixes supply gradients. The target test and validation batteries' first lives are excluded from source gradients. W5 supplies independent source validation only.</p><p>Only 3–18 source examples are available per fold. The encoder transfers; the output head and optimizer are reset. Future capacity labels never create missing exposure inputs.</p>`)}
      ${u.note("Ordered intervals are not calibrated guarantees", `At this selection, transfer coverage is ${u.percent(r2.coverage_80_mean)} for an 80% target; width ${u.fmt(r2.interval_width_mean * 100, 3)} pp. Empirical P10 / P50 / P90 frequencies are ${u.percent(r2.empirical_q10_mean)} / ${u.percent(r2.empirical_q50_mean)} / ${u.percent(r2.empirical_q90_mean)}. Read coverage and width together.`)}
      ${u.note("Full-history data gate stays closed", "The original v2 protocol has 13 rejected cycling batches and was not fitted. v3 is a separately registered verified-prefix amendment. No source defect is repaired by displaying its results.")}
      ${report(u, D.extensions.reports.transfer, "Open transfer review PDF")}</div></div>`
      + `<div class="spaced">${u.panel("Every held-out cell stays visible", "Seeds averaged within each cell · current selected context/horizon", u.table(["Cell", "Scratch RMSE", "Transfer RMSE", "XGBoost RMSE", "Transfer minus scratch (pp)"], cells.map(cell => {
        const take = model => r.per_cell.find(x => x.cell_id === cell && x.model === model && x.history_fraction === s.researchFraction && x.horizon === s.researchHorizon);
        const a = take("R1"), b = take("R2"), c = take("R5");
        return [cleanCell(cell), u.fmt(a.rmse * 100, 4), u.fmt(b.rmse * 100, 4), u.fmt(c.rmse * 100, 4), `${signed(u, (b.rmse - a.rmse) * 100, 5)} · ${b.rmse > a.rmse ? "higher error" : "lower error"}`];
      })))}</div><details class="spaced"><summary>Inspect all registered primary contrasts</summary>${u.table(["Contrast", "RMSE difference (pp)", "Descriptive 95% interval (pp)"], r.paired.map(x => [u.esc(x.comparison), signed(u, x.rmse_difference * 100, 6), `[${u.fmt(x.bootstrap_low * 100, 6)}, ${u.fmt(x.bootstrap_high * 100, 6)}]`]))}<p class="chart-caption">Fixed 10% context / next-checkpoint contrasts; six-cell bootstrap. An interval spanning zero is inconclusive. These are different features from the original six-feature reference.</p></details>`;
  }

  function calendar(D, u, s) {
    const r = D.extensions.calendar;
    const cases = [...new Set(r.summary.map(x => `${x.variant}/${x.regime}`))];
    const key = cases.includes(s.calendarCase) ? s.calendarCase : "primary/full";
    const [variant, regime] = key.split("/");
    const labels = {C0: "Constant health", C1: "Age only", C2: "Age + temperature + SOC"};
    const names = key => `${key.startsWith("primary") ? "Primary cohort" : "Exclude swap-note cells"} · ${key.endsWith("early180") ? "train ≤180 days, test later" : "full ages"}`;
    const selected = r.summary.filter(x => x.variant === variant && x.regime === regime);
    const types = r.types.filter(x => x.variant === variant && x.regime === regime);
    const typeNames = [...new Set(types.map(x => x.base_type))].sort();
    return u.title("Research / Calendar aging", "Time, temperature and stored charge.", "A separate registered storage-aging study tests unseen cell types. These are different batteries and protocols from the M50T second-life task; no calendar term is added to storage wear.")
      + `<div class="kpis">${u.kpi("Longitudinal cohort", "218", "cells", "Eight held-out base cell types; no LG M50T")}${u.kpi("Nonphysical predictions retained", r.nonphysical_predictions, "", "Negative SOH from the primary conditioned model")}${u.kpi("Worst absolute error", u.fmt(r.worst_absolute_error * 100, 2), "SOH pp", "A material failure, included in evaluation")}</div>`
      + u.note("Average improvement does not establish application readiness", `Primary conditioned-minus-age-only RMSE is ${signed(u, r.primary.rmse_difference * 100, 2)} pp; descriptive eight-type 95% interval [${u.fmt(r.primary.bootstrap_low_95 * 100, 2)}, ${u.fmt(r.primary.bootstrap_high_95 * 100, 2)}]. Failures prevent automatic adoption.`, true)
      + `<div class="filters">${u.select("calendarCase", "Registered comparison", cases.map(x => [x, names(x)]), key)}<p class="filter-note">Predeclared sensitivity/extrapolation comparisons, not refits or test-time choices.</p></div>
      <div class="two-col">${u.panel("Three standalone models", "Each held-out type gets equal final weight", u.bars(selected.map(x => ({label: labels[x.model], value: x.rmse * 100}))) + u.table(["Model", "RMSE (pp)", "MAE (pp)"], selected.map(x => [labels[x.model], u.fmt(x.rmse * 100, 2), u.fmt(x.mae * 100, 2)])))}
      ${u.panel("Why this is kept separate", "Storage experiments include periodic diagnostic cycling", `<p>The accepted pool contains 9,481 checkpoints from 232 available cell summaries. The predictive comparison uses 218 cells with future observations.</p><p>Storage settings span 24, 45, 60 and 85 °C, at 50% or 100% SOC. The NMC cells are Sony VTC6, not M50T.</p><p>Pure calendar and diagnostic-cycling losses are not separately identified. Adding this fitted curve to the current mixed-aging wear proxy would risk double-counting.</p><p>M50T calibration, physical temperature-probe mapping, storage conditions and intended-use clarification remain open.</p><div class="mt">${report(u, D.extensions.reports.calendar, "Open calendar review PDF")}</div>`)}</div>
      <div class="spaced">${u.panel("Performance varies by cell type", names(key), u.table(["Held-out type", "Constant RMSE", "Age-only RMSE", "Conditioned RMSE"], typeNames.map(name => [u.esc(name), ...["C0", "C1", "C2"].map(model => u.fmt(types.find(x => x.base_type === name && x.model === model).rmse * 100, 2))]), "All errors are SOH percentage points; a lower average can hide a bad type."))}</div>
      <div class="spaced">${u.panel("Impossible values are not clipped away", "Primary C2 failures · 85 °C and 100% storage SOC", `<p>${r.nonphysical_predictions} negative predictions occur across four K2 Energy LFP cells. They remain in reported scores. These findings are fixed to the primary study, independent of the selector above.</p><details class="mt"><summary>Inspect all ${r.nonphysical_predictions} failures</summary>${u.table(["Cell", "Age (days)", "Measured SOH (%)", "Predicted SOH (%)"], r.failures.map(x => [u.esc(x.physical_cell_id.replace("joule_calendar_", "")), u.fmt(x.elapsed_days, 0), u.fmt(x.soh * 100, 2), u.fmt(x.prediction * 100, 3)]))}</details>`)}</div>`;
  }

  function india(D, u, s) {
    const r = D.extensions.india;
    const dates = [...new Set(r.profiles.map(x => x.date_ist))];
    const day = dates.includes(s.siteDay) ? s.siteDay : dates[0];
    const model = r.predictions[s.siteModel] ? s.siteModel : r.selection.selected_model;
    const offset = r.profiles.findIndex(x => x.date_ist === day);
    const profile = r.profiles.slice(offset, offset + 96);
    const prediction = r.predictions[model].slice(offset, offset + 96);
    const chosen = r.test.find(x => x.model === r.selection.selected_model);
    const weekly = r.test.find(x => x.model === "weekly");
    const daily = r.daily.find(x => x.model === model && x.date_ist === day);
    return u.title("Research / Indian demand & PV", "Indian demand is measured. PV is modeled.", "The IIIT Delhi academic-building benchmark supplies 91 complete days of active demand. A separately declared NASA-resource conversion supplies hypothetical PV, with 60-minute source resolution retained.")
      + `<div class="kpis">${u.kpi("Frozen load blend test RMSE", u.fmt(chosen.rmse_kw, 3), "kW", `Previous-week baseline: ${u.fmt(weekly.rmse_kw, 3)} kW`)}${u.kpi("Test window", "16", "days", "60 training days + 15 validation days precede it")}${u.kpi("91-day PV scenario", u.fmt(r.pv.modeled_pv_total_ac_kwh, 0), "kWh", "Modeled AC output; not an inverter measurement")}</div>`
      + u.note("Choose on validation, inspect on test", "Five daily/weekly blends were fixed before scoring. The 50/50 blend was chosen on 15 validation days and frozen before 16 test days. At each midnight IST, only completed past quarters are available; reporting delay is assumed zero.", true)
      + u.panel("Forecast comparison", "Same 16 test days · selected model remains frozen", u.table(["Forecaster", "Validation RMSE (kW)", "Test RMSE (kW)", "Peak timing error (min)"], r.test.map(x => [loadNames[x.model], u.fmt(r.validation.find(v => v.model === x.model).rmse_kw, 3), u.fmt(x.rmse_kw, 3), u.fmt(x.mean_peak_time_absolute_error_minutes, 1)])))
      + `<div class="filters">${u.select("siteDay", "Test day (IST)", dates.map(d => [d, d]), day)}${u.select("siteModel", "Inspect saved forecast", Object.keys(r.predictions).map(m => [m, loadNames[m]]), model)}<p class="filter-note">Dates and quarter-hour clocks are in IST. Selecting a baseline does not replace the registered forecaster.</p></div>
      <div class="spaced">${u.panel("Demand forecast beside the meter", `${day} · ${loadNames[model]} · daily RMSE ${u.fmt(daily.rmse_kw, 3)} kW`, u.chart([{name: "Measured active demand", color: "#1a3c2b", points: profile.map(x => ({x: x.hour_ist, y: x.load_kw}))}, {name: "Day-ahead forecast", color: "#527d9a", dashed: true, points: profile.map((x, i) => ({x: x.hour_ist, y: prediction[i]}))}], {...quarterOptions, title: "Measured Delhi demand and saved day-ahead forecast", ylabel: "15-minute mean active power (kW)"}) + `<p class="chart-caption">This day's energy error is ${signed(u, daily.energy_error_kwh, 2)} kWh and peak-timing error is ${u.fmt(daily.peak_time_absolute_error_minutes, 0)} minutes. These peaks are not metered billing maximum demand.</p>`)}</div>
      <div class="spaced">${u.note("A low peak-magnitude error can hide the wrong time", "On 7 December the selected blend puts the peak at 12:45 IST, while the meter peaks at 22:15: 570 minutes apart. Mean test peak-timing error is about 122 minutes. Better RMSE alone does not establish peak-shaving or billed savings.")}</div>
      <div class="spaced">${u.panel("Two modeled PV profiles, not two meters", `${day} · 40 kWp DC / 32 kW AC · horizontal reference-temperature scenario`, u.chart([{name: "Historical-resource PV scenario", color: "#1a3c2b", points: profile.map(x => ({x: x.hour_ist, y: x.modeled_pv_kw}))}, {name: "Previous-day modeled-PV forecast", color: "#a97728", dashed: true, points: profile.map(x => ({x: x.hour_ist, y: x.forecast_pv_kw}))}], {...quarterOptions, title: "Modeled PV and previous-day modeled-PV persistence", ylabel: "Modeled AC power (kW); hourly resource distributed uniformly over quarters"}) + `<div class="formula">Pac = min(32, 40 × 0.96 × GHImean / 1000) kW\nQuarter energy = Pac × 0.25 h</div><p>PV cell temperature is fixed at 25 °C. Tilt, shading, soiling, thermal effects, outages and part-load efficiency are not calibrated. Ambient weather is not PV-cell or battery temperature.</p>`)}</div>
      <div class="two-col spaced">${u.note("The factory source was audited, not substituted", "The Jaipur factory workbook contains daily records, undeclared output units and 27 days with missing inverter values behind formula-derived zero totals. It cannot supply this benchmark's interval PV, and was not attached to the unrelated Delhi meter.", true)}
      ${u.note("Active-power data do not establish a customer bill", "Actual connection category, tariff amendments, ToD/demand charges, kVAh/PF and export terms remain unresolved. No PF=1 filling, billed-energy reconstruction or annualized savings is presented. Gross-load versus net-meter topology also needs confirmation.")}</div>
      <details class="spaced"><summary>Inspect this day's displayed values</summary>${u.table(["IST", "Meter load (kW)", "Load forecast (kW)", "Modeled PV (kW)", "PV forecast (modeled kW)"], profile.map((x, i) => [clock(x.hour_ist), u.fmt(x.load_kw, 3), u.fmt(prediction[i], 3), u.fmt(x.modeled_pv_kw, 3), u.fmt(x.forecast_pv_kw, 3)]))}</details>`;
  }

  function controller(D, u, s) {
    const r = D.extensions.controller, site = D.extensions.india;
    const dates = [...new Set(site.profiles.map(x => x.date_ist))];
    const cells = [...new Set(r.schedules.series.map(x => x.cell_id))].sort();
    const cell = cells.includes(s.controllerCell) ? s.controllerCell : cells[0];
    const policy = policies[s.controllerPolicy] ? s.controllerPolicy : "D_R2";
    const day = dates.includes(s.controllerDay) ? s.controllerDay : dates[0];
    const selected = r.schedules.series.find(x => x.cell_id === cell && x.policy === policy);
    const offset = site.profiles.findIndex(x => x.date_ist === day);
    const profile = site.profiles.slice(offset, offset + 96);
    const path = selected.rows.slice(offset, offset + 96).map(row => Object.fromEntries(r.schedules.columns.map((key, i) => [key, row[i]])));
    const get = id => r.summary.find(x => x.policy === id);
    const a = get("D_R1"), b = get("D_R2");
    const scales = [...new Set(r.sensitivities.map(x => x.reference_wear_multiplier))].sort((x, y) => x - y);
    const primaryDiff = r.differences.filter(x => x.candidate === "D_R2" && x.reference === "D_R1");
    return u.title("Research / Controller comparison", "Did better health forecasts improve decisions?", "This registered offline study answers a separate question from forecasting accuracy. Every policy in a case shares physical capacity, site profiles, efficiencies and recourse. Lab battery states are hypothetical inputs, not a battery installed in Delhi in 2014.")
      + `<div class="kpis">${u.kpi("Transfer minus scratch score", money(u, r.primary.difference_inr), "/ 16 days", "Higher is worse under the common wear/inventory proxy")}${u.kpi("Independent site window", "1", "site / 16 days", "Six hypothetical health cases × three model seeds")}${u.kpi("Reviewed realized actions", u.fmt(r.realized_rows, 0), "", "Repeated cases are not independent sites")}</div>`
      + u.note("The primary controller result is unfavorable", `Transfer-derived planning has a ${money(u, r.primary.difference_inr)} higher mean reference score than scratch-derived planning. Descriptive paired four-day-block 95% interval: [${u.rupees(r.primary.descriptive_low_95_inr)}, ${u.rupees(r.primary.descriptive_high_95_inr)}]. The result supports more data/calibration work, not operating or investment approval.`)
      + `<div class="spaced">${u.panel("Follow the complete score", "Mean scenario INR / 16 days · average seeds within cells, then six cells equally", u.table(["Policy", "Energy charge", "Common wear", "Inventory", "Reference score", "EFC"], r.summary.map(x => [policies[x.policy], u.rupees(x.grid_energy_charge_inr), u.rupees(x.reference_wear_cost_inr), u.rupees(x.inventory_adjustment_inr), u.rupees(x.reference_score_inr), u.fmt(x.equivalent_full_cycles, 3)]), "Inventory adjustments can be negative credits; they are not utility payments.") + `<p class="chart-caption">The no-storage policy has the lowest observed mean score in this particular proxy scenario. Demand/ToD charges, the actual bill, calibrated pack aging and investment costs are missing; this is not a conclusion about all Indian storage.</p>`)}</div>
      <div class="two-col spaced">${u.panel("Why the ranking changed", "Transfer minus scratch; totals computed before rounding", u.table(["Component", "Difference (INR)"], [["Energy charge", money(u, b.grid_energy_charge_inr - a.grid_energy_charge_inr)], ["Common wear proxy", money(u, b.reference_wear_cost_inr - a.reference_wear_cost_inr)], ["Inventory adjustment", money(u, b.inventory_adjustment_inr - a.inventory_adjustment_inr)], ["Reference score", money(u, r.primary.difference_inr)]]))}
      ${u.panel("What the objective counts", "Generic 40 kWh / 20 kW pack; illustrative ₹10/kWh", `<div class="formula">J = grid energy charge + common wear cost\n    − terminal value × (final − initial energy)\nWear = ₹4,00,000 × loss/EFC × EFC / 0.20\nTerminal value = ₹10 × √0.90 / internal kWh</div><p>Only four target-training cells calibrate wear. This is a mixed-aging proxy, not measured physical loss. Initial inventory is not free energy. No calendar term is added, and no actual customer tariff or quotation is inferred.</p>`)}</div>
      <div class="filters">${u.select("controllerCell", "Illustrative health case", cells.map(x => [x, cleanCell(x)]), cell)}${u.select("controllerPolicy", "Saved policy", Object.entries(policies), policy)}${u.select("controllerDay", "Replay day (IST)", dates.map(x => [x, x]), day)}<p class="filter-note">Schedule below: ${cleanCell(cell)}, seed 42, one saved path. Score table above averages all three seeds and six cases.</p></div>
      <div class="spaced">${u.panel("A quarter-hour storage schedule", `${day} · ${policies[policy]} · ${cleanCell(cell)} / seed 42`, u.chart([
        {name: "Modeled PV", color: "#1a3c2b", points: profile.map(x => ({x: x.hour_ist, y: x.modeled_pv_kw}))},
        {name: "Measured load", color: "#527d9a", points: profile.map(x => ({x: x.hour_ist, y: x.load_kw}))},
        {name: "Battery charging", color: "#a97728", points: profile.map((x, i) => ({x: x.hour_ist, y: path[i].charge_kw}))},
        {name: "Battery discharging", color: "#8a6590", points: profile.map((x, i) => ({x: x.hour_ist, y: path[i].discharge_kw}))}
      ], {...quarterOptions, title: "Realized quarter-hour powers for the selected hypothetical case", ylabel: "15-minute mean AC power (kW); charge and discharge shown positive"}) + `<p class="chart-caption">When storage is idle, charging/discharging lines overlap at zero. All four series remain in the legend and exact-value table.</p>` + (policy === "A_no_battery" ? u.note("SOC is not applicable", "The selected policy has no battery.", true) : u.chart([{name: "Battery SOC", color: "#1a3c2b", points: profile.map((x, i) => ({x: x.hour_ist, y: path[i].energy_end_kwh / selected.capacity_kwh * 100}))}], {...quarterOptions, max: 100, title: "End-of-quarter SOC", ylabel: `SOC (%) of ${u.fmt(selected.capacity_kwh, 3)} kWh common health-adjusted capacity; permitted 10–90%`})) + `<details class="mt"><summary>Inspect all 96 quarters</summary>${u.table(["IST", "PV (kW)", "Load (kW)", "Charge (kW)", "Discharge (kW)", "Import (kW)", "Energy (kWh)"], profile.map((x, i) => [clock(x.hour_ist), u.fmt(x.modeled_pv_kw, 3), u.fmt(x.load_kw, 3), u.fmt(path[i].charge_kw, 3), u.fmt(path[i].discharge_kw, 3), u.fmt(path[i].grid_import_kw, 3), u.fmt(path[i].energy_end_kwh, 3)]))}</details>`)}</div>
      <div class="spaced">${u.note("Past-only plans, ideal interval feedback", "Each midnight plan uses the frozen load blend and previous-day modeled PV. Realized SOC carries across all days; current-quarter mean feedback clamps actions to available power and energy. Within-quarter dynamics and live telemetry timing are unvalidated. PV-only charging and zero export are enforced in this study; residual PV is curtailed.", true)}</div>
      <div class="two-col spaced">${u.panel("Does the assumed wear rate change the answer?", "Same saved actions; score-only sensitivity, no reoptimization", u.table(["Evaluation wear multiplier", "Transfer minus scratch (INR)"], scales.map(scale => {
        const take = id => r.sensitivities.find(x => x.reference_wear_multiplier === scale && x.policy === id).inventory_adjusted_reference_score_inr;
        return [u.fmt(scale, 1), money(u, take("D_R2") - take("D_R1"))];
      })) + `<p class="chart-caption">The sign reverses as the unvalidated wear coefficient changes. This is not evidence of physical aging reduction or robustness after reoptimization.</p>`)}
      ${u.panel("Two health cases drive the primary difference", "Per-cell means across seeds · fixed primary comparison", u.table(["Health case", "Transfer minus scratch (INR)"], primaryDiff.map(x => [cleanCell(x.cell_id), signed(u, x.seed_mean_difference_inr, 4)])) + `<p class="chart-caption">W10 and W8 dominate. Four other effects are below ₹0.006 and numerically small. The 95% interval is conditional on this one 16-day window; repeated seeds are not independent sites.</p>`)}</div>
      <details class="spaced"><summary>Inspect paired controller comparisons and intervals</summary>${u.table(["Candidate minus reference", "Difference (INR)", "Descriptive 95% interval (INR)"], r.paired.map(x => [`${policies[x.candidate]} minus ${policies[x.reference]}`, money(u, x.difference_inr), `[${u.rupees(x.descriptive_low_95_inr)}, ${u.rupees(x.descriptive_high_95_inr)}]`]))}<p class="chart-caption">Same 16-day window, common scoring and paired four-day-block resampling. In particular, transfer versus XGBoost is inconclusive when its interval spans zero.</p></details>
      <div class="spaced">${report(u, D.extensions.reports.controller, "Open equations and controller review PDF")}</div>`;
  }

  function render(D, u, s) {
    const tab = studies[s.researchStudy] ? s.researchStudy : "transfer";
    const nav = `<nav class="research-tabs" aria-label="Research studies">${Object.entries(studies).map(([id, name]) => `<a href="#research/${id}" ${tab === id ? 'aria-current="page"' : ""}>${name}</a>`).join("")}</nav>`;
    return nav + ({transfer, calendar, india, controller}[tab])(D, u, s);
  }

  function brief(D, u) {
    const r = D.extensions, p = r.controller.primary;
    return `<section><h2>Completed research extensions</h2>${u.table(["Study", "Finding", "Boundary"], [
      ["First-life transfer", "Small GRU error improvement; XGBoost lowest mean", "Six familiar target cells; full-history v2 still failed"],
      ["Calendar aging", `${r.calendar.nonphysical_predictions} negative predictions retained`, "No M50T calibration or additive calendar wear"],
      ["Indian demand / PV", "Measured building load; modeled solar resource conversion", "Actual PV, bill and meter topology remain unverified"],
      ["Controller", `Transfer minus scratch: ${money(u, p.difference_inr)} per 16 days; higher is worse`, "Common-reference wear/inventory proxy; no field savings"]
    ])}<p>The controller's descriptive 95% day-block interval is [${u.rupees(p.descriptive_low_95_inr)}, ${u.rupees(p.descriptive_high_95_inr)}]. Its assumptions and objectives differ from the original household reference. Completed research does not constitute operational model promotion.</p></section>`;
  }
  root.ReCellResearch = {render, overview, brief, studies};
})(typeof window !== "undefined" ? window : globalThis);
