"""Verify an OSF archive against saved metadata, then safely extract into a new directory."""

import argparse
import json
import shutil
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from second_life_battery.data.inventory import sha256_file


def extract_verified(archive: Path, metadata: Path, destination: Path) -> dict:
    """Reject checksum mismatches, unsafe paths, links and existing destinations."""
    listing = json.loads(metadata.read_text(encoding="utf-8"))
    entries = listing["data"]
    if len(entries) != 1 or entries[0]["attributes"]["kind"] != "file":
        raise ValueError("Expected the reviewed OSF listing containing one archive")
    attributes = entries[0]["attributes"]
    expected = attributes["extra"]["hashes"]["sha256"]
    if archive.stat().st_size != attributes["size"] or sha256_file(archive) != expected:
        raise ValueError("Archive size or SHA-256 differs from the OSF metadata")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing destination: {destination}")
    with ZipFile(archive) as source:
        members = source.infolist()
        names = set()
        for member in members:
            path = PurePosixPath(member.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in member.filename
                or stat.S_ISLNK(member.external_attr >> 16)
                or ":" in member.filename
            ):
                raise ValueError(f"Unsafe archive entry: {member.filename}")
            normalized = str(path).casefold()
            if normalized in names:
                raise ValueError(f"Duplicate archive entry: {member.filename}")
            names.add(normalized)
        size = sum(member.file_size for member in members)
        if size > shutil.disk_usage(destination.parent).free:
            raise OSError(f"Insufficient free space: need {size} bytes")
        destination.mkdir()
        source.extractall(destination)
    return {
        "archive": str(archive.resolve()),
        "sha256": expected,
        "archive_bytes": archive.stat().st_size,
        "extracted_bytes": size,
        "archive_entries": len(members),
        "destination": str(destination.resolve()),
    }


def main() -> None:
    """Extract a completed download; never download or execute bundled source code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, default=Path("docs/osf_file_listing.json"))
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    record = extract_verified(args.archive, args.metadata, args.destination)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
