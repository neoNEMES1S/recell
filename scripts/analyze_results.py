"""Generate forecast calibration, importance, failure cases and limited-history figures."""

import argparse
from pathlib import Path

from second_life_battery.evaluation.analysis import analyze_forecasts, analyze_limited_history
from second_life_battery.utils.config import load_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    args = parser.parse_args()
    root = args.config.resolve().parent.parent
    analyze_forecasts(load_config(args.config), root)
    analyze_limited_history(root)
