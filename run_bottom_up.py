"""Independent Bottom-Up entry point; never invokes or modifies Top-Down."""
import argparse
from pathlib import Path

import pandas as pd

from src.bottom_up import RETURN_COLS, PORTFOLIO, run_bottom_up


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--return-unit", choices=("percent", "decimal"), required=True,
                        help="percent: 1 means 1%%; decimal: 0.01 means 1%%")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Local directory for confidential Bottom-Up outputs")
    parser.add_argument("--window", type=int, default=252)
    parser.add_argument("--min-obs", type=int, default=252)
    args = parser.parse_args()
   
    df = pd.read_csv(args.input)
    df.columns = df.columns.str.strip().str.strip("'")
    if not df.columns.is_unique or set(["Index", *RETURN_COLS]) - set(df.columns):
        parser.error("Input requires unique Index and all mapped instrument columns.")
    # Drop only entirely empty required-input rows (e.g. trailing CSV padding).
    blank = df[["Index", *RETURN_COLS]].replace(r"^\s*$", pd.NA, regex=True).isna()
    if (blank["Index"] & ~blank.all(axis=1)).any():
        parser.error("Undated row contains instrument data; correct input before running.")
    df = df.loc[~blank.all(axis=1)].copy()
    for col in RETURN_COLS:
        raw = df[col]
        text = raw.astype("string").str.strip()
        if args.return_unit == "decimal" and text.str.contains("%", na=False).any():
            parser.error("Percent signs conflict with decimal units.")
        numeric = pd.to_numeric(text.str.replace("%", "", regex=False), errors="coerce")
        if (raw.notna() & numeric.isna()).any():
            parser.error("Non-numeric return value; correct input before running.")
        df[col] = numeric.astype(float) / (100 if args.return_unit == "percent" else 1)
    returns, weights = run_bottom_up(df, args.window, args.min_obs)
    if weights.empty:
        parser.error("No eligible rebalance dates; provide more complete historical data.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    returns.to_csv(args.output_dir / "BottomUp_Level5_Returns.csv", index=False)
    weights.to_csv(args.output_dir / "BottomUp_Quarterly_Instrument_Weights.csv", index=False)
    print("Bottom-Up complete. Confidential results saved locally; no allocations printed.")


if __name__ == "__main__":
    main()
