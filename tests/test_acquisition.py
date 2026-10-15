"""Archive integrity and path-traversal checks use tiny synthetic archives."""

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from second_life_battery.data.inventory import sha256_file

spec = importlib.util.spec_from_file_location(
    "extract_dataset",
    Path(__file__).resolve().parents[1] / "scripts/extract_dataset.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_archive(tmp_path: Path, name: str) -> tuple[Path, Path]:
    archive = tmp_path / "test.zip"
    with ZipFile(archive, "w") as stream:
        stream.writestr(name, "test")
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "attributes": {
                            "kind": "file",
                            "size": archive.stat().st_size,
                            "extra": {"hashes": {"sha256": sha256_file(archive)}},
                        }
                    }
                ]
            }
        )
    )
    return archive, metadata


def test_verified_extraction_and_no_overwrite(tmp_path: Path) -> None:
    archive, metadata = make_archive(tmp_path, "data/file.txt")
    destination = tmp_path / "extracted"
    result = module.extract_verified(archive, metadata, destination)
    assert result["extracted_bytes"] == 4
    assert (destination / "data/file.txt").read_text() == "test"
    with pytest.raises(FileExistsError):
        module.extract_verified(archive, metadata, destination)


@pytest.mark.parametrize("name", ["../escape.txt", "/absolute.txt", "a/../../escape.txt"])
def test_unsafe_archive_paths(tmp_path: Path, name: str) -> None:
    archive, metadata = make_archive(tmp_path, name)
    with pytest.raises(ValueError, match="Unsafe"):
        module.extract_verified(archive, metadata, tmp_path / "extracted")
    assert not (tmp_path / "extracted").exists()


def test_checksum_failure_does_not_extract(tmp_path: Path) -> None:
    archive, metadata = make_archive(tmp_path, "file.txt")
    archive.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="SHA-256"):
        module.extract_verified(archive, metadata, tmp_path / "extracted")
