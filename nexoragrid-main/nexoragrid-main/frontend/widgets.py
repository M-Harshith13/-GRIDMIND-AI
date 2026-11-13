"""Reusable native widgets and Matplotlib chart helpers."""

from __future__ import annotations

from collections.abc import Callable

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .styles import PALETTE, set_label_style


class SurfaceFrame(QFrame):
    def __init__(self, background: str | None = None, border: str | None = None, radius: int = 14):
        super().__init__()
        self.surface_color = QColor(background or PALETTE["panel"])
        self.border_color = QColor(border or PALETTE["border"])
        self.corner_radius = radius
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.border_color, 1))
        painter.setBrush(self.surface_color)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), self.corner_radius, self.corner_radius)
        painter.end()


class AccentButton(QPushButton):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = PALETTE["cyan"] if self.isEnabled() else "#536274"
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        painter.setPen(QColor("#06121b" if self.isEnabled() else "#a2adba"))
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class MetricCard(SurfaceFrame):
    def __init__(self, title: str, value: str = "—", detail: str = "", accent: str | None = None):
        super().__init__(radius=12)
        self.setMinimumHeight(105)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(6)
        self.title_label = QLabel(title.upper())
        set_label_style(self.title_label, color=PALETTE["muted"], size=8.5, bold=True, letter_spacing=1)
        self.value_label = QLabel(value)
        set_label_style(self.value_label, color=accent or PALETTE["text"], size=23, bold=True)
        self.detail_label = QLabel(detail)
        set_label_style(self.detail_label, color=PALETTE["muted"], size=9)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str | None = None) -> None:
        self.value_label.setText(value)
        if detail is not None:
            self.detail_label.setText(detail)


class ChartCard(SurfaceFrame):
    def __init__(self, title: str, subtitle: str = "", minimum_height: int = 265):
        super().__init__(radius=14)
        self.setMinimumHeight(minimum_height)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(4)
        header = QVBoxLayout()
        self.title_label = QLabel(title)
        set_label_style(self.title_label, size=13, bold=True)
        header.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            set_label_style(self.subtitle_label, color=PALETTE["muted"], size=9)
            header.addWidget(self.subtitle_label)
        layout.addLayout(header)
        self.figure = Figure(figsize=(6, 2.5), dpi=100, facecolor=PALETTE["panel"])
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(minimum_height - 70)
        layout.addWidget(self.canvas, 1)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setMinimumHeight(27)
        layout.addWidget(self.toolbar)

    def axis(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PALETTE["panel"])
        ax.tick_params(colors=PALETTE["muted"], labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(PALETTE["border"])
        ax.spines["bottom"].set_color(PALETTE["border"])
        ax.grid(axis="y", color=PALETTE["border"], alpha=0.6, linewidth=0.7)
        ax.yaxis.label.set_color(PALETTE["muted"])
        ax.xaxis.label.set_color(PALETTE["muted"])
        self.figure.tight_layout(pad=1.4)
        return ax

    def redraw(self) -> None:
        self.figure.tight_layout(pad=1.4)
        self.canvas.draw_idle()


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(5)
        title_label = QLabel(title)
        set_label_style(title_label, size=22, bold=True)
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            set_label_style(sub, color=PALETTE["muted"], size=10)
            sub.setWordWrap(True)
            layout.addWidget(sub)


def build_table(headers: list[str], rows: list[list[object]], *, max_height: int | None = None) -> QTableWidget:
    table = QTableWidget(len(rows), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    for row_index, values in enumerate(rows):
        for col_index, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if col_index > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            table.setItem(row_index, col_index, item)
    table.setSortingEnabled(True)
    table.resizeColumnsToContents()
    table.setMinimumHeight(min(max_height or 120, max(1, len(rows)) * 34 + 40))
    if max_height:
        table.setMaximumHeight(max_height)
    return table


def metric_grid(cards: list[MetricCard], columns: int = 4) -> QWidget:
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(12)
    for index, card in enumerate(cards):
        grid.addWidget(card, index // columns, index % columns)
    return host


def legend(ax, *, location: str = "upper left") -> None:
    leg = ax.legend(frameon=False, fontsize=8, loc=location, ncol=2)
    if leg:
        for label in leg.get_texts():
            label.set_color(PALETTE["muted"])
