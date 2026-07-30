from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
)

from gpc_dtwin import __version__
from gpc_dtwin.paths import (
    ACTIVE_LEARNING_DIR, DURABILITY_DIR, EXPORT_DIR, MODEL_DIR, NDT_DIR,
    OPTIMIZATION_DIR, REFERENCE_DATASET, REPO_ROOT, TEMPLATE_DATASET, TWIN_DIR,
)
from gpc_dtwin.ui.widgets import SectionHeader


class SettingsPage(QWidget):
    theme_requested = pyqtSignal(str)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.settings = QSettings("GPC-DTwin", "GPC-DTwin-v0.8")
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
        form.addRow("Digital twin library", self._path_label(TWIN_DIR))
        form.addRow("NDT model library", self._path_label(NDT_DIR))
        form.addRow("Durability estimator library", self._path_label(DURABILITY_DIR))
        form.addRow("Optimization run library", self._path_label(OPTIMIZATION_DIR))
        form.addRow("Active-learning run library", self._path_label(ACTIVE_LEARNING_DIR))
        form.addRow("Current records", QLabel(str(len(self.context.dataframe))))
        form.addRow("Current fields", QLabel(str(len(self.context.dataframe.columns))))
        root.addWidget(information)

        open_exports = QPushButton("Open export folder")
        open_exports.clicked.connect(self.open_export_folder)
        open_models = QPushButton("Open model folder")
        open_models.clicked.connect(self.open_model_folder)
        open_twins = QPushButton("Open digital twin folder")
        open_twins.clicked.connect(self.open_twin_folder)
        open_ndt = QPushButton("Open NDT model folder")
        open_ndt.clicked.connect(self.open_ndt_folder)
        open_durability = QPushButton("Open durability estimator folder")
        open_durability.clicked.connect(self.open_durability_folder)
        open_optimization = QPushButton("Open optimization folder")
        open_optimization.clicked.connect(self.open_optimization_folder)
        open_active_learning = QPushButton("Open active-learning folder")
        open_active_learning.clicked.connect(self.open_active_learning_folder)
        root.addWidget(open_exports)
        root.addWidget(open_models)
        root.addWidget(open_twins)
        root.addWidget(open_ndt)
        root.addWidget(open_durability)
        root.addWidget(open_optimization)
        root.addWidget(open_active_learning)
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

    @staticmethod
    def open_twin_folder() -> None:
        TWIN_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(TWIN_DIR)))

    @staticmethod
    def open_ndt_folder() -> None:
        NDT_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(NDT_DIR)))

    @staticmethod
    def open_durability_folder() -> None:
        DURABILITY_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DURABILITY_DIR)))

    @staticmethod
    def open_optimization_folder() -> None:
        OPTIMIZATION_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(OPTIMIZATION_DIR)))

    @staticmethod
    def open_active_learning_folder() -> None:
        ACTIVE_LEARNING_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ACTIVE_LEARNING_DIR)))

