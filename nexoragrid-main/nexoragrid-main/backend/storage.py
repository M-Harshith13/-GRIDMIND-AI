"""SQLite persistence for the native GRIDMIND desktop application."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


DB_PATH = Path(__file__).resolve().parent / "data" / "gridmind.sqlite3"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create compatible tables and preserve any existing simulation records."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS simulation_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                battery_soc_pct REAL NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                demand_kw REAL NOT NULL,
                solar_kw REAL NOT NULL,
                battery_soc_pct REAL NOT NULL,
                grid_import_kw REAL NOT NULL,
                renewable_share_pct REAL NOT NULL
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS scenario_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                scenario TEXT NOT NULL,
                horizon INTEGER NOT NULL,
                peak_grid_import_kw REAL NOT NULL,
                avoided_carbon_kg REAL NOT NULL
            )"""
        )
        db.execute(
            "INSERT OR IGNORE INTO simulation_state (id, battery_soc_pct, updated_at) VALUES (1, 68.0, ?)",
            (now,),
        )


def get_battery_soc() -> float:
    initialize_database()
    with _connect() as db:
        row = db.execute("SELECT battery_soc_pct FROM simulation_state WHERE id=1").fetchone()
    return float(row["battery_soc_pct"])


def set_battery_soc(value: float) -> float:
    initialize_database()
    value = min(max(float(value), 20.0), 100.0)
    with _connect() as db:
        db.execute(
            "UPDATE simulation_state SET battery_soc_pct=?, updated_at=? WHERE id=1",
            (value, datetime.now(timezone.utc).isoformat()),
        )
    return value


def record_snapshot(dispatch: dict) -> None:
    with _connect() as db:
        db.execute(
            """INSERT INTO telemetry_snapshots
            (captured_at, demand_kw, solar_kw, battery_soc_pct, grid_import_kw, renewable_share_pct)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                dispatch["demand_kw"],
                dispatch["solar_kw"],
                dispatch["battery_soc_pct"],
                dispatch["grid_import_kw"],
                dispatch["renewable_share_pct"],
            ),
        )
        db.execute(
            "DELETE FROM telemetry_snapshots WHERE id NOT IN "
            "(SELECT id FROM telemetry_snapshots ORDER BY id DESC LIMIT 500)"
        )


def save_chat(user_message: str, assistant_message: str) -> None:
    with _connect() as db:
        db.execute(
            "INSERT INTO chat_messages (created_at, user_message, assistant_message) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), user_message, assistant_message),
        )


def get_chat_history(limit: int = 40) -> list[dict]:
    initialize_database()
    with _connect() as db:
        rows = db.execute(
            "SELECT created_at, user_message, assistant_message FROM chat_messages "
            "ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_scenario(
    scenario: str,
    horizon: int,
    peak_grid_import_kw: float,
    avoided_carbon_kg: float,
) -> None:
    with _connect() as db:
        db.execute(
            """INSERT INTO scenario_runs
            (created_at, scenario, horizon, peak_grid_import_kw, avoided_carbon_kg)
            VALUES (?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                scenario,
                int(horizon),
                float(peak_grid_import_kw),
                float(avoided_carbon_kg),
            ),
        )


def get_recent_scenarios(limit: int = 20) -> list[dict]:
    initialize_database()
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM scenario_runs ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 100)),),
        ).fetchall()
    return [dict(row) for row in rows]
