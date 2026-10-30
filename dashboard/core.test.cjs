const assert = require("node:assert/strict");
const C = require("./core.js");
const example = C.exampleMetrics([98, 97, 96], [97.8, 97.4, 95.9]);
assert.ok(Math.abs(example.mae - 7 / 30) < 1e-12);
assert.ok(Math.abs(example.rmse - Math.sqrt(.07)) < 1e-12);
assert.ok(Math.abs(example.r2 - .895) < 1e-12);
assert.equal(C.exampleMetrics([0, 1], [0, 1]).mape, null);
assert.equal(C.exampleMetrics([1, 1], [1, 2]).r2, null);
assert.throws(() => C.exampleMetrics([1, 2], [NaN, 2]));
assert.throws(() => C.parseNumbers("98,,96"));
assert.equal(C.mean([null, 0, 2]), 1);
assert.equal(C.mean([null]), null);
assert.equal(C.reduction(10, 8), 20);
assert.equal(C.reduction(0, 8), null);
assert.equal(C.moneyINR(100000), "₹1,00,000.00");
assert.equal(C.moneyINR(-12.5), "-₹12.50");
assert.equal(C.moneyINR(-1e-8), "₹0.00");
assert.equal(C.moneyINR(null), "—");
const data = {
  forecast_summary: [{model: "xgboost", horizon: 0, unit: "soh", rmse_mean: .002}],
  fold_metrics: [{model: "xgboost", horizon: 0, cell_id: "A", unit: "soh",
    history_fraction: 1, rmse: .001}, {model: "xgboost", horizon: 0, cell_id: "A",
    unit: "soh", history_fraction: 1, rmse: .003}],
  dispatch_summary: [{cell_id: "A", scenario: "C_second_life", degradation_weight: 0,
    electricity_cost_eur: -5}, {cell_id: "B", scenario: "C_second_life",
    degradation_weight: 0, electricity_cost_eur: -3}]
};
assert.equal(C.forecastMetric(data, "xgboost", 0).rmse_mean, .002);
assert.equal(C.forecastMetric(data, "xgboost", 0, "A").rmse_mean, .002);
assert.equal(C.forecastMetric(data, "xgboost", 0, "A").rmse_std, null);
assert.equal(C.dispatchMetric(data, "C_second_life", 0).electricity_cost_eur, -4);
assert.equal(C.dispatchMetric(data, "C_second_life", 0, "A").electricity_cost_eur, -5);
assert.equal(C.dispatchMetric(data, "D_degradation_aware", 1), null);
console.log("Dashboard calculation checks passed.");
