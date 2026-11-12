"""Standalone six-region Bottom-Up hierarchy; input returns are decimals."""
from numbers import Integral

import numpy as np
import pandas as pd

if __package__:  # Support package and src-on-path imports.
    from ..risk_budget import optimize_risk_budget
else:
    from risk_budget import optimize_risk_budget

# Excel CJB Edits: rows 39-58 and 76-81. MES represents the specified MSCI EM proxy.
REGION_MAP = {
    "US": ("SP500", "US10Y"),
    "Europe": ("EuroStoxx50", "BUND"),
    "UK": ("FTSE100", "LongGilt"),
    "Japan": ("Nikkei225", "JGB"),
    "China": ("MES", "CHN10Y"),
    "Canada": ("TSX60", "CA10Y"),
}
COMMODITIES = ("Gold", "Copper", "WTI", "NatGas", "Wheat")
RETURN_COLS = list(dict.fromkeys([*COMMODITIES, *(c for pair in REGION_MAP.values() for c in pair)]))
PORTFOLIO = "Bottom_Up_Total_Portfolio"


def _validate_returns(frame):
    if not frame.columns.is_unique:
        raise ValueError("Duplicate input columns are not supported.")
    missing = set(RETURN_COLS) - set(frame.columns)
    if missing:
        raise ValueError("Missing required instruments: " + ", ".join(sorted(missing)))
    raw = frame[RETURN_COLS]
    numeric = raw.apply(pd.to_numeric, errors="coerce")
    if (raw.notna() & numeric.isna()).any().any():
        raise ValueError("Returns must be numeric decimals; convert units before calling.")
    if np.isinf(numeric.to_numpy(dtype=float)).any():
        raise ValueError("Infinite returns are not supported.")
    if (numeric < -1).any().any():
        raise ValueError("Simple returns below -100% are not supported.")
    return numeric


def solve_bottomup_in_window(window, *, return_diagnostics=False):
    """Fit all five levels in one complete window with the unchanged SLSQP API.

    Singleton country equity/bond baskets are identity mappings. Every other
    basket is risk-budget optimized, then flattened onto the raw instruments.
    Diagnostics contain confidential allocations and must stay local.
    """
    data = _validate_returns(window)
    if len(data) < 2 or data.isna().any().any():
        raise ValueError("Estimation window requires at least two complete observations.")
    nodes = {c: data[c] for c in RETURN_COLS}
    exposures = {c: pd.Series(np.eye(len(RETURN_COLS))[i], index=RETURN_COLS)
                 for i, c in enumerate(RETURN_COLS)}
    diagnostics = []

    def build(name, children, targets=None):
        try:
            result = optimize_risk_budget(
                pd.DataFrame({c: nodes[c] for c in children}), target_risk=targets)
        except (ValueError, RuntimeError) as exc:
            raise ValueError(f"Bottom-Up optimization failed at {name}.") from exc
        weights = result.set_index("Asset")["Capital Weight"].reindex(children)
        if (not np.isfinite(weights).all() or (weights < 0).any()
                or not np.isclose(weights.sum(), 1.0, atol=1e-7)):
            raise ValueError(f"Invalid optimizer weights at {name}.")
        nodes[name] = sum(nodes[c] * weights[c] for c in children)
        exposures[name] = sum(exposures[c] * weights[c] for c in children)
        diagnostics.append(result.assign(Node=name))

    for region, (_, bond) in REGION_MAP.items():
        build(f"{region}_ILB", ["Gold", bond], [0.5, 0.5])
    build("Global_Commodities", list(COMMODITIES))
    for region, (equity, bond) in REGION_MAP.items():
        # Level 2 single-instrument baskets need no optimizer (engine requires >=2).
        for suffix, instrument in (("Equity", equity), ("Bonds", bond)):
            name = f"{region}_{suffix}"
            nodes[name], exposures[name] = nodes[instrument], exposures[instrument]
        eq, bd, ilb = f"{region}_Equity", f"{region}_Bonds", f"{region}_ILB"
        baskets = {
            "Rising_Growth": ([eq, "Global_Commodities"], [0.55, 0.45]),
            "Falling_Growth": ([bd, ilb], [0.5, 0.5]),
            "Rising_Inflation": (["Global_Commodities", ilb], [0.5, 0.5]),
            "Falling_Inflation": ([eq, bd], [0.5, 0.5]),
        }
        for environment, (children, targets) in baskets.items():
            build(f"{region}_{environment}", children, targets)
        build(f"{region}_Basket", [f"{region}_{env}" for env in baskets])
    build(PORTFOLIO, [f"{region}_Basket" for region in REGION_MAP])
    exposure = exposures[PORTFOLIO].copy()
    if return_diagnostics:
        return exposure, pd.concat(diagnostics, ignore_index=True)
    return exposure


def run_bottom_up(df, covariance_window=252, min_obs=252):
    """Quarterly fit on strictly earlier complete rows; no warm-up allocation.

    Daily capital weights remain constant within a quarter, matching Top-Down's
    convention (daily constant-mix returns, not drifting buy-and-hold holdings).
    Missing active-day instrument returns contribute zero, matching Top-Down.
    Estimation windows still require complete observations; warm-up stays missing.
    """
    if (any(isinstance(v, bool) or not isinstance(v, Integral)
            for v in (covariance_window, min_obs))
            or not 2 <= min_obs <= covariance_window):
        raise ValueError("Require integer 2 <= min_obs <= covariance_window.")
    numeric = _validate_returns(df)
    if "Index" not in df:
        raise ValueError("Missing Index date column.")
    dates = pd.to_datetime(df["Index"], errors="coerce")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError("Dates must be valid and unique.")
    if dates.dt.tz is not None:
        raise ValueError("Use timezone-naive daily dates.")
    data = numeric.assign(Index=dates).sort_values("Index").reset_index(drop=True)
    quarter = data["Index"].dt.to_period("Q")
    returns = pd.Series(np.nan, index=data.index, dtype=float)
    rows = []
    for q in sorted(quarter.unique()):
        mask = quarter == q
        start = data.loc[mask, "Index"].min()
        history = data.loc[data["Index"] < start].dropna(subset=RETURN_COLS).tail(covariance_window)
        if len(history) < min_obs:
            continue
        exposure = solve_bottomup_in_window(history)
        returns.loc[mask] = data.loc[mask, RETURN_COLS].fillna(0).mul(exposure).sum(axis=1)
        rows.append({"Quarter": str(q), "Effective Date": start,
                     "History Start": history["Index"].min(),
                     "History End": history["Index"].max(), "Observations": len(history),
                     "Gross Exposure": exposure.abs().sum(), **exposure.to_dict()})
    columns = ["Quarter", "Effective Date", "History Start", "History End", "Observations",
               "Gross Exposure", *RETURN_COLS]
    return pd.DataFrame({"Index": data["Index"], PORTFOLIO: returns}), pd.DataFrame(rows, columns=columns)
