"""Context-aware local rule-based assistant using current application state."""

from datetime import datetime


def answer(
    message: str,
    dashboard: dict,
    forecast: list[dict],
    model: dict,
    scenario_preview: dict | None = None,
) -> str:
    text = message.lower()
    demand = dashboard["current_demand_kw"]
    solar = dashboard["solar_kw"]
    grid = dashboard["grid_import_kw"]
    soc = dashboard["battery_soc_pct"]
    renewable = dashboard["renewable_share_pct"]
    mae = model["metrics"]["mae_kw"]

    if "20%" in text or "twenty percent" in text or "increase demand" in text:
        if scenario_preview:
            delta = scenario_preview["grid_energy_change_kwh"]
            direction = "increases" if delta > 0 else "decreases" if delta < 0 else "stays level"
            return (
                f"With demand raised by 20%, forecast grid energy {direction} by "
                f"{abs(delta):.1f} kWh over {scenario_preview['horizon_hours']} hours. "
                f"Peak grid import is {scenario_preview['peak_grid_import_kw']:.1f} kW; "
                f"the run leaves {scenario_preview['unserved_kwh']:.1f} kWh unserved."
            )
        return f"Demand is currently {demand:.1f} kW. Use Scenario Simulation to calculate the 20% demand uplift against the current storage and grid settings."

    if "empty" in text or "run out" in text:
        depleted = next(
            (point for point in forecast if point.get("next_battery_soc_pct", point.get("battery_soc_pct", 100)) <= 20.0),
            None,
        )
        if depleted:
            when = datetime.fromisoformat(depleted["timestamp"]).strftime("%H:%M")
            return f"Under the current 24-hour dispatch replay, the battery reaches its 20% reserve around {when}. It is not dispatched below that reserve."
        return f"The forecast keeps the battery above its 20% reserve for the next {len(forecast)} hours. Current state of charge is {soc:.0f}%."

    if "why" in text and any(word in text for word in ("grid", "import")):
        peak = max(forecast, key=lambda row: row["grid_import_kw"])
        average = sum(row["grid_import_kw"] for row in forecast) / max(len(forecast), 1)
        when = datetime.fromisoformat(peak["timestamp"]).strftime("%H:%M")
        return (
            f"Grid import rises when forecast demand is above solar plus available battery discharge. "
            f"The current import is {grid:.1f} kW; the 24-hour average is {average:.1f} kW and the "
            f"peak is {peak['grid_import_kw']:.1f} kW around {when}. The battery reserve is protected at 20%."
        )

    if any(word in text for word in ("battery", "charge", "storage", "soc")):
        battery_kw = dashboard["battery_kw"]
        if battery_kw < -0.05:
            action = f"charging at {abs(battery_kw):.1f} kW"
        elif battery_kw > 0.05:
            action = f"discharging at {battery_kw:.1f} kW"
        else:
            action = "on standby"
        return (
            f"The battery is at {soc:.0f}% state of charge and is {action}. "
            f"Current grid import is {dashboard['grid_import_kw']:.1f} kW."
        )
    if any(word in text for word in ("solar", "renewable", "clean")):
        if any(word in text for word in ("improve", "increase", "improve renewable", "improve clean")):
            peak_solar = max(forecast, key=lambda row: row["solar_kw"])
            peak_time = datetime.fromisoformat(peak_solar["timestamp"]).strftime("%H:%M")
            return (
                f"The highest solar window in the current forecast is around {peak_time}. "
                f"Shift flexible loads toward that window and charge storage from available surplus; "
                f"the current renewable contribution is {renewable:.0f}% and the protected battery reserve is 20%."
            )
        solar_energy = sum(row["solar_kw"] for row in forecast)
        return (
            f"Solar is supplying {solar:.1f} kW against {demand:.1f} kW of forecast demand. "
            f"The next {len(forecast)} hours project {solar_energy:.1f} kWh of solar output. "
            f"The current renewable contribution is {renewable:.0f}%, and grid import is {grid:.1f} kW."
        )
    if any(word in text for word in ("forecast", "tomorrow", "next", "demand")):
        peak = max(forecast, key=lambda row: row["demand_kw"])
        average = sum(row["demand_kw"] for row in forecast) / max(len(forecast), 1)
        return (
            f"The next {len(forecast)} hours average {average:.1f} kW. The peak is "
            f"{peak['demand_kw']:.1f} kW at {datetime.fromisoformat(peak['timestamp']).strftime('%H:%M')}. "
            f"Validation MAE is {mae:.2f} kW on the household training series."
        )
    if any(word in text for word in ("grid", "import", "carbon", "emission")):
        return (
            f"Current grid import is {grid:.1f} kW, with an estimated {dashboard['carbon_kg_per_hour']:.1f} "
            f"kg CO₂ per hour at the configured grid factor. The site has {dashboard['grid_headroom_kw']:.1f} kW "
            "of import headroom before its configured limit."
        )
    if any(word in text for word in ("scenario", "simulate", "peak event")):
        return (
            "Use Scenario Simulation to compare the current dispatch with adjusted solar capacity, battery capacity, "
            "starting SOC, demand, and grid availability. Each run uses the trained forecast and solar-first dispatch policy."
        )
    return (
        f"System is operating in model-backed replay. Demand is {demand:.1f} kW, solar is {solar:.1f} kW, "
        f"renewables contribute {renewable:.0f}%, and the battery is at {soc:.0f}%. "
        "Ask about the forecast, battery, solar, grid import, or scenarios."
    )
