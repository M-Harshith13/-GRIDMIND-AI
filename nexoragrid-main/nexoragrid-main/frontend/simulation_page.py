"""Editable site assumptions and baseline-versus-scenario dispatch runs."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .base_page import BasePage
from .styles import PALETTE, set_label_style
from .widgets import AccentButton, ChartCard, MetricCard, SectionHeader, build_table, legend, metric_grid


def _spin(minimum: float, maximum: float, value: float, suffix: str = "", step: float = 1.0, decimals: int = 1):
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    widget.setSingleStep(step)
    widget.setDecimals(decimals)
    widget.setSuffix(suffix)
    return widget


class SimulationPage(BasePage):
    def __init__(self, service, parent=None):
        super().__init__(service, parent)
        self.root_layout.addWidget(SectionHeader(
            "Scenario simulation",
            "Change the demo site's solar, storage, demand, and grid assumptions. Each run is compared with balanced dispatch on the same forecast.",
        ))

        form_card = QWidget()
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(22)
        form_layout.setVerticalSpacing(10)
        left_form = QFormLayout()
        right_form = QFormLayout()
        self.solar_capacity = _spin(0, 500, 75.4, " kW", 5, 1)
        self.battery_capacity = _spin(1, 2000, 120, " kWh", 10, 1)
        self.initial_soc = _spin(20, 100, 68, " %", 1, 0)
        self.demand_multiplier = _spin(0.5, 2.5, 1, "×", 0.05, 2)
        self.grid_available = QCheckBox("Grid intertie available")
        self.grid_available.setChecked(True)
        left_form.addRow("Solar generation capacity", self.solar_capacity)
        left_form.addRow("Battery capacity", self.battery_capacity)
        right_form.addRow("Initial battery SOC", self.initial_soc)
        right_form.addRow("Demand multiplier", self.demand_multiplier)
        right_form.addRow("Grid availability", self.grid_available)
        form_layout.addLayout(left_form, 0, 0)
        form_layout.addLayout(right_form, 0, 1)
        self.run_button = AccentButton("Run dispatch simulation")
        self.run_button.clicked.connect(self.run_simulation)
        form_layout.addWidget(self.run_button, 1, 0, 1, 2)
        self.root_layout.addWidget(form_card)

        self.cards = [
            MetricCard("Baseline grid energy", accent=PALETTE["muted"]),
            MetricCard("Scenario grid energy", accent=PALETTE["cyan"]),
            MetricCard("Grid-energy change", accent=PALETTE["amber"]),
            MetricCard("Unserved energy", accent=PALETTE["red"]),
        ]
        self.root_layout.addWidget(metric_grid(self.cards, 4))
        self.alert_label = QLabel("A scenario run changes simulation settings only; it does not control hardware.")
        set_label_style(self.alert_label, color=PALETTE["muted"], size=9)
        self.alert_label.setWordWrap(True)
        self.root_layout.addWidget(self.alert_label)
        charts = QGridLayout()
        charts.setSpacing(12)
        self.grid_chart = ChartCard("Grid import comparison", "Hourly kWh approximated from hourly kW steps")
        self.soc_chart = ChartCard("Scenario battery SOC", "Storage dispatch uses a protected 20% reserve")
        charts.addWidget(self.grid_chart, 0, 0)
        charts.addWidget(self.soc_chart, 0, 1)
        self.root_layout.addLayout(charts)
        self.root_layout.addWidget(QLabel("Recent saved runs · SQLite"))
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addWidget(self.history_container)
        self.root_layout.addWidget(self.status_label)
        self.result = None

    def refresh(self):
        self.launch(self.service.scenario_history, self.render_history)

    def run_simulation(self):
        inputs = {
            "solar_capacity_kw": self.solar_capacity.value(),
            "battery_capacity_kwh": self.battery_capacity.value(),
            "initial_soc_pct": self.initial_soc.value(),
            "demand_multiplier": self.demand_multiplier.value(),
            "grid_available": self.grid_available.isChecked(),
        }
        self.launch(
            lambda: self.service.simulate(inputs),
            self.render_result,
            busy_widget=self.run_button,
            busy_text="Simulating…",
        )

    def render_result(self, result: dict):
        self.result = result
        self.cards[0].set_value(f"{result['baseline_grid_energy_kwh']:.1f} kWh", "Balanced reference")
        self.cards[1].set_value(f"{result['scenario_grid_energy_kwh']:.1f} kWh", "Edited assumptions")
        delta = result["grid_energy_change_kwh"]
        self.cards[2].set_value(f"{delta:+.1f} kWh", "Change vs baseline")
        self.cards[3].set_value(f"{result['unserved_kwh']:.1f} kWh", "Demand not served during islanding")
        if result["unserved_kwh"] > 0.01:
            self.alert_label.setText(
                f"Grid unavailable: dispatch leaves {result['unserved_kwh']:.1f} kWh unserved over "
                f"{result['horizon_hours']} hours. This is a simulated constraint, not a hardware alarm."
            )
            set_label_style(self.alert_label, color=PALETTE["red"], size=9, bold=True)
        else:
            self.alert_label.setText(
                f"Scenario dispatch completed. Estimated carbon is {result['scenario_carbon_kg']:.1f} kg "
                f"versus {result['baseline_carbon_kg']:.1f} kg at baseline. Run saved to SQLite."
            )
            set_label_style(self.alert_label, color=PALETTE["muted"], size=9)

        points = result["points"]
        baseline = result["baseline"]
        labels = [datetime.fromisoformat(point["timestamp"]).strftime("%H:%M") for point in points]
        ax = self.grid_chart.axis()
        ax.plot(labels, [p["grid_import_kw"] for p in baseline], color=PALETTE["muted"], linewidth=1.8, label="Baseline")
        ax.plot(labels, [p["grid_import_kw"] for p in points], color=PALETTE["cyan"], linewidth=2, label="Scenario")
        ax.set_ylabel("kW")
        ax.set_xticks(range(0, len(labels), max(1, len(labels) // 6)), labels[::max(1, len(labels) // 6)])
        legend(ax)
        self.grid_chart.redraw()

        ax = self.soc_chart.axis()
        ax.plot(labels, [p["battery_soc_pct"] for p in points], color=PALETTE["blue"], linewidth=2, label="Battery SOC")
        ax.axhline(20, color=PALETTE["amber"], linewidth=1.2, linestyle="--", label="20% reserve")
        ax.set_ylim(0, 105)
        ax.set_ylabel("%")
        ax.set_xticks(range(0, len(labels), max(1, len(labels) // 6)), labels[::max(1, len(labels) // 6)])
        legend(ax)
        self.soc_chart.redraw()
        self.launch(self.service.scenario_history, self.render_history)

    def render_history(self, history: list[dict]):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = [
            [
                datetime.fromisoformat(row["created_at"]).astimezone().strftime("%d %b %H:%M"),
                row["scenario"],
                row["horizon"],
                f"{row['peak_grid_import_kw']:.1f} kW",
                f"{row['avoided_carbon_kg']:+.1f} kg",
            ]
            for row in history
        ]
        if rows:
            self.history_layout.addWidget(build_table(["Run time", "Scenario", "Hours", "Peak grid", "Avoided carbon"], rows, max_height=250))
        else:
            note = QLabel("No saved scenario runs yet.")
            set_label_style(note, color=PALETTE["muted"], size=9)
            self.history_layout.addWidget(note)
