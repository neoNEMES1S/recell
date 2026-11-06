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
    title: "Learn from an earlier life without leaking the test", label: "First-life transfer", destination: "research/transfer",
    summary: "Earlier history can initialize a model while each test battery stays physically unseen.",
    body: `<p>The v3 comparison uses past SOH, elapsed life-stage days and verified stage-relative Ah. First and second lives never become one uninterrupted sequence. Permitted first-life examples pretrain the encoder; fine-tuning resets the head and optimizer.</p><p>The held-out target and target-validation batteries supply no source gradients. W5 supplies independent source validation only. Future labels never fill missing exposure inputs.</p>`,
    formula: "x[j] = [past SOH[j], stage days[j], stage-relative Ah[j]]\nTransfer contrast = matched transfer RMSE − matched scratch RMSE",
    example: "At 10% context and the next checkpoint: scratch PGP-GRU 0.2972 SOH pp, transfer 0.2916 pp, XGBoost 0.2534 pp. The transfer improvement is small, and G1/W8 worsen.",
    caution: "Full-history v2 remains failed. v3 is a separate verified-prefix amendment, with only 3–18 source examples per fold and six familiar target batteries."
  },
  {
    title: "Keep calendar aging separate until calibrated", label: "Calendar-aging research", destination: "research/calendar",
    summary: "A different cell's storage curve is not automatically our pack's wear law.",
    body: `<p>The separate study compares constant health, age-only loss and age/temperature/SOC-conditioned loss across eight held-out cell types and 218 longitudinal cells. No LG M50T is present.</p><p>Storage experiments include periodic diagnostic cycling. Their calendar and diagnostic losses are not separately identified. Our existing throughput proxy already reflects mixed aging.</p>`,
    formula: "SOH = diagnostic capacity / first accepted capacity\nFinal error = mean types(mean cells(cell RMSE))\nIdentify the represented losses before combining aging terms",
    example: "Age-only RMSE is 12.16 pp and conditioned-model RMSE is 7.29 pp. However, 44 negative SOH predictions and a worst absolute error of 73.71 pp remain in the metrics.",
    caution: "Do not clip away the failures or add this curve to mixed-aging wear. M50T calibration, physical probe mapping, storage conditions and intended-use clarification remain open."
  },
  {
    title: "Separate a meter from a solar scenario", label: "Indian demand and modeled PV", destination: "research/india",
    summary: "Measured demand, modeled PV and day-ahead forecasts supply different evidence.",
    body: `<p>Delhi demand uses 60 training, 15 validation and 16 test days. A 50/50 daily/weekly blend is chosen on validation only and frozen before test scoring.</p><p>NASA hourly irradiance supplies a horizontal PV scenario, not inverter measurements. Quarter-hour values retain the 60-minute resource label. The controller forecasts PV by repeating previous-day modeled output, not by using a live weather service.</p>`,
    formula: "Load forecast = 0.5 × previous day + 0.5 × previous week\nModeled PV kW = min(32, 40 × 0.96 × GHImean / 1000)\nQuarter energy = mean kW × 0.25 h",
    example: "Selected load-blend RMSE is 2.150 kW versus 2.846 kW for the weekly baseline. On 7 December it predicts nearly the right peak magnitude but puts the peak 570 minutes too early.",
    caution: "Lower RMSE does not establish billed savings. Actual PV, meter topology, reporting delay, demand charges and kVAh/PF remain unverified. Ambient weather is not battery temperature."
  },
  {
    title: "Test the decision as well as the forecast", label: "Common controller objective", destination: "research/controller",
    summary: "Forecast accuracy and operating value require separate matched comparisons.",
    body: `<p>The quarter-hour study compares six policies with common physical capacity and operating limits within each hypothetical case. Only four target-training cells calibrate wear. Current-interval mean feedback is ideal offline recourse, not live hardware.</p><p>A common wear proxy evaluates all policies. A terminal inventory adjustment accounts for unequal final stored energy. SOC carries continuously across the 16-day period.</p>`,
    formula: "E[t+1] = E[t] + (η × charge[t] − discharge[t]/η) × 0.25 h\nReference score = grid charge + common wear − v × (Efinal − Einitial)\nv = ₹10 × √0.90 per internal kWh",
    example: "Transfer minus scratch: energy −₹88.16, common wear +₹93.58, inventory +₹11.82. The unrounded total is +₹17.25 per 16 days: less favorable under this proxy despite slightly better health forecasts.",
    caution: "The ranking reverses when the unvalidated evaluation-wear coefficient changes. These are scenario scores, not measured wear or customer bills. The no-storage policy has the lowest observed mean score in this particular scenario."
  },
  {
    title: "Model the immediate voltage response", label: "Dynamic electrical model", destination: "implementation/electrical",
    summary: "A one-RC circuit explains a fast voltage drop and slower relaxation.",
    body: `<p>The resistance-only model gives an instantaneous current-dependent voltage drop. A resistor-capacitor branch adds polarization with a time constant. It represents short-term electrical dynamics, while the health GRU forecasts capacity at future diagnostics.</p><p>The general engine requires an explicit OCV/SOC table and known initial state. The measured benchmark uses a narrower constant-OCV approximation for short pulse windows; it does not invent a global equilibrium curve.</p>`,
    formula: "V = OCV − R0 × I − v1\ndv1/dt = (R1 × I − v1) / τ\nSOC change = − I × seconds / (3600 × capacity Ah)",
    example: "With a 1 A discharge for 360 seconds and a 2 Ah cell, SOC falls by 0.05, or five percentage points. An ohmic resistance of 0.03 Ω produces a 30 mV instantaneous drop.",
    caution: "Voltage-response accuracy does not establish SOH accuracy, thermal safety, pack calibration or lifetime. Initial state, current sign, sample timing and the OCV reference must match."
  },
  {
    title: "Understand the new measured comparison", label: "Chronological pulse validation", destination: "implementation/electrical",
    summary: "Hold out later diagnostics and keep the first measurement's role explicit.",
    body: `<p>The audit accepts 333 pulse/rest/charge windows from 111 diagnostic sessions across six cells. Each cell's first diagnostic calibrates its own parameters. RPT-2 is validation, and RPT-3 onward provides 297 test windows.</p><p>The observed initial voltage anchors each short window and is excluded from error scoring. Error is computed within each window, then averaged within physical cells and across six cells equally.</p>`,
    formula: "Window RMSE mV = 1000 × sqrt(mean((Vpred − Vmeasured)²))\nStudy score = mean cells(mean held-out windows(window RMSE))",
    example: "One-RC mean test RMSE is 4.400 mV versus 8.182 mV for the resistance-only baseline. The interface reports a selected window's own error separately from these aggregate values.",
    caution: "These are later tests of known cells. An independent unseen-cell cohort, equilibrium OCV/SOC map and physical temperature assignment are still missing."
  },
  {
    title: "Choose on validation and retain the stronger baseline", label: "Bounded AI selection", destination: "implementation/ai",
    summary: "A larger search can improve validation fit without improving held-out performance.",
    body: `<p>The new CPU comparison registers twelve tree/GRU parameter settings plus three fixed references. Six outer folds and three seeds produce 270 validation trials. Each fold chooses using its own validation cell before scoring its test cell.</p><p>Rotating validation cells are not pooled into a global winner and then reused as untouched tests. All 2,610 test forecasts are independently replayed from saved model files.</p>`,
    formula: "Selected configuration for fold f = argmin permitted validation RMSE\nTest error is reported after that fold's selection is sealed",
    example: "Mean next-checkpoint RMSE is 0.2465 SOH pp for the selected models versus 0.2187 pp for fixed XGBoost. The difference interval includes zero; tuning has not established superiority.",
    caution: "This remains development on six familiar cells. Completed CPU experiments are not DGX evidence. An explicit CUDA request now fails if no CUDA device exists."
  },
  {
    title: "Distinguish software checks from life evidence", label: "BMS, Simscape and SOL gates", destination: "implementation/interfaces",
    summary: "A working adapter or simulation interface needs real observations before its application claims are validated.",
    body: `<p>The BMS adapter checks units, identities, clocks and measurement quality. Its current replay uses 60 explicitly synthetic electrical records. Health output stays unavailable without the diagnostic/history inputs required by the model.</p><p>Simscape numeric export is checked, but MATLAB source has not been run. SOL is not yet defined. A life model needs a declared threshold and units; if the last measurement is above threshold, the observed life is right-censored.</p>`,
    formula: "Effective capacity = forecast SOH × matching reference capacity\nObserved threshold crossing lies between the last above-threshold and first below-threshold tests",
    example: "A cell above the threshold at day 100 and below it at day 130 gives a crossing interval [100, 130], not an observed failure exactly at day 130. No threshold is assumed for the current inventory.",
    caution: "A synthetic replay, source file or exported MAT case does not close real BMS, Simscape, DGX, independent cohort or lifetime-validation requirements."
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
