# ILB Proxy and Risk-Budget Analysis

This repository organizes the overlapping notebook work into reusable Python
modules. It combines the quarterly ILB proxy construction with the top-down
portfolio workflow and keeps the SLSQP optimizer as the single optimization
method.

## Structure

- `src/risk_budget.py`: risk contributions, objective, SLSQP optimizer, and quarterly proxy builder.
- `src/ilb_proxies.py`: six geographic ILB proxies and the global ILB portfolio.
- `src/top_down.py`: four-level top-down portfolio construction.
- `src/performance.py`: return, volatility, Sharpe, Sortino, drawdown, and period summaries.
- `config/settings.py`: input/output paths, date filters, and estimation-window settings.
- `run_analysis.py`: end-to-end entry point.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Place the daily returns file at `data/daily_returns.csv`, then run:

```bash
python run_analysis.py
```

The CSV needs an `Index` column and the instruments used in `run_analysis.py`.
The loader uses the notebook's `clean_returns` convention: values are divided by 100 (for example, `1.0` means 1%).

## Estimation choices

- The optimizer uses SLSQP with multiple starting points.
- Quarterly proxy weights are estimated using observations strictly before the
  quarter and held fixed during that quarter.
- The default covariance window and minimum history are 252 trading observations.
- The first-layer ILB proxy target is 50/50 Gold and the corresponding nominal
  government bond. The global ILB portfolio uses equal target risk across six
  geographic proxies.
- Top-down target risk is explicit at each layer: 50/50 for each geographic ILB
  proxy, equal across six geographies for the global ILB portfolio, equal across
  instruments within each Level 2 group, the configured environment targets,
  and 25% per environment at the final level.
- `START_DATE` and `END_DATE` in `config/settings.py` default to `None`. Set them
  to impose a sample period. If the sample starts after the original data begins,
  make sure enough pre-start observations remain available for the 252-day
  estimation warm-up; otherwise early quarters will use the proxy builder's
  equal-weight fallback or the top-down workflow will remain unconstructed.

## Outputs

The script writes quarterly weights and return series to `outputs/`, including
geographic/global ILB weights and top-down instrument exposures. The performance
summary covers the available period, 2009–2022, and 2023 onward where data exists.

## Notes

This is a cleaned organization of the supplied notebooks, not a validation of
the underlying investment methodology. In particular, the source notebook
contains a fallback to equal capital weights when a quarterly proxy has fewer
than `min_obs` historical observations. Review that treatment before relying on
early-period results. No source data file is included.
