"""Create capacity targets and temporal features from inspected Stanford exports."""

import argparse
from pathlib import Path

from second_life_battery.data.preprocessing import prepare_data
from second_life_battery.utils.config import load_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    args = parser.parse_args()
    prepare_data(load_config(args.config), args.config.resolve().parent.parent)
