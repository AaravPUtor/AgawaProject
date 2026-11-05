import pandas as pd

from risk_budget import create_quarterly_risk_budget_proxy


BOND_MAP = {
    "US_ILB_Proxy": "US10Y",
    "Europe_ILB_Proxy": "BUND",
    "Japan_ILB_Proxy": "JGB",
    "China_ILB_Proxy": "CHN10Y",
    "Canada_ILB_Proxy": "CA10Y",
    "UK_ILB_Proxy": "LongGilt",
}

ILB_TARGET_RISK = [0.5, 0.5]


def build_ilb_proxies(
    df,
    covariance_window=252,
    min_obs=252,
    target_risk=None,
):
    """Build the six geographic ILB proxies and the global ILB portfolio."""
    data = df.copy()
    weight_tables = []

    for proxy_name, bond_col in BOND_MAP.items():
        proxy_returns, weights = create_quarterly_risk_budget_proxy(
            df=data,
            asset_cols=["Gold", bond_col],
            proxy_name=proxy_name,
            date_col="Index",
            covariance_window=covariance_window,
            min_obs=min_obs,
            target_risk=target_risk or ILB_TARGET_RISK,
        )
        data = data.merge(proxy_returns, on="Index", how="left")
        weight_tables.append(weights)

    ilb_weights = pd.concat(weight_tables, ignore_index=True)
    geography_assets = list(BOND_MAP.keys())

    global_returns, global_weights = create_quarterly_risk_budget_proxy(
        df=data,
        asset_cols=geography_assets,
        proxy_name="Global_ILB_Portfolio",
        date_col="Index",
        covariance_window=covariance_window,
        min_obs=min_obs,
        target_risk=[1 / len(geography_assets)] * len(geography_assets),
    )
    data = data.merge(global_returns, on="Index", how="left")

    return data, ilb_weights, global_returns, global_weights
