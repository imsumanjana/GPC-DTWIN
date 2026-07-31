"""Preview and save fixed square 600 dpi figure exports."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from gpc_dtwin.figure_export import (
    SUPPORTED_FIGURE_SUFFIXES, analyze_export_layout, export_profile,
    save_square_figure,
)


class ExportPreviewDialog(QDialog):
    def __init__(self, figure, parent=None, *, suggested_name: str = "figure.png"):
        super().__init__(parent)
        self.figure = figure
        self.suggested_name = suggested_name
        self.setWindowTitle("Export preview")
        self.resize(780, 760)
        root = QVBoxLayout(self)
        profile = export_profile()
        heading = QLabel("Square figure export")
        heading.setObjectName("SectionTitle")
        summary = QLabel(
            f"{profile.size_inches:g} × {profile.size_inches:g} inches · "
            f"{profile.dpi} dpi · {profile.pixel_size} × {profile.pixel_size} pixels for raster output"
        )
        summary.setObjectName("Muted")
        summary.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(summary)

        try:
            preview_figure = deepcopy(figure)
        except Exception:
            preview_figure = figure
        self.canvas = FigureCanvasQTAgg(preview_figure)
        self.canvas.setMinimumSize(560, 560)
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(8, 8, 8, 8)
        host_layout.addWidget(self.canvas)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(host)
        root.addWidget(area, 1)

        warnings = QLabel("\n".join(f"• {item}" for item in analyze_export_layout(figure)))
        warnings.setObjectName("Muted")
        warnings.setWordWrap(True)
        root.addWidget(warnings)

        actions = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "PDF", "SVG", "TIFF"])
        actions.addWidget(QLabel("Format"))
        actions.addWidget(self.format_combo)
        actions.addStretch()
        save_button = QPushButton("Save figure")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(save_button)
        actions.addWidget(close_button)
        root.addLayout(actions)

    def _save(self) -> None:
        suffix = {"PNG": ".png", "PDF": ".pdf", "SVG": ".svg", "TIFF": ".tiff"}[
            self.format_combo.currentText()
        ]
        default = str(Path(self.suggested_name).with_suffix(suffix))
        path, _ = QFileDialog.getSaveFileName(
            self, "Export figure", default,
            "Figure files (*.png *.pdf *.svg *.tif *.tiff)",
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() not in SUPPORTED_FIGURE_SUFFIXES:
            destination = destination.with_suffix(suffix)
        try:
            save_square_figure(self.figure, destination)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"Saved:\n{destination}")
