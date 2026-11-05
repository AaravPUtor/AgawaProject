import numpy as np
import pandas as pd
from scipy.optimize import minimize


# CLEAN RETURNS

def clean_returns(series):

    return pd.to_numeric(
        series
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.strip(),
        errors="coerce"
    ) / 100


# RISK CONTRIBUTIONS
# using covariance matrices now - taking cov_matrix in now

def risk_contributions(weights, cov_matrix):

    weights = np.asarray(weights)

    portfolio_variance = (
        weights @ cov_matrix @ weights
    )

    component_variance = (
        weights * (cov_matrix @ weights)
    )

    rc_percent = (
        component_variance / portfolio_variance
    )

    return rc_percent


# RISK BUDGET OBJECTIVE

def risk_budget_objective(
    weights,
    cov_matrix,
    target_risk
):

    actual_rc = risk_contributions(
        weights,
        cov_matrix
    )

    return np.sum(
        (actual_rc - target_risk) ** 2
    )


def optimize_risk_budget(
    asset_returns,
    target_risk=None,
    bounds=None,
    maxiter=5000
):
    asset_returns = (
        asset_returns
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .dropna(axis=0, how="any")
    )

    asset_cols = asset_returns.columns.tolist()
    n_assets = len(asset_cols)

    if n_assets < 2:
        raise ValueError("At least two assets are required.")

    if len(asset_returns) < 2:
        raise ValueError("Insufficient complete return observations.")

    cov = asset_returns.cov().to_numpy(dtype=float)
    cov = (cov + cov.T) / 2

    if not np.isfinite(cov).all():
        raise ValueError("Covariance matrix contains invalid values.")

    if np.any(np.diag(cov) <= 1e-14):
        raise ValueError(
            "At least one asset has zero or near-zero variance."
        )

    scale = np.max(np.diag(cov))
    cov = cov / scale

    if target_risk is None:
        target_rc = np.ones(n_assets) / n_assets
    else:
        target_rc = np.asarray(target_risk, dtype=float)

        if len(target_rc) != n_assets:
            raise ValueError(
                "Target risk length must match asset count."
            )

        if (
            not np.isfinite(target_rc).all()
            or np.any(target_rc < 0)
            or target_rc.sum() <= 0
        ):
            raise ValueError(
                "Target risk must contain finite, nonnegative values "
                "with a positive sum."
            )

        target_rc = target_rc / target_rc.sum()

    if bounds is None:
        bounds = [(0.001, 0.999)] * n_assets

    constraints = [
        {
            "type": "eq",
            "fun": lambda w: np.sum(w) - 1.0
        }
    ]

    objective = lambda w: risk_budget_objective(
        w, cov, target_rc
    )

    rng = np.random.default_rng(42)

    starts = [
        np.ones(n_assets) / n_assets
    ]

    starts.extend(
        rng.dirichlet(np.ones(n_assets))
        for _ in range(5)
    )

    candidates = []

    for x0 in starts:
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={
                "maxiter": maxiter,
                "ftol": 1e-12,
                "disp": False
            }
        )

        if (
            result.success
            and np.isfinite(result.fun)
            and np.isfinite(result.x).all()
        ):
            candidates.append(result)

    if not candidates:
        raise RuntimeError(
            "Risk-budget optimization failed for all starting "
            "points. Check risk_budget_objective(), the covariance "
            "matrix, and the feasibility of the bounds."
        )

    best = min(candidates, key=lambda r: r.fun)

    weights = best.x / best.x.sum()

    portfolio_variance = weights @ cov @ weights

    if portfolio_variance <= 0:
        raise ValueError(
            "Optimized portfolio has nonpositive variance."
        )

    marginal_risk = cov @ weights

    actual_rc = (
        weights * marginal_risk / portfolio_variance
    )

    return pd.DataFrame({
        "Asset": asset_cols,
        "Capital Weight": weights,
        "Target Risk Contribution": target_rc,
        "Actual Risk Contribution": actual_rc
    })


