"""Physical-cell partitions for the separately registered availability expansion."""

import pandas as pd

from second_life_battery.data.transfer import physical_folds, validate_features


def split_prefix_transfer(source: pd.DataFrame, target: pd.DataFrame, fold, protocol: dict):
    validate_features(source)
    validate_features(target)
    if set(source.life_stage) != {"first_life"} or set(target.life_stage) != {"second_life"}:
        raise ValueError("Prefix transfer partitions have inconsistent life stages")
    if set(target.cell_id) != set(protocol["target"]["cells"]) or fold not in physical_folds(
        target
    ):
        raise ValueError("Prefix transfer target folds differ from the registered six batteries")
    eligible = set(protocol["source"]["eligible_gradient_physical_cells"])
    validation = protocol["source"]["validation_physical_cell"]
    target_cells = set(target.physical_cell_id)
    if not eligible.issubset(target_cells) or validation in target_cells:
        raise ValueError("Prefix source roles conflict with target physical identities")
    if set(source.physical_cell_id) != eligible | {validation}:
        raise ValueError("Prefix source pool differs from the registered eligibility audit")
    gradient = eligible & set(fold.training)
    if not gradient or gradient & {fold.test, fold.validation, validation}:
        raise ValueError("Prefix source gradient identities cross a held-out role")
    parts = {
        "source_train": source[source.physical_cell_id.isin(gradient)].copy(),
        "source_validation": source[source.physical_cell_id.eq(validation)].copy(),
        "target_train": target[target.physical_cell_id.isin(fold.training)].copy(),
        "target_validation": target[target.physical_cell_id.eq(fold.validation)].copy(),
        "target_test": target[target.physical_cell_id.eq(fold.test)].copy(),
    }
    if any(part.empty for part in parts.values()):
        raise ValueError("Every prefix transfer partition needs measured rows")
    if set(parts["target_train"].physical_cell_id) != set(fold.training):
        raise ValueError("Prefix transfer omitted a target gradient-training battery")
    return parts
