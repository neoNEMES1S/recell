/* Client-side views over an immutable, verified experiment snapshot. */
(function () {
  "use strict";
  const D = window.RECELL_DATA, C = window.ReCell, R = window.ReCellResearch, I = window.ReCellImplementation;
  const main = document.getElementById("content");
  if (!D || !C || !R || !I || !D.implementation || D.schema_version !== 2 || !D.extensions || D.market?.currency !== "INR") {
    main.innerHTML = '<div class="error"><h1>Research snapshot unavailable</h1><p>Build the dashboard with <code>python scripts/build_dashboard.py</code>, then open <code>dashboard/dist/index.html</code>.</p></div>';
    return;
  }
  const models = Object.keys(C.modelNames);
  const colors = ["#1a3c2b", "#527d9a", "#a97728", "#8a6590", "#bd6b4d", "#628a60"];
  const state = {battery: "G1", cell: "all", horizon: 0, metric: "rmse", model: "pgp_gru",
    seed: D.settings.dispatch.forecast_seed, fraction: 0.1, dispatchCell: "all", weight: 1,
    day: 0, lesson: 0, researchStudy: "transfer", researchFraction: .1, researchHorizon: 1,
    calendarCase: "primary/full", siteDay: "", siteModel: "blend50",
    controllerCell: "secl_m50t_G1", controllerPolicy: "D_R2", controllerDay: "",
    implementationTab: "electrical", ecmCell: "G1", ecmSession: "RPT_3", ecmStep: "10", selectionHorizon: "1"};
  let storageAvailable = true;
  let review = {};
  try {
    const saved = JSON.parse(localStorage.getItem("recell-pilot-review-v1") || "{}");
    if (saved && typeof saved === "object" && !Array.isArray(saved)) review = saved;
  }
  catch (_) { storageAvailable = false; }
  const routes = {overview: "Overview", batteries: "Battery evidence", forecasts: "Reference forecasts",
    dispatch: "Reference dispatch", learn: "Learn the method", research: "Research extensions", implementation: "Model implementation", pilot: "Pilot review"};
  const checkItems = [
    ["scope", "Define a bounded pilot", "Agree the Indian C&I site, DISCOM, tariff category, sanctioned demand, batteries and owner."],
    ["baseline", "Choose the comparison before testing", "Include XGBoost and a conventional controller; keep operating assumptions comparable."],
    ["forecast", "Agree forecasting acceptance criteria", "Set error, coverage and interval-width thresholds before viewing new test outcomes."],
    ["wear", "Calibrate the wear estimate", "Collect pack-level aging evidence and account for calendar aging and temperature."],
    ["operations", "Validate the operational constraints", "Test Indian site demand and solar, SOC/power limits, heat exposure, BMS controls and any backup requirement."],
    ["decision", "Define a go / no-go review", "Evaluate measured outcomes against the agreed criteria before deployment approval."]
  ];
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = (v, digits = 2) => typeof v === "number" && Number.isFinite(v)
    ? v.toLocaleString("en-IN", {minimumFractionDigits: digits, maximumFractionDigits: digits}) : "—";
  const rupees = C.moneyINR;
  const pp = v => typeof v === "number" ? `${fmt(v * 100, 3)} pp` : "—";
  const percent = v => typeof v === "number" ? `${fmt(v * 100, 1)}%` : "—";
  const title = (eyebrow, heading, description) => `<div class="intro"><p class="eyebrow">${eyebrow}</p><h1>${heading}</h1><p>${description}</p></div>`;
  const panel = (heading, subtitle, body, extra = "") => `<section class="panel ${extra}"><div class="panel-head"><div><h2>${heading}</h2>${subtitle ? `<p>${subtitle}</p>` : ""}</div></div><div class="panel-body">${body}</div></section>`;
  const note = (heading, text, neutral = false) => `<div class="note ${neutral ? "neutral" : ""}"><strong>${heading}</strong>${text}</div>`;
  const kpi = (label, value, unit, foot) => `<div class="kpi"><p class="kpi-label">${label}</p><div class="kpi-value">${value}${unit ? `<small>${unit}</small>` : ""}</div><p class="kpi-foot">${foot}</p></div>`;
  const select = (id, label, values, current) => `<div class="field"><label for="${id}">${label}</label><select id="${id}" data-state="${id}">${values.map(([value, text]) => `<option value="${esc(value)}" ${String(value) === String(current) ? "selected" : ""}>${esc(text)}</option>`).join("")}</select></div>`;
  function table(headers, rows, caption = "") {
    return `<div class="table-wrap"><table>${caption ? `<caption>${caption}</caption>` : ""}<thead><tr>${headers.map((h, i) => `<th scope="col" class="${i ? "numeric" : ""}">${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((v, i) => `<td class="${i ? "numeric" : ""}">${v}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  function bars(items, unit = "pp") {
    const maximum = Math.max(...items.map(r => r.value), 1e-9);
    return `<div class="bar-chart" role="img" aria-label="${esc(items.map(i => `${i.label}: ${fmt(i.value, 3)} ${unit}`).join("; "))}">${items.map((r, i) => `<div><div class="bar-label"><span>${esc(r.label)}</span><strong>${fmt(r.value, 3)} <span class="muted">${unit}</span></strong></div><div class="bar-track"><div class="bar-fill ${i ? "alt" : ""}" style="width:${Math.max(0, r.value / maximum * 100)}%"></div></div></div>`).join("")}</div><p class="axis-note">Bars start at zero · lower error is better.</p>`;
  }
  function chart(series, options = {}) {
    const points = series.flatMap(s => s.points).filter(p => Number.isFinite(p.x) && Number.isFinite(p.y));
    if (!points.length) return '<p class="muted">No observations for this selection.</p>';
    const W = 720, H = 290, left = 58, right = 18, top = 18, bottom = 46;
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    if (options.band) ys.push(...options.band.flatMap(p => [p.low, p.high]));
    const xmin = Math.min(...xs), xmax = Math.max(...xs);
    let ymin = options.min ?? Math.min(...ys), ymax = options.max ?? Math.max(...ys);
    const padding = Math.max((ymax - ymin) * .12, options.padding ?? .05);
    if (options.min === undefined) ymin -= padding;
    if (options.max === undefined) ymax += padding;
    const x = v => left + (v - xmin) / (xmax - xmin || 1) * (W - left - right);
    const y = v => H - bottom - (v - ymin) / (ymax - ymin || 1) * (H - top - bottom);
    const path = pts => pts.map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(2)},${y(p.y).toFixed(2)}`).join(" ");
    const xticks = options.xTicks || [0, 1, 2, 3, 4].map(i => xmin + (xmax - xmin) * i / 4);
    const grid = [0, 1, 2, 3, 4].map(i => {
      const v = ymin + (ymax - ymin) * i / 4;
      return `<line class="gridline" x1="${left}" x2="${W - right}" y1="${y(v)}" y2="${y(v)}"/><text x="${left - 10}" y="${y(v) + 4}" text-anchor="end">${fmt(v, options.decimals ?? 1)}</text>`;
    }).join("");
    const band = options.band ? `<path d="${path(options.band.map(p => ({x: p.x, y: p.high})))} ${path([...options.band].reverse().map(p => ({x: p.x, y: p.low}))).replace(/^M/, "L")} Z" fill="#d5e6d3" opacity=".8"/>` : "";
    return `<div class="chart-legend">${series.map((s, i) => `<span><i style="background:${s.color || colors[i]}"></i>${esc(s.name)}</span>`).join("")}${options.band ? '<span><i style="background:#c0d7ba;height:9px"></i>P10–P90 range</span>' : ""}</div><div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(options.title || "Research data chart")}"><title>${esc(options.title || "Research data chart")}</title><desc>${esc(options.description || "Exact values are available in the accompanying data table or downloaded snapshot.")}</desc>${grid}${band}${xticks.map(v => `<text x="${x(v)}" y="${H - bottom + 23}" text-anchor="middle">${esc(options.xFormat ? options.xFormat(v) : fmt(v, 0))}</text>`).join("")}${series.map((s, i) => `<path class="series" d="${path(s.points)}" stroke="${s.color || colors[i]}" ${s.dashed ? 'stroke-dasharray="6 4"' : ""}/>${s.points.map(p => `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="2.7" fill="${s.color || colors[i]}"><title>${esc(s.name)}: ${fmt(p.y, 3)} at ${esc(options.xFormat ? options.xFormat(p.x) : fmt(p.x, 0))}</title></circle>`).join("")}`).join("")}<text x="${W / 2}" y="${H - 3}" text-anchor="middle">${esc(options.xlabel || "")}</text></svg></div>${options.ylabel ? `<p class="chart-caption">Vertical axis: ${options.ylabel}</p>` : ""}`;
  }
  function meanForecasts(horizon = 0, cell = "all", metric = "rmse") {
    return models.map(model => C.forecastMetric(D, model, horizon, cell)).filter(Boolean)
      .sort((a, b) => a[metric + "_mean"] - b[metric + "_mean"]);
  }
  const researchUI = {esc, fmt, rupees, pp, percent, title, panel, note, kpi, select, table, bars, chart};
  function research() { return R.render(D, researchUI, state); }
  function implementation() { return I.render(D, researchUI, state); }
  function costCards(b, d, label = "Wear-aware policy") {
    return `<div class="cost-grid"><div class="cost-case"><p class="eyebrow">C · Electricity-only policy</p><div class="cost-number">${rupees(b.electricity_plus_estimated_wear_inr)}</div><p class="cost-detail">${rupees(b.electricity_cost_inr)} electricity<br>+ ${rupees(b.estimated_degradation_cost_inr)} estimated wear</p></div><div class="cost-case highlight"><p class="eyebrow">${label}</p><div class="cost-number">${rupees(d.electricity_plus_estimated_wear_inr)}</div><p class="cost-detail">${rupees(d.electricity_cost_inr)} electricity<br>+ ${rupees(d.estimated_degradation_cost_inr)} estimated wear</p></div></div>`;
  }
  function marketContext() {
    const m = D.market;
    return panel("India C&I pilot assumptions", "Rupee economics · illustrative inputs to validate with the site", table(
      ["Input", "Scenario value"], [
        ["Grid energy charge", `${rupees(m.import_price_inr_per_kwh)} / kWh · flat`],
        ["Export credit", `${rupees(m.export_price_inr_per_kwh)} / kWh`],
        ["Battery replacement assumption", `${rupees(m.replacement_cost_inr)} · 10 kWh reference pack`]
      ]) + `<p class="chart-caption">Re-optimized in INR; no exchange-rate conversion. These inputs are assumptions, not a DISCOM tariff or supplier quotation. The 10 kWh / 3 kW system is a research reference, not a sized industrial installation.</p>
      <p class="mt"><strong>Data boundary:</strong> ${esc(m.profile_status)} Actual Indian site data is required before claiming C&I economics.</p>
      <p class="small muted mt"><strong>Excluded:</strong> ${esc(m.excluded_costs)}</p>
      <p class="small mt">For a site pilot, obtain the DISCOM tariff order, ToD slots, demand-charge rules and export agreement. <a href="${esc(m.policy_source.url)}" target="_blank" rel="noopener">${esc(m.policy_source.title)} (2023 reference)</a>.</p>`);
  }
  function overview() {
    const ranked = meanForecasts(), best = ranked[0];
    const b = D.dispatch_comparison.baseline, d = D.dispatch_comparison.aware;
    return title("India · Commercial &amp; industrial research", "Battery research, ready for review.",
      "Follow battery measurements through health forecasts and storage decisions. Review the original demonstration alongside the completed research extensions, with assumptions and remaining validation evidence visible.")
      + `<div class="spaced">${I.overview(D, researchUI)}</div><div class="spaced">${R.overview(D, researchUI)}</div>`
      + `<div class="spaced">${marketContext()}</div><div class="kpis">${kpi("Experimental scope", `${D.cells.length} <small>cells</small> / ${D.counts.checkpoints}`, "checkpoints", "Measured capacity at diagnostic tests")}${kpi(`Best forecast error · ${C.modelNames[best.model]}`, fmt(best.rmse_mean * 100, 3), "SOH pp", "RMSE · percentage points, not an accuracy score")}${kpi("Less cycling in the modeled comparison", fmt(C.reduction(b.equivalent_full_cycles, d.equivalent_full_cycles), 1) + "%", "", "C vs median D · same health and wear assumptions")}</div>
      <div class="grid-main"><div class="stack">${panel("How well can we forecast health?", "Next one and two diagnostic checkpoints · both horizons combined", bars(ranked.map(r => ({label: C.modelNames[r.model], value: r.rmse_mean * 100}))) + '<p class="chart-caption">Each cell is weighted equally after averaging three seeds. XGBoost leads this reference run; the physics-guided model does not beat every baseline.</p><a class="button secondary mt" href="#forecasts">Explore forecast quality →</a>')}
      ${panel("What changes when we account for wear?", "INR scenario · energy charge + estimated wear · proxy replay", costCards(b, d, "D · Wear-aware policy") + `<p class="comparison-caption">${fmt(C.reduction(b.electricity_plus_estimated_wear_inr, d.electricity_plus_estimated_wear_inr), 1)}% lower modeled combined cost. Energy-charge and wear costs depend on the selected INR assumptions. These are simulated costs, not a measured C&I bill saving.</p><a class="button secondary mt" href="#dispatch">Explore storage decisions →</a>`)}</div>
      <div class="stack"><section class="panel decision"><div class="panel-body"><p class="eyebrow">Decision for discussion</p><h2>Approve a<br>validation pilot.</h2><p>Proposed next step: a bounded pilot at an Indian commercial or industrial site. The next step is to test the assumptions against independent batteries and real operating conditions.</p><ul><li>Agree success criteria before testing</li><li>Calibrate aging at pack level</li><li>Compare against a conventional controller</li></ul><a class="button light" href="#pilot">Review the pilot scope →</a></div></section>
      ${note("Original reference demonstration", "The costs and cycling comparison on this overview use the original six-cell / German-household perfect-foresight replay. The separate Indian public-data controller study has an unfavorable primary result. No measured lifetime extension or field savings is claimed.")}
      ${panel("New to the project?", `${window.RECELL_LESSONS.length} short lessons, in plain language`, '<p>Follow measurement, forecasting and storage arithmetic, then learn how the transfer, calendar, Indian demand/PV and controller extensions change the research question.</p><a class="button secondary mt" href="#learn" data-action="start-guide">Learn how this works →</a>')}</div></div>
      <div class="evidence-strip"><div><h3><span class="evidence-dot"></span>Observed</h3><p>Discharge capacity and cycling histories from six second-life cells.</p></div><div><h3><span class="evidence-dot gold"></span>Modeled</h3><p>Future health, uncertainty and optimal dispatch under explicit assumptions.</p></div><div><h3><span class="evidence-dot coral"></span>Still to validate</h3><p>Pack aging, realistic forecasts, operational safety and realized economics.</p></div></div>`;
  }
  function batteries() {
    const rows = D.checkpoints.filter(r => r.cell_id === state.battery).sort((a, b) => a.elapsed_days - b.elapsed_days);
    const first = rows[0], last = rows[rows.length - 1];
    return title("02 / Battery evidence", "Start with what we measured.", "A checkpoint is a reviewed diagnostic test. We extract discharge capacity and compare it with the first observed second-life capacity of the same cell.")
      + `<div class="filters">${select("battery", "Battery cell", D.cells.map(c => [c, c]), state.battery)}<p class="filter-note">Observed data · temperature and EIS are excluded from the initial forecast predictors.</p></div>
      <div class="kpis">${kpi("First observed capacity", fmt(first.capacity_ah, 3), "Ah", "The SOH reference for this cell")}${kpi("Last observed SOH", fmt(last.soh * 100, 2), "%", "Relative to this cell’s second-life starting point")}${kpi("Available measurements", rows.length, "checkpoints", `${fmt(last.elapsed_days, 0)} days of observed follow-up`)}</div>
      <div class="grid-main"><div class="stack">${panel(`${state.battery}: measured health through time`, "Capacity recoveries are preserved, not smoothed away", chart([{name: "Measured SOH", points: rows.map(r => ({x: r.elapsed_days, y: r.soh * 100}))}], {title: `${state.battery} measured SOH`, xlabel: "Days since first second-life checkpoint", ylabel: "SOH (%) · zoomed to the observed range; not a zero-based axis."}) + `<details><summary>View all ${rows.length} measurements</summary>${table(["Checkpoint date", "Capacity (Ah)", "SOH (%)", "Prior cycling (Ah)"], rows.map(r => [esc(r.timestamp.slice(0, 10)), fmt(r.capacity_ah, 4), fmt(r.soh * 100, 3), fmt(r.cumulative_ah, 1)]))}</details>`)}</div>
      <div class="stack">${panel("What does 100% mean?", "A second-life reference, not factory-new", `<p>For ${state.battery}, the reference is ${fmt(first.reference_capacity_ah, 4)} Ah. The same reference is used throughout its trajectory.</p><div class="formula">${fmt(last.capacity_ah, 4)} Ah ÷ ${fmt(last.reference_capacity_ah, 4)} Ah\n= ${fmt(last.soh, 5)}\n= ${fmt(last.soh * 100, 2)}% SOH</div><p>SOH describes remaining capacity. SOC describes how full that capacity is right now.</p>`)}
      ${note("Trust comes before modeling", "We check source hashes, remove exact overlapping records, inspect the discharge protocol and cross-check integrated capacity against instrument counters. Ambiguous records are excluded.", true)}</div></div>
      <div class="spaced">${panel("The measurement-to-forecast chain", "Every input has a specific role", `<ol class="roadmap"><li><strong>Current and time → capacity</strong><p>Integrate four low-current discharge segments. Exclude rests, recharge and short pulses.</p></li><li><strong>Capacity → relative health</strong><p>Divide by the first observed second-life capacity. Never use future observations to choose the reference.</p></li><li><strong>Past exposure → model inputs</strong><p>Use only cycling sessions ending before the diagnostic test begins.</p></li><li><strong>Checkpoint history → future targets</strong><p>Forecast the next one and two diagnostic checkpoints. Their calendar spacing varies.</p></li></ol><a href="#learn" class="button secondary" data-lesson="1">Walk through the calculation →</a>`)}</div>`;
  }
  function forecasts() {
    const ranked = meanForecasts(state.horizon, state.cell, state.metric);
    const chosen = C.forecastMetric(D, state.model, state.horizon, state.cell);
    const plotCell = state.cell === "all" ? D.cells[0] : state.cell;
    const plotHorizon = state.horizon || 1;
    const pred = D.predictions.filter(r => r.cell_id === plotCell && r.model === state.model
      && r.seed === state.seed && r.horizon === plotHorizon).sort((a, b) => a.origin_index - b.origin_index);
    const observed = pred.map(r => ({x: r.origin_index + r.horizon + 1, y: r.y_true * 100}));
    const forecast = pred.map(r => ({x: r.origin_index + r.horizon + 1, y: r.q50 * 100}));
    const probabilistic = pred.length && pred.every(r => r.q10 !== null && r.q90 !== null);
    const fold = D.folds.find(f => f.test === plotCell);
    const historyModels = [...new Set([state.model, "xgboost"])];
    const historySeries = historyModels.map((m, i) => ({name: C.modelNames[m], color: colors[i],
      points: D.limited_history.filter(r => r.model === m && r.horizon === state.horizon && r.unit === "soh")
        .sort((a, b) => a.history_fraction - b.history_fraction).map(r => ({x: r.history_fraction * 100, y: r.rmse_mean * 100}))}));
    const selectedHistory = D.limited_history.filter(r => r.history_fraction === state.fraction
      && r.horizon === state.horizon && r.unit === "soh").sort((a, b) => a.rmse_mean - b.rmse_mean);
    return title("03 / Original forecasting reference", "Good forecasts earn their place.", "Compare the original six-feature approaches on held-out batteries. The separately registered three-feature transfer comparison is available under Research extensions. Smaller errors, honest uncertainty and fair comparisons all matter.")
      + `<div class="filters">${select("cell", "Evaluation scope", [["all", "All six cells"], ...D.cells.map(c => [c, c])], state.cell)}${select("horizon", "Forecast horizon", [[0, "Both checkpoints"], [1, "Next checkpoint"], [2, "Second checkpoint"]], state.horizon)}${select("metric", "Comparison metric", [["rmse", "RMSE · larger misses matter"], ["mae", "MAE · typical absolute miss"]], state.metric)}<p class="filter-note">SOH errors shown in percentage points (pp). Three seeds averaged per cell.</p></div>
      <div class="grid-main"><div class="stack">${panel("Model comparison", `${state.cell === "all" ? "Equal-weight mean across six held-out cells" : `Held-out ${state.cell} · mean across three seeds`}`, bars(ranked.map(r => ({label: C.modelNames[r.model], value: r[state.metric + "_mean"] * 100}))) + `<details><summary>Inspect metrics and uncertainty</summary>${table(["Model", "MAE (pp)", "RMSE (pp)", "R²", "80% coverage", "Width (pp)"], ranked.map(r => [C.modelNames[r.model], fmt(r.mae_mean * 100, 3), fmt(r.rmse_mean * 100, 3), fmt(r.r2_mean, 3), percent(r.coverage_80_mean), r.interval_width_mean === null ? "—" : fmt(r.interval_width_mean * 100, 3)]), "A dash means the model does not supply an interval. It never means zero error.")}</details>`)}</div><div class="stack">
      ${panel("How the test is kept separate", `Example fold: ${plotCell} is held out`, `<div class="phase-row">${D.cells.map(c => `<span class="phase-cell ${c === fold.test ? "test" : c === fold.validation ? "validation" : ""}">${c}</span>`).join("")}</div><p class="phase-legend">Green: test (${fold.test}) · gold: validation (${fold.validation}) · pale: training.</p><p class="mt">Imputation and scaling learn from the four training cells only. Validation chooses when training stops; test results do not tune these saved fits.</p>`)}
      ${note("Read the evidence, not the model name", "XGBoost has the lowest aggregate error in the reference run. Physics guidance improves on some baselines, but it does not establish universal superiority. Only six independent cells were tested.")}</div></div>
      <div class="spaced">${panel("A forecast beside the measurement", "This chart shows one cell, one seed and one forecast horizon", `<div class="filters">${select("model", "Model to inspect", models.map(m => [m, C.modelNames[m]]), state.model)}${select("seed", "Random seed", D.settings.evaluation.seeds.map(s => [s, String(s)]), state.seed)}<p class="filter-note">${plotCell} · horizon ${plotHorizon}${state.cell === "all" ? " · representative cell for the chart" : ""}${state.horizon === 0 ? " · next checkpoint shown" : ""}</p></div>
      ${chart([{name: "Measured", color: "#172b22", points: observed}, {name: "Forecast median / point", color: "#628a60", points: forecast, dashed: true}], {title: `${C.modelNames[state.model]} forecast versus observation on ${plotCell}`, xlabel: "Target diagnostic checkpoint number (irregular calendar spacing)", ylabel: "SOH (%) · zoomed axis.", band: probabilistic ? pred.map(r => ({x: r.origin_index + r.horizon + 1, low: r.q10 * 100, high: r.q90 * 100})) : null})}
      <p class="chart-caption">${probabilistic ? "The shaded P10–P90 range targets 80% coverage across repeated outcomes. It is not a guarantee for an individual forecast." : "This model supplies point predictions only. No uncertainty interval has been invented."}</p>
      <details><summary>View the plotted predictions</summary>${table(["Target date", "Measured SOH (%)", "Forecast (%)", "P10 (%)", "P90 (%)"], pred.map(r => [esc(r.target_time.slice(0, 10)), fmt(r.y_true * 100, 3), fmt(r.q50 * 100, 3), r.q10 === null ? "—" : fmt(r.q10 * 100, 3), r.q90 === null ? "—" : fmt(r.q90 * 100, 3)]))}</details>`)}</div>
      <div class="two-col">${panel("Does the uncertainty range behave as intended?", `${C.modelNames[state.model]} · current evaluation scope`, `<div class="metric-definitions"><div><h3>${percent(chosen.coverage_80_mean)}</h3><p>Observed P10–P90 coverage; target 80%.</p></div><div><h3>${pp(chosen.interval_width_mean)}</h3><p>Average interval width. Coverage needs context.</p></div><div><h3>${percent(chosen.empirical_q10_mean)} / ${percent(chosen.empirical_q50_mean)} / ${percent(chosen.empirical_q90_mean)}</h3><p>Fraction at or below P10 / P50 / P90; ideal 10% / 50% / 90%.</p></div><div><h3>${fmt(chosen.quantile_loss_mean, 5)}</h3><p>Mean pinball loss in SOH units; lower is better.</p></div></div><p class="chart-caption">Point-only models show dashes. Coverage above 80% can reflect broad intervals; it is not an accuracy percentage.</p>`)}
      ${panel("What happens with less history?", "All six cells · full training histories · shortened inference context", chart(historySeries, {title: "RMSE versus retained history", decimals: 2, xTicks: [10, 25, 50, 75, 100], xFormat: x => `${fmt(x, 0)}%`, xlabel: "Retained pre-origin checkpoint history", ylabel: "SOH RMSE (percentage points) · same forecast origins at every fraction."}) + `<div class="filters">${select("fraction", "Inspect context fraction", D.settings.evaluation.history_fractions.map(f => [f, `${f * 100}%`]), state.fraction)}</div>${table(["Model", "RMSE (pp)"], selectedHistory.map(r => [C.modelNames[r.model], fmt(r.rmse_mean * 100, 3)]))}<p class="chart-caption">The SOH reference and cumulative-exposure metadata remain available even when older context is removed.</p>`)}</div>
      <div class="spaced">${note("Want to understand the arithmetic?", '<a href="#learn" data-lesson="5">Open the worked MAE / RMSE calculator</a>, then follow the quantile and physics-guided training objective.', true)}</div>`;
  }
  function dispatch() {
    const cell = state.dispatchCell;
    const b = C.dispatchMetric(D, "C_second_life", 0, cell);
    const scenario = state.weight === 0 ? "C_second_life" : "D_degradation_aware";
    const d = C.dispatchMetric(D, scenario, state.weight, cell);
    const plotCell = cell === "all" ? D.cells[0] : cell;
    const schedule = D.schedules.series.find(s => s.cell === plotCell && s.weight === state.weight);
    const cols = D.schedules.columns;
    const rows = schedule.rows.slice(state.day * 24, (state.day + 1) * 24)
      .map(row => Object.fromEntries(cols.map((c, i) => [c, row[i]])));
    const sample = C.dispatchMetric(D, scenario, state.weight, plotCell);
    const conversion = D.wear_conversion.find(c => c.cell_id === plotCell);
    const forecast = D.selected_forecasts.find(r => r.cell_id === plotCell);
    const battery = D.settings.dispatch.battery;
    const savings = C.reduction(b.electricity_plus_estimated_wear_inr, d.electricity_plus_estimated_wear_inr);
    const cycles = C.reduction(b.equivalent_full_cycles, d.equivalent_full_cycles);
    const options = [
      ["A_no_battery", 0], ["B_conventional", 0], ["C_second_life", 0],
      ["D_degradation_aware", 1], ["D_conservative", 1]
    ].map(([name, weight]) => C.dispatchMetric(D, name, weight, cell));
    const sensitivity = D.cells.map((c, i) => ({name: c, color: colors[i], points:
      [0, ...D.settings.dispatch.degradation_weights].map(w => ({x: w,
        y: C.dispatchMetric(D, w === 0 ? "C_second_life" : "D_degradation_aware", w, c).equivalent_full_cycles}))}));
    const units = cell === "all" ? "Mean across six cell health scenarios" : `Cell health scenario: ${cell}`;
    const date = rows[0].timestamp.slice(0, 10);
    return title("04 / Original storage reference", "The original solar-storage trade-off.", "This is the retained German-household proxy demonstration. The newer Indian public-data controller comparison is under Research extensions. Each selector here chooses a saved reference result, without running a new simulation.")
      + `<div class="spaced">${marketContext()}</div><div class="filters">${select("dispatchCell", "Battery health scenario", [["all", "Mean of six cells"], ...D.cells.map(c => [c, c])], cell)}${select("weight", "Wear-cost multiplier λ", [[0, "0 · electricity only"], ...D.settings.dispatch.degradation_weights.map(w => [w, `${w} · ${w === 1 ? "reference wear-aware" : "sensitivity"}`])], state.weight)}<p class="filter-note">INR scenario · ${D.solar_provenance.hours} proxy hours · June 2016 source data. ${units}.</p></div>
      <div class="kpis">${kpi("Modeled electricity + estimated wear", rupees(d.electricity_plus_estimated_wear_inr), "/ month", `${fmt(Math.abs(savings), 1)}% ${savings >= 0 ? "lower" : "higher"} than C under matched assumptions`)}${kpi("Battery cycling", fmt(d.equivalent_full_cycles), "EFC", `${fmt(Math.abs(cycles), 1)}% ${cycles >= 0 ? "less" : "more"} than C · nominal-energy basis`)}${kpi("Net electricity cost", rupees(d.electricity_cost_inr), "/ month", "Imports minus exports · excludes estimated wear")}</div>
      <div class="grid-main"><div class="stack">${panel("Follow the money, term by term", units, costCards(b, d, state.weight === 0 ? "Selected: electricity only" : `Selected: wear weight ${state.weight}`) + `<div class="formula">Solver objective = electricity + λ × estimated wear\n${rupees(d.electricity_cost_inr)} + ${state.weight} × ${rupees(d.estimated_degradation_cost_inr)} = ${rupees(d.objective_inr)}</div><p>The comparison total above always includes wear at weight 1. When λ is 0.5 or 2, that total differs from the solver objective. Export revenue is ₹0 in this scenario. Only energy charges and estimated wear enter the objective.</p>`)}</div>
      <div class="stack">${note("A fair policy comparison", "C and the median D cases use the same health and wear assumptions. Their only policy difference is the weight placed on estimated wear. The P10 conservative case changes assumptions and belongs in sensitivity analysis.", true)}${note("What this replay assumes", `${battery.nominal_energy_kwh} kWh nominal pack; ${battery.power_kw} kW power; ${fmt(battery.round_trip_efficiency * 100, 0)}% round-trip efficiency; ${battery.soc_min * 100}–${battery.soc_max * 100}% SOC. The full solar/load horizon is known in advance. Health is fixed during replay. Demand charges, duties, financing and backup value are excluded. No total-bill saving or carbon benefit is claimed.`)}</div></div>
      <div class="spaced">${panel("The five reference cases", "Median D is shown at λ = 1; the P10 case is a separate sensitivity", table(["Case", "Electricity (₹)", "Wear proxy (₹)", "Combined (₹)", "Cycles (EFC)", "Solar used onsite"], options.map(r => [C.scenarioNames[r.scenario], rupees(r.electricity_cost_inr), rupees(r.estimated_degradation_cost_inr), rupees(r.electricity_plus_estimated_wear_inr), fmt(r.equivalent_full_cycles), percent(r.solar_self_consumption)])) + '<p class="chart-caption">B assumes full nominal capacity but reuses the same wear proxy for a controlled comparison. Solar self-consumption counts direct solar plus battery charging, including conversion losses. No export revenue is credited; this is not a zero-export control simulation.</p>')}
      </div><div class="spaced">${panel("A day in the proxy storage schedule", `${plotCell} example · ${date} UTC · wear weight ${state.weight}`, `<div class="filters">${select("day", "Replay day (UTC)", Array.from({length: schedule.rows.length / 24}, (_, i) => [i, schedule.rows[i * 24][0].slice(0, 10)]), state.day)}<p class="filter-note">${cell === "all" ? `The costs above average six scenarios. This schedule specifically shows ${plotCell}.` : "This schedule uses the selected cell’s assumed health."}</p></div>
      ${chart(["solar_kw", "load_kw", "charge_kw", "discharge_kw"].map((key, i) => ({name: ["Solar generation", "Proxy demand", "Battery charging", "Battery discharging"][i], color: colors[i], points: rows.map((r, hour) => ({x: hour, y: r[key]}))})), {title: `${plotCell} hourly solar, load and storage power on ${date}`, min: 0, xlabel: "Hour (UTC) · charging and discharging both shown as positive power", xTicks: [0, 6, 12, 18, 23], xFormat: v => `${String(Math.round(v)).padStart(2, "0")}:00`, ylabel: "Average power (kW) over each hour."})}
      ${chart([{name: "Battery state of charge", points: rows.map((r, hour) => ({x: hour, y: r.energy_end_kwh / sample.usable_energy_capacity_kwh * 100}))}], {title: "End-of-hour state of charge", min: 0, max: 100, xTicks: [0, 6, 12, 18, 23], xFormat: v => `${String(Math.round(v)).padStart(2, "0")}:00`, xlabel: "Hour (UTC)", ylabel: `End-of-hour SOC (% of ${fmt(sample.usable_energy_capacity_kwh, 3)} kWh health-adjusted capacity). Permitted range: 10–90%.`})}
      <details><summary>Inspect the hourly schedule</summary>${table(["Hour UTC", "Solar (kW)", "Load (kW)", "Charge (kW)", "Discharge (kW)", "Import (kW)", "Stored energy (kWh)"], rows.map(r => [esc(r.timestamp.slice(11, 16)), fmt(r.solar_kw, 3), fmt(r.load_kw, 3), fmt(r.charge_kw, 3), fmt(r.discharge_kw, 3), fmt(r.grid_import_kw, 3), fmt(r.energy_end_kwh, 3)]))}</details>`)}</div>
      <div class="two-col">${panel("How much does the wear assumption matter?", "All six health scenarios · same proxy replay", chart(sensitivity, {title: "Equivalent cycles versus wear-cost multiplier", min: 0, xTicks: [0, .5, 1, 2], xFormat: v => fmt(v, 1), xlabel: "Wear-cost multiplier λ", ylabel: "Equivalent full cycles per replay month."}) + '<p class="chart-caption">A stronger wear penalty can discourage cycling. This sensitivity does not measure real aging or prove a longer service life.</p>')}
      ${panel("Trace the forecast into capacity and wear", `${plotCell} · held-out PGP-GRU forecast · seed ${forecast.seed}`, `<p>The median SOH forecast is ${fmt(forecast.q50 * 100, 3)}% of this cell’s second-life reference. Convert to nominal health using ${fmt(forecast.reference_capacity_ah, 4)} Ah ÷ ${D.settings.dispatch.nominal_cell_capacity_ah} Ah.</p><div class="formula">Nominal health = ${fmt(conversion.median.health_fraction * 100, 3)}%\nAvailable pack energy = ${fmt(sample.usable_energy_capacity_kwh, 3)} kWh\nSOC-window swing = ${fmt(sample.usable_energy_capacity_kwh * (battery.soc_max - battery.soc_min), 3)} kWh\nExpected EFC / checkpoint = ${fmt(conversion.median.expected_efc_per_checkpoint, 3)}\nWear / EFC = ${fmt(conversion.median.wear_per_efc, 7)}</div><p>Exposure calibration uses training cells ${conversion.training_cells.join(", ")}. The held-out cell is excluded.</p><a class="button secondary mt" href="#learn" data-lesson="7">Learn the conversion →</a>`)}</div>`;
  }
  function metricCalculator() {
    return `<section class="calculator" aria-label="Illustrative forecast metric calculator"><h3>Try a three-point example</h3><p class="small muted">Illustrative numbers, separate from the research results. Enter SOH percentages, such as 98.</p><form id="metric-form"><div class="fields"><div class="field"><label for="actual">Measured SOH percentages</label><input id="actual" name="actual" value="98, 97, 96" required></div><div class="field"><label for="predicted">Predicted SOH percentages</label><input id="predicted" name="predicted" value="97.8, 97.4, 95.9" required></div></div><button class="button" type="submit">Calculate the errors</button></form><div id="calculator-output" aria-live="polite"></div></section>`;
  }
  function learn() {
    const lessons = window.RECELL_LESSONS, item = lessons[state.lesson];
    return title("05 / Learn the method", "Let’s follow the calculation.", "Work through the project at your own pace. Each lesson connects the plain-language idea, the actual formula and the limit on what we can claim.")
      + `<div class="lesson-layout"><nav class="lesson-nav" aria-label="Lessons">${lessons.map((l, i) => `<button data-lesson="${i}" ${state.lesson === i ? 'aria-current="step"' : ""}><span>${String(i + 1).padStart(2, "0")}</span>${esc(l.label)}</button>`).join("")}</nav>
      <section class="panel lesson-card"><div class="panel-body"><p class="eyebrow">Lesson ${state.lesson + 1} / ${lessons.length} · ${esc(item.label)}</p><h2>${esc(item.title)}</h2><p class="lesson-summary">${esc(item.summary)}</p><div class="lesson-copy">${item.body}</div><div class="formula">${esc(item.formula)}</div><div class="example">${esc(item.example)}</div>${item.calculator ? metricCalculator() : ""}${note("Keep this distinction in mind", esc(item.caution))}<a class="button secondary mt" href="#${item.destination}">Explore this in the dashboard →</a></div>
      <div class="lesson-controls"><button class="button secondary" data-action="previous-lesson" ${state.lesson === 0 ? "disabled" : ""}>← Previous</button><span class="lesson-progress">${state.lesson + 1} of ${lessons.length} lessons</span>${state.lesson === lessons.length - 1 ? '<a class="button" href="#pilot">Review the pilot →</a>' : '<button class="button" data-action="next-lesson">Next lesson →</button>'}</div></section></div>
      <div class="spaced">${panel("Metric reference", "A glossary for the client discussion", `<div class="metric-definitions">
      <div><h3>MAE / RMSE</h3><p>Typical absolute miss / error that emphasizes large misses. SOH errors × 100 are percentage points.</p></div>
      <div><h3>MAPE / R²</h3><p>100 × mean absolute error relative to the target / 1 − squared-error sum divided by target variation. MAPE is undefined near zero; R² can be negative.</p></div>
      <div><h3>Coverage / interval width</h3><p>How often measurements land inside P10–P90 / how broad that range is. The coverage target is 80%; wider is not automatically better.</p></div>
      <div><h3>Pinball loss / calibration</h3><p>Asymmetric quantile error / whether observed fractions align with 10%, 50% and 90% quantile levels.</p></div>
      <div><h3>SOH / SOC</h3><p>Remaining capacity relative to a stated reference / how full the current available battery capacity is.</p></div>
      <div><h3>EFC / throughput</h3><p>Equivalent full cycles = internal charge + discharge energy ÷ twice nominal energy. Throughput is that total energy movement.</p></div>
      <div><h3>Solar self-consumption</h3><p>(Direct solar + solar charged into storage) ÷ total solar. It includes later conversion losses; it is not self-sufficiency.</p></div>
      <div><h3>Training loss / dispatch objective</h3><p>One adjusts a model’s weights to forecast better. The other chooses a storage schedule under electricity and wear assumptions.</p></div></div>`)}</div>`;
  }
  function pilot() {
    const done = checkItems.filter(([key]) => review[key]).length;
    return title("07 / Pilot review", "Plan an Indian C&I validation pilot.", "Use this page to structure the client discussion. The immediate next step is data access and calibration, with success criteria agreed before independent site outcomes are evaluated.")
      + `<div class="spaced">${R.overview(D, researchUI)}</div>`
      + `<div class="pilot-banner"><h2>Proposed decision: proceed to a validation pilot.</h2><p>This is a discussion proposal. No approval is submitted by this dashboard, and the checklist is not a formal sign-off.</p></div>
      <div class="grid-main"><div class="stack">${panel("What we can demonstrate today", "A working research prototype with traceable results", `<ol class="roadmap"><li><strong>Measurements become auditable capacity targets</strong><p>Source hashes, duplicate checks and reviewed diagnostic segments support the extraction.</p></li><li><strong>Forecasts are evaluated on held-out cells</strong><p>Six approaches, three seeds, separate validation and matched-origin limited-history tests.</p></li><li><strong>Uncertainty can be inspected</strong><p>Quantile predictions, empirical coverage and width expose limitations beyond a single point score.</p></li><li><strong>Wear-aware assumptions change storage operation</strong><p>Saved schedules satisfy numerical constraints under the modeled replay. Physical benefit remains to be tested.</p></li></ol>`)}
      ${panel("Proposed acceptance criteria to agree", "Set thresholds before evaluating the pilot; none are imposed here", table(["Question", "Measure to agree"], [
        ["Do forecasts generalize?", "SOH MAE/RMSE on independent cells or packs"],
        ["Is uncertainty useful?", "Coverage near target, with acceptable interval width"],
        ["Is operation feasible?", "Observed constraint compliance under forecast error"],
        ["Is the wear proxy credible?", "Agreement with measured aging across pilot conditions"],
        ["Does the policy improve outcomes?", "Measured INR cost and aging versus a matched controller; include the site’s full tariff"]
      ]))}</div><div class="stack">${note("What still needs validation", "Independent cell/pack generalization, wear calibration, calendar aging and temperature, realistic solar/load forecast errors, closed-loop operation and hardware safety. No measured lifetime extension, field saving or carbon benefit is established.")}
      ${panel("A focused pilot sequence", "Keep the scope bounded", '<ol class="roadmap"><li><strong>Agree scope and baseline</strong><p>Choose the Indian site, DISCOM, tariff category, sanctioned demand, pack and comparator.</p></li><li><strong>Calibrate and replay</strong><p>Collect Indian interval-meter and solar data; include ToD rates, demand charges and realistic forecast errors.</p></li><li><strong>Run supervised trials</strong><p>Validate the pack, BMS, thermal conditions and operating limits. Test backup requirements separately.</p></li><li><strong>Review the evidence</strong><p>Apply the pre-agreed criteria to a deployment decision.</p></li></ol>')}</div></div>
      <div class="spaced">${panel("Discussion checklist", `<span id="check-count">${done} of ${checkItems.length}</span> topics covered · not a readiness score`, `<div class="checklist">${checkItems.map(([key, heading, detail]) => `<label class="check-item"><input type="checkbox" data-check="${key}" ${review[key] ? "checked" : ""}><span><strong>${heading}</strong><small>${detail}</small></span></label>`).join("")}</div><div class="mt"><label for="pilot-notes"><strong>Meeting notes</strong> <span class="small muted">optional · stored in this browser only</span></label><textarea id="pilot-notes" placeholder="Record agreed scope, open questions, owners and next steps…">${esc(review.notes || "")}</textarea></div><p id="storage-status" class="chart-caption">${storageAvailable ? "Changes stay in this browser. They are not sent to a server or recorded as an approval." : "Browser storage is unavailable. Notes last for this session only; print the brief to retain them."}</p><div class="actions mt"><button class="button" data-action="print">Print the client brief</button><button class="button secondary" data-action="download-guide">Download the learning guide</button></div>`)}</div>`;
  }
  function calculate() {
    const output = document.getElementById("calculator-output");
    if (!output) return;
    try {
      const result = C.exampleMetrics(C.parseNumbers(document.getElementById("actual").value),
        C.parseNumbers(document.getElementById("predicted").value));
      output.innerHTML = `<div class="calculator-results"><div><strong>${fmt(result.mae, 4)}</strong>MAE · pp</div><div><strong>${fmt(result.rmse, 4)}</strong>RMSE · pp</div><div><strong>${fmt(result.mape, 4)}${result.mape === null ? "" : "%"}</strong>MAPE</div><div><strong>${fmt(result.r2, 4)}</strong>R²</div></div><p class="small muted">Signed errors (prediction − actual): ${result.errors.map(e => fmt(e, 3)).join(", ")} pp. ${result.r2 === null ? "R² is undefined for constant observations." : ""} ${result.mape === null ? "MAPE is undefined because an observation is zero or near zero." : ""}</p>`;
    } catch (error) { output.innerHTML = `<p class="error mt">${esc(error.message)}</p>`; }
  }
  function currentRoute() { return location.hash.slice(1).split("/")[0] || "overview"; }
  function render(focus = false) {
    const active = document.activeElement?.id;
    const route = currentRoute();
    const requestedStudy = location.hash.slice(1).split("/")[1];
    if (route === "research" && R.studies[requestedStudy]) state.researchStudy = requestedStudy;
    if (route === "implementation" && I.tabs[requestedStudy]) state.implementationTab = requestedStudy;
    const pages = {overview, batteries, forecasts, dispatch, learn, research, implementation, pilot};
    main.innerHTML = (pages[route] || overview)();
    document.title = `ReCell · ${routes[route] || "Overview"}`;
    document.querySelectorAll(".navigation a").forEach(link => {
      if (link.hash === `#${pages[route] ? route : "overview"}`) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    if (route === "learn" && state.lesson === 5) calculate();
    if (focus) { main.focus({preventScroll: true}); window.scrollTo({top: 0, behavior: "instant"}); }
    else if (active) document.getElementById(active)?.focus({preventScroll: true});
    document.getElementById("announcement").textContent = `${routes[route] || "Overview"} updated.`;
  }
  function persistReview() {
    try { localStorage.setItem("recell-pilot-review-v1", JSON.stringify(review)); }
    catch (_) { storageAvailable = false; }
    const counter = document.getElementById("check-count");
    if (counter) counter.textContent = `${checkItems.filter(([key]) => review[key]).length} of ${checkItems.length}`;
    if (!storageAvailable && document.getElementById("storage-status"))
      document.getElementById("storage-status").textContent = "Browser storage is unavailable. Notes last for this session only; print the brief to retain them.";
  }
  function download(filename, content, type) {
    const blob = new Blob([content], {type}), url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function printBrief() {
    const ranked = meanForecasts(), b = D.dispatch_comparison.baseline, d = D.dispatch_comparison.aware;
    document.getElementById("print-report").innerHTML = `<p class="eyebrow">ReCell · Client discussion brief</p><h1>Evidence for an Indian C&I validation pilot</h1><p>India C&I research snapshot exported ${esc(D.generated_at.slice(0, 10))}. This brief summarizes the original illustrative INR comparison across six cells and the separately reported research extensions, independently of current dashboard filters.</p>
      <section><h2>What we have tested</h2><p>${D.cells.length} battery cells; ${D.counts.checkpoints} diagnostic checkpoints; ${D.counts.models} forecasting models; ${D.counts.seeds} seeds; ${D.solar_provenance.hours} hours of one household replay. Test cells are held out from training.</p>
      ${table(["Model", "SOH MAE (pp)", "SOH RMSE (pp)", "P10–P90 coverage"], ranked.map(r => [C.modelNames[r.model], fmt(r.mae_mean * 100, 3), fmt(r.rmse_mean * 100, 3), percent(r.coverage_80_mean)]))}<p>Errors average seeds within cells, then cells equally. SOH is relative to each cell’s first second-life measurement. XGBoost leads the aggregate reference comparison.</p></section>
      ${marketContext()}<section><h2>Modeled operating trade-off · INR</h2>${table(["Reference policy", "Electricity (₹)", "Estimated wear (₹)", "Combined (₹)", "Cycles"], [["C · Electricity only", rupees(b.electricity_cost_inr), rupees(b.estimated_degradation_cost_inr), rupees(b.electricity_plus_estimated_wear_inr), fmt(b.equivalent_full_cycles)], ["D · Wear-aware, λ = 1", rupees(d.electricity_cost_inr), rupees(d.estimated_degradation_cost_inr), rupees(d.electricity_plus_estimated_wear_inr), fmt(d.equivalent_full_cycles)]])}<p>C and median D share health and wear assumptions. No export revenue is credited in this INR scenario. Combined cost is electricity + estimated wear. Only energy charges and estimated wear are counted; the actual C&I bill also requires site-specific tariff components.</p></section>
      ${note("Original reference interpretation limits", "Six cells and a German household proxy replay; illustrative Indian C&I energy charges and pack cost; linear wear proxy; demand charges and backup value excluded; perfect solar/load foresight; fixed health during dispatch. No demonstrated lifetime extension, field saving or carbon benefit. Hardware and pack-level aging still need validation.")}
      ${R.brief(D, researchUI)}
      ${I.brief(D, researchUI)}
      <section><h2>Proposed decision: a data and calibration pilot</h2><p>Agree criteria before collecting new outcomes. Validate independent forecasting, uncertainty, wear calibration, operational constraints and measured economics against a matched baseline.</p><ul>${checkItems.map(([key, label]) => `<li>${review[key] ? "[Discussed]" : "[Open]"} ${label}</li>`).join("")}</ul><p>The checklist is a discussion aid, not an approval or signature.</p></section>${review.notes ? `<section><h2>Meeting notes</h2><p style="white-space:pre-wrap">${esc(review.notes)}</p></section>` : ""}<p class="small">Original reference: Stanford second-life (OSF 8JNR5) and OPSD/CoSSMic. Extensions: linked EV first-life, separate calendar cohort, I-BLEND Delhi demand and modeled NASA-resource PV. Exact source hashes are available in Sources &amp; snapshot. The original reference was exported ${esc(D.reference_generated_at.slice(0, 10))}; the integrated review was exported ${esc(D.generated_at.slice(0, 10))}.</p>`;
    window.print();
  }
  function sources() {
    document.getElementById("source-content").innerHTML = `<p>This snapshot retains the original INR reference and adds four completed research studies. It is not a live training or control service. Integrated export: ${esc(D.generated_at)}. Original reference export: ${esc(D.reference_generated_at)}.</p><p class="small muted mt">Battery source: <a href="https://osf.io/8jnr5/" target="_blank" rel="noopener">Stanford second-life dataset</a>. Household source: <a href="https://data.open-power-system-data.org/household_data/2020-04-15/" target="_blank" rel="noopener">OPSD/CoSSMic, version 2020-04-15</a> (CC BY 4.0). The German household and battery measurements are separate datasets. India C&I economics use the illustrative INR inputs in configs/india_ci.yaml; neither dataset is an Indian industrial measurement.</p><div class="note neutral mt"><strong>How these numbers are grounded</strong>The build verifies that forecast and dispatch provenance point to the same checkpoint data, selected predictions and solar inputs. The original reference was optimized in INR using its hashed India scenario configuration. A preserved reference can be reused without rerunning optimization; extension results come from separately completed studies. SHA-256 values below identify the exact exported artifact files.</div><ul class="source-list">${D.sources.map(s => `<li><strong>${esc(s.path)}${s.rows ? ` · ${s.rows.toLocaleString()} rows` : ""}</strong><span>${esc(s.sha256)}</span></li>`).join("")}</ul>`;
    document.getElementById("source-content").insertAdjacentHTML("beforeend", `<h3 class="mt">Completed research extensions</h3><p class="small">Saved completed-run and independent-review manifests are checked during export. Forecasts and schedules are not recalculated in the browser. New research views are not an operational model promotion.</p><ul class="source-list">${D.extensions.sources.map(s => `<li><strong>${esc(s.path)}${s.rows ? ` · ${s.rows.toLocaleString()} rows` : ""}</strong><span>${esc(s.sha256)}</span></li>`).join("")}</ul>`);
    document.getElementById("source-content").insertAdjacentHTML("beforeend", `<h3 class="mt">Model implementation evidence</h3><p class="small">Measured local pulse study, CPU selection and independently checked replay. Simscape/DGX and physical external validation remain open. BMS replay is synthetic.</p><ul class="source-list">${D.implementation.sources.map(s => `<li><strong>${esc(s.path)}</strong><span>${esc(s.sha256)}</span></li>`).join("")}</ul>`);
    document.getElementById("source-dialog").showModal();
  }
  document.addEventListener("click", event => {
    const lesson = event.target.closest("[data-lesson]");
    if (lesson) {
      event.preventDefault(); state.lesson = Number(lesson.dataset.lesson);
      if (currentRoute() !== "learn") location.hash = "learn"; else render(false);
      return;
    }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "start-guide") { state.lesson = 0; if (currentRoute() === "learn") render(true); }
    if (action === "previous-lesson") { state.lesson = Math.max(0, state.lesson - 1); render(false); }
    if (action === "next-lesson") { state.lesson = Math.min(window.RECELL_LESSONS.length - 1, state.lesson + 1); render(false); }
    if (action === "sources") sources();
    if (action === "close-sources") document.getElementById("source-dialog").close();
    if (action === "print") printBrief();
    if (action === "download") download("recell-analysis-snapshot.json", JSON.stringify(D, null, 2), "application/json");
    if (action === "download-guide") {
      const text = "ReCell — Guided project walkthrough\n\n" + window.RECELL_LESSONS.map((l, i) => {
        const el = document.createElement("div"); el.innerHTML = l.body;
        return `${i + 1}. ${l.title}\n${l.summary}\n\n${el.textContent}\n\n${l.formula}\n\n${l.example}\n\nLimit: ${l.caution}`;
      }).join("\n\n----------------\n\n");
      download("recell-guided-walkthrough.txt", text, "text/plain;charset=utf-8");
    }
  });
  document.addEventListener("change", event => {
    const target = event.target;
    if (target.dataset.state) {
      const key = target.dataset.state;
      state[key] = ["horizon", "seed", "fraction", "weight", "day", "researchFraction", "researchHorizon"].includes(key) ? Number(target.value) : target.value;
      render(false);
    }
    if (target.dataset.check) { review[target.dataset.check] = target.checked; persistReview(); }
  });
  document.addEventListener("input", event => {
    if (event.target.id === "pilot-notes") { review.notes = event.target.value; persistReview(); }
  });
  document.addEventListener("submit", event => {
    if (event.target.id === "metric-form") { event.preventDefault(); calculate(); }
  });
  window.addEventListener("hashchange", () => render(true));
  document.getElementById("run-status").textContent = `India C&I · reference, research & model implementation`;
  document.getElementById("snapshot-date").textContent = `Snapshot exported ${D.generated_at.slice(0, 10)}`;
  render();
})();
