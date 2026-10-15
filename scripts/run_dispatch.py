"""Run the four solar-storage scenarios and export schedules, summaries and figures."""

import argparse
from pathlib import Path

from second_life_battery.optimization.experiments import run_dispatch
from second_life_battery.utils.config import load_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    args = parser.parse_args()
    run_dispatch(load_config(args.config), args.config.resolve().parent.parent)
