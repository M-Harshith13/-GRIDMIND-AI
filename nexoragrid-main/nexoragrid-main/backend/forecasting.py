"""Inference helpers for recursive hourly demand forecasts."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from data_loader import load_hourly_data
from orchestration import build_dispatch, solar_output_kw
from train_model import FEATURES, MODEL_PATH


SITE_SCALE_FACTOR = 32.0
SCENARIOS = {
    "balanced": {
        "name": "Balanced operations",
        "description": "Reference mix using the standard solar curve and forecast demand.",
        "demand_multiplier": 1.0,
        "solar_multiplier": 1.0,
    },
    "solar_surge": {
        "name": "Solar surge",
        "description": "Expanded PV availability tests how much grid import can be displaced.",
        "demand_multiplier": 1.0,
        "solar_multiplier": 1.45,
    },
    "demand_spike": {
        "name": "Peak demand",
        "description": "A 22% demand uplift tests battery and grid headroom during a peak event.",
        "demand_multiplier": 1.22,
        "solar_multiplier": 1.0,
    },
}


@lru_cache(maxsize=1)
def load_model_bundle() -> dict:
    if not Path(MODEL_PATH).exists():
        raise RuntimeError("Trained model is missing. Run `python train_model.py` from backend first.")
    return joblib.load(MODEL_PATH)


def _features_for(timestamp: datetime, history: list[float]) -> dict[str, float]:
    recent = np.asarray(history, dtype=float)
    return {
        "hour": timestamp.hour,
        "day_of_week": timestamp.weekday(),
        "month": timestamp.month,
        "day_of_year": timestamp.timetuple().tm_yday,
        "is_weekend": int(timestamp.weekday() >= 5),
        "lag_1": float(recent[-1]),
        "lag_24": float(recent[-24]),
        "mean_24": float(recent[-24:].mean()),
        "mean_168": float(recent[-168:].mean()),
    }


def predict_household_kw(horizon: int, start_at: datetime | None = None) -> list[dict]:
    bundle = load_model_bundle()
    series = load_hourly_data()
    history = series["load_kw"].tail(168).astype(float).tolist()
    timestamp = start_at or datetime.now().replace(minute=0, second=0, microsecond=0)
    results: list[dict] = []
    model = bundle["model"]
    for step in range(1, horizon + 1):
        target_time = timestamp + timedelta(hours=step)
        row = pd.DataFrame([_features_for(target_time, history)], columns=FEATURES)
        value = max(float(model.predict(row)[0]), 0.05)
        results.append({"timestamp": target_time.isoformat(), "load_kw": value})
        history.append(value)
        history = history[-168:]
    return results


def build_forecast(horizon: int = 24, scenario: str = "balanced", initial_soc_pct: float = 68.0) -> list[dict]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Choose from: {', '.join(SCENARIOS)}")
    config = SCENARIOS[scenario]
    raw = predict_household_kw(horizon)
    points = []
    battery_soc = float(initial_soc_pct)
    for row in raw:
        timestamp = datetime.fromisoformat(row["timestamp"])
        demand = row["load_kw"] * SITE_SCALE_FACTOR * config["demand_multiplier"]
        solar = solar_output_kw(timestamp.hour, config["solar_multiplier"])
        dispatch = build_dispatch(demand, solar, battery_soc)
        points.append({
            "timestamp": row["timestamp"],
            "hour_label": timestamp.strftime("%H:%M"),
            "demand_kw": round(demand, 2),
            "solar_kw": round(solar, 2),
            "battery_kw": round(dispatch["battery_kw"], 2),
            "battery_soc_pct": dispatch["battery_soc_pct"],
            "next_battery_soc_pct": dispatch["next_battery_soc_pct"],
            "grid_import_kw": round(dispatch["grid_import_kw"], 2),
            "renewable_share_pct": round(min(solar / max(demand, 0.1) * 100, 100), 1),
            "carbon_kg": round(dispatch["grid_import_kw"] * 0.42, 2),
        })
        battery_soc = dispatch["next_battery_soc_pct"]
    return points
