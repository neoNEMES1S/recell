"""Hourly dispatch inputs from explicitly documented cumulative household meters."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from second_life_battery.data.inventory import sha256_file


def prepare_solar(config: dict, root: Path) -> pd.DataFrame:
    """Difference OPSD counters and preserve upstream interpolation flags."""
    settings = config["solar"]
    source = root / settings["raw_file"]
    digest = sha256_file(source)
    if digest != settings["raw_sha256"]:
        raise ValueError("Solar data hash differs from the reviewed release")
    raw = pd.read_csv(source)
    timestamp = pd.to_datetime(raw["utc_timestamp"], utc=True, errors="raise")
    if (
        timestamp.isna().any()
        or not timestamp.is_monotonic_increasing
        or timestamp.duplicated().any()
    ):
        raise ValueError("Solar source timestamps must be present, unique and increasing")
    names = settings["columns"]
    values = raw[list(names.values())].apply(pd.to_numeric, errors="raise").diff()
    start = timestamp.shift(1)
    chosen = (start >= pd.Timestamp(settings["start"])) & (start < pd.Timestamp(settings["end"]))
    if not np.allclose(timestamp.diff().dt.total_seconds()[chosen], 3600):
        raise ValueError("Selected solar data are not contiguous hourly readings")
    values = values.loc[chosen].copy()
    if values.isna().any().any() or (values < -1e-8).any().any():
        raise ValueError("Selected meter increments are missing or contain counter resets")
    solar = values[names["pv"]].to_numpy()
    load = (values[names["import"]] + values[names["pv"]] - values[names["export"]]).to_numpy()
    if np.any(load < -1e-8):
        raise ValueError("Meter reconstruction gives negative household consumption")
    times = pd.DatetimeIndex(start[chosen])
    expected = pd.date_range(settings["start"], settings["end"], freq="h", inclusive="left")
    if expected.empty or not times.equals(expected):
        raise ValueError("Solar source does not cover the complete requested hourly period")
    hours = times.tz_convert(settings["tariff_timezone"]).hour
    tariff = np.where(
        (hours >= settings["peak_start_hour"]) & (hours < settings["peak_end_hour"]),
        settings["peak_price_eur_per_kwh"],
        settings["offpeak_price_eur_per_kwh"],
    )
    flags = raw["interpolated"].fillna("").str.lower()
    relevant = pd.Series(False, index=raw.index)
    for name in names.values():
        relevant |= flags.str.contains(name.lower(), regex=False)
    result = pd.DataFrame(
        {
            "timestamp": times,
            "solar_kw": solar,
            "load_kw": load,
            "import_price": tariff,
            "export_price": settings["export_price_eur_per_kwh"],
            "source_interpolated": (relevant | relevant.shift(1, fill_value=False))[
                chosen
            ].to_numpy(),
        }
    )
    validate_dispatch_input(result)
    output = root / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "solar_load.csv", index=False)
    (output / "solar_provenance.json").write_text(
        json.dumps(
            {
                "source": settings["source_url"],
                "sha256": digest,
                "household": "DE_KN_residential3",
                "hours": len(result),
                "upstream_interpolated_hours": int(result.source_interpolated.sum()),
                "units": "Cumulative kWh counters differenced over one hour -> average kW",
                "load_identity": "import + PV - export",
                "tariff_status": "assumed scenario, not observed",
                "carbon_status": "not supplied; no emissions claim",
            },
            indent=2,
        )
    )
    return result


def validate_dispatch_input(frame: pd.DataFrame) -> None:
    """Reject missing, nonfinite or physically inconsistent hourly inputs at the boundary."""
    required = ["solar_kw", "load_kw", "import_price", "export_price"]
    if frame.empty or not set(required + ["timestamp"]).issubset(frame):
        raise ValueError("Dispatch requires timestamp, load, solar and import/export prices")
    if not np.isfinite(frame[required].to_numpy(dtype=float)).all():
        raise ValueError("Dispatch inputs must be finite")
    if (frame[required] < 0).any().any() or (frame.export_price > frame.import_price).any():
        raise ValueError("PV-only dispatch requires nonnegative prices with export <= import")
    times = pd.to_datetime(frame.timestamp, utc=True, errors="raise")
    if (
        times.isna().any()
        or times.duplicated().any()
        or not np.allclose(times.diff().dt.total_seconds().iloc[1:], 3600)
    ):
        raise ValueError("Dispatch timestamps must be unique contiguous hours")
    if "carbon_kg_per_kwh" in frame:
        if not np.isfinite(frame.carbon_kg_per_kwh).all() or (frame.carbon_kg_per_kwh < 0).any():
            raise ValueError("Carbon intensity must be finite and nonnegative")
