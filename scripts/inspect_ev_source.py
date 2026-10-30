"""Read paginated OSF metadata only; retain responses and never execute source code."""

import argparse
import json
from pathlib import Path

from second_life_battery.data.osf import inspect_listing

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect_listing(args.url, args.output)
    for record in result["data"]:
        attr = record["attributes"]
        print(
            json.dumps(
                {
                    "name": attr["name"],
                    "kind": attr["kind"],
                    "bytes": attr["size"],
                    "folder": record.get("relationships", {})
                    .get("files", {})
                    .get("links", {})
                    .get("related", {})
                    .get("href"),
                    "download": record.get("links", {}).get("download"),
                }
            )
        )
