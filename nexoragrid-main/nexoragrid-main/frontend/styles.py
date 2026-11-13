"""Native Qt palette and drawing helpers; no HTML or stylesheet language."""

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel


PALETTE = {
    "window": "#080f1b",
    "sidebar": "#0c1524",
    "panel": "#111d2e",
    "panel_alt": "#15243a",
    "border": "#22334a",
    "text": "#edf5ff",
    "muted": "#8ea2ba",
    "cyan": "#40d6e8",
    "green": "#55e2a2",
    "blue": "#729cff",
    "amber": "#ffc56c",
    "red": "#ff7484",
}


def configure_application(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(PALETTE["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(PALETTE["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0c1726"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#132136"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PALETTE["panel_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(PALETTE["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(PALETTE["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(PALETTE["panel_alt"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(PALETTE["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(PALETTE["cyan"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(PALETTE["cyan"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#06121b"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#65768a"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#65768a"))
    app.setPalette(palette)
    font = QFont("Segoe UI", 10)
    app.setFont(font)


def set_label_style(
    label: QLabel,
    *,
    color: str | None = None,
    size: float | None = None,
    bold: bool | None = None,
    letter_spacing: float | None = None,
) -> None:
    font = label.font()
    if size is not None:
        font.setPointSizeF(size)
    if bold is not None:
        font.setBold(bold)
    if letter_spacing is not None:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
    label.setFont(font)
    if color:
        label_palette = label.palette()
        label_palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
        label_palette.setColor(QPalette.ColorRole.Text, QColor(color))
        label.setPalette(label_palette)


class ColorBlockLabel(QLabel):
    """Rounded native label surface painted with QPainter."""

    def __init__(self, text: str, background: str, foreground: str, radius: int = 10):
        super().__init__(text)
        self.background = QColor(background)
        self.foreground = QColor(foreground)
        self.radius = radius
        self.setAutoFillBackground(False)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, self.foreground)
        self.setPalette(palette)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background)
        painter.drawRoundedRect(self.rect(), self.radius, self.radius)
        painter.end()
        super().paintEvent(event)
