import numpy as np
import pandas as pd

from risk_budget import optimize_risk_budget


return_cols = [
    "Gold", "US10Y", "BUND", "JGB", "CHN10Y", "CA10Y", "LongGilt",
    "SP500", "EuroStoxx50", "Nikkei225", "TSX60", "MES", "FTSE100",
    "Copper", "WTI", "NatGas", "Wheat",
]


bond_map = {
    "US_ILB_Proxy": "US10Y", "Europe_ILB_Proxy": "BUND", "Japan_ILB_Proxy": "JGB",
    "China_ILB_Proxy": "CHN10Y", "Canada_ILB_Proxy": "CA10Y", "UK_ILB_Proxy": "LongGilt"
}
geography_map = {
    "US": "US_ILB_Proxy", "Europe": "Europe_ILB_Proxy", "UK": "UK_ILB_Proxy",
    "Japan": "Japan_ILB_Proxy", "China": "China_ILB_Proxy", "Canada": "Canada_ILB_Proxy"
}
level_2_map = {
    "Global_Commodities": ["Gold", "Copper", "WTI", "NatGas", "Wheat"],
    "Global_Equity": ["SP500", "EuroStoxx50", "Nikkei225", "TSX60", "MES", "FTSE100"],
    "Global_Bonds": ["US10Y", "BUND", "JGB", "CA10Y", "CHN10Y", "LongGilt"],
}
environment_map = {
    "Rising_Growth":     {"assets": ["Global_Equity", "Global_Commodities"],      "target_risk": [0.55, 0.45]},
    "Falling_Growth":    {"assets": ["Global_Bonds", "Global_ILB_Portfolio"],     "target_risk": [0.50, 0.50]},
    "Rising_Inflation":  {"assets": ["Global_Commodities", "Global_ILB_Portfolio"], "target_risk": [0.50, 0.50]},
    "Falling_Inflation": {"assets": ["Global_Equity", "Global_Bonds"],            "target_risk": [0.50, 0.50]},
}




def solve_topdown_in_window(window):
    """Solve Levels 1-4 inside ONE estimation window of raw daily returns.
    Returns the flattened capital weights on the raw instruments."""
    node_returns = {col: window[col] for col in return_cols}
    node_exposure = {}
    for col in return_cols:
        e = pd.Series(0.0, index=return_cols)
        e[col] = 1.0
        node_exposure[col] = e

    def build(name, children, target_risk=None):
        result = optimize_risk_budget(
            pd.DataFrame({c: node_returns[c] for c in children}),
            target_risk=target_risk
        )
        w = result.set_index("Asset")["Capital Weight"].reindex(children)
        node_returns[name]  = sum(node_returns[c]  * w[c] for c in children)
        node_exposure[name] = sum(node_exposure[c] * w[c] for c in children)

    for proxy_name, bond_col in bond_map.items():          # Level 1: ILB proxies
        build(proxy_name, ["Gold", bond_col], [0.50, 0.50])
    build("Global_ILB_Portfolio", list(geography_map.values()), [1 / 6] * 6)
    for name, cols in level_2_map.items():
        build(name, cols, [1 / len(cols)] * len(cols))
    for name, s in environment_map.items():                # Level 3: environments
        build(name, s["assets"], s["target_risk"])
    build("Top_Down_Total_Portfolio", list(environment_map.keys()), [0.25] * 4)   # Level 4
    return node_exposure["Top_Down_Total_Portfolio"]

def run_topdown_in_window(df, covariance_window=252, min_obs=252):
    data = df[["Index"] + return_cols].sort_values("Index").reset_index(drop=True)
    data["Quarter"] = data["Index"].dt.to_period("Q")
    port = pd.Series(np.nan, index=data.index)
    weight_rows = []

    for q in sorted(data["Quarter"].unique()):
        mask = data["Quarter"] == q
        q_start = data.loc[mask, "Index"].min()

        # only data strictly before the quarter starts, all 17 series available
        hist = (data.loc[data["Index"] < q_start, return_cols]
                .dropna().tail(covariance_window))
        if len(hist) < min_obs:
            continue                                # still warming up (one window only)

        exposure = solve_topdown_in_window(hist)
        port[mask] = (data.loc[mask, return_cols].fillna(0)
                      .mul(exposure, axis=1).sum(axis=1))
        hist_dates = data.loc[
            hist.index,
            "Index"
        ]

        weight_rows.append({
            "Quarter": str(q),
            "Effective Date": q_start,
            "History Start": hist_dates.min(),
            "History End": hist_dates.max(),
            "Observations": len(hist),
            "Gross Exposure": exposure.abs().sum(),
            **exposure.to_dict()
        })
    out = pd.DataFrame({"Index": data["Index"], "Top_Down_Total_Portfolio": port})
    return out, pd.DataFrame(weight_rows)
def run_top_down(df, covariance_window=252, min_obs=252):
    return run_topdown_in_window(
        df,
        covariance_window=covariance_window,
        min_obs=min_obs,
    )
