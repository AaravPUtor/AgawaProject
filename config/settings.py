from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "daily_returns.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Set either value to None to use the full available date range.
START_DATE = None
END_DATE = None

COVARIANCE_WINDOW = 252
MIN_OBSERVATIONS = 252
ANNUALIZATION = 252
