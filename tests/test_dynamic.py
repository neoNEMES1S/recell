import numpy as np
import pandas as pd
import pytest

from second_life_battery.data.dynamic import pulse_windows


def frame():
    return pd.DataFrame(
        {
            "time_s": np.arange(7, dtype=float),
            "step": [5, 6, 6, 7, 7, 8, 8],
            "current_a": [-0.2, -2, -2, 0, 0, 2, 2],
            "voltage_v": [3.7, 3.65, 3.64, 3.7, 3.71, 3.75, 3.76],
        }
    )


SETTINGS = dict(pulse_steps=[6], following_steps=2, maximum_sample_gap_s=2)


def test_sign_and_pre_pulse_anchor_are_preserved():
    w = pulse_windows(frame(), SETTINGS)[0]
    assert w["current_a"] == [0.2, 2, 2, 0, 0, -2, -2]
    assert w["anchor_voltage_v"] == 3.7


@pytest.mark.parametrize("times", [[0, 1, 1, 3, 4, 5, 6], [0, 1, 5, 6, 7, 8, 9]])
def test_reject_reset_duplicates_and_gaps(times):
    f = frame()
    f["time_s"] = times
    with pytest.raises(ValueError):
        pulse_windows(f, SETTINGS)
