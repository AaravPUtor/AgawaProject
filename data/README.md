# Input data

Place the daily returns CSV here as `daily_returns.csv`.

The file must contain an `Index` date column and the instrument columns listed in
`run_analysis.py`. The loader strips whitespace and surrounding single quotes
from column names. It applies the `clean_returns` convention from the notebook:
values are divided by 100 (so `1.0` represents a 1% return).

Keep the full history in this file. Date filters are applied to the reported
top-down return series after the rolling estimation windows have been built.

The source workbooks/CSV were not included in this repository archive.
