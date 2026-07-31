"""Preview and save square figures at a user-selected export quality."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from gpc_dtwin.figure_export import (
    EXPORT_DPI, EXPORT_DPI_OPTIONS, SUPPORTED_FIGURE_SUFFIXES,
    analyze_export_layout, export_profile, save_square_figure,
)


class QualityNavigationToolbar(NavigationToolbar2QT):
    """Matplotlib toolbar whose Save action always asks for export quality."""

    def save_figure(self, *args) -> None:
        title = getattr(self.canvas.figure, "_suptitle", None)
        suggested = "figure.png"
        if title is not None and title.get_text().strip():
            cleaned = "_".join(title.get_text().strip().split())
            suggested = f"{cleaned}.png"
        open_figure_export_dialog(
            self, self.canvas.figure, suggested_name=suggested
        )


class ExportPreviewDialog(QDialog):
    def __init__(self, figure, parent=None, *, suggested_name: str = "figure.png"):
        super().__init__(parent)
        self.figure = figure
        self.suggested_name = suggested_name
        self.setWindowTitle("Export preview")
        self.resize(780, 760)
        root = QVBoxLayout(self)
        heading = QLabel("Square figure export")
        heading.setObjectName("SectionTitle")
        self.summary = QLabel()
        self.summary.setObjectName("Muted")
        self.summary.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(self.summary)

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
        self.dpi_combo = QComboBox()
        for dpi in EXPORT_DPI_OPTIONS:
            self.dpi_combo.addItem(f"{dpi} dpi", dpi)
        default_index = self.dpi_combo.findData(EXPORT_DPI)
        self.dpi_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        self.dpi_combo.currentIndexChanged.connect(self._update_summary)
        actions.addWidget(QLabel("Format"))
        actions.addWidget(self.format_combo)
        actions.addSpacing(12)
        actions.addWidget(QLabel("Quality"))
        actions.addWidget(self.dpi_combo)
        actions.addStretch()
        save_button = QPushButton("Save figure")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(save_button)
        actions.addWidget(close_button)
        root.addLayout(actions)
        self._update_summary()

    def _update_summary(self) -> None:
        profile = export_profile(int(self.dpi_combo.currentData()))
        warning = ""
        if profile.dpi >= 1200:
            warning = " · high memory and export time"
        self.summary.setText(
            f"{profile.size_inches:g} × {profile.size_inches:g} inches · "
            f"{profile.dpi} dpi · {profile.pixel_size} × {profile.pixel_size} "
            f"pixels for raster output{warning}"
        )

    def _save(self) -> None:
        selected_dpi = int(self.dpi_combo.currentData())
        if selected_dpi >= 1200:
            answer = QMessageBox.question(
                self,
                "High-resolution export",
                f"{selected_dpi} dpi creates a very large square raster and may require "
                "substantial memory and time. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
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
            save_square_figure(
                self.figure, destination, dpi=selected_dpi
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"Saved:\n{destination}")
        self.accept()


class BatchExportOptionsDialog(QDialog):
    """Choose one format and quality for exporting a set of figures."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Figure export quality")
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "PDF", "SVG", "TIFF"])
        self.dpi_combo = QComboBox()
        for dpi in EXPORT_DPI_OPTIONS:
            self.dpi_combo.addItem(f"{dpi} dpi", dpi)
        index = self.dpi_combo.findData(EXPORT_DPI)
        self.dpi_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow("Format", self.format_combo)
        form.addRow("Quality", self.dpi_combo)
        root.addLayout(form)
        note = QLabel(
            "All figures remain square at 6 × 6 inches. High DPI options create very large raster files."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def selected_format(self) -> str:
        return self.format_combo.currentText()

    @property
    def selected_dpi(self) -> int:
        return int(self.dpi_combo.currentData())


def open_figure_export_dialog(
    parent, figure, *, suggested_name: str = "figure.png"
) -> bool:
    """Open the mandatory quality/preview popup for a user-triggered figure export."""
    dialog = ExportPreviewDialog(
        figure, parent, suggested_name=suggested_name
    )
    return dialog.exec() == QDialog.DialogCode.Accepted
