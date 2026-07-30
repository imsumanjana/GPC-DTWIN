"""GPC-DTwin application entry point."""

from __future__ import annotations
import os
import sys

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from gpc_dtwin import __version__
from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.ui.main_window import MainWindow


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("GPC-DTwin")
    app.setOrganizationName("GPC-DTwin")
    app.setApplicationVersion(__version__)
    app.setFont(QFont("Segoe UI", 10))

    context = ApplicationContext()
    try:
        context.bootstrap()
    except Exception as error:
        QMessageBox.critical(
            None, "GPC-DTwin could not start",
            f"The project database or reference dataset could not be prepared.\n\n{error}",
        )
        return 1

    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
