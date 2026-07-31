from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from gpc_dtwin import __version__
from gpc_dtwin.health import health_check_text, run_health_check
from gpc_dtwin.metadata import (
    COPYRIGHT_TEXT, ORCID_ID, ORCID_URL, ORGANIZATION_NAME, SETTINGS_APPLICATION,
)
from gpc_dtwin.paths import (
    ACTIVE_LEARNING_DIR, APP_DATA_ROOT, BACKUP_DIR, BUNDLE_DIR, DURABILITY_DIR,
    EXPORT_DIR, INSTALL_ROOT, LOG_DIR, MODEL_DIR, NDT_DIR, OPTIMIZATION_DIR,
    REFERENCE_DATASET, REPORT_DIR, TEMPLATE_DATASET, TWIN_DIR,
)


class SettingsPage(QWidget):
    theme_requested = pyqtSignal(str)
    layout_reset_requested = pyqtSignal()

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.settings = QSettings(ORGANIZATION_NAME, SETTINGS_APPLICATION)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)

        appearance = QFrame()
        appearance.setObjectName("Card")
        appearance_form = QFormLayout(appearance)
        appearance_form.setContentsMargins(18, 18, 18, 18)
        appearance_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setCurrentText(str(self.settings.value("theme", "Dark")))
        appearance_form.addRow("Appearance", self.theme_combo)
        reset_button = QPushButton("Reset window layout")
        reset_button.clicked.connect(self.layout_reset_requested.emit)
        appearance_form.addRow("Window", reset_button)
        root.addWidget(appearance)

        attribution = QFrame()
        attribution.setObjectName("Card")
        attribution_form = QFormLayout(attribution)
        attribution_form.setContentsMargins(18, 18, 18, 18)
        attribution_form.addRow("Copyright", self._text_label(COPYRIGHT_TEXT))
        attribution_form.addRow("ORCID", self._link_label(ORCID_ID, ORCID_URL))
        root.addWidget(attribution)

        information = QFrame()
        information.setObjectName("Card")
        form = QFormLayout(information)
        form.setContentsMargins(18, 18, 18, 18)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Application version", QLabel(__version__))
        form.addRow("Installation folder", self._path_label(INSTALL_ROOT))
        form.addRow("Writable data folder", self._path_label(APP_DATA_ROOT))
        form.addRow("Project database", self._path_label(self.context.database_path))
        form.addRow("Reference dataset", self._path_label(REFERENCE_DATASET))
        form.addRow("Blank CSV template", self._path_label(TEMPLATE_DATASET))
        form.addRow("Model library", self._path_label(MODEL_DIR))
        form.addRow("Digital twin library", self._path_label(TWIN_DIR))
        form.addRow("NDT model library", self._path_label(NDT_DIR))
        form.addRow("Durability estimator library", self._path_label(DURABILITY_DIR))
        form.addRow("Optimization run library", self._path_label(OPTIMIZATION_DIR))
        form.addRow("Active-learning run library", self._path_label(ACTIVE_LEARNING_DIR))
        form.addRow("Report library", self._path_label(REPORT_DIR))
        form.addRow("Bundle library", self._path_label(BUNDLE_DIR))
        form.addRow("Backup library", self._path_label(BACKUP_DIR))
        form.addRow("Diagnostic log folder", self._path_label(LOG_DIR))
        form.addRow("Current records", QLabel(str(len(self.context.dataframe))))
        form.addRow("Current fields", QLabel(str(len(self.context.dataframe.columns))))
        root.addWidget(information)

        actions = QFrame()
        actions.setObjectName("Card")
        action_layout = QVBoxLayout(actions)
        action_layout.setContentsMargins(18, 18, 18, 18)
        health_button = QPushButton("Run application check")
        health_button.setObjectName("PrimaryButton")
        health_button.clicked.connect(self.run_check)
        action_layout.addWidget(health_button)
        for label, path in (
            ("Open writable data folder", APP_DATA_ROOT),
            ("Open export folder", EXPORT_DIR), ("Open model folder", MODEL_DIR),
            ("Open digital twin folder", TWIN_DIR), ("Open NDT model folder", NDT_DIR),
            ("Open durability estimator folder", DURABILITY_DIR),
            ("Open optimization folder", OPTIMIZATION_DIR),
            ("Open active-learning folder", ACTIVE_LEARNING_DIR),
            ("Open report folder", REPORT_DIR), ("Open bundle folder", BUNDLE_DIR),
            ("Open backup folder", BACKUP_DIR), ("Open log folder", LOG_DIR),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, p=path: self.open_folder(p))
            action_layout.addWidget(button)
        root.addWidget(actions)
        root.addStretch()
        self.theme_combo.currentTextChanged.connect(self.change_theme)

    @staticmethod
    def _text_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Muted")
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        return label

    @classmethod
    def _path_label(cls, path) -> QLabel:
        return cls._text_label(str(path))

    @staticmethod
    def _link_label(text: str, url: str) -> QLabel:
        label = QLabel(f'<a href="{url}">{text}</a>')
        label.setObjectName("Muted")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        return label

    def change_theme(self, value: str) -> None:
        self.settings.setValue("theme", value)
        self.theme_requested.emit(value.lower())

    def run_check(self) -> None:
        items = run_health_check(self.context.database_path)
        passed = all(item.passed for item in items)
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Application check")
        dialog.setIcon(QMessageBox.Icon.Information if passed else QMessageBox.Icon.Warning)
        dialog.setText("All checks passed." if passed else "One or more checks require attention.")
        dialog.setDetailedText(health_check_text(items))
        dialog.exec()

    @staticmethod
    def open_folder(path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
