import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from risk_budget import risk_contributions, optimize_risk_budget


def test_risk_contributions_sum_to_one():
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    weights = np.array([0.5, 0.5])
    assert np.isclose(risk_contributions(weights, cov).sum(), 1.0)


def test_optimizer_returns_valid_long_only_weights():
    rng = np.random.default_rng(7)
    returns = pd.DataFrame(rng.normal(0, 0.01, size=(400, 3)), columns=list("ABC"))
    result = optimize_risk_budget(returns)
    assert np.isclose(result["Capital Weight"].sum(), 1.0)
    assert (result["Capital Weight"] >= 0).all()
    assert np.isfinite(result["Actual Risk Contribution"]).all()
