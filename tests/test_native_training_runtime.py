"""Check the macOS-sensitive PyTorch/XGBoost combination in a fresh bounded runtime."""

import os
import subprocess
import sys


def test_single_thread_native_libraries_can_fit_in_one_process():
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "faulthandler",
            "-c",
            """
import numpy as np
from second_life_battery.models.baselines import fit_baseline
from second_life_battery.utils.reproducibility import seed_everything
seed_everything(42)
x = np.random.default_rng(42).normal(size=(20, 7))
y = np.random.default_rng(43).normal(size=(20, 2))
model = fit_baseline('xgboost', x, y, {
    'tree_estimators': 3, 'tree_depth': 2, 'tree_learning_rate': .03
}, 42)
prediction = model.predict(x)
assert prediction.shape == (20, 2) and np.isfinite(prediction).all()
print('native_fit_passed')
""",
        ],
        env={**os.environ, "OMP_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "native_fit_passed" in result.stdout
