/* Shared, testable calculations. Saved metrics retain their original aggregation. */
(function (root) {
  "use strict";
  const modelNames = {
    persistence: "Persistence", linear: "Ridge regression", xgboost: "XGBoost",
    gru: "Vanilla GRU", pgp_gru: "Physics-guided GRU", quantile_gru: "Quantile GRU"
  };
  const scenarioNames = {
    A_no_battery: "A · No battery", B_conventional: "B · Full nominal capacity",
    C_second_life: "C · Electricity-only policy", D_degradation_aware: "D · Wear-aware policy",
    D_conservative: "P10 · Conservative assumptions"
  };
  function mean(values) {
    const valid = values.filter(v => typeof v === "number" && Number.isFinite(v));
    return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null;
  }
  function reduction(before, after) {
    return Number.isFinite(before) && Number.isFinite(after) && before > 0
      ? 100 * (before - after) / before : null;
  }
  function moneyINR(value) {
    return typeof value === "number" && Number.isFinite(value)
      ? new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR"})
        .format(Math.abs(value) < .005 ? 0 : value) : "—";
  }
  function forecastMetric(data, model, horizon, cell = "all") {
    if (cell === "all") {
      return data.forecast_summary.find(r => r.model === model && r.horizon === horizon
        && r.unit === "soh") || null;
    }
    const rows = data.fold_metrics.filter(r => r.model === model && r.horizon === horizon
      && r.cell_id === cell && r.unit === "soh" && r.history_fraction === 1);
    if (!rows.length) return null;
    const result = {model, horizon, unit: "soh"};
    for (const key of ["mae", "rmse", "mape_percent", "r2", "quantile_loss", "coverage_80",
      "interval_width", "empirical_q10", "empirical_q50", "empirical_q90"]) {
      result[key + "_mean"] = mean(rows.map(r => r[key]));
      result[key + "_std"] = null; // Cell-to-cell SD does not apply to a single cell.
    }
    return result;
  }
  function dispatchMetric(data, scenario, weight, cell = "all") {
    const rows = data.dispatch_summary.filter(r => r.scenario === scenario
      && r.degradation_weight === weight && (cell === "all" || r.cell_id === cell));
    if (!rows.length) return null;
    const result = {scenario, degradation_weight: weight, cell_id: cell};
    for (const key of Object.keys(rows[0])) {
      if (!["scenario", "degradation_weight", "cell_id"].includes(key))
        result[key] = mean(rows.map(r => r[key]));
    }
    return result;
  }
  function exampleMetrics(actual, predicted) {
    if (!Array.isArray(actual) || !Array.isArray(predicted) || actual.length < 2
      || actual.length !== predicted.length || ![...actual, ...predicted].every(Number.isFinite))
      throw new Error("Enter at least two finite numbers in each list, with matching lengths.");
    const errors = actual.map((v, i) => predicted[i] - v);
    const mse = mean(errors.map(e => e * e));
    const center = mean(actual);
    const variance = mean(actual.map(v => (v - center) ** 2));
    return {errors, mae: mean(errors.map(Math.abs)), rmse: Math.sqrt(mse),
      mape: actual.every(v => Math.abs(v) > 1e-8)
        ? 100 * mean(errors.map((e, i) => Math.abs(e / actual[i]))) : null,
      r2: variance > 0 ? 1 - mse / variance : null};
  }
  function parseNumbers(text) {
    const pieces = text.split(",").map(s => s.trim());
    if (pieces.some(s => s === "")) throw new Error("Separate numbers with commas; do not leave empty entries.");
    return pieces.map(Number);
  }
  const api = {modelNames, scenarioNames, mean, reduction, forecastMetric, dispatchMetric,
    exampleMetrics, parseNumbers, moneyINR};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReCell = api;
})(typeof window === "undefined" ? globalThis : window);
