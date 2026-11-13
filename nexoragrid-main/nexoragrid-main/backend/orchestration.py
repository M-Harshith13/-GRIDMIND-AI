"""Deterministic microgrid dispatch policy for a solar-plus-storage site."""

from __future__ import annotations

import math


BATTERY_CAPACITY_KWH = 120.0
BATTERY_INVERTER_KW = 28.0
GRID_LIMIT_KW = 180.0
PV_PEAK_KW = 52.0
PV_CAPACITY_KW = 75.4


def solar_output_kw(
    hour: int,
    multiplier: float = 1.0,
    capacity_kw: float = PV_CAPACITY_KW,
) -> float:
    daylight = max(math.sin(math.pi * (hour - 6) / 13), 0.0)
    configured_capacity = max(float(capacity_kw), 0.0)
    configured_peak = PV_PEAK_KW * configured_capacity / PV_CAPACITY_KW
    return round(min(configured_peak * daylight * multiplier, configured_capacity), 2)


def build_dispatch(
    demand_kw: float,
    solar_kw: float,
    battery_soc_pct: float,
    *,
    battery_capacity_kwh: float = BATTERY_CAPACITY_KWH,
    battery_inverter_kw: float = BATTERY_INVERTER_KW,
    grid_limit_kw: float = GRID_LIMIT_KW,
    reserve_pct: float = 20.0,
    grid_available: bool = True,
) -> dict:
    battery_capacity_kwh = max(float(battery_capacity_kwh), 0.1)
    battery_inverter_kw = max(float(battery_inverter_kw), 0.0)
    grid_limit_kw = max(float(grid_limit_kw), 0.0) if grid_available else 0.0
    reserve_pct = min(max(float(reserve_pct), 0.0), 99.0)
    battery_soc_pct = min(max(float(battery_soc_pct), reserve_pct), 100.0)
    net = max(float(demand_kw) - float(solar_kw), 0.0)
    available_energy_kw = max((battery_soc_pct - reserve_pct) / 100 * battery_capacity_kwh, 0.0)
    battery_out = min(net, battery_inverter_kw, available_energy_kw)

    surplus = max(float(solar_kw) - float(demand_kw), 0.0)
    charge_headroom_kw = max((100.0 - battery_soc_pct) / 100 * battery_capacity_kwh, 0.0)
    battery_in = min(surplus, battery_inverter_kw, charge_headroom_kw)
    grid_import = max(net - battery_out, 0.0)
    curtailed = max(surplus - battery_in, 0.0)
    grid_import = min(grid_import, grid_limit_kw)
    unserved = max(net - battery_out - grid_import, 0.0)

    next_soc = battery_soc_pct + (battery_in - battery_out) / battery_capacity_kwh * 100
    next_soc = min(max(next_soc, reserve_pct), 100.0)
    renewable_share = min((solar_kw + battery_out) / max(demand_kw, 0.1) * 100, 100.0)
    if not grid_available:
        status = "islanded-unserved" if unserved > 0.05 else "islanded-balanced"
    else:
        status = "balanced" if grid_import < grid_limit_kw * 0.82 else "grid-watch"
    return {
        "demand_kw": round(float(demand_kw), 2),
        "solar_kw": round(float(solar_kw), 2),
        "battery_kw": round(battery_out - battery_in, 2),
        "battery_soc_pct": round(float(battery_soc_pct), 1),
        "next_battery_soc_pct": round(next_soc, 1),
        "grid_import_kw": round(grid_import, 2),
        "curtailed_kw": round(curtailed, 2),
        "renewable_share_pct": round(renewable_share, 1),
        "carbon_kg_per_hour": round(grid_import * 0.42, 2),
        "grid_headroom_kw": round(max(grid_limit_kw - grid_import, 0), 2),
        "unserved_kw": round(unserved, 2),
        "status": status,
    }
