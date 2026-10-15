"""Battery-disjoint outer test folds and a deterministic, independent validation battery."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Fold:
    """Cell identities assigned before any preprocessing or model fitting."""

    test: str
    validation: str
    training: tuple[str, ...]


def lobo_folds(frame: pd.DataFrame) -> list[Fold]:
    """Rotate one validation cell among the non-test cells; never split time-series rows."""
    cells = sorted(frame.cell_id.unique())
    if len(cells) < 3:
        raise ValueError("LOBO with independent validation requires at least three cells")
    result = []
    for index, test in enumerate(cells):
        validation = cells[(index + 1) % len(cells)]
        training = tuple(cell for cell in cells if cell not in {test, validation})
        result.append(Fold(test, validation, training))
    return result


def split_fold(frame: pd.DataFrame, fold: Fold) -> tuple[pd.DataFrame, ...]:
    """Validate separation and return training, validation, then test checkpoints."""
    if fold.test == fold.validation or {fold.test, fold.validation} & set(fold.training):
        raise ValueError("A battery cannot appear in multiple partitions")
    parts = (
        frame[frame.cell_id.isin(fold.training)].copy(),
        frame[frame.cell_id == fold.validation].copy(),
        frame[frame.cell_id == fold.test].copy(),
    )
    if any(part.empty for part in parts):
        raise ValueError("Every fold partition must contain checkpoints")
    return parts
