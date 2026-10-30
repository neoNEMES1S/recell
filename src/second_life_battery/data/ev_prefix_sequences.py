"""Build source H1 samples from measured labels and independently verified past features."""

import numpy as np
import pandas as pd

from second_life_battery.data.sequences import Sample
from second_life_battery.data.transfer import FEATURES, validate_features


def source_sequences(features: pd.DataFrame, labels: pd.DataFrame) -> list[Sample]:
    validate_features(features)
    required = {
        "physical_cell_id",
        "cell_id",
        "life_stage",
        "diagnostic",
        "timestamp",
        "capacity_ah",
        "reference_capacity_ah",
        "soh",
    }
    if labels.empty or not required.issubset(labels) or labels[list(required)].isna().any().any():
        raise ValueError("Source labels need complete measured capacity, clock and identity")
    if set(features.life_stage) != {"first_life"} or set(labels.life_stage) != {"first_life"}:
        raise ValueError("Prefix source samples cannot cross life stages")
    if set(features.physical_cell_id) != set(labels.physical_cell_id):
        raise ValueError("Source feature and label physical-cell coverage differs")
    if labels.duplicated(["physical_cell_id", "diagnostic"]).any():
        raise ValueError("Duplicate measured source capacity label")
    numbers = labels.diagnostic.to_numpy(dtype=float)
    if (
        not np.isfinite(numbers).all()
        or (numbers < 1).any()
        or (numbers != np.floor(numbers)).any()
    ):
        raise ValueError("Source diagnostic identifiers must be positive integers")
    values = labels[["capacity_ah", "reference_capacity_ah", "soh"]].to_numpy(dtype=float)
    if (
        not np.isfinite(values).all()
        or (values <= 0).any()
        or not np.allclose(
            labels.soh, labels.capacity_ah / labels.reference_capacity_ah, rtol=0, atol=1e-8
        )
    ):
        raise ValueError("Source label capacity/reference/SOH is invalid")
    samples = []
    for identity, group in features.groupby("physical_cell_id", sort=True):
        group = group.sort_values("diagnostic").reset_index(drop=True)
        if group.diagnostic.tolist() != list(range(1, len(group) + 1)):
            raise ValueError("Source feature history is not a contiguous verified prefix")
        future = labels[labels.physical_cell_id.eq(identity)].sort_values("diagnostic")
        if future.cell_id.nunique() != 1 or set(future.cell_id) != set(group.cell_id):
            raise ValueError("Source label and feature aliases disagree")
        times = pd.to_datetime(future.timestamp, format="ISO8601", errors="raise")
        if times.isna().any() or (times.diff().dropna() <= pd.Timedelta(0)).any():
            raise ValueError("Source labels must follow their original diagnostic chronology")
        if (
            future.diagnostic.iloc[0] != 1
            or not np.allclose(
                future.reference_capacity_ah, group.reference_capacity_ah.iloc[0], rtol=0, atol=1e-8
            )
            or not np.isclose(
                future.capacity_ah.iloc[0], group.capacity_ah.iloc[0], rtol=0, atol=1e-8
            )
        ):
            raise ValueError("Source label reference differs from the observed first capacity")
        by_number = future.set_index("diagnostic")
        for index, row in group.iterrows():
            if row.diagnostic not in by_number.index:
                raise ValueError("A source feature checkpoint has no matching measured label")
            label = by_number.loc[row.diagnostic]
            if pd.Timestamp(row.timestamp) != pd.Timestamp(label.timestamp) or not np.allclose(
                [row.capacity_ah, row.soh], [label.capacity_ah, label.soh], rtol=0, atol=1e-8
            ):
                raise ValueError("Measured source label differs from its input checkpoint")
            number = int(row.diagnostic)
            if number < 3 or number + 1 not in by_number.index:
                continue
            target = by_number.loc[number + 1]
            if pd.Timestamp(target.timestamp) <= pd.Timestamp(row.timestamp):
                raise ValueError("Source target does not strictly follow its forecast origin")
            samples.append(
                Sample(
                    str(identity),
                    index,
                    str(row.timestamp),
                    [str(target.timestamp)],
                    group.loc[:index, FEATURES].to_numpy(dtype=np.float32),
                    np.array([target.soh], dtype=np.float32),
                    float(row.soh),
                    float(row.reference_capacity_ah),
                )
            )
    return samples
