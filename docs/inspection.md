# Inspection methodology

This stage inventories structure and provenance. It does not assign scientific
meaning from a filename or a column that merely looks familiar.

XLSX/XLSM workbooks are read with openpyxl in read-only mode. All sheets are inspected,
including preambles and empty sheets. Formula text is retained; formulas/macros are
never executed. CSV/TSV use UTF-8 (optional BOM) and their standard delimiters. Other
encodings/delimiters need an explicit adapter once encountered. Nonempty rows and
native Excel datetime ranges are reported; datetime strings, Excel serial values,
elapsed seconds and timezone assumptions are not automatically converted.

The initial discovery pass scanned at most 200 rows per table. The final base config
uses `scan_limit: null` to scan every row. Every table
has `scan_complete`; sampled counts/missingness/date ranges are explicitly partial.
`number_of_observations` stays null for truncated scans. Exporter-declared dimensions
are recorded separately and are not trusted as exact observations. `--full-scan`
reads every row, including when worksheet dimensions are missing or incorrect.
Four independent worker processes are used by the base configuration.

Preview rows preserve original values. All-text rows in the preview are header
**candidates**, including possible title rows. Only a reviewed one-based header row
sets `detected_columns` and enables provisional observation/missingness counts:

```yaml
inspection:
  header_rows:
    relative/path/observed-file.xlsx:
      observed_sheet_name: 3
```

This example is a configuration shape, not a claim about the dataset. Missingness
counts are indexed by one-based column position to preserve duplicate/blank labels.
Counts include nonempty rows below the header, so footers still require review.
No summation across sheets/files is made: exports can duplicate or partition records.

The initial inspection was used to review 865 header rows across 529 actual files.
Those locations are saved in `configs/reviewed_headers.json`, loaded by `header_rows_file`,
and expanded in every configuration snapshot. The remaining workbook layouts need
individual interpretation; they are preserved in the manifest.

MAT v4–v7.2 inspection uses scipy `whosmat` to avoid loading large arrays. MATLAB
struct fields require subsequent focused decoding. HDF5-backed MAT candidates use
h5py to list nested dataset paths/shapes/dtypes, without evaluating references or
assuming MATLAB orientation. Neither array size nor shape is labeled an observation
count. Unsupported files are hashed and recorded. Read failures are logged, preserved
per file, and produce a nonzero exit status. Programming failures are not hidden by
a catch-all exception handler.

The downloaded cycling MAT files expose opaque MATLAB tables that cause scipy's
`whosmat` to fail. For files below 16 MiB only, the inspector uses `loadmat` to verify
the opaque class and report its shape/dtype; it does not decode the table as measurements.
Larger unsupported opaque files retain an error rather than being silently omitted.

The reviewed registry in base.yaml supplies six cell labels and publication-backed
duty cycles. Whole cell tokens are matched against observed paths. Conflicting tokens
produce an ambiguous identity with no selected cell; a single token remains a path
label requiring measurement-level validation. Test types use reviewed path patterns.
Experiment `date_time_coverage` and target validity require further semantic review.
`missing_fields: null` means
unknown; `unverified_fields` lists unresolved semantics. Unknown is not absent.
The expected six cells in configuration comes from the publication, not a discovery.

Source SHA-256 hashes identify exact bytes. Outputs store resolved configuration,
runtime/package versions and UTC inspection time. Reruns replace the output directory's
named reports; select `--output-dir` to retain separate runs. Raw files are read only.
Do not change source files while an inspection is running.

## Gate before parsing/modeling

1. Identify actual cells and residential/commercial assignment from source evidence.
2. Inspect each export layout and distinguish cycling, capacity/pulse tests and EIS.
3. Confirm units, current sign, timestamp origin/timezone, step identities and ordering.
4. Confirm a discharge capacity target per RPT, excluding pulses/rests as appropriate.
5. Reconcile raw XLSX and processed MAT to avoid duplicate measurements.
6. Record missingness, first-life metadata and SOH reference availability by battery.
7. Only then implement semantic parsing, preprocessing and trajectory QA.
