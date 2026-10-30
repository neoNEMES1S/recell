"""Daily spreadsheet totals cannot manufacture measured subdaily PV or true zeros."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "audit_jaipur_pv", Path(__file__).resolve().parents[1] / "scripts/audit_jaipur_pv.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    rows = [(None,) * 5 for _ in range(6)]
    rows += [
        ("Month", "Date", "Inv-1", "Inv-2", "Main"),
        (1, 1, None, None, 0),
        (1, 2, 0, 0, 0),
        (None, None, None, None, 123),
    ]
    formulas = list(rows)
    formulas[7] = (1, 1, None, None, "=SUM(C8:D8)")
    formulas[8] = (1, 2, 0, 0, "=SUM(C9:D9)")
    return rows, formulas


def test_missing_inverter_outputs_stay_missing_despite_cached_zero_total():
    ledger, excluded = module.daily_ledger(*fixture(), 2022)
    assert ledger.date.tolist() == ["2022-01-01", "2022-01-02"]
    assert ledger.main_zero_with_both_missing.tolist() == [True, False]
    assert ledger.main_is_sum_formula.tolist() == [True, True]
    assert ledger.inv1_reported_daily_output.isna().tolist() == [True, False]
    assert excluded == [10]


@pytest.mark.parametrize("defect", ["duplicate", "fractional_day", "invalid_date", "header"])
def test_date_and_schema_defects_are_not_silently_repaired(defect):
    rows, formulas = fixture()
    if defect == "duplicate":
        rows[8] = rows[7]
    elif defect == "fractional_day":
        rows[8] = (1, 2.5, 0, 0, 0)
    elif defect == "invalid_date":
        rows[8] = (2, 30, 0, 0, 0)
    else:
        rows[6] = ("Month", "Date", "Power", "Inv-2", "Main")
    with pytest.raises(ValueError):
        module.daily_ledger(rows, formulas, 2022)
