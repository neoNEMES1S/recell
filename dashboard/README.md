# ReCell client dashboard

A buildless browser dashboard over saved research results. The interface implements
the approved Superdesign draft `fb78883f-9918-44f8-b1d1-e015dafbb8eb` with audited
metrics, six analysis views and ten teaching lessons. No external frontend packages,
CDN scripts or runtime API calls are required.

From the ReCell repository root:

```bash
.venv/bin/python scripts/build_dashboard.py
open dashboard/dist/index.html
```

Alternatively, serve `dashboard/dist` with Python's HTTP server. The exporter needs
the local checkpoints, LOBO, limited-history, analysis and dispatch artifacts. It
checks the recorded source hashes and matched C/D cost assumptions before export,
then re-optimizes all 42 health/weight cases in INR using `configs/india_ci.yaml`.
This requires the existing research/CVXPY environment; no model retraining is needed.
`dist/data.js` holds the generated snapshot. Rebuild after rerunning experiments;
the page never trains a model or recalculates an optimization schedule.

The presentation targets Indian commercial and industrial behind-the-meter storage.
All costs use INR and Indian digit grouping. Assumptions are ₹10/kWh flat grid energy,
₹0/kWh export credit and ₹1,00,000 replacement cost for the 10 kWh reference pack.
These are illustrative inputs, not a DISCOM tariff, a market quotation or an FX
conversion. The German household power profile remains an explicitly identified
research proxy. Original EUR research outputs are preserved. Demand charges, ToD
variation, taxes, duties, financing, installation, O&M, subsidies and backup value
are excluded. A real C&I pilot must supply Indian site data and its full tariff.

Run calculation checks with `node dashboard/core.test.cjs` and exporter tests with
`.venv/bin/python -m pytest tests/test_dashboard.py -q` from the repository root.

Presentation order: Overview → Battery evidence → Forecast quality → Storage
decisions → Pilot review. Use Learn the method for formulas and worked examples.
Print brief creates a report of the reference comparison, independent of selected
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
