"""Primary GRIDMIND native desktop shell and navigation."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.desktop_service import DesktopService
from backend.storage import DB_PATH

from .assistant_page import AssistantPage
from .dashboard import DashboardPage
from .forecasting_page import ForecastingPage
from .monitoring_page import MonitoringPage
from .orchestration_page import OrchestrationPage
from .simulation_page import SimulationPage
from .styles import ColorBlockLabel, PALETTE, set_label_style
from .widgets import SurfaceFrame


class NavigationButton(QPushButton):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            background = QColor("#12283a")
            foreground = QColor(PALETTE["cyan"])
        elif self.underMouse():
            background = QColor("#142236")
            foreground = QColor(PALETTE["text"])
        else:
            background = QColor(PALETTE["sidebar"])
            foreground = QColor(PALETTE["muted"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        if self.isChecked():
            painter.setBrush(QColor(PALETTE["cyan"]))
            painter.drawRoundedRect(1, 8, 3, max(1, self.height() - 16), 1, 1)
        painter.setPen(foreground)
        font = self.font()
        font.setBold(self.isChecked())
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(15, 0, -6, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()


class MainWindow(QMainWindow):
    PAGE_NAMES = ["Live dashboard", "Demand forecast", "Microgrid control", "Scenario simulation", "GRIDMIND assistant", "System monitoring"]
    NAV_LABELS = [
        "◉   Live dashboard",
        "⌁   Demand forecast",
        "⟲   Microgrid control",
        "◇   Scenario simulation",
        "▤   GRIDMIND assistant",
        "▥   System monitoring",
    ]

    def __init__(self):
        super().__init__()
        self.service = DesktopService()
        self.setWindowTitle("GRIDMIND AI · Intelligent Microgrid Orchestration")
        self.setMinimumSize(1120, 720)
        self.resize(1480, 930)

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.setCentralWidget(shell)

        sidebar = SurfaceFrame(background=PALETTE["sidebar"], radius=0)
        sidebar.setFixedWidth(245)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(17, 20, 14, 16)
        sidebar_layout.setSpacing(8)
        brand = QHBoxLayout()
        mark = ColorBlockLabel("GM", "#12303b", PALETTE["cyan"], radius=11)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(40, 40)
        set_label_style(mark, size=13, bold=True)
        brand_text = QVBoxLayout()
        name = QLabel("GRIDMIND AI")
        set_label_style(name, size=12, bold=True, letter_spacing=0.5)
        sub = QLabel("ENERGY INTELLIGENCE")
        set_label_style(sub, color=PALETTE["muted"], size=7.5, letter_spacing=1)
        brand_text.addWidget(name)
        brand_text.addWidget(sub)
        brand.addWidget(mark)
        brand.addSpacing(10)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        sidebar_layout.addLayout(brand)

        workspace = ColorBlockLabel("NORTHSTAR MICROGRID\nOperations workspace", PALETTE["panel"], PALETTE["muted"], radius=9)
        workspace.setContentsMargins(11, 10, 11, 10)
        sidebar_layout.addWidget(workspace)

        self.nav_buttons: list[QPushButton] = []
        section_labels = ["WORKSPACE", "FORECAST & CONTROL", "INTELLIGENCE"]
        sections = [[0], [1, 2, 3], [4, 5]]
        for section, indices in zip(section_labels, sections):
            label = QLabel(section)
            set_label_style(label, color=PALETTE["muted"], size=8, bold=True, letter_spacing=1)
            label.setContentsMargins(0, 14, 0, 0)
            sidebar_layout.addWidget(label)
            for index in indices:
                button = NavigationButton(self.NAV_LABELS[index])
                button.setCheckable(True)
                button.setMinimumHeight(39)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(lambda checked=False, page=index: self.show_page(page))
                sidebar_layout.addWidget(button)
                self.nav_buttons.append(button)
        sidebar_layout.addStretch(1)

        rule = ColorBlockLabel("SOLAR  →  BATTERY  →  GRID", "#10251f", PALETTE["green"], radius=8)
        rule.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_label_style(rule, size=8, bold=True, letter_spacing=0.3)
        rule.setContentsMargins(5, 8, 5, 8)
        sidebar_layout.addWidget(rule)
        local_note = QLabel("LOCAL DESKTOP MODE\nNo server · no hardware link")
        set_label_style(local_note, color=PALETTE["muted"], size=8)
        local_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        local_note.setContentsMargins(4, 8, 4, 4)
        sidebar_layout.addWidget(local_note)
        shell_layout.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        topbar = SurfaceFrame(background=PALETTE["window"], radius=0)
        topbar.setFixedHeight(58)
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(22, 7, 20, 7)
        trail = QLabel("NORTHSTAR MICROGRID   /   OPERATIONS")
        set_label_style(trail, color=PALETTE["muted"], size=9, bold=True, letter_spacing=0.8)
        self.local_state = QLabel("●  MODEL REPLAY")
        set_label_style(self.local_state, color=PALETTE["green"], size=9, bold=True)
        self.clock_label = QLabel("")
        set_label_style(self.clock_label, color=PALETTE["muted"], size=9)
        self.refresh_button = QPushButton("Refresh data")
        self.refresh_button.clicked.connect(self.refresh_current)
        top_layout.addWidget(trail)
        top_layout.addStretch(1)
        top_layout.addWidget(self.local_state)
        top_layout.addSpacing(18)
        top_layout.addWidget(self.clock_label)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.refresh_button)
        main_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self.pages = [
            DashboardPage(self.service),
            ForecastingPage(self.service),
            OrchestrationPage(self.service),
            SimulationPage(self.service),
            AssistantPage(self.service),
            MonitoringPage(self.service),
        ]
        for page in self.pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        main_layout.addWidget(self.stack, 1)

        status = self.statusBar()
        status.showMessage(f"SQLite · {DB_PATH}   |   Historical meter period: Dec 2006 – Nov 2010")
        shell_layout.addWidget(main, 1)
        self.show_page(0)

        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self.periodic_refresh)
        self.timer.start()
        self.update_clock()

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        self.setWindowTitle(f"{self.PAGE_NAMES[index]} · GRIDMIND AI")
        if index > 0:
            self.pages[index].refresh()

    def refresh_current(self) -> None:
        index = self.stack.currentIndex()
        self.pages[index].refresh()
        self.statusBar().showMessage(f"Refreshing local model and SQLite state · {datetime.now().strftime('%H:%M:%S')}", 4000)

    def periodic_refresh(self) -> None:
        self.update_clock()
        page_index = self.stack.currentIndex()
        if page_index in (0, 2, 5):
            self.pages[page_index].refresh()

    def update_clock(self) -> None:
        self.clock_label.setText(datetime.now().astimezone().strftime("%d %b %Y  ·  %H:%M"))

