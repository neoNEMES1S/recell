"""Prepare the reviewed OPSD hourly household replay and scenario tariffs."""

import argparse
from pathlib import Path

from second_life_battery.optimization.inputs import prepare_solar
from second_life_battery.utils.config import load_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    args = parser.parse_args()
    prepare_solar(load_config(args.config), args.config.resolve().parent.parent)
