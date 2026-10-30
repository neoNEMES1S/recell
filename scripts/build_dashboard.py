"""Build the client dashboard from existing verified experiment outputs."""

import argparse
from pathlib import Path

from second_life_battery.evaluation.dashboard import build_dashboard

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dashboard/dist"))
    args = parser.parse_args()
    build_dashboard(Path(__file__).resolve().parent.parent, args.output.resolve())
