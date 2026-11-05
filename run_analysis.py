import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import pandas as pd

from settings import (
    DATA_FILE, OUTPUT_DIR, START_DATE, END_DATE,
    COVARIANCE_WINDOW, MIN_OBSERVATIONS,
)
from ilb_proxies import build_ilb_proxies
from top_down import run_top_down
from performance import build_performance_summary
from risk_budget import clean_returns


def load_returns(path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.strip("'")
    df["Index"] = pd.to_datetime(df["Index"], errors="coerce")
    df = (
        df.dropna(subset=["Index"])
        .sort_values("Index")
        .drop_duplicates("Index", keep="last")
        .reset_index(drop=True)
    )

    return df.reset_index(drop=True)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_returns(DATA_FILE)

    required = [
        "Gold", "US10Y", "BUND", "JGB", "CHN10Y", "CA10Y", "LongGilt",
        "SP500", "EuroStoxx50", "Nikkei225", "TSX60", "MES", "FTSE100",
        "Copper", "WTI", "NatGas", "Wheat",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Required columns are missing: {missing}")

    for col in required:
        df[col] = clean_returns(df[col])

    data, ilb_weights, global_returns, global_weights = build_ilb_proxies(
        df,
        covariance_window=COVARIANCE_WINDOW,
        min_obs=MIN_OBSERVATIONS,
    )

    ilb_weights.to_csv(OUTPUT_DIR / "ILB_Quarterly_Weights.csv", index=False)
    global_returns.to_csv(OUTPUT_DIR / "Global_ILB_Returns.csv", index=False)
    global_weights.to_csv(OUTPUT_DIR / "Global_ILB_Weights.csv", index=False)

    top_down_returns, top_down_weights = run_top_down(
        df,
        covariance_window=COVARIANCE_WINDOW,
        min_obs=MIN_OBSERVATIONS,
    )
    if START_DATE is not None:
        top_down_returns = top_down_returns.loc[
            top_down_returns["Index"] >= pd.Timestamp(START_DATE)
        ]
    if END_DATE is not None:
        top_down_returns = top_down_returns.loc[
            top_down_returns["Index"] <= pd.Timestamp(END_DATE)
        ]

    top_down_returns.to_csv(OUTPUT_DIR / "TopDown_Level4_Returns.csv", index=False)
    top_down_weights.to_csv(OUTPUT_DIR / "TopDown_Quarterly_Instrument_Weights.csv", index=False)

    valid = top_down_returns.dropna().set_index("Index")["Top_Down_Total_Portfolio"]
    if not valid.empty:
        summary = build_performance_summary(valid)
        summary.to_csv(OUTPUT_DIR / "TopDown_Performance_Summary.csv")

    print(f"Loaded {len(df):,} rows from {df['Index'].min().date()} to {df['Index'].max().date()}")
    print(f"Outputs written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
