"""Asset and constraint monitoring for the simulated operating envelope."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .base_page import BasePage
from .styles import PALETTE, set_label_style
from .widgets import MetricCard, SectionHeader, build_table, metric_grid


class MonitoringPage(BasePage):
    def __init__(self, service, parent=None):
        super().__init__(service, parent)
        self.root_layout.addWidget(SectionHeader(
            "System monitoring",
            "Asset states and alerts are computed by the dispatch simulator. GRIDMIND does not connect to or control physical equipment.",
        ))
        self.mode_label = QLabel("SIMULATION MONITORING · NO FIELD TELEMETRY")
        set_label_style(self.mode_label, color=PALETTE["cyan"], size=9, bold=True, letter_spacing=0.8)
        self.root_layout.addWidget(self.mode_label)
        self.cards = [
            MetricCard("Online assets", accent=PALETTE["green"]),
            MetricCard("Current alerts", accent=PALETTE["amber"]),
            MetricCard("Battery reserve", accent=PALETTE["blue"]),
            MetricCard("Grid headroom", accent=PALETTE["cyan"]),
        ]
        self.root_layout.addWidget(metric_grid(self.cards, 4))
        self.root_layout.addWidget(QLabel("Asset status and capacity"))
        self.asset_host = QWidget()
        self.asset_layout = QVBoxLayout(self.asset_host)
        self.asset_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addWidget(self.asset_host)
        self.root_layout.addWidget(QLabel("Dispatch alerts"))
        self.alert_host = QWidget()
        self.alert_layout = QVBoxLayout(self.alert_host)
        self.alert_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addWidget(self.alert_host)
        self.root_layout.addWidget(self.status_label)
        self.refresh()

    def refresh(self):
        self.launch(self.service.monitoring, self.render, busy_text="Checking assets…")

    def render(self, data: dict):
        assets = data["assets"]
        alerts = data["alerts"]
        while self.alert_layout.count():
            item = self.alert_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards[0].set_value(f"{len(assets)}", "Modeled assets in dispatch plan")
        self.cards[1].set_value(f"{sum(a['severity'] != 'info' for a in alerts)}", "Constraint alerts")
        battery = next((a for a in assets if a["type"].lower() == "storage"), {})
        grid = next((a for a in assets if a["type"].lower() == "intertie"), {})
        self.cards[2].set_value(f"{battery.get('soc_pct', 0):.0f}%", "Protected dispatch floor 20%")
        self.cards[3].set_value(f"{max(grid.get('capacity_kw', 0) - grid.get('output_kw', 0), 0):.1f} kW", "Configured intertie headroom")

        asset_rows = [
            [
                asset["name"],
                asset["type"],
                asset["status"],
                f"{asset['output_kw']:.1f} kW",
                f"{asset['capacity_kw']:.1f} kW",
                f"{asset.get('soc_pct', 0):.0f}%" if "soc_pct" in asset else "—",
            ]
            for asset in assets
        ]
        self._replace(self.asset_layout, build_table(["Asset", "Role", "Status", "Output", "Capacity", "SOC"], asset_rows, max_height=240))

        for alert in alerts:
            row = QLabel(f"{alert['severity'].upper()}  ·  {alert['message']}")
            row.setWordWrap(True)
            if alert["severity"] == "critical":
                set_label_style(row, color=PALETTE["red"], size=10, bold=True)
            elif alert["severity"] == "warning":
                set_label_style(row, color=PALETTE["amber"], size=10, bold=True)
            else:
                set_label_style(row, color=PALETTE["muted"], size=10)
            row.setContentsMargins(8, 6, 8, 6)
            self.alert_layout.addWidget(row)

    @staticmethod
    def _replace(layout, widget):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        layout.addWidget(widget)
