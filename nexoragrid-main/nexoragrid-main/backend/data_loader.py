"""Load the packaged, hourly UCI household demand series."""

from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parent
DATA_PATH = BACKEND_DIR / "data" / "demand_hourly.csv"
DATA_SOURCE = "UCI Individual household electric power consumption"


def load_hourly_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Training data was not found at {DATA_PATH}. See README.md for provenance."
        )

    frame = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    required = {"timestamp", "load_kw"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Dataset must contain columns: {', '.join(sorted(required))}")

    frame = frame[["timestamp", "load_kw"]].dropna().sort_values("timestamp")
    frame["load_kw"] = pd.to_numeric(frame["load_kw"], errors="coerce")
    frame = frame.dropna(subset=["load_kw"]).drop_duplicates("timestamp")
    frame = frame.set_index("timestamp").resample("h").mean().interpolate(limit_direction="both")
    frame = frame.reset_index()
    if len(frame) < 24 * 14:
        raise ValueError("At least 14 days of hourly demand data are required to train the model.")
    return frame
