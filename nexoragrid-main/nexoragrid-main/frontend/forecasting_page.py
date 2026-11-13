"""Forecasts, chronological holdout evaluation, and model metrics."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from .base_page import BasePage
from .styles import PALETTE
from .widgets import ChartCard, MetricCard, SectionHeader, build_table, legend, metric_grid


class ForecastingPage(BasePage):
    def __init__(self, service, parent=None):
        super().__init__(service, parent)
        self.root_layout.addWidget(SectionHeader(
            "AI demand forecasting",
            "The trained model runs locally. Historical validation actuals and model estimates are shown separately from the future forecast.",
        ))
        self.model_label = QLabel("Loading saved model…")
        self.model_label.setObjectName("Eyebrow")
        self.root_layout.addWidget(self.model_label)
        self.cards = [
            MetricCard("MAE", accent=PALETTE["cyan"]),
            MetricCard("RMSE", accent=PALETTE["blue"]),
            MetricCard("R²", accent=PALETTE["green"]),
            MetricCard("MAPE", accent=PALETTE["amber"]),
        ]
        self.root_layout.addWidget(metric_grid(self.cards, 4))
        charts = QGridLayout()
        charts.setSpacing(12)
        self.validation_chart = ChartCard("Historical holdout · actual vs model estimate", "Chronological validation sample · household kW")
        self.future_chart = ChartCard("Next 24 hours · forecast", "Projected to the demo site; this is not live meter data")
        self.importance_chart = ChartCard("Model feature influence", "Permutation importance from the saved chronological holdout", minimum_height=245)
        charts.addWidget(self.validation_chart, 0, 0)
        charts.addWidget(self.future_chart, 0, 1)
        charts.addWidget(self.importance_chart, 1, 0, 1, 2)
        self.root_layout.addLayout(charts)
        self.root_layout.addWidget(QLabel("Upcoming intervals"))
        self.table_container = QWidget()
        self.table_layout = QVBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_layout.addWidget(QLabel("Forecast rows load with the saved model."))
        self.root_layout.addWidget(self.table_container)
        self.root_layout.addWidget(self.status_label)

    def refresh(self):
        self.launch(self.service.forecast_page, self.render, busy_text="Evaluating…")

    def render(self, data: dict):
        m = data["metrics"]
        self.cards[0].set_value(f"{m['mae_kw']:.3f} kW", "Mean absolute error · household series")
        self.cards[1].set_value(f"{m['rmse_kw']:.3f} kW", "Root mean squared error")
        self.cards[2].set_value(f"{m['r2']:.3f}", "Coefficient of determination")
        self.cards[3].set_value(f"{m['mape_pct']:.1f}%", "Percentage error; small night loads affect MAPE")
        self.model_label.setText(f"{data['algorithm']}  ·  {data['training_rows']:,} train rows  ·  {data['evaluation_rows']:,} chronological holdout rows")

        validation = data["evaluation"]
        labels = [datetime.fromisoformat(row["timestamp"]).strftime("%m/%d %H") for row in validation]
        ax = self.validation_chart.axis()
        ax.plot(labels, [row["actual_kw"] for row in validation], color=PALETTE["cyan"], linewidth=1.9, label="Measured actual")
        ax.plot(labels, [row["predicted_kw"] for row in validation], color=PALETTE["amber"], linewidth=1.8, linestyle="--", label="Model estimate")
        stride = max(1, len(labels) // 7)
        ax.set_xticks(range(0, len(labels), stride), labels[::stride])
        ax.set_ylabel("Household kW")
        legend(ax)
        self.validation_chart.redraw()

        forecast = data["forecast"]
        future_labels = [datetime.fromisoformat(row["timestamp"]).strftime("%H:%M") for row in forecast]
        ax = self.future_chart.axis()
        ax.plot(future_labels, [row["demand_kw"] for row in forecast], color=PALETTE["cyan"], linewidth=2.2, label="Demand forecast")
        ax.plot(future_labels, [row["solar_kw"] for row in forecast], color=PALETTE["green"], linewidth=2, label="Solar simulation")
        ax.fill_between(range(len(forecast)), [row["demand_kw"] for row in forecast], color=PALETTE["cyan"], alpha=0.07)
        ax.set_xticks(range(0, len(future_labels), 4), future_labels[::4])
        ax.set_ylabel("kW · site scale")
        legend(ax)
        self.future_chart.redraw()

        importance = data["feature_importance"][:8]
        ax = self.importance_chart.axis()
        names = [row["feature"] for row in importance]
        scores = [row["importance"] * 100 for row in importance]
        colors = [PALETTE["cyan"] if idx == 0 else PALETTE["blue"] for idx in range(len(names))]
        ax.barh(names[::-1], scores[::-1], color=colors[::-1], height=0.62)
        ax.set_xlabel("MAE reduction contribution · %")
        ax.grid(axis="x", color=PALETTE["border"], alpha=0.6, linewidth=0.7)
        ax.grid(axis="y", visible=False)
        self.importance_chart.redraw()

        rows = [
            [
                datetime.fromisoformat(row["timestamp"]).strftime("%a %H:%M"),
                f"{row['demand_kw']:.1f}",
                f"{row['solar_kw']:.1f}",
                f"{row['grid_import_kw']:.1f}",
                f"{row['battery_soc_pct']:.0f}%",
            ]
            for row in forecast
        ]
        table = build_table(["Interval", "Demand kW", "Solar kW*", "Grid kW", "Battery SOC"], rows, max_height=370)
        table.setMinimumHeight(250)
        while self.table_layout.count():
            item = self.table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.table_layout.addWidget(table)

        footnote = QLabel(
            f"Dataset: {data['dataset_source']} · {data['dataset_start'][:10]} to {data['dataset_end'][:10]}. "
            "Solar output is simulated; measured historical values are only available for household demand."
        )
        footnote.setObjectName("Muted")
        footnote.setWordWrap(True)
        self.table_layout.addWidget(footnote)
