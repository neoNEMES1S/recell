# ReCell client dashboard

A buildless browser dashboard over saved research results. The interface implements
the approved Superdesign draft `fb78883f-9918-44f8-b1d1-e015dafbb8eb` with audited
metrics, seven views and fourteen teaching lessons. No external frontend packages,
CDN scripts or runtime API calls are required.

From the ReCell repository root:

```bash
.venv/bin/python scripts/build_dashboard.py
open dashboard/dist/index.html
```

Alternatively, serve `dashboard/dist` with Python's HTTP server. The exporter needs
reference artifacts plus the completed transfer/calendar/Indian demand/PV/controller
runs and their independent review manifests. It checks saved artifact hashes,
review/completion links and chart clocks. It never retrains or reoptimizes the
extension studies. The browser selects saved results only.

The default build re-optimizes the original 42 reference cases in INR. When the
preserved reference snapshot is present, reuse its exact values without optimization:

```bash
.venv/bin/python scripts/build_dashboard.py \
  --reference-snapshot outputs/dashboard/reference_20261023/data.js
```

That earlier dashboard was preserved before integration. Schema 2 `dist/data.js`
contains separate reference/extension sections; `reference_generated_at` identifies
the old reference. Four unchanged review PDFs are copied into `dist/reports/`.

The presentation targets Indian commercial and industrial behind-the-meter storage.
All costs use INR and Indian digit grouping. Assumptions are ₹10/kWh flat grid energy,
₹0/kWh export credit and ₹1,00,000 replacement cost for the 10 kWh reference pack.
These are illustrative inputs, not a DISCOM tariff, a market quotation or an FX
conversion. The German household power profile remains an explicitly identified
research proxy. Original EUR research outputs are preserved. Demand charges, ToD
variation, taxes, duties, financing, installation, O&M, subsidies and backup value
are excluded. These assumptions describe the original reference, not every new
study. A real C&I pilot requires paired site measurements and its full tariff.

## Research extensions

- `#research/transfer`: six matched arms, context/horizon selectors, per-cell
  negative-transfer cases, uncertainty and paired primary contrasts. v3 is
  separate from the failed full-history v2 gate.
- `#research/calendar`: held-out-type errors, predefined extrapolation/swap-note
  sensitivities and all 44 primary negative predictions. No M50T application or
  additive calendar wear is implied.
- `#research/india`: five saved load forecasts, test-day selectors, measured
  Delhi demand and explicitly modeled PV. New quarter-hour charts use IST;
  60-minute NASA resource resolution remains visible.
- `#research/controller`: six policy score components, the unfavorable primary
  transfer result, uncertainty, fixed-path wear sensitivities and saved power/SOC
  paths. Schedules identify a single health case and seed 42. Summary scores
  average all three seeds within cells, then six cells equally. This generic
  pack is 40 kWh/20 kW; its assumptions differ from the original reference.

Overview, print brief, source hashes, full analysis download, learning guide and
pilot discussion include these extensions. The original forecasts/dispatch have
reference labels. Research visibility does not promote a model for operation or
establish a customer bill saving, measured wear reduction or investment case.

Run calculation checks with `node dashboard/core.test.cjs`, research presentation
checks with `node dashboard/research.test.cjs`, and exporter tests with
`.venv/bin/python -m pytest tests/test_dashboard.py tests/test_research_dashboard.py -q`
from the repository root.

Presentation order: Overview → Battery evidence → Reference forecasts/dispatch →
Research extensions → Pilot review. Learn the method covers formulas and examples.
Print brief includes reference and extension findings, independent of selected
filters, with the current browser's discussion checklist and notes. Save it as PDF
using the browser print dialog. These controls never record a formal approval.

The hosted deployment is owner-private. Sharing a URL alone does not grant clients
access. It contains the authorized research snapshot; no raw workbook or credentials
are included. The deployed static artifact can also be opened offline. Meeting notes
are browser-local and are not synchronized between devices or local/hosted origins.

The source and generated assets are packaged through Sites using the project ID in
the local `.openai/hosting.json`. Hosting connection metadata and generated results
are ignored by ReCell's Git repository. Cloning the source does not grant access
to the hosted project or include its generated research snapshot.
