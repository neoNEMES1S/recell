"""Small immutable-study receipts shared by the proposal implementation scripts."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from second_life_battery.data.inventory import sha256_file
from second_life_battery.utils.reproducibility import verify_artifacts


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def begin(output, config, inputs=()):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    root = Path.cwd().resolve()
    paths = [Path(config), *map(Path, inputs)]
    source = [*Path("src/second_life_battery").rglob("*.py"), *Path("scripts").glob("*.py")]
    for path in source:
        target = output / "code_snapshot" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    record = {
        "status": "running",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            str(p.resolve().relative_to(root))
            if p.resolve().is_relative_to(root)
            else str(p.resolve()): sha256_file(p)
            for p in paths
        },
        "code": {str(p): sha256_file(p) for p in sorted(source)},
    }
    write_json(output / "registration.json", record)
    return record


def complete(output, record, **details):
    output = Path(output)
    manifest = {
        str(p.relative_to(output)): sha256_file(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "completion.json"
    }
    result = {**record, **details, "status": "completed", "artifacts": manifest}
    write_json(output / "completion.json", result)
    return result


def verified(folder, input_root=None):
    folder = Path(folder)
    result = json.loads((folder / "completion.json").read_text())
    if result["status"] != "completed":
        raise ValueError("Study is not complete")
    verify_artifacts(folder, result["artifacts"])
    for name, expected in result["inputs"].items():
        path = Path(name) if input_root is None else Path(input_root) / name
        if sha256_file(path) != expected:
            raise ValueError(f"Registered study input changed: {name}")
    return result
