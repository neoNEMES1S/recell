# Raw Stanford data

Download the dataset from https://osf.io/8jnr5/ and preserve its original filenames
and folder structure beneath `data/raw/stanford_second_life/`.

The OSF listing retrieved during setup names `SL_Dataset_SECL_INR21700-M50T.zip`
(2,153,883,052 bytes, version 2). Its published SHA-256 is:

```text
201b21b8e2e9623887d03e9bd6620341e5c91cd28bce34294ccbad2d4e7c6fe3
```

The associated paper describes cycling and diagnostic tests, but actual local
filenames and columns are discovered by inspection. Do not rename or concatenate
raw exports, run bundled MATLAB scripts, or overwrite raw files during preprocessing.

An alternative dataset location is supported by `--raw-dir`. Configured relative
paths are resolved from the parent of the configuration directory; command-line
paths are resolved from the current working directory.

Keep download metadata and checksum evidence with the acquisition record in `docs/`.
Do not commit the raw dataset or assume its licensing is the same as software licensing.

Reproduce acquisition from the repository root (requires curl and network access):

```bash
curl --fail --location --retry 3 https://osf.io/download/j2ne9/ \
  --output data/raw/stanford_second_life/SL_Dataset_SECL_INR21700-M50T.zip
python scripts/extract_dataset.py \
  --archive data/raw/stanford_second_life/SL_Dataset_SECL_INR21700-M50T.zip \
  --metadata docs/osf_file_listing.json \
  --destination data/raw/stanford_second_life/extracted
```

Run this only in a fresh acquisition directory. Extraction refuses to overwrite an
existing destination, validates the SHA-256 and available disk space, rejects unsafe
archive paths, and verifies each extracted member's CRC through Python's zip reader.
The preserved archive includes macOS resource forks in `__MACOSX`; the configured
inspection root is the actual dataset folder, outside that metadata directory.
An upstream dataset update will fail checksum verification until reviewed explicitly.
