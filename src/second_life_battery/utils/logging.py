"""JSON-lines logging suitable for machine-readable inspection runs."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Serialize each record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time_utc": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
                "source_file": getattr(record, "source_file", None),
            }
        )


def configure_logging(path: Path) -> logging.Logger:
    """Send structured records to stderr and a fresh run log."""
    logger = logging.getLogger("second_life_battery")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in [logging.StreamHandler(), logging.FileHandler(path, mode="w")]:
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger
