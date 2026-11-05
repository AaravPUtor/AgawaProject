"""Run the top-down portfolio workflow independently."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import pandas as pd

from settings import DATA_FILE, OUTPUT_DIR, START_DATE, END_DATE, COVARIANCE_WINDOW, MIN_OBSERVATIONS
from portfolio import run_top_down
from performance import build_performance_summary
from risk_budget import clean_returns


def load_returns(path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.strip("'")
    df["Index"] = pd.to_datetime(df["Index"], errors="coerce")
    return (df.dropna(subset=["Index"]).sort_values("Index")
            .drop_duplicates("Index", keep="last").reset_index(drop=True))


def main():
    output_dir = OUTPUT_DIR / "top_down"
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_returns(DATA_FILE)

    from portfolio import return_cols
    missing = [c for c in return_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Required columns are missing: {missing}")
    for col in return_cols:
        df[col] = clean_returns(df[col])

    returns, weights = run_top_down(df, COVARIANCE_WINDOW, MIN_OBSERVATIONS)
    if START_DATE is not None:
        returns = returns.loc[returns["Index"] >= pd.Timestamp(START_DATE)]
    if END_DATE is not None:
        returns = returns.loc[returns["Index"] <= pd.Timestamp(END_DATE)]

    returns.to_csv(output_dir / "TopDown_Level4_Returns.csv", index=False)
    weights.to_csv(output_dir / "TopDown_Quarterly_Instrument_Weights.csv", index=False)
    valid = returns.dropna().set_index("Index")["Top_Down_Total_Portfolio"]
    if not valid.empty:
        build_performance_summary(valid).to_csv(output_dir / "TopDown_Performance_Summary.csv")
    print(f"Top-down workflow complete: {len(weights)} quarterly allocations")
    print(f"Outputs: {output_dir}")


if __name__ == "__main__":
    main()
