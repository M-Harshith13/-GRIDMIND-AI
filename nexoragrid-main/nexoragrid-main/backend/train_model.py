"""Train and persist the Gridmind hourly demand forecaster."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.inspection import permutation_importance

from data_loader import BACKEND_DIR, DATA_SOURCE, load_hourly_data


MODEL_DIR = BACKEND_DIR / "models"
MODEL_PATH = MODEL_DIR / "gridmind_demand.joblib"
METRICS_PATH = MODEL_DIR / "performance.json"
FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "day_of_year",
    "is_weekend",
    "lag_1",
    "lag_24",
    "mean_24",
    "mean_168",
]


def make_training_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    indexed = frame.set_index("timestamp")["load_kw"].sort_index()
    values = pd.DataFrame(index=indexed.index)
    values["hour"] = values.index.hour
    values["day_of_week"] = values.index.dayofweek
    values["month"] = values.index.month
    values["day_of_year"] = values.index.dayofyear
    values["is_weekend"] = (values.index.dayofweek >= 5).astype(int)
    values["lag_1"] = indexed.shift(1)
    values["lag_24"] = indexed.shift(24)
    values["mean_24"] = indexed.shift(1).rolling(24).mean()
    values["mean_168"] = indexed.shift(1).rolling(168).mean()
    joined = values.assign(target=indexed).dropna()
    return joined[FEATURES], joined["target"]


def train() -> dict:
    data = load_hourly_data()
    X, y = make_training_frame(data)
    split = min(max(int(len(X) * 0.82), 24), len(X) - 24)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = HistGradientBoostingRegressor(
        max_iter=220,
        learning_rate=0.06,
        max_leaf_nodes=31,
        l2_regularization=2.0,
        random_state=42,
    )
    model.fit(X_train, y_train)
    predicted = np.maximum(model.predict(X_test), 0)
    mae = float(mean_absolute_error(y_test, predicted))
    rmse = float(np.sqrt(mean_squared_error(y_test, predicted)))
    denominator = np.maximum(np.abs(y_test.to_numpy()), 0.1)
    mape = float(np.mean(np.abs(y_test.to_numpy() - predicted) / denominator) * 100)
    r2 = float(r2_score(y_test, predicted))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    importance_result = permutation_importance(
        model, X_test, y_test, scoring="neg_mean_absolute_error", n_repeats=3, random_state=42, n_jobs=1
    )
    importance_values = np.maximum(importance_result.importances_mean, 0)
    if importance_values.sum() == 0:
        importance_values = np.ones(len(FEATURES), dtype=float)
    importance_values = importance_values / importance_values.sum()
    metadata = {
        "model": model,
        "algorithm": "HistGradientBoostingRegressor",
        "features": FEATURES,
        "metrics": {"mae_kw": mae, "rmse_kw": rmse, "mape_pct": mape, "r2": r2},
        "feature_importance": [
            {"feature": name, "importance": float(value)}
            for name, value in sorted(
                zip(FEATURES, importance_values), key=lambda pair: pair[1], reverse=True
            )
        ],
        "feature_importance_method": "Permutation importance (MAE reduction)",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": int(len(X_train)),
        "evaluation_rows": int(len(X_test)),
        "dataset_rows": int(len(data)),
        "dataset_start": data["timestamp"].min().isoformat(),
        "dataset_end": data["timestamp"].max().isoformat(),
        "dataset_source": DATA_SOURCE,
    }
    joblib.dump(metadata, MODEL_PATH, compress=3)
    METRICS_PATH.write_text(json.dumps({k: v for k, v in metadata.items() if k != "model"}, indent=2))
    print(f"Trained on {len(X_train):,} hourly rows; evaluated on {len(X_test):,}.")
    print(f"Validation MAE {mae:.3f} kW | RMSE {rmse:.3f} kW | MAPE {mape:.1f}% | R² {r2:.3f}")
    print(f"Saved model: {MODEL_PATH}")
    return metadata


if __name__ == "__main__":
    train()
