"""Synthetic-only regression tests; no confidential inputs."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import bottom_up as bu


def sample(n=120):
    rng = np.random.default_rng(901)
    return pd.DataFrame(rng.normal(0, .01, (n, len(bu.RETURN_COLS))),
                        columns=bu.RETURN_COLS).assign(Index=pd.bdate_range('2020-01-01', periods=n))


class BottomUpTests(unittest.TestCase):
    def test_hierarchy_and_flattening(self):
        frame = sample()
        original = frame.copy(deep=True)
        with patch.object(bu, 'optimize_risk_budget', wraps=bu.optimize_risk_budget) as engine:
            exposure, audit = bu.solve_bottomup_in_window(frame, return_diagnostics=True)
        self.assertEqual(engine.call_count, 38)
        self.assertEqual(bu.REGION_MAP, {
            'US': ('SP500', 'US10Y'), 'Europe': ('EuroStoxx50', 'BUND'),
            'UK': ('FTSE100', 'LongGilt'), 'Japan': ('Nikkei225', 'JGB'),
            'China': ('MES', 'CHN10Y'), 'Canada': ('TSX60', 'CA10Y')})
        self.assertAlmostEqual(exposure.sum(), 1)
        self.assertTrue((exposure >= 0).all())
        nodes = {c: frame[c] for c in bu.RETURN_COLS}
        for r, (eq, bd) in bu.REGION_MAP.items():
            nodes[r + '_Equity'], nodes[r + '_Bonds'] = frame[eq], frame[bd]
        for name, records in audit.groupby('Node', sort=False):
            nodes[name] = sum(nodes[row['Asset']] * row['Capital Weight']
                              for _, row in records.iterrows())
        np.testing.assert_allclose(frame[bu.RETURN_COLS] @ exposure, nodes[bu.PORTFOLIO], atol=1e-14)
        pd.testing.assert_frame_equal(frame, original)

    def test_no_lookahead_missing_and_warmup(self):
        frame = sample()
        out, weights = bu.run_bottom_up(frame, 40, 40)
        cutoff = pd.Timestamp('2020-04-01')
        changed = frame.copy()
        changed.loc[changed.Index >= cutoff, bu.RETURN_COLS] *= 4
        _, changed_weights = bu.run_bottom_up(changed, 40, 40)
        pd.testing.assert_frame_equal(weights, changed_weights)
        self.assertTrue(out.loc[out.Index < cutoff, bu.PORTFOLIO].isna().all())
        self.assertTrue((weights['History End'] < weights['Effective Date']).all())
        changed.loc[changed.Index == cutoff, 'Gold'] = np.nan
        missing, _ = bu.run_bottom_up(changed, 40, 40)
        expected = changed.loc[changed.Index == cutoff, bu.RETURN_COLS].fillna(0).mul(
            weights.iloc[0][bu.RETURN_COLS].astype(float)).sum(axis=1)
        np.testing.assert_allclose(missing.loc[missing.Index == cutoff, bu.PORTFOLIO], expected)
        self.assertFalse(missing.loc[missing.Index == cutoff, bu.PORTFOLIO].isna().any())
        w = weights.iloc[0][bu.RETURN_COLS].astype(float)
        np.testing.assert_allclose(out.loc[out.Index >= cutoff, bu.PORTFOLIO],
                                  frame.loc[frame.Index >= cutoff, bu.RETURN_COLS] @ w)

    def test_guards(self):
        frame = sample()
        for window, minimum in [(1, 1), (10, 11), (20.5, 10), (True, 2)]:
            with self.assertRaises(ValueError): bu.run_bottom_up(frame, window, minimum)
        for bad in [frame.drop(columns='MES'), frame.assign(Index=pd.NaT),
                    pd.concat([frame, frame.iloc[:1]]), frame.assign(Gold=np.inf),
                    frame.assign(Gold='bad'), frame.assign(Gold=-2)]:
            with self.assertRaises(ValueError): bu.run_bottom_up(bad, 40, 40)
        with self.assertRaises(ValueError): bu.solve_bottomup_in_window(frame.assign(Gold=0))
        returns, weights = bu.run_bottom_up(frame.iloc[:10])
        self.assertTrue(returns[bu.PORTFOLIO].isna().all())
        self.assertTrue(weights.empty)

    def test_existing_optimizer_tests(self):
        spec = importlib.util.spec_from_file_location('existing_tests', ROOT / 'tests/test_risk_budget.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.test_risk_contributions_sum_to_one()
        module.test_optimizer_returns_valid_long_only_weights()


if __name__ == '__main__': unittest.main()
