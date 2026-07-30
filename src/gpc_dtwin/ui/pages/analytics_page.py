from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from gpc_dtwin.figure_export import save_square_figure
from gpc_dtwin.paths import EXPORT_DIR
from gpc_dtwin.services.analytics_service import AnalyticsService
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.ui.widgets import SectionHeader


class AnalyticsPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.analytics = AnalyticsService()
        self.figure = Figure(figsize=(9, 5), constrained_layout=True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        root.addWidget(SectionHeader(
            "Visual analytics",
            "Interactive property comparisons generated from the active dataset."
        ))

        controls = QFrame()
        controls.setObjectName("Card")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.addWidget(QLabel("Chart"))
        self.chart_combo = QComboBox()
        for definition in self.analytics.CHARTS:
            self.chart_combo.addItem(definition.title, definition.key)
        self.chart_combo.setMinimumWidth(300)
        controls_layout.addWidget(self.chart_combo)
        controls_layout.addWidget(QLabel("Mix"))
        self.mix_combo = QComboBox()
        controls_layout.addWidget(self.mix_combo)
        controls_layout.addStretch()
        self.export_button = QPushButton("Export figure")
        self.export_button.setObjectName("PrimaryButton")
        controls_layout.addWidget(self.export_button)
        root.addWidget(controls)

        self.description = QLabel()
        self.description.setObjectName("Muted")
        self.description.setWordWrap(True)
        root.addWidget(self.description)

        card = QFrame()
        card.setObjectName("Card")
        self.chart_layout = QVBoxLayout(card)
        self.chart_layout.setContentsMargins(14, 14, 14, 14)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.chart_layout.addWidget(self.canvas, 1)
        root.addWidget(card, 1)

        self.chart_combo.currentIndexChanged.connect(self.render)
        self.mix_combo.currentTextChanged.connect(self.render)
        self.export_button.clicked.connect(self.export_figure)
        self.context.data_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        current = self.mix_combo.currentText()
        self.mix_combo.blockSignals(True)
        self.mix_combo.clear()
        self.mix_combo.addItems(DataService.unique_values(self.context.dataframe, "mix_id"))
        index = self.mix_combo.findText(current)
        self.mix_combo.setCurrentIndex(index if index >= 0 else 0)
        self.mix_combo.blockSignals(False)
        self.render()

    def render(self) -> None:
        key = self.chart_combo.currentData()
        if not key:
            return
        definition = self.analytics.definition(key)
        self.description.setText(definition.description)
        self.mix_combo.setEnabled(definition.supports_mix_filter)
        try:
            figure = self.analytics.create_figure(
                self.context.dataframe, key, self.mix_combo.currentText() or "M2"
            )
        except Exception as error:
            QMessageBox.critical(self, "Chart generation failed", str(error))
            return
        self.chart_layout.removeWidget(self.canvas)
        self.canvas.setParent(None)
        self.canvas.deleteLater()
        self.figure = figure
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.chart_layout.addWidget(self.canvas, 1)
        self.canvas.draw_idle()

    def export_figure(self) -> None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        key = self.chart_combo.currentData() or "chart"
        default = EXPORT_DIR / f"{key}.png"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export figure",
            str(default),
            "PNG image (*.png);;PDF document (*.pdf);;SVG image (*.svg);;TIFF image (*.tiff *.tif)",
        )
        if not path:
            return
        destination = Path(path)
        if not destination.suffix:
            destination = destination.with_suffix(".png")
        try:
            save_square_figure(self.figure, destination)
            self.context.message.emit(f"Figure exported to {destination.name}.")
        except Exception as error:
            QMessageBox.critical(self, "Figure export failed", str(error))
