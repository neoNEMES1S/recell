# ReCell client dashboard

Primary style source: Superdesign `mosaic-grid-architecture-style`, adapted for a readable analytical application.

Audience: nontechnical clients deciding whether to approve a validation pilot, and the project owner learning the methodology.
Task: understand the evidence, inspect real results, understand the calculations, and distinguish an implemented research prototype from deployment readiness.

Use a restrained editorial dashboard. Paper #F7F7F5 background; white panels; forest #1A3C2B primary; ink #172B22; muted #617067; thin #DDE3DB dividers. Mint #9EFFBF for emphasis; gold #F4D35E and coral #FF8C69 for sensitivity and caveats. Avoid gradients, shadows and decorative animation. Corners 4–8px for usability. Font: system sans for a self-contained offline application; use generous 16px body text, 13px minimum metadata, 38–48px page titles. Tabular numbers and monospace only for formulas, not body prose. Strong focus outlines; no color-only meanings.

Desktop layout: 220px forest sidebar with ReCell wordmark, workspace name and numbered destinations; roomy top bar with reference-run status, guided walkthrough button and print action. Main content max width 1250px, 32px gutters. Responsive sidebar becomes a compact horizontal navigation. No stock imagery: use actual charts as the visual focus.

Pages: Overview; Battery evidence; Forecast quality; Storage decisions; Learn the method; Pilot review. Six pages share one application shell. Plain-language headline before technical details. Persistent research-prototype label. Full formulas and provenance under explicit details disclosures.

Overview: title 'A second life, backed by evidence.'; three headline metrics: 6 cells / 111 checkpoints; 0.215 percentage-point best SOH RMSE (XGBoost); 18.8% fewer equivalent cycles in the modeled median policy comparison. A large model-comparison horizontal chart and a decision panel explaining the validation pilot. Use actual forecast RMSEs: XGBoost .2146 pp; ridge .2671; PGP-GRU .2739; quantile GRU .2838; GRU .3018; persistence .4393. A C vs D cost bridge states EUR13.13 vs EUR11.66 modeled electricity plus wear, NOT measured savings. Three bottom evidence statements: observed, modeled, still to validate.

Exploration: battery, model, checkpoint horizon, and wear-weight selectors. Forecast charts compare measured values to predictions; P10–P90 is an interval with nominal 80% coverage, not 80% accuracy. The aggregate averages seeds within cells, then cells equally. Dispatch sliders choose already solved scenarios, never claim live optimization. Label period June 2016 / 720 hours / one household replay. Show costs can be negative because of export revenue.

Learning: eight short sequential lessons with a previous/next control, plain-language analogy, exact formula and worked example. Include SOH, MAE, RMSE, MAPE, R², quantile loss, coverage, interval width, the GRU training loss, SOC balance, equivalent cycles, solar self-consumption, wear calibration and dispatch objective. Interactive toy examples explicitly labelled illustrative. Explain 100% SOH reference is first second-life measurement, not factory capacity.

Pilot review: what has been demonstrated; open scientific assumptions; proposed success criteria to agree with the client; approval checklist kept locally and clearly not formal sign-off. No invented readiness scores, customer claims or claims of proven lifetime extension.

Data: existing verified CSV/JSON artifacts; source hashes and downloaded snapshot accessible. No personal data, no credentials, no new model fitting. Design should work without external fonts, image downloads or a frontend framework.
