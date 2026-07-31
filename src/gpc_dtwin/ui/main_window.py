from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings, QSize, Qt, QUrl
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon, QKeySequence, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QStatusBar, QVBoxLayout, QWidget,
)

from gpc_dtwin import __version__
from gpc_dtwin.metadata import (
    APP_EDITION, APP_NAME, COPYRIGHT_HOLDER, COPYRIGHT_TEXT, ORCID_ID, ORCID_URL,
    ORGANIZATION_NAME, SETTINGS_APPLICATION, attribution_html,
)
from gpc_dtwin.paths import APP_DATA_ROOT, BACKUP_DIR, EXPORT_DIR, ICON_PATH
from gpc_dtwin.ui.pages.active_learning_page import ActiveLearningPage
from gpc_dtwin.ui.pages.analytics_page import AnalyticsPage
from gpc_dtwin.ui.pages.audit_page import AuditPage
from gpc_dtwin.ui.pages.database_page import DatabasePage
from gpc_dtwin.ui.pages.digital_twin_page import DigitalTwinPage
from gpc_dtwin.ui.pages.modeling_page import ModelingPage
from gpc_dtwin.ui.pages.ndt_durability_page import NDTDurabilityPage
from gpc_dtwin.ui.pages.optimization_page import OptimizationPage
from gpc_dtwin.ui.pages.overview_page import OverviewPage
from gpc_dtwin.ui.pages.reporting_page import ReportingPage
from gpc_dtwin.ui.pages.settings_page import SettingsPage
from gpc_dtwin.ui.pages.statistics_page import StatisticsPage
from gpc_dtwin.ui.pages.visualization_3d_page import Visualization3DPage
from gpc_dtwin.ui.polish import polish_workspace
from gpc_dtwin.ui.scrolling import ResponsiveScrollArea, scrollable_page
from gpc_dtwin.ui.theme import stylesheet


class NavButton(QPushButton):
    def __init__(self, code: str, text: str, parent=None):
        super().__init__(parent)
        self.code = code
        self.label = text
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(text)
        self.set_expanded(True)

    def set_expanded(self, expanded: bool) -> None:
        self.setText(f"{self.code:<3}  {self.label}" if expanded else self.code)
        self.setTextAlignment(expanded)

    def setTextAlignment(self, expanded: bool) -> None:
        self.setProperty("compact", not expanded)
        self.setStyleSheet("text-align: left;" if expanded else "text-align: center;")


