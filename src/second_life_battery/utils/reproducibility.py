"""Reproducible CPU/GPU seeds and run provenance."""

import json
import platform
import random
from importlib.metadata import version
from pathlib import Path

import numpy as np
import torch
import yaml

from second_life_battery.data.inventory import sha256_file


def seed_everything(seed: int) -> None:
    """Seed all RNGs and request deterministic kernels; CPU remains the reference runtime."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def save_run(config: dict, root: Path, output: Path) -> None:
    """Persist effective configuration, source data hash and numerical package versions."""
    output.mkdir(parents=True, exist_ok=True)
    (output / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "python": platform.python_version(),
                "checkpoint_data_sha256": sha256_file(root / "data/processed/checkpoints.csv"),
                "packages": {
                    name: version(name)
                    for name in ["numpy", "pandas", "scikit-learn", "torch", "xgboost", "cvxpy"]
                },
            },
            indent=2,
        )
    )
