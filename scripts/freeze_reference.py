"""Archive reference inputs, results and actual source before transfer experiments."""

import argparse
import hashlib
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from second_life_battery.data.inventory import sha256_file


def freeze_reference(root: Path, destination: Path) -> dict:
    """Preserve uncommitted source as well as artifacts; never overwrite a freeze."""
    root, destination = root.resolve(), destination.resolve()
    required = [
        "data/processed/checkpoints.csv",
        "outputs/lobo/config.yaml",
        "outputs/lobo/folds.json",
        "outputs/lobo/predictions.csv",
    ]
    for name in required:
        if not (root / name).is_file():
            raise FileNotFoundError(f"Missing reference artifact: {name}")
    selected = [
        "src",
        "scripts",
        "configs",
        "tests",
        "docs",
        "dashboard",
        "data/processed",
        "outputs/lobo",
        "outputs/limited_history",
        "outputs/dispatch",
        "outputs/analysis",
        "README.md",
        ".gitignore",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
    ]
    files = []
    for name in selected:
        candidate = root / name
        for path in sorted(candidate.rglob("*") if candidate.is_dir() else [candidate]):
            if path.is_symlink():
                raise ValueError(f"Reference contains a symlink: {path.relative_to(root)}")
            if path.is_file() and not set(path.parts) & {"__pycache__", ".pytest_cache", ".git"}:
                if path.is_relative_to(destination):
                    raise ValueError("Freeze destination overlaps selected reference files")
                files.append(path)
    records = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]

    def git(*args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
        return result.stdout.decode("utf-8") if result.returncode == 0 else None

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": (git("rev-parse", "HEAD") or "").strip() or None,
        "git_status": git("status", "--short"),
        "notebooks": (
            "User notebook edits are untouched; computational source is archived separately"
        ),
        "files": records,
    }
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination / "reference.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for path in files:
            stream.add(path, arcname=str(path.relative_to(root)), recursive=False)
    # Verify the stored bytes, rather than assuming the source stayed unchanged while archiving.
    with tarfile.open(archive) as stream:
        for record in records:
            digest = hashlib.sha256()
            with stream.extractfile(record["path"]) as member:
                for block in iter(lambda: member.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != record["sha256"]:
                raise ValueError(f"Reference changed during capture: {record['path']}")
    metadata.update(
        archive="reference.tar.gz", archive_sha256=sha256_file(archive), status="verified_complete"
    )
    (destination / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = freeze_reference(Path(__file__).resolve().parent.parent, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "files": len(result["files"]),
                "archive_sha256": result["archive_sha256"],
            },
            indent=2,
        )
    )
