(function () {
  const D = window.RECELL_DATA, money = window.ReCell.moneyINR;
  const b = D.dispatch_comparison.baseline, d = D.dispatch_comparison.aware;
"use strict";
window.RECELL_LESSONS = [
  {
    title: "Start with the decision", label: "The research question", destination: "overview",
    summary: "Can used-battery health forecasts support behind-the-meter solar storage at Indian commercial and industrial sites?",
    body: `<p>We are asking for a <strong>validation pilot</strong>. We have a working research pipeline and encouraging simulated behavior. We still need independent batteries, pack-level calibration and operational testing.</p><p>There are two different objectives: the forecasting model learns to make useful predictions; the storage optimizer chooses actions that balance electricity cost with an estimate of battery wear.</p>`,
    formula: "Measurements → health forecasts → operating scenarios → evidence for a pilot",
    example: "Six independently observed cells, 111 diagnostic checkpoints, one 720-hour German household proxy replay with illustrative INR economics. Indian C&I measurements remain a pilot requirement. Repeating predictions does not create more independent batteries.",
    caution: "Software completion and physical validation are different milestones. No readiness score or guaranteed return is claimed."
  },
  {
    title: "Measure how much charge remains", label: "From current to capacity", destination: "batteries",
    summary: "Capacity is the amount of electric charge a battery can deliver. We calculate it from current over time.",
    body: `<p>The instrument records time and current. Think of current as a flow rate: adding that flow over the discharge period gives capacity in ampere-hours (Ah).</p><p>We integrate four reviewed low-current discharge segments, excluding pulses, rests and recharge. We check the voltage range, sample gaps and agreement with the instrument’s own counters. Overlapping exports are deduplicated; ambiguous identities are excluded.</p>`,
    formula: "Capacity (Ah) = −Σ [(Iⱼ + Iⱼ₊₁) ÷ 2 × (tⱼ₊₁ − tⱼ)] ÷ 3600",
    example: "Illustrative: a constant 2 A discharge lasting 2 hours delivers 4 Ah. In this dataset discharge current is negative, so the minus sign makes delivered capacity positive.",
    caution: "Ah is charge capacity, not energy in kWh. The raw capacity test protocol matters; we do not treat every raw measurement row as a training target."
  },
  {
    title: "Separate health from charge", label: "SOH, SOC and the reference", destination: "batteries",
    summary: "Health describes the size of the remaining energy container. Charge describes how full that container is right now.",
    body: `<p><strong>State of Health (SOH)</strong> compares measured capacity with the first observed second-life capacity of that same cell. This starting reference is known before we forecast.</p><p><strong>State of Charge (SOC)</strong> is the fraction of current available energy held in the battery. A healthy battery can be empty; an aged battery can be fully charged.</p>`,
    formula: "SOH = measured capacity ÷ first observed second-life capacity",
    example: "Illustrative: 4.32 Ah ÷ 4.50 Ah = 0.96, or 96% SOH. Relative to a 5 Ah factory rating, the same measurement is 86.4% of nominal capacity.",
    caution: "100% on our SOH charts means the first second-life measurement—not a brand-new battery. Recoveries in measured capacity are preserved."
  },
  {
    title: "Give the model only the past", label: "Features and forecasting", destination: "forecasts",
    summary: "At each diagnostic checkpoint, the model sees the history available so far and predicts the next one or two checkpoints.",
    body: `<p>The predictors are SOH, elapsed days, prior cycling throughput, a pulse-resistance proxy, duty class and documented capacity at the end of first life. Temperature and EIS stay out of the initial model because their interpretation is not sufficiently verified.</p><p>Persistence repeats the latest health. Ridge learns a linear relationship. XGBoost combines small decision trees. GRUs read sequences. Quantile models return P10, a low forecast; P50, the median; and P90, a high forecast.</p>`,
    formula: "Past checkpoints → [P10, P50, P90] at each future checkpoint",
    example: "A two-checkpoint forecast is not a two-day forecast. Diagnostic visits are irregularly spaced. The low-to-high range is intended to cover 80% of outcomes over repeated forecasts.",
    caution: "A prediction interval is not a guarantee for an individual battery. We do not forecast a validated remaining lifetime or observed failure date."
  },
  {
    title: "Test on a battery we held back", label: "Fair evaluation", destination: "forecasts",
    summary: "A useful result must work on a different battery, rather than memorizing later measurements from the same one.",
    body: `<p>Each fold uses four cells to learn, one separate cell to select when training stops, and one held-out cell to evaluate. We rotate the test cell and repeat with three random seeds. Missing-value replacement and scaling are fitted only on training cells.</p><p>Limited-history tests retain the newest 10%, 25%, 50%, 75% or 100% of pre-origin observations. The origins and targets stay the same, so the comparison measures available context fairly.</p>`,
    formula: "4 training cells + 1 validation cell + 1 test cell; rotate × 6; repeat × 3 seeds",
    example: "We calculate metrics per seed and cell, average seeds within each cell, then average the six cells equally. A cell with more prediction rows does not dominate the headline.",
    caution: "The reduced-history models still train on full training-cell histories. The original SOH reference and cumulative-exposure metadata remain available. Six cells limit generalization."
  },
  {
    title: "Read an error without calling it accuracy", label: "Forecast metrics", destination: "forecasts",
    summary: "MAE measures the typical miss. RMSE makes large misses matter more. Neither should be subtracted from 100 to invent an accuracy score.",
    body: `<p>For each observation, error = prediction − measured value. <strong>MAE</strong> averages the absolute errors. <strong>RMSE</strong> squares errors, averages them, then takes the square root. <strong>MAPE</strong> expresses absolute error relative to each measured value. <strong>R²</strong> compares squared error with an observed-mean benchmark and can be negative.</p><p>For uncertainty, <strong>coverage</strong> counts how often the measurement lands between P10 and P90; the target is 80%. <strong>Interval width</strong> measures how broad that range is. Read both together: a very wide range can cover everything and still be unhelpful.</p>`,
    formula: "MAE = mean(|prediction − actual|)\nRMSE = √mean((prediction − actual)²)\nCoverage = count(P10 ≤ actual ≤ P90) ÷ count(all predictions)",
    example: "SOH RMSE 0.002146 is 0.2146 percentage points. Try the worked example below: errors of −0.2, +0.4 and −0.1 percentage points give MAE 0.2333 and RMSE 0.2646.",
    caution: "Our aggregate metrics average seeds, then cells. The example below calculates a single small sample; it does not replace the research results.", calculator: true
  },
  {
    title: "Understand what the neural model minimizes", label: "Training objective", destination: "forecasts",
    summary: "The physics-guided GRU balances prediction error, useful uncertainty and soft preferences about how health changes.",
    body: `<p>The point term penalizes median forecast error. Pinball loss trains the three quantiles with asymmetric penalties. For residual u = actual − quantile forecast, each quantile q uses max(q × u, (q − 1) × u).</p><p>We build a median trajectory from origin SOH and the next two forecasts. The monotonicity term penalizes upward increments above tolerance 0.002. The smoothness term penalizes changes in those increments. Scale s = 0.02 makes the terms comparable.</p>`,
    formula: "L = 1 × mean(((P50 − y)/s)²) + 1 × pinball/s\n    + 0.1 × mean(max((increment − 0.002)/s, 0)²)\n    + 0.1 × mean((change in increment / s)²)",
    example: "Vanilla GRU uses the scaled point term. The quantile-GRU ablation switches both physical penalty weights to zero. Validation selects the best epoch using prediction loss without these physical penalties.",
    caution: "These are soft trajectory preferences, not a validated electrochemical law. Smoothness is per checkpoint, not per equal time interval. Training loss is different from reported RMSE."
  },
  {
    title: "Translate a cell forecast into an operating assumption", label: "Health and wear conversion", destination: "dispatch",
    summary: "A future SOH forecast changes the assumed pack capacity. A training-cell exposure estimate turns predicted decline into a wear proxy.",
    body: `<p>Convert second-life-relative SOH to nominal health by multiplying by reference Ah ÷ nominal cell Ah. A nominal 10 kWh pack is scaled by that health fraction. The 10–90% SOC window permits an 80% swing of that health-adjusted capacity.</p><p>Training cells supply the median positive cycling Ah increment between checkpoints. Divide by twice nominal cell Ah to get expected equivalent cycles. Divide predicted nominal-health decline by that exposure and horizon to obtain wear per equivalent cycle.</p>`,
    formula: "Nominal health = forecast SOH × reference Ah ÷ nominal Ah\nAvailable energy = nominal pack kWh × nominal health\nWear per EFC = max(0, predicted nominal-health decline ÷ expected EFC over horizon)",
    example: "Saved G1 median case: nominal health ≈ 88.244%; health-adjusted capacity ≈ 8.824 kWh; SOC-window swing ≈ 7.060 kWh. The detailed conversion is available in Storage decisions.",
    caution: "This linear wear proxy needs calibration. It does not separate calendar aging or prove that cell-level estimates transfer to a pack. P10 changes both capacity and wear assumptions."
  },
  {
    title: "Follow the electricity and wear arithmetic", label: "Dispatch objective", destination: "dispatch",
    summary: "The optimizer can accept a higher electricity bill if it reduces estimated battery wear enough to improve the combined objective.",
    body: `<p>Net electricity cost is import cost minus export revenue. Equivalent full cycles (EFC) are internal charge-plus-discharge throughput divided by twice nominal pack energy. Estimated wear cost = replacement cost × predicted nominal-capacity loss ÷ loss budget.</p><p>The replay uses a 10 kWh nominal pack, 3 kW power, 90% round-trip efficiency and a 10–90% SOC window. Initial and final SOC are both 50%. Only surplus solar charges storage, and discharge serves remaining proxy demand. No grid arbitrage is modeled. INR inputs are illustrative: ₹10/kWh purchased energy, ₹0 export credit and ₹1,00,000 replacement cost. Demand charges, ToD variation, taxes, subsidies and backup value are excluded.</p>`,
    formula: "Objective = net electricity cost + λ × estimated wear cost\nEFC = Σ(η × charge + discharge/η) × 1 hour ÷ (2 × nominal kWh)\nWear cost = ₹1,00,000 × (wear per EFC × EFC) ÷ 0.20\nE[t+1] = E[t] + η × charge[t] − discharge[t]/η; η = √0.90",
    example: `INR scenario means: electricity-only policy ${money(b.electricity_cost_inr)} + ${money(b.estimated_degradation_cost_inr)} wear = ${money(b.electricity_plus_estimated_wear_inr)}. Wear-aware policy ${money(d.electricity_cost_inr)} + ${money(d.estimated_degradation_cost_inr)} wear = ${money(d.electricity_plus_estimated_wear_inr)}. Grid energy ₹10/kWh, export credit ₹0/kWh; these are illustrative C&I assumptions, not a DISCOM tariff.`,
    caution: "The objective uses λ-weighted wear; the comparison total always reports electricity + unweighted wear. Tariffs and wear are assumed, load/solar are perfectly known, and battery health stays fixed during the replay."
  },
  {
    title: "Turn findings into a pilot agreement", label: "The approval conversation", destination: "pilot",
    summary: "Ask the client to approve collecting the evidence needed for deployment—not to accept a claim that deployment is already proven.",
    body: `<p>Agree the operational site, representative batteries, measurement plan and baseline controller. Set acceptance criteria before evaluating new outcomes. Check forecasting error, uncertainty coverage and width, constraint compliance and measured operating costs.</p><p>The reference result favors XGBoost on average forecast error. PGP-GRU’s probabilistic forecasts are useful to investigate, but we should not hide the stronger baseline. The pilot should test whether better predictions or conservative assumptions actually improve operation.</p>`,
    formula: "Proposed pilot → independent measurements → pre-agreed evaluation → deployment decision",
    example: "A useful client question: What evidence and threshold would convince us to proceed? The review checklist records discussion points locally; it is not a signature or formal sign-off.",
    caution: "No carbon benefit, lifetime extension or realized savings has been established. The private hosted site is for owner review; client access is a separate decision."
  }
];

})();
