# ReCell client dashboard

Primary style source: Superdesign `mosaic-grid-architecture-style`, adapted for a readable analytical application.

Audience: nontechnical clients deciding whether to approve a validation pilot, and the project owner learning the methodology.
Task: understand the evidence, inspect real results, understand the calculations, and distinguish an implemented research prototype from deployment readiness.

Use a restrained editorial dashboard. Paper #F7F7F5 background; white panels; forest #1A3C2B primary; ink #172B22; muted #617067; thin #DDE3DB dividers. Mint #9EFFBF for emphasis; gold #F4D35E and coral #FF8C69 for sensitivity and caveats. Avoid gradients, shadows and decorative animation. Corners 4–8px for usability. Font: system sans for a self-contained offline application; use generous 16px body text, 13px minimum metadata, 38–48px page titles. Tabular numbers and monospace only for formulas, not body prose. Strong focus outlines; no color-only meanings.

Desktop layout: 220px forest sidebar with ReCell wordmark, workspace name and numbered destinations; roomy top bar with reference-run status, guided walkthrough button and print action. Main content max width 1250px, 32px gutters. Responsive sidebar becomes a compact horizontal navigation. No stock imagery: use actual charts as the visual focus.

Pages: Overview; Battery evidence; Forecast quality; Storage decisions; Learn the method; Research extensions; Pilot review. Seven views share one shell. Research extensions has four tabs: first-life transfer, calendar aging, Indian demand/modeled PV and controller comparison. Reuse established panels, tables, charts, notes and selectors. Persistent research-prototype label; formulas/provenance under explicit disclosures.

Overview: lead with completed research extensions and distinguish them from the original six-cell / German-household demonstration. All money uses INR from the verified snapshot, not FX conversion. Retain unfavorable findings: a small transfer-GRU improvement with XGBoost lowest mean; 44 negative calendar predictions; transfer-minus-scratch controller score +INR17.25 per 16 days under a common unvalidated proxy. No field savings established. Bottom evidence statements: observed, modeled, still to validate.

Exploration: battery, model, checkpoint horizon, and wear-weight selectors. Forecast charts compare measured values to predictions; P10–P90 is an interval with nominal 80% coverage, not 80% accuracy. The aggregate averages seeds within cells, then cells equally. Dispatch sliders choose already solved scenarios, never claim live optimization. Label period June 2016 / 720 hours / one household replay. Show costs can be negative because of export revenue.

Learning: fourteen short sequential lessons with previous/next controls, formulas and worked examples. Include original metrics plus physical-cell-disjoint transfer, separate calendar aging, measured Indian demand versus modeled PV, and the quarter-hour wear/inventory objective. Toy examples are illustrative. Explain first-observed SOH is not factory capacity; improved forecasts do not establish operating savings.

Pilot review: what has been demonstrated; open scientific assumptions; proposed success criteria to agree with the client; approval checklist kept locally and clearly not formal sign-off. No invented readiness scores, customer claims or claims of proven lifetime extension.

Data: existing verified CSV/JSON artifacts; source hashes and downloaded snapshot accessible. No personal data, no credentials, no new model fitting. Design should work without external fonts, image downloads or a frontend framework.
