"""Solar-first dispatch plan and energy balance."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from .base_page import BasePage
from .styles import PALETTE
from .widgets import ChartCard, MetricCard, SectionHeader, build_table, legend, metric_grid


class OrchestrationPage(BasePage):
    def __init__(self, service, parent=None):
        super().__init__(service, parent)
        self.root_layout.addWidget(SectionHeader(
            "Intelligent energy orchestration",
            "Solar serves the load first, storage follows while respecting its reserve, and the grid supplies the remaining requirement.",
        ))
        self.policy_label = QLabel("POLICY: SOLAR → BATTERY → GRID  ·  MODEL REPLAY")
        self.policy_label.setObjectName("Eyebrow")
        self.root_layout.addWidget(self.policy_label)
        self.cards = [
            MetricCard("Forecast load", accent=PALETTE["cyan"]),
            MetricCard("Solar supply", accent=PALETTE["green"]),
            MetricCard("Battery dispatch", accent=PALETTE["blue"]),
            MetricCard("Grid import", accent=PALETTE["amber"]),
        ]
        self.root_layout.addWidget(metric_grid(self.cards, 4))
        self.balance_label = QLabel("Energy balance will appear after dispatch loads.")
        self.balance_label.setObjectName("Muted")
        self.root_layout.addWidget(self.balance_label)
        self.chart = ChartCard("Demand and dispatch outlook", "24-hour model forecast and asset response", minimum_height=300)
        self.root_layout.addWidget(self.chart)
        self.root_layout.addWidget(QLabel("Dispatch schedule"))
        self.table_container = QWidget()
        self.table_layout = QVBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addWidget(self.table_container)
        self.root_layout.addWidget(self.status_label)

    def refresh(self):
        self.launch(self.service.orchestration, self.render, busy_text="Recalculating…")

    def render(self, data: dict):
        state = data["dispatch"]
        self.cards[0].set_value(f"{state['demand_kw']:.1f} kW", "Model forecast for next interval")
        self.cards[1].set_value(f"{state['solar_kw']:.1f} kW", "Available PV · simulated")
        flow = "Charging" if state["battery_kw"] < -0.05 else "Discharging" if state["battery_kw"] > 0.05 else "Standby"
        self.cards[2].set_value(f"{abs(state['battery_kw']):.1f} kW", f"{flow} · SOC {state['battery_soc_pct']:.0f}%")
        self.cards[3].set_value(f"{state['grid_import_kw']:.1f} kW", f"{state['grid_headroom_kw']:.1f} kW intertie headroom")
        net_supply = state["solar_kw"] + state["battery_kw"] + state["grid_import_kw"]
        balance = net_supply - state["demand_kw"]
        self.balance_label.setText(
            f"Energy balance: {net_supply:.1f} kW net supply − {state['demand_kw']:.1f} kW load = "
            f"{balance:+.1f} kW (rounded model outputs). Renewable contribution {state['renewable_share_pct']:.0f}%; "
            f"estimated emissions {state['carbon_kg_per_hour']:.1f} kg CO₂/h."
        )

        points = data["next_24h"]
        labels = [datetime.fromisoformat(point["timestamp"]).strftime("%H:%M") for point in points]
        ax = self.chart.axis()
        ax.plot(labels, [p["demand_kw"] for p in points], color=PALETTE["text"], linewidth=2.2, label="Demand")
        ax.plot(labels, [p["solar_kw"] for p in points], color=PALETTE["green"], linewidth=2, label="Solar")
        ax.plot(labels, [max(p["battery_kw"], 0) for p in points], color=PALETTE["blue"], linewidth=1.8, label="Battery discharge")
        ax.plot(labels, [p["grid_import_kw"] for p in points], color=PALETTE["amber"], linewidth=1.8, label="Grid import")
        ax.set_ylabel("kW")
        ax.set_xticks(range(0, len(labels), 3), labels[::3])
        legend(ax)
        self.chart.redraw()

        rows = [
            [
                datetime.fromisoformat(p["timestamp"]).strftime("%a %H:%M"),
                f"{p['demand_kw']:.1f}",
                f"{p['solar_kw']:.1f}",
                (f"{abs(p['battery_kw']):.1f} charge" if p["battery_kw"] < -0.05 else f"{p['battery_kw']:.1f} discharge" if p["battery_kw"] > 0.05 else "Standby"),
                f"{p['battery_soc_pct']:.0f}%",
                f"{p['grid_import_kw']:.1f}",
                f"{p['renewable_share_pct']:.0f}%",
            ]
            for p in points
        ]
        table = build_table(["Interval", "Demand", "Solar", "Battery", "SOC", "Grid", "Renewables"], rows, max_height=420)
        table.setMinimumHeight(300)
        while self.table_layout.count():
            item = self.table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.table_layout.addWidget(table)
