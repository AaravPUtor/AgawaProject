
"""Export covariance matrices and optimization weights for either hierarchy."""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# Allow imports from the project's src directory.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from src.bottom_up.portfolio import (
    RETURN_COLS as BOTTOM_UP_COLS,
    solve_bottomup_in_window,
)

from top_down.portfolio import (
    return_cols as TOP_DOWN_COLS,
    solve_topdown_in_window,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export covariance matrices and weights for portfolio optimizations."
    )

    parser.add_argument(
        "--method",
        choices=["bottom_up", "top_down"],
        required=True,
    )
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--return-unit",
        choices=["decimal", "percent"],
        default="decimal",
    )
    parser.add_argument(
        "--quarter",
        default="all",
        help="Quarter such as 2025Q2, or 'all'.",
    )
    parser.add_argument(
        "--level",
        default="all",
        help="Optimization level 1-5, or 'all'.",
    )
    parser.add_argument("--covariance-window", type=int, default=252)
    parser.add_argument("--min-obs", type=int, default=252)
    parser.add_argument(
        "--output-dir",
        default="outputs/diagnostics",
    )

    return parser.parse_args()


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def export_node(node, quarter, history, output_dir, method):
    level = node["Level"]
    name = safe_name(node["Node"])

    folder = (
        output_dir
        / method
        / quarter
        / f"Level_{level}"
    )
    folder.mkdir(parents=True, exist_ok=True)

    # Exact covariance matrices used by the optimizer.
    node["Raw Covariance"].to_csv(
        folder / f"{name}_Covariance.csv"
    )

    node["Normalized Covariance"].to_csv(
        folder / f"{name}_Normalized_Covariance.csv"
    )

    # Capital weights and risk contributions.
    node["Weights"].to_csv(
        folder / f"{name}_Weights.csv",
        index=False
    )

    # Metadata for independent verification.
    metadata = pd.DataFrame([{
        "Method": method,
        "Quarter": quarter,
        "Node": node["Node"],
        "Level": level,
        "Assets": ", ".join(node["Assets"]),
        "History Start": history.index.min(),
        "History End": history.index.max(),
        "Observations": node["Observations"],
        "Covariance Scale": node["Covariance Scale"],
        "Objective Value": node["Objective Value"],
        "Iterations": node["Iterations"],
    }])

    metadata.to_csv(
        folder / f"{name}_Metadata.csv",
        index=False
    )


def main():
    args = parse_args()

    if args.covariance_window < 2:
        raise ValueError("--covariance-window must be at least 2.")

    if not 2 <= args.min_obs <= args.covariance_window:
        raise ValueError(
            "Require 2 <= --min-obs <= --covariance-window."
        )

    if args.level != "all":
        try:
            selected_level = int(args.level)
        except ValueError:
            raise ValueError("--level must be 1, 2, 3, 4, 5, or all.")

        if selected_level not in range(1, 6):
            raise ValueError("--level must be between 1 and 5.")

    if args.quarter != "all":
        try:
            pd.Period(args.quarter, freq="Q")
        except Exception as exc:
            raise ValueError(
                "Quarter must look like 2025Q2 or be 'all'."
            ) from exc

    # Select the hierarchy's underlying instruments.
    columns = (
        BOTTOM_UP_COLS
        if args.method == "bottom_up"
        else TOP_DOWN_COLS
    )

    # Load and prepare data.
    data = pd.read_csv(args.input)

    if "Index" not in data.columns:
        raise ValueError("Input CSV must contain an Index column.")

    missing = set(columns) - set(data.columns)
    if missing:
        raise ValueError(
            "Missing required instruments: " + ", ".join(sorted(missing))
        )

    data["Index"] = pd.to_datetime(data["Index"], errors="coerce")

    if data["Index"].isna().any():
        raise ValueError("Invalid dates found in Index column.")

    if data["Index"].duplicated().any():
        raise ValueError("Duplicate dates found in Index column.")

    data = data.sort_values("Index").reset_index(drop=True)

    data[columns] = data[columns].apply(
        pd.to_numeric,
        errors="coerce"
    )

    if data[columns].isna().all().any():
        raise ValueError("At least one instrument has no valid numeric returns.")

    if args.return_unit == "percent":
        data[columns] = data[columns] / 100.0

    if (data[columns] < -1).any().any():
        raise ValueError(
            "Returns below -100% found. Check the return-unit argument."
        )

    data["Quarter"] = data["Index"].dt.to_period("Q")

    # Select quarters.
    quarters = sorted(data["Quarter"].unique())

    if args.quarter != "all":
        requested = pd.Period(args.quarter, freq="Q")
        if requested not in quarters:
            raise ValueError(f"No observations found for {requested}.")
        quarters = [requested]

    output_dir = Path(args.output_dir)
    exported_nodes = 0
    skipped_quarters = []

    for quarter in quarters:
        quarter_mask = data["Quarter"] == quarter
        quarter_start = data.loc[quarter_mask, "Index"].min()

        # Match the historical-window logic used by the portfolio runners.
        history = (
            data.loc[data["Index"] < quarter_start, ["Index", *columns]]
            .dropna(subset=columns)
            .tail(args.covariance_window)
            .set_index("Index")
        )

        if len(history) < args.min_obs:
            skipped_quarters.append(str(quarter))
            print(
                f"Skipping {quarter}: only {len(history)} "
                f"historical observations."
            )
            continue

        # Run the actual hierarchy with diagnostics enabled.
        if args.method == "bottom_up":
            _, diagnostics = solve_bottomup_in_window(
                history,
                return_covariance_diagnostics=True
            )
        else:
            _, diagnostics = solve_topdown_in_window(
                history,
                return_covariance_diagnostics=True
            )

        for node in diagnostics:
            if (
                args.level != "all"
                and node["Level"] != int(args.level)
            ):
                continue

            export_node(
                node,
                str(quarter),
                history,
                output_dir,
                args.method
            )
            exported_nodes += 1

        print(
            f"{quarter}: exported diagnostics for "
            f"{sum(1 for n in diagnostics if args.level == 'all' or n['Level'] == int(args.level))} "
            "optimization nodes."
        )

    print("\nExport complete.")
    print(f"Method: {args.method}")
    print(f"Exported optimization nodes: {exported_nodes}")
    print(f"Output directory: {output_dir / args.method}")

    if skipped_quarters:
        print("Skipped quarters:", ", ".join(skipped_quarters))


if __name__ == "__main__":
    main()
