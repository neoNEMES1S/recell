"""Generate descriptive plots from the prepared real-data checkpoints."""

import argparse
from pathlib import Path

from second_life_battery.evaluation.plots import run_eda

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    args = parser.parse_args()
    run_eda(args.config.resolve().parent.parent)
