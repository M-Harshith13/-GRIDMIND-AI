"""Convert UCI's measured one-minute power readings to hourly mean kW.

The checked-in `data/demand_hourly.csv` is the prepared dataset used by training.
To reproduce it, put the UCI zip (or its household_power_consumption.txt) in data/.
"""

from pathlib import Path
import zipfile

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"
ZIP_PATH = DATA_DIR / "household_power_consumption.zip"
RAW_PATH = DATA_DIR / "household_power_consumption.txt"
OUTPUT_PATH = DATA_DIR / "demand_hourly.csv"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip"


def prepare() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_PATH.exists():
        if not ZIP_PATH.exists():
            raise FileNotFoundError(
                f"Place the UCI source archive at {ZIP_PATH} or extract its household_power_consumption.txt.\n"
                f"Source: {SOURCE_URL}"
            )
        with zipfile.ZipFile(ZIP_PATH) as archive:
            member = next(name for name in archive.namelist() if name.endswith("household_power_consumption.txt"))
            RAW_PATH.write_bytes(archive.read(member))

    frame = pd.read_csv(
        RAW_PATH,
        sep=";",
        usecols=["Date", "Time", "Global_active_power"],
        na_values=["?"],
        low_memory=False,
    )
    frame["timestamp"] = pd.to_datetime(
        frame["Date"] + " " + frame["Time"], format="%d/%m/%Y %H:%M:%S", errors="coerce"
    )
    frame["load_kw"] = pd.to_numeric(frame["Global_active_power"], errors="coerce")
    hourly = (
        frame.dropna(subset=["timestamp", "load_kw"])
        .set_index("timestamp")["load_kw"]
        .resample("h")
        .mean()
        .interpolate(limit_direction="both")
        .rename("load_kw")
        .reset_index()
    )
    hourly.to_csv(OUTPUT_PATH, index=False, date_format="%Y-%m-%d %H:%M:%S")
    print(f"Saved {len(hourly):,} measured hourly means to {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    prepare()