# ROLLING QUARTERLY OPTIMIZATION
# subject to change based on feedback on whether we should just stick to the static approach

def create_quarterly_risk_budget_proxy(
    df,
    asset_cols,
    proxy_name,
    date_col="Index",
    covariance_window=252,
    min_obs=252,
    target_risk=None,
    bounds=None
):

    data = df[
        [date_col] + asset_cols
    ].copy()

    data[date_col] = pd.to_datetime(
        data[date_col],
        errors="coerce"
    )

    data = (
        data
        .dropna(subset=[date_col])
        .sort_values(date_col)
        .reset_index(drop=True)
    )

    # group each daily return into its quarter
    data["Quarter"] = (
        data[date_col]
        .dt.to_period("Q")
    )

    data[proxy_name] = np.nan

    weight_history = []

    quarters = sorted(
        data["Quarter"].unique()
    )

    for quarter in quarters:

        quarter_mask = (
            data["Quarter"] == quarter
        )

        # redo the optimization at the start of each quarter
        quarter_start = (
            data.loc[
                quarter_mask,
                date_col
            ].min()
        )

        # only use data available before the quarter starts
        historical_data = (
            data.loc[
                data[date_col] < quarter_start,
                [date_col] + asset_cols
            ]
            .dropna(subset=asset_cols)
        )

        # use the most recent covariance_window trading observations
        history = (
            historical_data
            .tail(covariance_window)
            .copy()
        )

        if len(history) > 0:

            history_start = (
                history[date_col].min()
            )

            history_end = (
                history[date_col].max()
            )

        else:

            history_start = pd.NaT
            history_end = pd.NaT

        history_returns = (
            history[asset_cols]
        )

        if len(history_returns) < min_obs:

            weights = pd.Series(
                np.repeat(
                    1 / len(asset_cols),
                    len(asset_cols)
                ),
                index=asset_cols
            )

            if target_risk is None:

                target_rc = pd.Series(
                    np.repeat(
                        1 / len(asset_cols),
                        len(asset_cols)
                    ),
                    index=asset_cols
                )

            else:

                target_rc = pd.Series(
                    target_risk,
                    index=asset_cols
                )

            actual_rc = pd.Series(
                np.repeat(
                    np.nan,
                    len(asset_cols)
                ),
                index=asset_cols
            )

        else:

            # otherwise optimize using the historical window
            optimization = optimize_risk_budget(
                asset_returns=history_returns,
                target_risk=target_risk,
                bounds=bounds
            )

            weights = (
                optimization
                .set_index("Asset")
                ["Capital Weight"]
                .reindex(asset_cols)
            )

            target_rc = (
                optimization
                .set_index("Asset")
                ["Target Risk Contribution"]
                .reindex(asset_cols)
            )

            actual_rc = (
                optimization
                .set_index("Asset")
                ["Actual Risk Contribution"]
                .reindex(asset_cols)
            )

        # keep these weights fixed for every day in the quarter
        quarter_returns = (
            data.loc[
                quarter_mask,
                asset_cols
            ]
        )

        weighted_returns = (
            quarter_returns
            .mul(
                weights,
                axis=1
            )
        )

        data.loc[
            quarter_mask,
            proxy_name
        ] = (
            weighted_returns
            .sum(
                axis=1,
                min_count=len(asset_cols)
            )
        )

        # save the weights so we can see how they changed each quarter
        record = {
            "Quarter": str(quarter),
            "Proxy": proxy_name,
            "History Start": history_start,
            "History End": history_end,
            "Observations": len(history_returns),
            "Covariance Window": covariance_window
        }

        for asset in asset_cols:

            record[
                f"{asset} Weight"
            ] = weights[asset]

            record[
                f"{asset} Target RC"
            ] = target_rc[asset]

            record[
                f"{asset} Actual RC"
            ] = actual_rc[asset]

        weight_history.append(
            record
        )

    weights_df = pd.DataFrame(
        weight_history
    )

    proxy_df = data[
        [
            date_col,
            proxy_name
        ]
    ].copy()

    return (
        proxy_df,
        weights_df
    )
