import numpy as np
import pandas as pd


def performance_metrics(returns, annualization=252):
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        raise ValueError("No valid returns in the selected period.")

    wealth = (1.0 + r).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    years = len(r) / annualization
    annual_return = wealth.iloc[-1] ** (1.0 / years) - 1.0
    annual_volatility = r.std(ddof=1) * np.sqrt(annualization)
    daily_std = r.std(ddof=1)

    sharpe_ratio = (
        r.mean() / daily_std * np.sqrt(annualization)
        if daily_std > 0 else np.nan
    )
    downside_returns = np.minimum(r, 0.0)
    downside_deviation = np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(annualization)
    sortino_ratio = (
        r.mean() * annualization / downside_deviation
        if downside_deviation > 0 else np.nan
    )

    return {
        "Start": r.index.min(),
        "End": r.index.max(),
        "Observations": len(r),
        "Annual Return": annual_return,
        "Annual Volatility": annual_volatility,
        "Sharpe Ratio (rf=0)": sharpe_ratio,
        "Sortino Ratio": sortino_ratio,
        "Maximum Drawdown": drawdown.min(),
        "Cumulative Return": wealth.iloc[-1] - 1.0,
        "Positive Day %": (r > 0).mean(),
    }


def build_performance_summary(returns):
    periods = {
        "Full Available Period": (returns.index.min(), returns.index.max()),
        "Available sample through 2022": (pd.Timestamp("2009-01-01"), pd.Timestamp("2022-12-31")),
        "Post-Covid": (pd.Timestamp("2023-01-01"), returns.index.max()),
    }
    summary = pd.DataFrame.from_dict(
        {
            name: performance_metrics(returns.loc[start:end])
            for name, (start, end) in periods.items()
        },
        orient="index",
    )
    summary.index.name = "Period"
    return summary
