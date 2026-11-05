"""Synthetic-only tests for independent comparison calculations."""
import unittest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.performance_comparison import metrics, period_metrics, load


class ComparisonTests(unittest.TestCase):
    def test_metrics_capture_initial_loss(self):
        r = pd.Series([-.1, 0, .1])
        m = metrics(r, 3)
        self.assertAlmostEqual(m['Maximum drawdown'], -.1)
        self.assertAlmostEqual(m['Cumulative return'], -.01)
        self.assertAlmostEqual(m['CAGR'], -.01)
        self.assertAlmostEqual(m['Annualized volatility'], .1 * np.sqrt(3))

    def test_missing_not_silently_filled(self):
        frame = pd.DataFrame({'Top-Down': [.01, -.02, .03],
                              'Bottom-Up': [.01, np.nan, .03]})
        result = period_metrics(frame)
        self.assertTrue(result['Bottom-Up'].isna().all())
        self.assertFalse(result['Top-Down'].isna().any())

    def test_full_period_not_reset_at_boundary(self):
        r = pd.Series([-.1, -.1, .1, .1])
        result = metrics(r)
        self.assertAlmostEqual(result['Cumulative return'], .9*.9*1.1*1.1-1)
        self.assertAlmostEqual(result['Maximum drawdown'], -.19)

    def test_zero_volatility_ratio_undefined(self):
        m = metrics(pd.Series([0., 0., 0.]))
        self.assertTrue(np.isnan(m['Sharpe (rf=0)']))
        self.assertTrue(np.isnan(m['Calmar']))


if __name__ == '__main__':
    unittest.main()
