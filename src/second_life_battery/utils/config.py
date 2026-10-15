"""Load inspection configuration without silently accepting invalid settings."""

import json
from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> dict[str, Any]:
    """Read YAML; validate settings consumed by the inspection stage."""
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a YAML mapping")
    for section, field in [("dataset", "raw_dir"), ("inspection", "output_dir")]:
        if not isinstance(config.get(section), dict):
            raise ValueError(f"Missing configuration section: {section}")
        if not isinstance(config[section].get(field), str) or not config[section][field]:
            raise ValueError(f"{section}.{field} must be a nonempty path string")
    rows = config["inspection"].get("preview_rows", 20)
    if type(rows) is not int or not 1 <= rows <= 100:
        raise ValueError("inspection.preview_rows must be an integer between 1 and 100")
    limit = config["inspection"].get("scan_limit")
    if limit is not None and (type(limit) is not int or limit < rows):
        raise ValueError("inspection.scan_limit must be null or at least preview_rows")
    workers = config["inspection"].get("workers", 1)
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("inspection.workers must be an integer between 1 and 8")
    if "header_rows_file" in config["inspection"]:
        if config["inspection"].get("header_rows"):
            raise ValueError("Use either header_rows or header_rows_file, not both")
        source = path.parent / config["inspection"].pop("header_rows_file")
        config["inspection"]["header_rows"] = json.loads(source.read_text(encoding="utf-8"))
    headers = config["inspection"].get("header_rows", {})
    if not isinstance(headers, dict):
        raise ValueError("inspection.header_rows must be a mapping")
    for file, tables in headers.items():
        if not isinstance(file, str) or not isinstance(tables, dict):
            raise ValueError("header_rows maps relative filenames to table/row mappings")
        for table, row in tables.items():
            if not isinstance(table, str) or type(row) is not int or row < 1:
                raise ValueError("Header table names must be strings and rows positive integers")
    return config
