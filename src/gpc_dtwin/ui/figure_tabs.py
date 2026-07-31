"""Reorderable, expandable, and exportable tabbed figure presentation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
import re

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QMessageBox,
    QSizePolicy, QTabWidget, QToolButton, QVBoxLayout, QWidget, QScrollArea,
)

from gpc_dtwin.figure_export import save_square_figure
from gpc_dtwin.ui.export_preview_dialog import (
    BatchExportOptionsDialog, QualityNavigationToolbar, open_figure_export_dialog,
)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_")
    return cleaned or "figure"


class ExpandedFigureDialog(QDialog):
    def __init__(self, figure: Figure, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(980, 980)
        layout = QVBoxLayout(self)
        try:
            expanded = deepcopy(figure)
        except Exception:
            expanded = figure
        canvas = FigureCanvasQTAgg(expanded)
        canvas.setMinimumSize(820, 820)
        toolbar = QualityNavigationToolbar(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas, 1)
        canvas.draw_idle()


class FigureTabs(QWidget):
    """Show one full-size figure at a time with a compact icon toolbar.

    ``square_display`` keeps the on-screen figure area square at a natural size.
    The containing scroll area is deliberately not resizable in that mode, so a
    smaller viewport receives horizontal and vertical scrollbars instead of
    compressing or stretching the chart.
    """

    def __init__(
        self,
        parent=None,
        *,
        minimum_canvas_size: tuple[int, int] = (620, 540),
        square_display: bool = False,
        natural_square_side: int | None = None,
    ):
        super().__init__(parent)
        self.minimum_canvas_size = minimum_canvas_size
        self.square_display = bool(square_display)
        self.natural_square_side = int(
            natural_square_side or max(minimum_canvas_size[0], minimum_canvas_size[1])
        )
        self._canvases: dict[str, FigureCanvasQTAgg] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        tools = QHBoxLayout()
        tools.addStretch()
        self.expand_button = self._tool("⛶", "Expand current figure", self.expand_current)
        self.export_button = self._tool("⇩", "Export current figure", self.export_current)
        self.export_all_button = self._tool("⇩×", "Export all figure tabs", self.export_all)
        tools.addWidget(self.expand_button)
        tools.addWidget(self.export_button)
        tools.addWidget(self.export_all_button)
        layout.addLayout(tools)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        layout.addWidget(self.tabs, 1)

    @staticmethod
    def _tool(text: str, tooltip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setObjectName("FigureActionButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(32, 30)
        button.clicked.connect(slot)
        return button

    def clear(self) -> None:
        self._canvases.clear()
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            # Hide and close first so any pending paint events are suppressed.
            widget.hide()
            widget.close()
            widget.setParent(None)
            widget.deleteLater()

    def _figure_host(self, name: str, figure: Figure) -> tuple[QScrollArea, FigureCanvasQTAgg]:
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(10, 10, 10, 10)
        host_layout.setSpacing(0)
        canvas = FigureCanvasQTAgg(figure)
        canvas.setObjectName(f"FigureTabCanvas_{_safe_name(name)}")
        canvas.setProperty("gpcChartKey", f"figure_tab_{_safe_name(name).lower()}")

        if self.square_display:
            side = max(self.natural_square_side, 420)
            canvas.setFixedSize(side, side)
            host.setFixedSize(side + 20, side + 20)
            host_layout.addWidget(canvas, 0, Qt.AlignmentFlag.AlignCenter)
        else:
            host.setMinimumSize(*self.minimum_canvas_size)
            canvas.setMinimumSize(*self.minimum_canvas_size)
            canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            host_layout.addWidget(canvas, 1)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidgetResizable(not self.square_display)
        scroll.setWidget(host)
        return scroll, canvas

    def set_figures(self, figures: Mapping[str, Figure], *, active_name: str | None = None) -> None:
        previous = active_name or self.current_name()
        self.clear()
        for name, figure in figures.items():
            scroll, canvas = self._figure_host(name, figure)
            self.tabs.addTab(scroll, name)
            self._canvases[name] = canvas
            canvas.draw_idle()
        if previous and previous in self._canvases:
            self.tabs.setCurrentIndex(self._tab_index(previous))

    def _tab_index(self, name: str) -> int:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == name:
                return index
        return 0

    def current_name(self) -> str | None:
        index = self.tabs.currentIndex()
        return self.tabs.tabText(index) if index >= 0 else None

    def current_figure(self) -> Figure | None:
        canvas = self._canvases.get(self.current_name() or "")
        return canvas.figure if canvas is not None else None

    def figures(self) -> dict[str, Figure]:
        return {name: canvas.figure for name, canvas in self._canvases.items()}

    def expand_current(self) -> None:
        figure = self.current_figure()
        if figure is None:
            return
        dialog = ExpandedFigureDialog(figure, self.current_name() or "Figure", self.window())
        dialog.exec()

    def export_current(self) -> None:
        figure = self.current_figure()
        if figure is None:
            return
        default = f"{_safe_name(self.current_name() or 'figure')}.png"
        open_figure_export_dialog(self, figure, suggested_name=default)

    def export_all(self) -> None:
        if not self._canvases:
            return
        directory = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not directory:
            return
        options = BatchExportOptionsDialog(self)
        if options.exec() != QDialog.DialogCode.Accepted:
            return
        suffix = {"PNG": ".png", "PDF": ".pdf", "SVG": ".svg", "TIFF": ".tiff"}[
            options.selected_format
        ]
        exported = 0
        try:
            for name, figure in self.figures().items():
                save_square_figure(
                    figure,
                    Path(directory) / f"{_safe_name(name)}{suffix}",
                    dpi=options.selected_dpi,
                )
                exported += 1
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"Exported {exported} figures.")
