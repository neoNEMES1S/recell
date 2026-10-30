"""A reference freeze must retain real source bytes, not merely a Git revision."""

import importlib.util
import tarfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "freeze_reference", Path(__file__).resolve().parents[1] / "scripts/freeze_reference.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def reference(root):
    for path in [
        "data/processed/checkpoints.csv",
        "outputs/lobo/config.yaml",
        "outputs/lobo/folds.json",
        "outputs/lobo/predictions.csv",
        "src/untracked.py",
    ]:
        source = root / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"Original content: {path}\n")


def test_freeze_preserves_untracked_source_and_refuses_overwrite(tmp_path):
    reference(tmp_path)
    destination = tmp_path / "outputs/transfer/reference"
    result = module.freeze_reference(tmp_path, destination)
    assert result["status"] == "verified_complete"
    source = tmp_path / "src/untracked.py"
    source.write_text("Changed after freeze\n")
    with tarfile.open(destination / "reference.tar.gz") as archive:
        assert (
            archive.extractfile("src/untracked.py").read()
            == b"Original content: src/untracked.py\n"
        )
    with pytest.raises(FileExistsError):
        module.freeze_reference(tmp_path, destination)


def test_missing_reference_and_symlinks_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        module.freeze_reference(tmp_path, tmp_path / "freeze")
    reference(tmp_path)
    (tmp_path / "src/alias.py").symlink_to(tmp_path / "src/untracked.py")
    with pytest.raises(ValueError, match="symlink"):
        module.freeze_reference(tmp_path, tmp_path / "freeze")
