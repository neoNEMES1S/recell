# Second-life battery AI

Physics-Guided Probabilistic Health Forecasting and Degradation-Aware Optimization
of Second-Life EV Batteries for Solar Energy Storage.

**Current scope: phases 1–2, environment and real dataset inspection.** No forecasting
models, SOH calculations, dispatch optimizer, or experimental results are implemented.
Inspection does not certify scientific target validity.

## Setup

Python 3.11 is the reference runtime. From this directory:

```bash
uv sync --locked --extra dev
source .venv/bin/activate
python scripts/inspect_dataset.py --config configs/base.yaml
pytest -q
```

`uv.lock` pins the environment. If uv is unavailable, use `python3.11 -m venv .venv`,
activate it, then `python -m pip install -r requirements.txt`; this fallback resolves
the version ranges rather than reproducing the lock exactly. Future research
dependencies are declared separately: `uv sync --locked --extra dev --extra research`.
The current stage runs on CPU and needs neither PyTorch nor a GPU.

## Data

Official dataset: [OSF 8JNR5](https://osf.io/8jnr5/), DOI
[10.17605/OSF.IO/8JNR5](https://doi.org/10.17605/OSF.IO/8JNR5).
Paper: Moy et al., *Data in Brief* 57 (2024), 111046,
[10.1016/j.dib.2024.111046](https://doi.org/10.1016/j.dib.2024.111046).

The downloaded archive and extracted files are under `data/raw/stanford_second_life/`.
The base config points at `extracted/SL_Dataset_SECL_INR21700-M50T/` within it.
Preserve the downloaded directory hierarchy. Alternatively supply `--raw-dir /absolute/path`
with a config whose reviewed header locations match that root.
See [data placement](data/raw/README.md) and [inspection methodology](docs/inspection.md).
Raw data and generated outputs are excluded from version control.

```bash
python scripts/inspect_dataset.py --config configs/base.yaml
python scripts/inspect_dataset.py --config configs/base.yaml \
  --full-scan --output-dir outputs/inventory_full
```

Generated files in `outputs/inventory/`:

- `dataset_manifest.json`: file hashes, sizes, sheets, previews, header candidates,
  MATLAB variable shapes, missingness where a header is reviewed, and read errors.
- `files.csv`: one row per source file.
- `column_availability.csv`: missingness per reviewed column, with scan completeness.
- `inspection_report.md`: status and next review steps.
- `inspection.jsonl`: structured event/error log.
- `config.snapshot.yaml`, `environment.json`: exact settings and installed versions.

Default inspection scans every row for complete structural counts, missingness and
native date ranges. Set `inspection.scan_limit: 200` for a fast preview;
`--full-scan` overrides that limit.
Neither mode turns a discharge-capacity column into a validated RPT target.

Exit codes: `0` means structural inspection finished and semantic review remains;
`1` means a source failed inspection; `2` means missing/empty/no supported data.
Errors are retained in the manifest. Unsupported files are listed and hashed.

## Layout

```text
configs/                  YAML configuration
data/{raw,interim,processed}/
notebooks/                inspection and future analysis entry points
src/second_life_battery/
  data/                   inventory (implemented); semantic parsing follows review
  models/                 reserved for phases 5–8
  training/               reserved for phases 5–9
  evaluation/             reserved for EDA and experiment reporting
  optimization/           reserved for phases 11–12
  utils/                  configuration and JSON logging
scripts/                  runnable commands
tests/                    synthetic file-format tests, never research observations
outputs/                  manifests, checkpoints, metrics, figures and tables
docs/                     methods, acquisition and phase status
```

The package namespace avoids generic import names such as `data` and `utils`.
Future modules have directories only; there are no nonfunctional training stubs.

## Research gates

Before phase 3, review actual cell identities, timestamp units/origins, raw versus
processed duplicates, RPT discharge capacity extraction, and optional sensor coverage.
The declared SOH reference is the first observed second-life RPT capacity; this must
be available at the forecast origin. Fixed nominal or documented first-life end
capacity are alternatives to evaluate explicitly. Never normalize by future maxima.

Later evaluation must use leave-one-battery-out folds with a separate training battery
for validation and training-only fit of scalers/imputers. Limited-history experiments
must distinguish a shortened context window from an earlier forecast origin; retain
the same future evaluation horizon when comparing context lengths. Six cells limit
independent statistical evidence. No observed RUL labels or superiority claims will
be manufactured. See [phase status](docs/phase_status.md).
# recell
