"""Run battery-disjoint forecasting comparisons from the YAML experiment configuration."""

import argparse
from pathlib import Path

from second_life_battery.training.experiments import run_experiments
from second_life_battery.utils.config import load_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    args = parser.parse_args()
    run_experiments(load_config(args.config), args.config.resolve().parent.parent)
