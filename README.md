# ReCell

**Physics-guided battery health forecasting for second-life solar storage.**

ReCell is a Python research project investigating how the remaining capacity of used
EV batteries can inform their operation in solar energy storage. It combines a
probabilistic health-forecasting pipeline with degradation-aware storage optimization,
using real second-life lithium-ion battery aging data from Stanford Energy Control Lab.

> **Development status:** The 13-phase research prototype is implemented, with real-data
> targets, six-model forecasting experiments, limited-history evaluation and solar-storage
> replay results. See [phase status](docs/phase_status.md), [methods](docs/methods.md) and
> [results](docs/results.md). Dispatch wear and tariffs are explicit scenario assumptions.

## Research objective

**Can a physics-guided probabilistic sequence model forecast second-life battery
health for unseen cells with limited historical data, and can those forecasts improve
solar-storage dispatch?**

The project targets six connected tasks:

1. Inspect and preprocess cycling and diagnostic measurements.
2. Estimate State of Health (SOH) from measured discharge capacity.
3. Forecast future capacity/SOH and quantify uncertainty.
4. Compare against persistence, linear regression, XGBoost, and vanilla GRU baselines.
5. Evaluate unseen-battery generalization and limited-history performance.
6. Use health forecasts in a degradation-aware solar-storage optimizer.

Full research title: *Physics-Guided Probabilistic Health Forecasting and
Degradation-Aware Optimization of Second-Life EV Batteries for Solar Energy Storage*.

## What works today

| Component | Status |
| --- | --- |
| Python environment, package structure, configuration, and logging | Implemented |
| Dataset download verification and safe archive extraction | Implemented |
| Excel/CSV/TSV inspection and MATLAB metadata inspection | Implemented |
| File hashes, reviewed headers, row counts, and missingness reports | Implemented |
| Cell-label conflict detection and inspection notebook | Implemented |
| Semantic parsing, RPT capacity extraction, SOH, and EDA | Implemented; 111 checkpoints |
| Baselines, GRU, PGP-GRU, and evaluation experiments | Run; six cells, three seeds |
| Solar/load interface and CVXPY dispatch optimization | Run; 720-hour household replay |

The current stage runs on CPU. See the [phase report](docs/phase_status.md) for
completed work, validation, assumptions, and remaining scientific limitations.

## Dataset

ReCell uses the Stanford Energy Control Lab **Second-life lithium-ion battery aging
dataset based on grid storage cycling**, described by Moy et al. in *Data in Brief*
(2024).

