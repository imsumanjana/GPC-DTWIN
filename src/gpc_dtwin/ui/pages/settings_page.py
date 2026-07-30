from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
)

from gpc_dtwin import __version__
from gpc_dtwin.paths import EXPORT_DIR, MODEL_DIR, REFERENCE_DATASET, REPO_ROOT, TEMPLATE_DATASET
from gpc_dtwin.ui.widgets import SectionHeader


class SettingsPage(QWidget):
    theme_requested = pyqtSignal(str)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.settings = QSettings("GPC-DTwin", "GPC-DTwin-v0.4")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        root.addWidget(SectionHeader(
            "Settings",
            "Appearance, storage locations, and active dataset information."
        ))

        appearance = QFrame()
        appearance.setObjectName("Card")
        appearance_form = QFormLayout(appearance)
        appearance_form.setContentsMargins(18, 18, 18, 18)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setCurrentText(str(self.settings.value("theme", "Dark")))
        appearance_form.addRow("Appearance", self.theme_combo)
        root.addWidget(appearance)

        information = QFrame()
        information.setObjectName("Card")
        form = QFormLayout(information)
        form.setContentsMargins(18, 18, 18, 18)
        form.addRow("Application version", QLabel(__version__))
        form.addRow("Application folder", self._path_label(REPO_ROOT))
        form.addRow("Project database", self._path_label(self.context.database_path))
        form.addRow("Reference dataset", self._path_label(REFERENCE_DATASET))
        form.addRow("Blank CSV template", self._path_label(TEMPLATE_DATASET))
        form.addRow("Model library", self._path_label(MODEL_DIR))
        form.addRow("Current records", QLabel(str(len(self.context.dataframe))))
        form.addRow("Current fields", QLabel(str(len(self.context.dataframe.columns))))
        root.addWidget(information)

        open_exports = QPushButton("Open export folder")
        open_exports.clicked.connect(self.open_export_folder)
        open_models = QPushButton("Open model folder")
        open_models.clicked.connect(self.open_model_folder)
        root.addWidget(open_exports)
        root.addWidget(open_models)
        root.addStretch()
        self.theme_combo.currentTextChanged.connect(self.change_theme)

    @staticmethod
    def _path_label(path) -> QLabel:
        label = QLabel(str(path))
        label.setObjectName("Muted")
        label.setTextInteractionFlags(
            label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        label.setWordWrap(True)
        return label

    def change_theme(self, value: str) -> None:
        self.settings.setValue("theme", value)
        self.theme_requested.emit(value.lower())

    @staticmethod
    def open_export_folder() -> None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(EXPORT_DIR)))

    @staticmethod
    def open_model_folder() -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(MODEL_DIR)))
