"""Local application services shared by the PySide6 pages."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from chatbot import answer as chatbot_answer
from data_loader import DATA_SOURCE, load_hourly_data
from forecasting import (
    SITE_SCALE_FACTOR,
    build_forecast,
    load_model_bundle,
    predict_household_kw,
)
from orchestration import (
    BATTERY_CAPACITY_KWH,
    BATTERY_INVERTER_KW,
    GRID_LIMIT_KW,
    PV_CAPACITY_KW,
    build_dispatch,
    solar_output_kw,
)
from storage import (
    get_battery_soc,
    get_chat_history,
    get_recent_scenarios,
    initialize_database,
    record_snapshot,
    save_chat,
    save_scenario,
    set_battery_soc,
)
from train_model import make_training_frame


class DesktopService:
    """Own model-backed reads and simulations without an HTTP server."""

    def __init__(self) -> None:
        initialize_database()

    @staticmethod
    @lru_cache(maxsize=1)
    def model_bundle() -> dict:
        return load_model_bundle()

    @staticmethod
    def dataset():
        return load_hourly_data()

    def dashboard(self) -> dict:
        data = self.dataset()
        bundle = self.model_bundle()
        soc = get_battery_soc()
        forecast = build_forecast(24, "balanced", soc)
        first = forecast[0]
        dispatch = build_dispatch(first["demand_kw"], first["solar_kw"], soc)
        dispatch["demand_kw"] = first["demand_kw"]
        dispatch["solar_kw"] = first["solar_kw"]
        dispatch["battery_soc_pct"] = soc

        recent = data.tail(48)
        recent_actual = [
            {
                "timestamp": row.timestamp.isoformat(),
                "demand_kw": round(float(row.load_kw) * SITE_SCALE_FACTOR, 2),
            }
            for row in recent.itertuples()
        ]
        recent_solar = [
            {
                "timestamp": row.timestamp.isoformat(),
                "solar_kw": solar_output_kw(row.timestamp.hour),
            }
            for row in recent.itertuples()
        ]
        assets = [
            {
                "name": "Solar array",
                "type": "Generation",
                "status": "Simulated · available",
                "output_kw": first["solar_kw"],
                "capacity_kw": PV_CAPACITY_KW,
            },
            {
                "name": "Battery storage",
                "type": "Storage",
                "status": "Charging" if first["battery_kw"] < -0.05 else "Discharging" if first["battery_kw"] > 0.05 else "Standby",
                "output_kw": abs(first["battery_kw"]),
                "capacity_kw": BATTERY_INVERTER_KW,
                "soc_pct": soc,
            },
            {
                "name": "Grid intertie",
                "type": "Intertie",
                "status": "Importing" if first["grid_import_kw"] > 0.05 else "Standby",
                "output_kw": first["grid_import_kw"],
                "capacity_kw": GRID_LIMIT_KW,
            },
        ]
        state = {
            "captured_at": datetime.now().astimezone().isoformat(timespec="minutes"),
            "telemetry_mode": "Model replay · no hardware connection",
            "dataset_source": DATA_SOURCE,
            "dataset_start": data["timestamp"].min().isoformat(),
            "dataset_end": data["timestamp"].max().isoformat(),
            "current_demand_kw": first["demand_kw"],
            "solar_kw": first["solar_kw"],
            "battery_kw": first["battery_kw"],
            "battery_soc_pct": soc,
            "grid_import_kw": first["grid_import_kw"],
            "renewable_share_pct": first["renewable_share_pct"],
            "carbon_kg_per_hour": first["carbon_kg"],
            "grid_headroom_kw": round(GRID_LIMIT_KW - first["grid_import_kw"], 2),
            "status": dispatch["status"],
            "forecast": forecast,
            "recent_actual": recent_actual,
            "recent_solar_simulation": recent_solar,
            "asset_status": assets,
            "battery_capacity_kwh": BATTERY_CAPACITY_KWH,
            "model_mae_kw": round(bundle["metrics"]["mae_kw"] * SITE_SCALE_FACTOR, 2),
        }
        record_snapshot(
            {
                "demand_kw": state["current_demand_kw"],
                "solar_kw": state["solar_kw"],
                "battery_soc_pct": state["battery_soc_pct"],
                "grid_import_kw": state["grid_import_kw"],
                "renewable_share_pct": state["renewable_share_pct"],
            }
        )
        return state

    def forecast_page(self, horizon: int = 24) -> dict:
        data = self.dataset()
        bundle = self.model_bundle()
        X, y = make_training_frame(data)
        validation_count = int(bundle["evaluation_rows"])
        validation_start = max(len(X) - validation_count, 0)
        X_holdout = X.iloc[validation_start:]
        y_holdout = y.iloc[validation_start:]
        limit = min(96, len(X_holdout))
        X_eval = X_holdout.tail(limit)
        y_eval = y_holdout.tail(limit)
        prediction = bundle["model"].predict(X_eval)
        evaluation = [
            {
                "timestamp": timestamp.isoformat(),
                "actual_kw": round(float(actual), 3),
                "predicted_kw": round(float(predicted), 3),
            }
            for timestamp, actual, predicted in zip(y_eval.index, y_eval.to_numpy(), prediction)
        ]
        return {
            "forecast": build_forecast(horizon, "balanced", get_battery_soc()),
            "evaluation": evaluation,
            "metrics": bundle["metrics"],
            "algorithm": bundle["algorithm"],
            "trained_at": bundle["trained_at"],
            "training_rows": bundle["training_rows"],
            "evaluation_rows": bundle["evaluation_rows"],
            "dataset_rows": len(data),
            "dataset_start": data["timestamp"].min().isoformat(),
            "dataset_end": data["timestamp"].max().isoformat(),
            "dataset_source": DATA_SOURCE,
            "feature_importance": bundle["feature_importance"],
        }

    @staticmethod
    def _dispatch_plan(raw_forecast: list[dict], config: dict) -> list[dict]:
        soc = float(config["initial_soc_pct"])
        points = []
        for row in raw_forecast:
            timestamp = datetime.fromisoformat(row["timestamp"])
            demand = float(row["load_kw"]) * SITE_SCALE_FACTOR * float(config["demand_multiplier"])
            solar = solar_output_kw(timestamp.hour, capacity_kw=float(config["solar_capacity_kw"]))
            dispatch = build_dispatch(
                demand,
                solar,
                soc,
                battery_capacity_kwh=float(config["battery_capacity_kwh"]),
                battery_inverter_kw=BATTERY_INVERTER_KW,
                grid_limit_kw=GRID_LIMIT_KW,
                grid_available=bool(config["grid_available"]),
            )
            points.append(
                {
                    "timestamp": row["timestamp"],
                    "hour_label": timestamp.strftime("%a %H:%M"),
                    "demand_kw": dispatch["demand_kw"],
                    "solar_kw": dispatch["solar_kw"],
                    "battery_kw": dispatch["battery_kw"],
                    "battery_soc_pct": dispatch["battery_soc_pct"],
                    "next_battery_soc_pct": dispatch["next_battery_soc_pct"],
                    "grid_import_kw": dispatch["grid_import_kw"],
                    "unserved_kw": dispatch["unserved_kw"],
                    "renewable_share_pct": dispatch["renewable_share_pct"],
                    "carbon_kg": dispatch["carbon_kg_per_hour"],
                    "status": dispatch["status"],
                }
            )
            soc = dispatch["next_battery_soc_pct"]
        return points

    def simulate(self, inputs: dict, horizon: int = 24, persist: bool = True) -> dict:
        horizon = max(6, min(int(horizon), 48))
        config = {
            "solar_capacity_kw": max(0.0, min(float(inputs["solar_capacity_kw"]), 1000.0)),
            "battery_capacity_kwh": max(1.0, min(float(inputs["battery_capacity_kwh"]), 10000.0)),
            "initial_soc_pct": max(20.0, min(float(inputs["initial_soc_pct"]), 100.0)),
            "demand_multiplier": max(0.1, min(float(inputs["demand_multiplier"]), 5.0)),
            "grid_available": bool(inputs["grid_available"]),
        }
        baseline_config = {
            "solar_capacity_kw": PV_CAPACITY_KW,
            "battery_capacity_kwh": BATTERY_CAPACITY_KWH,
            "initial_soc_pct": config["initial_soc_pct"],
            "demand_multiplier": 1.0,
            "grid_available": True,
        }
        raw = predict_household_kw(horizon)
        baseline = self._dispatch_plan(raw, baseline_config)
        scenario_points = self._dispatch_plan(raw, config)
        baseline_grid_energy = sum(point["grid_import_kw"] for point in baseline)
        scenario_grid_energy = sum(point["grid_import_kw"] for point in scenario_points)
        baseline_carbon = sum(point["carbon_kg"] for point in baseline)
        scenario_carbon = sum(point["carbon_kg"] for point in scenario_points)
        unserved = sum(point["unserved_kw"] for point in scenario_points)
        result = {
            "inputs": config,
            "horizon_hours": horizon,
            "baseline_grid_energy_kwh": round(baseline_grid_energy, 2),
            "scenario_grid_energy_kwh": round(scenario_grid_energy, 2),
            "grid_energy_change_kwh": round(scenario_grid_energy - baseline_grid_energy, 2),
            "baseline_carbon_kg": round(baseline_carbon, 2),
            "scenario_carbon_kg": round(scenario_carbon, 2),
            "avoided_carbon_kg": round(baseline_carbon - scenario_carbon, 2),
            "peak_grid_import_kw": round(max((point["grid_import_kw"] for point in scenario_points), default=0.0), 2),
            "unserved_kwh": round(unserved, 2),
            "baseline": baseline,
            "points": scenario_points,
        }
        if persist:
            save_scenario(
                "custom",
                horizon,
                result["peak_grid_import_kw"],
                result["avoided_carbon_kg"],
            )
        return result

    def orchestration(self) -> dict:
        state = self.dashboard()
        return {
            "policy": "Solar first → battery second → grid last",
            "dispatch": {
                "demand_kw": state["current_demand_kw"],
                "solar_kw": state["solar_kw"],
                "battery_kw": state["battery_kw"],
                "battery_soc_pct": state["battery_soc_pct"],
                "grid_import_kw": state["grid_import_kw"],
                "renewable_share_pct": state["renewable_share_pct"],
                "carbon_kg_per_hour": state["carbon_kg_per_hour"],
                "grid_headroom_kw": state["grid_headroom_kw"],
                "status": state["status"],
            },
            "assets": state["asset_status"],
            "next_24h": state["forecast"],
        }

    def monitoring(self) -> dict:
        state = self.dashboard()
        alerts = []
        if state["battery_soc_pct"] <= 25:
            alerts.append({"severity": "warning", "message": "Battery is approaching its protected 20% reserve."})
        if state["grid_import_kw"] >= GRID_LIMIT_KW * 0.82:
            alerts.append({"severity": "critical", "message": "Grid import is near the configured intertie limit."})
        if not alerts:
            alerts.append({"severity": "info", "message": "No dispatch constraint alerts in the current model replay."})
        return {"assets": state["asset_status"], "alerts": alerts, "telemetry_mode": state["telemetry_mode"]}

    def chat(self, message: str) -> dict:
        if not message.strip():
            raise ValueError("Enter a question before sending it.")
        state = self.dashboard()
        model = self.model_bundle()
        context = {
            "current_demand_kw": state["current_demand_kw"],
            "solar_kw": state["solar_kw"],
            "battery_kw": state["battery_kw"],
            "battery_soc_pct": state["battery_soc_pct"],
            "grid_import_kw": state["grid_import_kw"],
            "renewable_share_pct": state["renewable_share_pct"],
            "carbon_kg_per_hour": state["carbon_kg_per_hour"],
            "grid_headroom_kw": state["grid_headroom_kw"],
        }
        scenario_preview = None
        lowered = message.lower()
        if "20%" in lowered or "twenty percent" in lowered or "increase demand" in lowered:
            scenario_preview = self.simulate(
                {
                    "solar_capacity_kw": PV_CAPACITY_KW,
                    "battery_capacity_kwh": BATTERY_CAPACITY_KWH,
                    "initial_soc_pct": state["battery_soc_pct"],
                    "demand_multiplier": 1.2,
                    "grid_available": True,
                },
                persist=False,
            )
        reply = chatbot_answer(
            message,
            context,
            state["forecast"],
            model,
            scenario_preview=scenario_preview,
        )
        save_chat(message.strip(), reply)
        return {"reply": reply, "history": get_chat_history()}

    @staticmethod
    def chat_history() -> list[dict]:
        return get_chat_history()

    @staticmethod
    def scenario_history() -> list[dict]:
        return get_recent_scenarios()

    @staticmethod
    def set_current_soc(value: float) -> float:
        return set_battery_soc(value)