- **Data:** [OSF 8JNR5](https://osf.io/8jnr5/)
- **Dataset DOI:** [10.17605/OSF.IO/8JNR5](https://doi.org/10.17605/OSF.IO/8JNR5)
- **Paper DOI:** [10.1016/j.dib.2024.111046](https://doi.org/10.1016/j.dib.2024.111046)

The study follows six previously aged LG Chem INR21700-M50T cells under residential
and commercial stationary-storage duty cycles. Measurements include cycling exports,
Reference Performance Tests (RPTs), capacity tests with pulses, and EIS data.

### Findings from the inspected release

The version-2 archive downloaded on October 14, 2026 was verified against the
SHA-256 published by OSF.

| Inventory item | Observed value |
| --- | ---: |
| Files in the extracted dataset root | 777 |
| Excel workbooks | 542 |
| MATLAB data files | 91 |
| Workbook sheets fully scanned | 1,408 |
| Observed cell labels | G1, V4, V5, W8, W9, W10 |
| Cycling / RPT directories | 18 / 19 |
| Raw rows in Channel sheets | 10,546,631 |
| Native timestamp coverage | October 2022–February 2025 |

These are inventory findings, not model results. Raw rows are not independent samples
or validated capacity targets. The inspection identified two conflicting cell labels,
one empty capacity workbook, substantial resistance-column missingness, and uneven
late-campaign coverage. Timestamp timezone and sensor assignments still require review.

See [dataset findings](docs/dataset_findings.md) for the evidence and unresolved issues.
Raw data and generated outputs are excluded from Git; cloning this repository does
not download the dataset.

## Quick start

Use Python 3.11 and `uv` for the reference environment. Dataset acquisition also uses
`curl`. Run the following commands in a POSIX shell.

### 1. Clone and install

```bash
git clone https://github.com/neoNEMES1S/recell.git
cd recell
uv sync --locked --extra dev
source .venv/bin/activate
```

`uv.lock` pins dependency versions. The Python distribution is named
`second-life-battery-ai`; its import namespace is `second_life_battery`.

<details>
<summary>Alternative installation with pip</summary>

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

This installs the declared version ranges rather than reproducing the uv lock exactly.

</details>

### 2. Download and verify the dataset

For a fresh checkout, download the approximately 2.15 GB archive and extract it:

```bash
mkdir -p data/raw/stanford_second_life
curl --fail --location --retry 3 https://osf.io/download/j2ne9/ \
  --output data/raw/stanford_second_life/SL_Dataset_SECL_INR21700-M50T.zip

python scripts/extract_dataset.py \
  --archive data/raw/stanford_second_life/SL_Dataset_SECL_INR21700-M50T.zip \
  --metadata docs/osf_file_listing.json \
  --destination data/raw/stanford_second_life/extracted
```

The extractor checks the archive size and SHA-256 against the saved OSF metadata,
rejects unsafe archive paths, and refuses to overwrite an existing extraction.
Skip this step if the verified dataset is already present. An upstream archive change
requires reviewing and updating the saved acquisition metadata.

The default configuration expects:

```text
data/raw/stanford_second_life/
├── SL_Dataset_SECL_INR21700-M50T.zip
└── extracted/
    └── SL_Dataset_SECL_INR21700-M50T/
        ├── cycling_tests/
        └── diagnostic_tests/
```

For a different location, pass `--raw-dir` pointing to the directory containing those
two test folders. Preserve relative file paths so the reviewed header mappings match.
See [acquisition details](data/raw/README.md).

### 3. Generate the inventory

```bash
python scripts/inspect_dataset.py --config configs/base.yaml
```

The default configuration scans every row using four worker processes. For a fast
structural preview, set `inspection.scan_limit: 200` in the configuration. Sampled
counts and date ranges are marked incomplete; `--full-scan` overrides that limit.

To preserve a separate inspection run:

```bash
python scripts/inspect_dataset.py --config configs/base.yaml \
  --full-scan --output-dir outputs/inventory_full
```

| Output in `outputs/inventory/` | Contents |
| --- | --- |
| `dataset_manifest.json` | Source hashes, identities, sheets, columns, counts, date ranges, and quality flags |
| `files.csv` | File-level inventory |
| `column_availability.csv` | Missing values per reviewed column and scan completeness |
| `inspection_report.md` | Human-readable status and review steps |
| `inspection.jsonl` | Structured events and errors |
| `config.snapshot.yaml` | Resolved settings used for the run |
| `environment.json` | Python, platform, and package versions |

Exit codes are `0` for completed structural inspection, `1` for file-read failures,
and `2` for missing, empty, or unsupported-only datasets. Scientific target validation
remains a separate step even when inspection succeeds. Unsupported files are listed
and hashed; malformed files are retained in the report with their errors.

### 4. Run checks

```bash
python -m pytest -q
ruff check src scripts tests
```

Tests cover inspection, archive integrity, capacity extraction, causal features, fold
separation, losses, metrics, recurrence, meter preparation and dispatch constraints.
Synthetic test fixtures are never used as research observations.

To open the inspection notebook, install the optional research environment:

```bash
uv sync --locked --extra dev --extra research
jupyter lab notebooks/01_dataset_inspection.ipynb
```

The EDA and results notebooks read generated tables and figures; they do not retrain models.

### 5. Reproduce the research pipeline

Install the optional research dependencies before these commands:

```bash
uv sync --locked --extra dev --extra research
source .venv/bin/activate
python scripts/prepare_data.py
python scripts/run_eda.py
python scripts/run_lobo_cv.py
python scripts/run_limited_history_experiment.py
python scripts/analyze_results.py
```

The reference config runs six models, six held-out batteries and three seeds, with
1- and 2-checkpoint horizons. Limited-history experiments keep forecast origins fixed.
Training is on CPU; raw parsing uses caches verified against the manifest hashes.

Download the pinned OPSD/CoSSMic household data for the dispatch replay:

```bash
mkdir -p data/raw/solar
curl --fail --location --retry 3 \
  https://data.open-power-system-data.org/household_data/2020-04-15/household_data_60min_singleindex.csv \
  --output data/raw/solar/household_data_60min_singleindex.csv
python scripts/prepare_solar_data.py
python scripts/run_dispatch.py
```

`run_dispatch.py` also prepares the meters, verifies the forecast dataset hash and
exports schedules, assumptions, source hashes and figures. Existing output filenames
are replaced when rerunning a stage. No model fitting is required to rerun dispatch.

| Generated location | Contents |
| --- | --- |
| `data/processed/` | Checkpoints, cycling summaries, source audits and solar/load inputs |
| `outputs/figures/eda/`, `outputs/tables/` | Dataset plots and descriptive tables |
| `outputs/lobo/` | Predictions, fold metrics, model checkpoints and provenance |
| `outputs/limited_history/` | Matched-origin results for five history fractions |
| `outputs/analysis/` | Calibration, comparisons, importance and failure cases |
| `outputs/dispatch/` | Seven scenario/weight combinations per cell, schedules and figures |

Results are generated from local data and excluded from Git. The tracked
[results summary](docs/results.md) records the reference run and its limitations.
OPSD data attribution and all replay assumptions are in [methods](docs/methods.md).

## Implemented modeling approach

The **Physics-Guided Probabilistic GRU (PGP-GRU)** forecasts future
capacity/SOH at RPT checkpoints using a small, configurable sequence model.

- Predict **P10, P50, and P90** with quantile loss and ordered outputs.
- Use **soft monotonicity and smoothness penalties**, allowing temporary capacity
  recovery, measurement noise, and temperature effects.
- Select features according to availability and physical meaning rather than including
  every recorded signal.
- Compare with persistence, linear regression, XGBoost, and a vanilla GRU.

The SOH definition is:

```text
SOH(t) = measured discharge capacity(t) / reference capacity
```

The current configuration declares the first observed second-life RPT as the reference.
It is available at every modeled forecast origin. Fixed nominal or documented first-life
end capacity can be supplied explicitly; the reported runs use first observed second-life RPT.

## Evaluation and reproducibility

- **Leave-one-battery-out validation:** Hold out one battery for testing, use a different
  training battery for validation, and fit preprocessing on training data only.
- **Temporal ordering:** Never randomly split measurements from the same battery across
  training and test sets or use a test battery's future trajectory for preprocessing.
- **Limited history:** Compare approximately 10%, 25%, 50%, 75%, and 100% of the available
  pre-forecast history. Define context length, forecast origin, and horizon explicitly.
- **Point metrics:** MAE, RMSE, appropriate MAPE, and R².
- **Uncertainty metrics:** Quantile loss, empirical interval coverage, interval width,
  and calibration plots.
- **Reporting:** Per-battery and per-fold results, aggregate means and standard deviations,
  saved seeds/configuration, and command-generated tables and figures.

Six independent cells limit statistical evidence. Forecast-derived time-to-threshold
will be identified as an estimate; it will not be presented as observed RUL when no
failure threshold was observed. Model superiority requires experimental support.

## Solar-storage optimization

The CVXPY module combines solar generation, demand, assumed tariffs, battery constraints,
and held-out predicted health to compare:

| Scenario | Dispatch objective |
| --- | --- |
| A. No battery | Grid supply and available solar |
| B. Conventional battery | Electricity-cost minimization |
| C. Second-life battery | Electricity-cost minimization with reduced usable capacity |
| D. Degradation-aware second-life battery | Electricity cost plus degradation and optional carbon penalties |

Outputs include electricity cost, grid energy, solar self-consumption, battery
throughput, equivalent full cycles, and estimated degradation. Median and conservative
forecasts and wear-price sensitivity are exported. Carbon effects are not reported in
the reference run because carbon-intensity data are absent. This perfect-foresight replay
uses a linear wear proxy; it does not establish real-world savings or pack lifetime.

## Repository structure

```text
recell/
├── configs/                       # Base configuration and reviewed header locations
├── data/
│   ├── raw/                       # Original dataset; excluded from Git
│   ├── interim/
│   └── processed/
├── docs/                          # Inspection methods, findings, and phase status
├── notebooks/
│   ├── 01_dataset_inspection.ipynb
│   ├── 02_eda.ipynb
│   └── 03_results_analysis.ipynb
├── src/second_life_battery/
│   ├── data/                      # Inspection, parsing, features and sequences
│   ├── utils/                     # Configuration and structured logging
│   ├── models/                    # Baselines and point/quantile GRUs
│   ├── training/                  # LOBO, early stopping and history experiments
│   ├── evaluation/                # Metrics, analysis and publication plots
│   └── optimization/              # Meter inputs, wear conversion and dispatch
├── scripts/
│   ├── extract_dataset.py
│   ├── inspect_dataset.py
│   ├── prepare_data.py
│   ├── run_eda.py
│   ├── run_lobo_cv.py
│   ├── run_limited_history_experiment.py
│   ├── analyze_results.py
│   ├── prepare_solar_data.py
│   └── run_dispatch.py
├── tests/
├── outputs/                       # Generated artifacts; excluded from Git
├── pyproject.toml
├── requirements.txt
└── uv.lock
```

## Roadmap

- [x] Phase 1: Repository scaffold and reproducible inspection environment.
- [x] Phase 2: Download, verify, inspect, and inventory the real dataset.
- [x] Phase 3: Resolve data ambiguities and build standardized parsers and targets.
- [x] Phase 4: EDA and capacity/SOH trajectory inspection.
- [x] Phases 5–7: Baselines, vanilla GRU, and leave-one-battery-out evaluation.
- [x] Phases 8–10: PGP-GRU, limited-history experiments, and failure analysis.
- [x] Phases 11–12: Solar/load interface and degradation-aware optimization.
- [x] Phase 13: Reproducible experiment tables and publication figures.

## Reference

Moy et al. (2024). *Second-life lithium-ion battery aging dataset based on grid storage
cycling*. **Data in Brief, 57**, 111046.
[https://doi.org/10.1016/j.dib.2024.111046](https://doi.org/10.1016/j.dib.2024.111046).

Cite the original dataset and paper when using these measurements. ReCell does not
yet have an associated research publication.
