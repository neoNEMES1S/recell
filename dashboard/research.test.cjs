const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const C = require("./core.js");

const context = vm.createContext({});
vm.runInContext(fs.readFileSync(`${__dirname}/research.js`, "utf8"), context);
const R = context.ReCellResearch;
const u = {
  esc: String,
  fmt: (value, digits) => Number(value).toFixed(digits),
  rupees: C.moneyINR,
  panel: (title, subtitle, body) => `${title}\n${subtitle}\n${body}`,
  table: (headers, rows) => JSON.stringify({headers, rows}),
};
const D = {extensions: {
  calendar: {nonphysical_predictions: 44},
  controller: {primary: {difference_inr: 17.2473,
    descriptive_low_95_inr: .84099, descriptive_high_95_inr: 32.90489}},
  reports: {method: "reports/method.pdf"},
}};
const overview = R.overview(D, u);
for (const study of ["transfer", "calendar", "india", "controller"])
  assert.ok(overview.includes(`#research/${study}`));
assert.ok(overview.includes("44"));
assert.ok(overview.includes("+₹17.25"));
assert.ok(overview.includes("Higher is worse"));
assert.equal(R.overview({}, u), "");
const brief = R.brief(D, u);
assert.ok(brief.includes("+₹17.25 per 16 days; higher is worse"));
assert.ok(brief.includes("44 negative predictions retained"));
assert.ok(brief.includes("No M50T calibration"));
assert.ok(brief.includes("no field savings"));
console.log("Research overview and client-brief evidence checks passed.");
