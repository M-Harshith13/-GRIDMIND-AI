"""Local, rule-based assistant grounded in current application state."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .base_page import BasePage
from .styles import PALETTE, set_label_style
from .widgets import AccentButton, SectionHeader, SurfaceFrame


class AssistantPage(BasePage):
    def __init__(self, service, parent=None):
        super().__init__(service, parent)
        self.root_layout.addWidget(SectionHeader(
            "GRIDMIND energy assistant",
            "A local rule-based assistant that reads the current forecast, battery dispatch, grid import, and saved model metrics. It is not an LLM.",
        ))
        badge = QLabel("LOCAL RULE-BASED ASSISTANT · CURRENT MODEL REPLAY CONTEXT")
        set_label_style(badge, color=PALETTE["cyan"], size=9, bold=True, letter_spacing=0.8)
        self.root_layout.addWidget(badge)
        self.context_label = QLabel("Questions and answers are saved in the local SQLite database.")
        set_label_style(self.context_label, color=PALETTE["muted"], size=9)
        self.root_layout.addWidget(self.context_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.message_host = QWidget()
        self.message_layout = QVBoxLayout(self.message_host)
        self.message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.message_layout.setSpacing(10)
        self.scroll.setWidget(self.message_host)
        self.root_layout.addWidget(self.scroll, 1)

        examples = QGridLayout()
        prompts = (
            "Why is grid import increasing?",
            "How much solar energy is being generated?",
            "What if demand increases by 20%?",
            "When will the battery be empty?",
        )
        for index, prompt in enumerate(prompts):
            button = QPushButton(prompt)
            button.clicked.connect(lambda checked=False, text=prompt: self.ask_example(text))
            examples.addWidget(button, index // 2, index % 2)
        self.root_layout.addLayout(examples)
        entry_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask about demand, solar, battery, grid import, or a scenario…")
        self.input.returnPressed.connect(self.send_message)
        entry_row.addWidget(self.input, 1)
        self.send_button = AccentButton("Ask GRIDMIND")
        self.send_button.clicked.connect(self.send_message)
        entry_row.addWidget(self.send_button)
        self.root_layout.addLayout(entry_row)
        self.root_layout.addWidget(self.status_label)

    def refresh(self):
        self.launch(self.service.chat_history, self.render_history)

    def ask_example(self, text: str):
        self.input.setText(text)
        self.send_message()

    def send_message(self):
        text = self.input.text().strip()
        if not text:
            self.status_label.setText("Enter a question first.")
            return
        self.input.clear()
        self.launch(
            lambda: self.service.chat(text),
            lambda response: self.render_history(response["history"]),
            busy_widget=self.send_button,
            busy_text="Checking state…",
        )

    def render_history(self, history: list[dict]):
        while self.message_layout.count():
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not history:
            welcome = QLabel(
                "I can explain grid import, report solar output, check the battery's projected reserve, "
                "and estimate the effect of a 20% demand increase."
            )
            welcome.setWordWrap(True)
            set_label_style(welcome, color=PALETTE["muted"], size=10)
            self.message_layout.addWidget(welcome)
        for entry in history:
            self._add_bubble("You", entry["user_message"], PALETTE["panel_alt"], PALETTE["text"])
            self._add_bubble("GRIDMIND", entry["assistant_message"], "#102b32", PALETTE["green"])
        self.message_layout.addStretch(1)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _add_bubble(self, title: str, text: str, color: str, title_color: str):
        bubble = SurfaceFrame(background=color, border=PALETTE["border"], radius=10)
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(5)
        heading = QLabel(title)
        set_label_style(heading, color=title_color, size=9, bold=True)
        message = QLabel(text)
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(heading)
        layout.addWidget(message)
        self.message_layout.addWidget(bubble)
