"""Automated offscreen interface checks for release installations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QScrollArea, QToolButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from gpc_dtwin import __version__
from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.metadata import ORGANIZATION_NAME, SETTINGS_APPLICATION
from gpc_dtwin.paths import UI_CHECK_DIR
from gpc_dtwin.ui.main_window import MainWindow
from gpc_dtwin.ui.figure_tabs import FigureTabs
from gpc_dtwin.ui.scrolling import ResponsiveScrollArea


def run_ui_check(output: Path, screenshots: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication(["gpc-dtwin-ui-check"])
    findings: list[dict] = []
    settings = QSettings(ORGANIZATION_NAME, SETTINGS_APPLICATION)
    saved = {key: settings.value(key) for key in settings.allKeys()}
    settings.clear()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            context = ApplicationContext(database_path=Path(temporary) / "ui-check.sqlite3")
            context.bootstrap()
            window = MainWindow(context)
            for width, height in ((1024, 720), (1366, 768), (1920, 1080)):
                window.resize(width, height)
                window.show()
                application.processEvents()
                for index, (title, _) in enumerate(window.PAGE_META):
                    window.navigate(index)
                    application.processEvents()
                    container = window.page_containers[index]
                    passed_scroll = isinstance(container, ResponsiveScrollArea)
                    if not passed_scroll:
                        findings.append({"size": [width, height], "page": title, "issue": "workspace is not scrollable"})
                    for button in window.pages[index].findChildren(QPushButton):
                        if button.isVisible() and button.height() < 28:
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": f"button below minimum readable height: {button.text()}",
                            })
                    for figure_tabs in window.pages[index].findChildren(FigureTabs):
                        if not figure_tabs.tabs.isMovable():
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": "figure tabs are not reorderable",
                            })
                        if figure_tabs.tabs.tabBar().expanding():
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": "figure tabs stretch unnecessarily",
                            })
                        if figure_tabs.square_display:
                            if figure_tabs.natural_square_side < 600:
                                findings.append({
                                    "size": [width, height], "page": title,
                                    "issue": "square figure host is below the natural-size threshold",
                                })
                            if figure_tabs.tabs.count():
                                scroll = figure_tabs.tabs.currentWidget()
                                if not isinstance(scroll, QScrollArea) or scroll.widgetResizable():
                                    findings.append({
                                        "size": [width, height], "page": title,
                                        "issue": "square figure host does not preserve scrollable natural dimensions",
                                    })
                        actions = figure_tabs.findChildren(QToolButton, "FigureActionButton")
                        if len(actions) < 3:
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": "figure tab actions are incomplete",
                            })
                    for canvas in window.pages[index].findChildren(FigureCanvasQTAgg):
                        style_button = getattr(canvas, "_gpc_style_button", None)
                        if style_button is None:
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": "chart canvas is missing its appearance icon",
                            })
                        elif style_button.x() < 0 or style_button.y() < 0 or (
                            style_button.x() + style_button.width() > canvas.width()
                            or style_button.y() + style_button.height() > canvas.height()
                        ):
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": "chart appearance icon is outside the canvas bounds",
                            })
                        if canvas.minimumWidth() < 520 or canvas.minimumHeight() < 420:
                            findings.append({
                                "size": [width, height], "page": title,
                                "issue": "chart canvas minimum size is below the readability threshold",
                            })
                    if screenshots:
                        safe = title.lower().replace(" ", "_").replace("&", "and")
                        window.grab().save(str(output / f"{width}x{height}_{index:02d}_{safe}.png"))
            window.close()
    finally:
        settings.clear()
        for key, value in saved.items():
            settings.setValue(key, value)
        settings.sync()
    report = {
        "application": "GPC-DTwin",
        "version": __version__,
        "pages": len(MainWindow.PAGE_META),
        "sizes": [[1024, 720], [1366, 768], [1920, 1080]],
        "passed": not findings,
        "chart_style_icons": len(window.findChildren(QToolButton, "ChartStyleButton")) if 'window' in locals() else 0,
        "figure_action_buttons": len(window.findChildren(QToolButton, "FigureActionButton")) if 'window' in locals() else 0,
        "findings": findings,
    }
    (output / "ui-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(prog="gpc-dtwin-ui-check")
    parser.add_argument("--output", type=Path, default=UI_CHECK_DIR)
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    report = run_ui_check(args.output, args.screenshots)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
