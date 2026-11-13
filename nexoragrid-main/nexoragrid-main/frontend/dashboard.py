"""Live model-replay dashboard with measured and simulated series separated."""

from __future__ import annotations

from datetime import datetime

from matplotlib.ticker import MaxNLocator
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .base_page import BasePage
from .styles import PALETTE, set_label_style
from .widgets import ChartCard, MetricCard, SectionHeader, legend, metric_grid


class DashboardPage(BasePage):
    def __init__(self, service, parent=None):
        super().__init__(service, parent)
        self.root_layout.addWidget(SectionHeader(
            "Energy at a glance",
            "Model-backed operating replay. Historical demand comes from the UCI household meter; solar and dispatch are simulated.",
        ))
        self.mode_label = QLabel("MODEL REPLAY · NO HARDWARE CONNECTION")
        set_label_style(self.mode_label, color=PALETTE["cyan"], size=9, bold=True, letter_spacing=0.8)
        self.root_layout.addWidget(self.mode_label)
        self.operational_label = QLabel("DISPATCH STATUS · LOADING")
        set_label_style(self.operational_label, color=PALETTE["muted"], size=10, bold=True)
        self.root_layout.addWidget(self.operational_label)
        self.cards = [
            MetricCard("Forecast demand", accent=PALETTE["cyan"]),
            MetricCard("Solar generation", accent=PALETTE["green"]),
            MetricCard("Battery state", accent=PALETTE["blue"]),
            MetricCard("Grid import", accent=PALETTE["amber"]),
            MetricCard("Renewable share", accent=PALETTE["green"]),
            MetricCard("Carbon estimate", accent=PALETTE["muted"]),
        ]
        self.root_layout.addWidget(metric_grid(self.cards, columns=3))

        grid = QGridLayout()
        grid.setSpacing(12)
        self.forecast_chart = ChartCard("24-hour demand and solar", "Forecast demand with simulated PV generation")
        self.history_chart = ChartCard("Historical demand signal", "Measured UCI household demand, projected to demo-site scale")
        self.soc_chart = ChartCard("Battery state of charge", "Dispatch projection; protected reserve is 20%")
        self.mix_chart = ChartCard("Current energy distribution", "Model-replay supply at the next forecast interval")
        grid.addWidget(self.forecast_chart, 0, 0)
        grid.addWidget(self.history_chart, 0, 1)
        grid.addWidget(self.soc_chart, 1, 0)
        grid.addWidget(self.mix_chart, 1, 1)
        self.root_layout.addLayout(grid)

        footer = QHBoxLayout()
        self.source_label = QLabel("Source: UCI · 1-minute measurements · 2006–2010")
        set_label_style(self.source_label, color=PALETTE["muted"], size=9)
        self.updated_label = QLabel("Waiting for local model…")
        set_label_style(self.updated_label, color=PALETTE["muted"], size=9)
        footer.addWidget(self.source_label)
        footer.addStretch(1)
        footer.addWidget(self.updated_label)
        self.root_layout.addLayout(footer)
        self.root_layout.addWidget(self.status_label)
        self.refresh()

    def refresh(self):
        self.launch(self.service.dashboard, self.render, busy_text="Refreshing…")

    def render(self, data: dict):
        self.cards[0].set_value(f"{data['current_demand_kw']:.1f} kW", "Next interval · model estimate")
        self.cards[1].set_value(f"{data['solar_kw']:.1f} kW", "Solar availability · simulated")
        self.cards[2].set_value(f"{data['battery_soc_pct']:.0f}%", f"{abs(data['battery_kw']):.1f} kW " + ("charging" if data["battery_kw"] < -0.05 else "discharging" if data["battery_kw"] > 0.05 else "standby"))
        self.cards[3].set_value(f"{data['grid_import_kw']:.1f} kW", f"{data['grid_headroom_kw']:.1f} kW headroom")
        self.cards[4].set_value(f"{data['renewable_share_pct']:.0f}%", "Current dispatch contribution")
        self.cards[5].set_value(f"{data['carbon_kg_per_hour']:.1f} kg/h", "Estimated from configured grid factor")
        status = data["status"].replace("-", " ").upper()
        status_color = PALETTE["amber"] if "WATCH" in status else PALETTE["green"]
        self.operational_label.setText(f"OPERATING STATUS · {status}")
        set_label_style(self.operational_label, color=status_color, size=10, bold=True)
        self.updated_label.setText(f"Updated {datetime.fromisoformat(data['captured_at']).strftime('%H:%M')}")

        points = data["forecast"]
        labels = [datetime.fromisoformat(row["timestamp"]).strftime("%H:%M") for row in points]
        ax = self.forecast_chart.axis()
        ax.plot(labels, [p["demand_kw"] for p in points], color=PALETTE["cyan"], linewidth=2.2, label="Demand forecast")
        ax.fill_between(range(len(points)), [p["demand_kw"] for p in points], color=PALETTE["cyan"], alpha=0.08)
        ax.plot(labels, [p["solar_kw"] for p in points], color=PALETTE["green"], linewidth=2, label="Solar simulation")
        ax.set_ylabel("kW")
        ax.set_xticks(range(0, len(labels), 4), labels[::4], rotation=0)
        ax.yaxis.set_major_locator(MaxNLocator(5))
        legend(ax)
        self.forecast_chart.redraw()

        actual = data["recent_actual"]
        hist_labels = [datetime.fromisoformat(row["timestamp"]).strftime("%d %b %H") for row in actual]
        ax = self.history_chart.axis()
        ax.plot(hist_labels, [row["demand_kw"] for row in actual], color=PALETTE["blue"], linewidth=1.8, label="Measured demand")
        ax.set_ylabel("kW · site-scaled")
        ax.set_xticks(range(0, len(hist_labels), max(1, len(hist_labels) // 6)), hist_labels[::max(1, len(hist_labels) // 6)], rotation=0)
        legend(ax)
        self.history_chart.redraw()

        ax = self.soc_chart.axis()
        soc = [p["battery_soc_pct"] for p in points]
        ax.plot(labels, soc, color=PALETTE["blue"], linewidth=2.2, label="Battery SOC")
        ax.axhline(20, color=PALETTE["amber"], linestyle="--", linewidth=1.2, label="20% reserve")
        ax.fill_between(range(len(points)), soc, 20, color=PALETTE["blue"], alpha=0.08)
        ax.set_ylim(0, 105)
        ax.set_ylabel("%")
        ax.set_xticks(range(0, len(labels), 4), labels[::4])
        legend(ax)
        self.soc_chart.redraw()

        supply = [
            max(0.0, min(data["solar_kw"], data["current_demand_kw"])),
            max(0.0, data["battery_kw"]),
            max(0.0, data["grid_import_kw"]),
        ]
        labels_mix = ["Solar", "Battery", "Grid"]
        colors = [PALETTE["green"], PALETTE["blue"], PALETTE["amber"]]
        if sum(supply) < 0.01:
            supply, labels_mix, colors = [1], ["No supply data"], [PALETTE["muted"]]
        ax = self.mix_chart.axis()
        ax.pie(supply, labels=labels_mix, colors=colors, startangle=90, counterclock=False,
               wedgeprops={"width": 0.36, "edgecolor": PALETTE["panel"]},
               textprops={"color": PALETTE["muted"], "fontsize": 9})
        ax.text(0, 0, f"{data['current_demand_kw']:.0f}\nkW", ha="center", va="center",
                color=PALETTE["text"], fontsize=14, fontweight="bold")
        self.mix_chart.redraw()
