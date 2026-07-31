from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from gpc_dtwin.ui.export_preview_dialog import open_figure_export_dialog
from gpc_dtwin.paths import EXPORT_DIR
from gpc_dtwin.services.analytics_service import AnalyticsService
from gpc_dtwin.services.data_service import DataService


class AnalyticsPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.analytics = AnalyticsService()
        self.figure = Figure(figsize=(9, 5), constrained_layout=True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)

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
        key = self.chart_combo.currentData() or "chart"
        open_figure_export_dialog(
            self, self.figure, suggested_name=str(EXPORT_DIR / f"{key}.png")
        )

