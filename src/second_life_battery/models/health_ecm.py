"""Causal capacity-reference bridge; no inferred resistance or joint uncertainty."""

import numpy as np
import pandas as pd

from second_life_battery.models.ecm import simulate


def effective_capacity(
    soh,
    reference_capacity_ah,
    reference_basis,
    feature_cutoff,
    forecast_origin,
    reference_available_at,
):
    if reference_basis != "first_observed_rpt":
        raise ValueError("A separately reviewed conversion is required for another SOH reference")
    if (
        not np.isfinite([soh, reference_capacity_ah]).all()
        or soh <= 0
        or reference_capacity_ah <= 0
    ):
        raise ValueError("SOH and reference capacity must be positive and finite")
    cutoff, origin, reference = map(
        pd.Timestamp, [feature_cutoff, forecast_origin, reference_available_at]
    )
    if any(pd.isna(x) for x in [cutoff, origin, reference]):
        raise ValueError("Causal timestamps must be present")
    if cutoff > origin or reference > origin:
        raise ValueError("Future features/reference cannot parameterize this forecast")
    return float(soh * reference_capacity_ah)


def simulate_health_case(time_s, current_a, params, health, **electrical):
    capacity = effective_capacity(**health)
    return simulate(time_s, current_a, params, capacity_ah=capacity, **electrical)
