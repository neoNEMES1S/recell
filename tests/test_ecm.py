import numpy as np
import pytest
from scipy.integrate import solve_ivp

from second_life_battery.models.ecm import (
    Parameters,
    fit_pulses,
    polarization,
    pulse_response,
    simulate,
)


def test_exact_rc_against_independent_ode_and_relaxation():
    p = Parameters(0.02, 0.03, 4)
    t = np.array([0, 0.3, 1.1, 2.7, 4.0])
    expected = solve_ivp(
        lambda t, y: (-y + 0.03 * 2) / 4, [0, 4], [0], t_eval=t, rtol=1e-11, atol=1e-13
    ).y[0]
    np.testing.assert_allclose(polarization(t, np.full(5, 2), p), expected, atol=1e-11)
    np.testing.assert_allclose(polarization(t, np.zeros(5), p, 0.2), 0.2 * np.exp(-t / 4))


def test_coulomb_counting_charge_efficiency_and_initial_voltage():
    p = Parameters(0.02)
    r = simulate([0, 360], [1, 1], p, 2, 0.8, [0, 1], [3, 4])
    np.testing.assert_allclose(r["soc"], [0.8, 0.75])
    np.testing.assert_allclose(r["voltage_v"], [3.78, 3.73])
    r = simulate([0, 360], [-1, -1], p, 2, 0.8, [0, 1], [3, 4], charge_efficiency=0.9)
    assert r["soc"][-1] == pytest.approx(0.845)


@pytest.mark.parametrize("args", [(0, 0, 1), (0.1, -0.1, 1), (0.1, 0.1, 0), (np.nan, 0, 1)])
def test_bad_parameters(args):
    with pytest.raises(ValueError):
        Parameters(*args)


def test_reject_clock_and_soc_extrapolation():
    with pytest.raises(ValueError):
        polarization([0, 0], [1, 1], Parameters(0.1))
    with pytest.raises(ValueError, match="SOC leaves"):
        simulate([0, 3600], [2, 2], Parameters(0.1), 1, 0.5, [0, 1], [3, 4])


def test_calibration_recovers_parameters_without_scoring_fit_targets_as_test():
    t = np.arange(100, dtype=float)
    current = np.r_[np.full(5, 0.2), np.full(20, 2), np.zeros(35), np.full(40, -1)]
    truth = Parameters(0.025, 0.013, 8)
    measured = pulse_response(t, current, 3.7, truth)
    p, record = fit_pulses([dict(time_s=t, current_a=current, voltage_v=measured)])
    np.testing.assert_allclose([p.r0_ohm, p.r1_ohm, p.tau_s], [0.025, 0.013, 8], rtol=1e-5)
    assert record["success"] and not record["bound_contact"]
