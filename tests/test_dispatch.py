"""Energy balance, causal wear conversion and solar meter trust-boundary checks."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.inventory import sha256_file
from second_life_battery.optimization.degradation import forecast_wear
from second_life_battery.optimization.inputs import prepare_solar, validate_dispatch_input
from second_life_battery.optimization.solar_dispatch import solve_dispatch


@pytest.fixture
def battery():
    return {
        "nominal_energy_kwh": 4,
        "power_kw": 2,
        "round_trip_efficiency": 0.81,
        "soc_min": 0,
        "soc_max": 1,
        "initial_soc": 0,
        "replacement_cost_eur": 1000,
        "capacity_loss_budget": 0.2,
        "solver": "CLARABEL",
    }


@pytest.fixture
def hours():
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=4, freq="h", tz="UTC"),
            "solar_kw": [3.0, 2.0, 0.0, 0.0],
            "load_kw": [1.0, 1.0, 2.0, 2.0],
            "import_price": [0.3] * 4,
            "export_price": [0.05] * 4,
        }
    )


def test_dispatch_balance_and_degradation_tradeoff(hours, battery):
    no_storage, baseline = solve_dispatch(hours, battery, 0.8, 0.01, no_battery=True)
    schedule, cheap = solve_dispatch(hours, battery, 0.8, 0.01)
    _, careful = solve_dispatch(hours, battery, 0.8, 0.01, degradation_weight=1)
    assert baseline["electricity_cost_eur"] == pytest.approx(1.05, abs=1e-6)
    assert np.max(abs(no_storage.charge_kw)) < 1e-6
    assert cheap["electricity_cost_eur"] < baseline["electricity_cost_eur"]
    assert careful["battery_throughput_kwh"] < cheap["battery_throughput_kwh"]
    assert (
        careful["electricity_plus_estimated_wear_eur"]
        < cheap["electricity_plus_estimated_wear_eur"]
    )
    np.testing.assert_allclose(
        schedule.solar_kw + schedule.grid_import_kw + schedule.discharge_kw,
        schedule.load_kw + schedule.charge_kw + schedule.grid_export_kw + schedule.curtailed_kw,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        schedule.energy_end_kwh,
        schedule.energy_start_kwh + 0.9 * schedule.charge_kw - schedule.discharge_kw / 0.9,
        atol=1e-6,
    )
    assert schedule.energy_end_kwh.iloc[-1] == pytest.approx(0, abs=1e-6)
    assert (schedule.charge_kw * schedule.discharge_kw).max() < 1e-6
    assert schedule.energy_end_kwh.max() <= 3.2 + 1e-6


@pytest.mark.parametrize(
    "field,value",
    [
        ("round_trip_efficiency", -1),
        ("replacement_cost_eur", -1),
        ("power_kw", np.inf),
        ("soc_min", np.nan),
    ],
)
def test_invalid_battery_rejected(hours, battery, field, value):
    battery[field] = value
    with pytest.raises(ValueError):
        solve_dispatch(hours, battery, 0.8, 0.001)


def test_dispatch_rejects_bad_inputs_and_missing_carbon(hours, battery):
    bad = hours.copy()
    bad.loc[0, "timestamp"] = pd.NaT
    with pytest.raises(ValueError):
        validate_dispatch_input(bad)
    bad = hours.copy()
    bad.loc[0, "export_price"] = 1
    with pytest.raises(ValueError):
        validate_dispatch_input(bad)
    battery["carbon_price_eur_per_kg"] = 1
    with pytest.raises(ValueError, match="Carbon"):
        solve_dispatch(hours, battery, 0.8, 0.001)


def test_wear_uses_training_exposure_and_forecast_horizon():
    training = pd.DataFrame(
        {
            "cell_id": ["A", "A", "B", "B"],
            "timestamp": [1, 2, 1, 2],
            "cumulative_ah": [0, 100, 0, 100],
        }
    )
    forecast = pd.Series(
        {
            "cell_id": "C",
            "reference_capacity_ah": 4.5,
            "origin_soh": 1.0,
            "q10": 0.96,
            "q50": 0.98,
            "q90": 1.0,
            "horizon": 2,
        }
    )
    settings = {"nominal_cell_capacity_ah": 5}
    median = forecast_wear(forecast, training, settings, False)
    low = forecast_wear(forecast, training, settings, True)
    assert median["wear_per_efc"] == pytest.approx(0.0009)
    assert low["wear_per_efc"] == pytest.approx(0.0018)
    assert median["health_fraction"] == pytest.approx(0.882)
    with pytest.raises(ValueError, match="Held-out"):
        forecast_wear(forecast, training.assign(cell_id="C"), settings, False)
    forecast.q50 = np.nan
    with pytest.raises(ValueError):
        forecast_wear(forecast, training, settings, False)


def test_meter_differencing_provenance_and_full_coverage(tmp_path: Path):
    source = tmp_path / "meters.csv"
    raw = pd.DataFrame(
        {
            "utc_timestamp": pd.date_range("2020-01-01", periods=4, freq="h", tz="UTC"),
            "pv": [0, 2, 3, 3],
            "import": [0, 0, 1, 2],
            "export": [0, 1, 1, 1],
            "interpolated": ["pv", "", "", ""],
        }
    )
    raw.to_csv(source, index=False)
    settings = {
        "raw_file": "meters.csv",
        "raw_sha256": sha256_file(source),
        "columns": {"pv": "pv", "import": "import", "export": "export"},
        "start": "2020-01-01T00:00:00Z",
        "end": "2020-01-01T03:00:00Z",
        "tariff_timezone": "UTC",
        "peak_start_hour": 1,
        "peak_end_hour": 2,
        "peak_price_eur_per_kwh": 0.4,
        "offpeak_price_eur_per_kwh": 0.2,
        "export_price_eur_per_kwh": 0.05,
        "source_url": "test fixture",
    }
    result = prepare_solar({"solar": settings}, tmp_path)
    assert result.load_kw.tolist() == [1, 2, 1]
    assert result.solar_kw.tolist() == [2, 1, 0]
    assert result.import_price.tolist() == [0.2, 0.4, 0.2]
    assert result.source_interpolated.tolist() == [True, False, False]
    settings["end"] = "2020-01-01T04:00:00Z"
    with pytest.raises(ValueError, match="complete"):
        prepare_solar({"solar": settings}, tmp_path)
    settings["raw_sha256"] = "incorrect"
    with pytest.raises(ValueError, match="hash"):
        prepare_solar({"solar": settings}, tmp_path)
