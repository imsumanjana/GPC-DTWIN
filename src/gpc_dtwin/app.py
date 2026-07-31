"""GPC-DTwin application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from gpc_dtwin import __version__
from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.health import health_check_text, run_health_check
from gpc_dtwin.logging_config import configure_logging
from gpc_dtwin.metadata import APP_NAME, ORGANIZATION_NAME
from gpc_dtwin.paths import ICON_PATH, ensure_user_directories
from gpc_dtwin.ui.main_window import MainWindow


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gpc-dtwin", add_help=True)
    parser.add_argument("--version", action="store_true", help="show application version")
    parser.add_argument("--self-check", action="store_true", help="run local health checks")
    return parser


def _install_exception_handler(log_path) -> None:
    def handle(exception_type, exception, trace):
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, trace)
            return
        details = "".join(traceback.format_exception(exception_type, exception, trace))
        logging.getLogger("gpc_dtwin").critical("Unhandled exception\n%s", details)
        message = QMessageBox()
        message.setIcon(QMessageBox.Icon.Critical)
        message.setWindowTitle(f"{APP_NAME} encountered a problem")
        message.setText("The requested operation could not be completed.")
        message.setInformativeText(f"A diagnostic record was written to:\n{log_path}")
        message.setDetailedText(details)
        message.exec()
    sys.excepthook = handle


def main() -> int:
    args = _parser().parse_args()
    if args.version:
        print(f"{APP_NAME} {__version__}")
        return 0

    ensure_user_directories()
    log_path = configure_logging()
    logging.getLogger("gpc_dtwin").info("Starting %s %s", APP_NAME, __version__)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setApplicationVersion(__version__)
    app.setFont(QFont("Segoe UI", 10))
    if ICON_PATH.is_file():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    _install_exception_handler(log_path)

    if args.self_check:
        items = run_health_check()
        print(health_check_text(items))
        return 0 if all(item.passed for item in items) else 1

    context = ApplicationContext()
    try:
        context.bootstrap()
    except Exception as error:
        logging.getLogger("gpc_dtwin").exception("Startup failed")
        QMessageBox.critical(
            None, f"{APP_NAME} could not start",
            f"The local database or bundled reference data could not be prepared.\n\n{error}\n\n"
            f"Diagnostic log: {log_path}",
        )
        return 1

    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
