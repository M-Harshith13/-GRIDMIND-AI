"""Launch the native GRIDMIND AI desktop application."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
# Avoid joblib's Windows WMIC probe in restricted environments; this keeps
# model startup quiet while preserving the machine's available logical cores.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from frontend.main_window import MainWindow
        from frontend.styles import configure_application
    except ImportError as exc:
        message = (
            "GRIDMIND AI needs its desktop dependencies. From this project folder, run:\n\n"
            "python -m pip install -r requirements.txt\n\n"
            f"Import detail: {exc}"
        )
        print(message, file=sys.stderr)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "GRIDMIND AI · Dependencies", message)
        except ImportError:
            pass
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("GRIDMIND AI")
    app.setOrganizationName("GRIDMIND")
    app.setStyle("Fusion")
    configure_application(app)
    try:
        window = MainWindow()
    except Exception as exc:
        detail = f"GRIDMIND AI could not initialize its local model or SQLite store.\n\n{exc}"
        print(detail, file=sys.stderr)
        QMessageBox.critical(None, "GRIDMIND AI · Startup error", detail)
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
