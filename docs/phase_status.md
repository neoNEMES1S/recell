# Phase status

## Phase 1 — implemented

- Python package under `src/second_life_battery`, environment metadata and uv lock.
- Local Python 3.11 environment with inspection and development dependencies installed.
- Research dependencies declared as an optional extra; future module directories reserved.
- YAML configuration, JSON logging, ignore rules and three notebook entry points.
- README, raw-data acquisition instructions and scientific review gates.

Assumptions: Python 3.11 is the reproducibility target. The setup stage requires CPU
only. SOH is declared relative to first observed second-life RPT, pending target parsing.
No future measurements may determine a reference capacity at an earlier forecast origin.

## Phase 2 — structural inspection implemented and run on real data

- Downloaded the official OSF version-2 archive; verified its published SHA-256.
- Extracted with path validation and CRC checking, preserving the original hierarchy.
- Inspected every dataset file and every workbook sheet; recorded hashes and errors.
- Reviewed 865 header locations across 529 workbooks and saved those locations in config.
- Recorded six path-based cell identities, duty assignments with publication provenance,
  column availability, full row counts and native date ranges.
- Identified two conflicting cell labels, one empty capacity workbook, twelve multi-cell
  EIS workbooks and opaque cycling MAT objects.

Generated outputs (recreate with `python scripts/inspect_dataset.py --config configs/base.yaml`):

- `outputs/inventory/dataset_manifest.json`
- `outputs/inventory/files.csv`
- `outputs/inventory/column_availability.csv`
- `outputs/inventory/inspection_report.md`
- `outputs/inventory/inspection.jsonl`
- `outputs/inventory/config.snapshot.yaml`
- `outputs/inventory/environment.json`

Source/acquisition records: `docs/osf_file_listing.json`, `docs/dataset_findings.md`,
`configs/reviewed_headers.json`. Raw archive and extraction are under
`data/raw/stanford_second_life/`. Notebook analysis reads these outputs rather than
embedding hand-entered research results.

## Verification

`python -m pytest -q`: 23 tests cover workbook preambles/multiple sheets, duplicate
headers, missing values, native datetimes, both MATLAB storage families, corrupt files,
empty datasets, bad configurations, output isolation, sampling completeness, parallel
inspection, cell-label conflicts, checksum checks and unsafe archive paths.
`ruff check src scripts tests` checks the Python code. The real-data full scan confirms
633 supported files read successfully; 144 metadata/script files remain listed and
hashed as unsupported content. Bundled MATLAB code was not executed.

## Remaining gate before phase 3

Review identity conflicts and multi-cell EIS layouts, establish physical sensor units
and current sign, reconcile split/duplicate exports, verify diagnostic step sequences,
and choose a consistent discharge-capacity calculation. File timestamps are naive;
no timezone has been inferred. Late campaign coverage differs by battery.

Phase 3 parsers, target extraction, EDA, baselines, leakage tests, GRUs, uncertainty,
limited-history experiments and dispatch optimization are deliberately not implemented
in this phase. Capacity/SOH, throughput, sequence, loss, metric and optimizer tests
must accompany those modules when they exist. No research-model comparison is claimed.