class MainWindow(QMainWindow):
    PAGE_META = [
        ("Overview", "Material-test coverage, quality, and performance at a glance"),
        ("Data Explorer", "Search, filter, review, and manage structured records"),
        ("Quality Check", "Deterministic checks for consistency and completeness"),
        ("Visual Analytics", "Interactive property comparisons and heatmaps"),
        ("Statistical Analysis", "Descriptive statistics, group comparison, and regression"),
        ("Predictive Models", "Cross-validated model comparison, prediction, and model storage"),
        ("Digital Twin", "Uncertainty-aware prediction, calibration, reliability, and response maps"),
        ("3D Explorer", "Interactive response surfaces, uncertainty landscapes, and specimen fields"),
        ("NDT & Durability", "NDT fusion, exposure profiles, and uncertainty-aware durability estimates"),
        ("Optimization", "Pareto trade-offs, engineering constraints, and inverse material design"),
        ("Active Learning", "Uncertainty-guided experiment selection and closed-loop model updates"),
        ("Reports & Provenance", "Reports, fingerprints, manifests, and integrity-verifiable bundles"),
        ("Settings", "Appearance, storage, attribution, and dataset information"),
    ]
    NAV_ITEMS = [
        ("O", "Overview"), ("D", "Data Explorer"), ("Q", "Quality Check"),
        ("V", "Visual Analytics"), ("S", "Statistical Analysis"),
        ("M", "Predictive Models"), ("T", "Digital Twin"), ("3D", "3D Explorer"),
        ("ND", "NDT & Durability"), ("OP", "Optimization"),
        ("AL", "Active Learning"), ("RP", "Reports & Provenance"), ("⚙", "Settings"),
    ]

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.settings = QSettings(ORGANIZATION_NAME, SETTINGS_APPLICATION)
        self._sidebar_expanded = True
        self._responsive_sidebar = True
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        if ICON_PATH.is_file():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1480, 900)
        self.setMinimumSize(900, 640)

        root_widget = QWidget()
        root_widget.setObjectName("AppRoot")
        self.setCentralWidget(root_widget)
        shell = QHBoxLayout(root_widget)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = self._build_sidebar()
        shell.addWidget(self.sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.pages = [
            OverviewPage(context), DatabasePage(context), AuditPage(context),
            AnalyticsPage(context), StatisticsPage(context), ModelingPage(context),
            DigitalTwinPage(context), Visualization3DPage(context),
            NDTDurabilityPage(context), OptimizationPage(context),
            ActiveLearningPage(context), ReportingPage(context), SettingsPage(context),
        ]
        self.page_containers = []
        for page in self.pages:
            polish_workspace(page)
            container = scrollable_page(page, minimum_width=920)
            self.page_containers.append(container)
            self.stack.addWidget(container)
        self.pages[-1].theme_requested.connect(self.apply_theme)
        self.pages[-1].layout_reset_requested.connect(self.reset_window_layout)
        main_layout.addWidget(self.stack, 1)
        shell.addWidget(main, 1)

        self._build_menu()
        self._build_statusbar()
        self.context.message.connect(self.show_message)
        self.context.data_changed.connect(self.update_dataset_label)
        self.update_dataset_label()
        self.apply_theme(str(self.settings.value("theme", "Dark")).lower())
        self._restore_layout()
        self.navigate(int(self.settings.value("page", 0)))

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(82)
        sidebar.setMaximumWidth(276)
        sidebar.setFixedWidth(276)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(8)

        self.brand_host = QWidget()
        brand = QHBoxLayout(self.brand_host)
        brand.setContentsMargins(0, 0, 0, 0)
        mark = QLabel("GPC")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(46, 46)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_text = QWidget()
        titles = QVBoxLayout(self.brand_text)
        titles.setContentsMargins(0, 0, 0, 0)
        title = QLabel(APP_NAME)
        title.setObjectName("BrandTitle")
        subtitle = QLabel(f"{APP_EDITION} · v{__version__}")
        subtitle.setObjectName("BrandSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        brand.addWidget(mark)
        brand.addWidget(self.brand_text, 1)
        layout.addWidget(self.brand_host)
        layout.addSpacing(10)

        nav_host = QWidget()
        nav_layout = QVBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 4, 4, 4)
        nav_layout.setSpacing(7)
        self.nav_buttons: list[NavButton] = []
        for index, (code, label) in enumerate(self.NAV_ITEMS):
            button = NavButton(code, label)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
        nav_layout.addStretch()
        self.coverage_label = QLabel("FA · GGBS · SF\nMechanical · NDT · Durability")
        self.coverage_label.setObjectName("BrandSubtitle")
        self.coverage_label.setWordWrap(True)
        nav_layout.addWidget(self.coverage_label)

        nav_scroll = ResponsiveScrollArea(nav_host)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(nav_scroll, 1)
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setMinimumHeight(88)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(18, 12, 20, 12)
        layout.setSpacing(12)

        self.sidebar_toggle = QPushButton("☰")
        self.sidebar_toggle.setObjectName("SidebarToggle")
        self.sidebar_toggle.setToolTip("Show or hide navigation labels")
        self.sidebar_toggle.setFixedSize(38, 38)
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        layout.addWidget(self.sidebar_toggle)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.page_title = QLabel()
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("PageSubtitle")
        self.page_subtitle.setWordWrap(True)
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        layout.addLayout(titles, 1)

        actions = QWidget()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        refresh_button = QPushButton("Refresh")
        refresh_button.setToolTip("Reload the active database (F5)")
        refresh_button.clicked.connect(self.refresh_project)
        export_button = QPushButton("Export CSV")
        export_button.setToolTip("Export the active dataset (Ctrl+E)")
        export_button.clicked.connect(self.export_csv)
        import_button = QPushButton("Import CSV")
        import_button.setObjectName("PrimaryButton")
        import_button.setToolTip("Replace the active dataset from a compatible CSV (Ctrl+I)")
        import_button.clicked.connect(self.import_csv)
        action_layout.addWidget(refresh_button)
        action_layout.addWidget(export_button)
        action_layout.addWidget(import_button)
        actions.setMinimumWidth(actions.sizeHint().width())

        action_scroll = QScrollArea()
        action_scroll.setObjectName("TopActionScroll")
        action_scroll.setWidgetResizable(True)
        action_scroll.setFrameShape(QFrame.Shape.NoFrame)
        action_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        action_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        action_scroll.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        action_scroll.setFixedHeight(56)
        action_scroll.setWidget(actions)
        layout.addWidget(action_scroll)
        return topbar

    def _build_statusbar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("Ready")
        status.addWidget(self.status_label, 1)
        self.dataset_label = QLabel()
        status.addPermanentWidget(self.dataset_label)
        attribution = QLabel(
            f'© 2026 {COPYRIGHT_HOLDER} · <a href="{ORCID_URL}">ORCID</a>'
        )
        attribution.setTextFormat(Qt.TextFormat.RichText)
        attribution.setOpenExternalLinks(True)
        attribution.setToolTip(f"ORCID: {ORCID_ID}")
        status.addPermanentWidget(attribution)

    def _action(self, text: str, slot, shortcut: str | None = None) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        return action

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self._action("Import CSV…", self.import_csv, "Ctrl+I"))
        file_menu.addAction(self._action("Export active dataset…", self.export_csv, "Ctrl+E"))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Back up database…", self.backup_database, "Ctrl+Shift+B"))
        file_menu.addAction(self._action("Restore database…", self.restore_database))
        file_menu.addAction(self._action("Open application data folder", self.open_data_folder))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Exit", self.close, "Alt+F4"))

        data_menu = self.menuBar().addMenu("Data")
        data_menu.addAction(self._action("Run quality check", self.context.run_audit, "Ctrl+Q"))
        data_menu.addAction(self._action("Reload database", self.refresh_project, "F5"))

        analysis_menu = self.menuBar().addMenu("Analysis")
        for label, index in [
            ("Predictive models", 5), ("Digital twin", 6), ("3D explorer", 7),
            ("NDT and durability", 8), ("Optimization", 9),
            ("Active learning", 10), ("Reports and provenance", 11),
        ]:
            analysis_menu.addAction(self._action(label, lambda checked=False, i=index: self.navigate(i)))

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self._action("Toggle navigation", self.toggle_sidebar, "Ctrl+Shift+N"))
        view_menu.addAction(self._action("Reset window layout", self.reset_window_layout))

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self._action("About GPC-DTwin", self.show_about))

    def show_about(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("About GPC-DTwin")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText(
            attribution_html() + f"<br><br>Version {__version__}<br>"
            + "A local desktop platform for structured geopolymer-concrete analytics, "
              "uncertainty-aware modelling, optimization, active learning, and reproducibility."
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        for label in dialog.findChildren(QLabel):
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        dialog.exec()

    def navigate(self, index: int) -> None:
        index = max(0, min(index, self.stack.count() - 1))
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        title, subtitle = self.PAGE_META[index]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        self.settings.setValue("page", index)

    def toggle_sidebar(self, checked: bool = False, expanded: bool | None = None) -> None:
        self._responsive_sidebar = False
        target = (not self._sidebar_expanded) if expanded is None else bool(expanded)
        self._set_sidebar_expanded(target)
        self.settings.setValue("sidebarExpanded", target)

    def _set_sidebar_expanded(self, expanded: bool) -> None:
        self._sidebar_expanded = expanded
        self.sidebar.setFixedWidth(276 if expanded else 82)
        self.brand_text.setVisible(expanded)
        self.coverage_label.setVisible(expanded)
        for button in self.nav_buttons:
            button.set_expanded(expanded)
        self.sidebar_toggle.setText("☰" if expanded else "›")

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        width = event.size().width()
        if width < 1160 and self._sidebar_expanded:
            self._set_sidebar_expanded(False)
        elif width > 1320 and not self._sidebar_expanded and self._responsive_sidebar:
            self._set_sidebar_expanded(True)

    def apply_theme(self, name: str) -> None:
        theme_name = "light" if name.lower() == "light" else "dark"
        QApplication.instance().setStyleSheet(stylesheet(theme_name))
        self.settings.setValue("theme", theme_name.title())

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import compatible dataset", str(APP_DATA_ROOT), "CSV data (*.csv)"
        )
        if not path:
            return
        answer = QMessageBox.question(
            self, "Replace active dataset?",
            "Importing a CSV replaces all records in the active local database. "
            "An automatic database backup will be created first. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.context.import_csv(path)
        except Exception as error:
            QMessageBox.critical(self, "CSV import failed", str(error))

    def export_csv(self) -> None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        default = EXPORT_DIR / "GPC_DTwin_Dataset_Export.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export active dataset", str(default), "CSV data (*.csv)"
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != ".csv":
            destination = destination.with_suffix(".csv")
        try:
            self.context.export_csv(destination)
        except Exception as error:
            QMessageBox.critical(self, "CSV export failed", str(error))

    def backup_database(self) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        default = BACKUP_DIR / self.context._backup_name()
        path, _ = QFileDialog.getSaveFileName(
            self, "Back up local database", str(default), "SQLite database (*.sqlite3)"
        )
        if not path:
            return
        try:
            self.context.backup_database(path)
        except Exception as error:
            QMessageBox.critical(self, "Database backup failed", str(error))

    def restore_database(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Restore local database", str(BACKUP_DIR), "SQLite database (*.sqlite3 *.db)"
        )
        if not path:
            return
        answer = QMessageBox.warning(
            self, "Restore database?",
            "The current database will be backed up automatically and then replaced. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.context.restore_database(path)
        except Exception as error:
            QMessageBox.critical(self, "Database restore failed", str(error))

    @staticmethod
    def open_data_folder() -> None:
        APP_DATA_ROOT.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DATA_ROOT)))

    def refresh_project(self) -> None:
        try:
            self.context.reload(emit=False)
            self.context.run_audit(emit=False)
            self.context.data_changed.emit()
            self.context.audit_changed.emit()
            self.context.message.emit("Dataset refreshed.")
        except Exception as error:
            QMessageBox.critical(self, "Refresh failed", str(error))

    def update_dataset_label(self) -> None:
        self.dataset_label.setText(
            f"{len(self.context.dataframe)} records · {len(self.context.dataframe.columns)} fields"
        )

    def show_message(self, text: str) -> None:
        self.status_label.setText(text)
        self.statusBar().showMessage(text, 7000)

    def _restore_layout(self) -> None:
        geometry = self.settings.value("windowGeometry")
        state = self.settings.value("windowState")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            self.restoreState(state)
        saved_sidebar = self.settings.value("sidebarExpanded")
        if saved_sidebar is not None:
            expanded = str(saved_sidebar).lower() in {"true", "1", "yes"}
            self._responsive_sidebar = False
            self._set_sidebar_expanded(expanded)

    def reset_window_layout(self) -> None:
        self.settings.remove("windowGeometry")
        self.settings.remove("windowState")
        self.resize(1480, 900)
        self._responsive_sidebar = True
        self._set_sidebar_expanded(True)
        self.settings.remove("sidebarExpanded")
        self.context.message.emit("Window layout reset.")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
