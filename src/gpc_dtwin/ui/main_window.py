from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from gpc_dtwin import __version__
from gpc_dtwin.paths import EXPORT_DIR
from gpc_dtwin.ui.pages.active_learning_page import ActiveLearningPage
from gpc_dtwin.ui.pages.analytics_page import AnalyticsPage
from gpc_dtwin.ui.pages.audit_page import AuditPage
from gpc_dtwin.ui.pages.database_page import DatabasePage
from gpc_dtwin.ui.pages.digital_twin_page import DigitalTwinPage
from gpc_dtwin.ui.pages.modeling_page import ModelingPage
from gpc_dtwin.ui.pages.ndt_durability_page import NDTDurabilityPage
from gpc_dtwin.ui.pages.optimization_page import OptimizationPage
from gpc_dtwin.ui.pages.overview_page import OverviewPage
from gpc_dtwin.ui.pages.settings_page import SettingsPage
from gpc_dtwin.ui.pages.statistics_page import StatisticsPage
from gpc_dtwin.ui.pages.visualization_3d_page import Visualization3DPage
from gpc_dtwin.ui.scrolling import ResponsiveScrollArea, scrollable_page
from gpc_dtwin.ui.theme import stylesheet


class NavButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


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
        ("Settings", "Appearance, storage, and dataset information"),
    ]

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.settings = QSettings("GPC-DTwin", "GPC-DTwin-v0.8")
        self.setWindowTitle(f"GPC-DTwin v{__version__}")
        self.resize(1560, 960)
        self.setMinimumSize(1040, 700)

        root_widget = QWidget()
        root_widget.setObjectName("AppRoot")
        self.setCentralWidget(root_widget)
        shell = QHBoxLayout(root_widget)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.pages = [
            OverviewPage(context),
            DatabasePage(context),
            AuditPage(context),
            AnalyticsPage(context),
            StatisticsPage(context),
            ModelingPage(context),
            DigitalTwinPage(context),
            Visualization3DPage(context),
            NDTDurabilityPage(context),
            OptimizationPage(context),
            ActiveLearningPage(context),
            SettingsPage(context),
        ]
        self.page_containers = []
        for page in self.pages:
            container = scrollable_page(page, minimum_width=980)
            self.page_containers.append(container)
            self.stack.addWidget(container)
        self.pages[-1].theme_requested.connect(self.apply_theme)
        main_layout.addWidget(self.stack, 1)
        shell.addWidget(main, 1)

        self._build_menu()
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("Ready")
        status.addWidget(self.status_label, 1)
        self.dataset_label = QLabel()
        status.addPermanentWidget(self.dataset_label)

        self.context.message.connect(self.show_message)
        self.context.data_changed.connect(self.update_dataset_label)
        self.update_dataset_label()
        self.navigate(0)
        self.apply_theme(str(self.settings.value("theme", "Dark")).lower())

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(8)

        brand = QHBoxLayout()
        mark = QLabel("GPC")
        mark.setObjectName("BrandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titles = QVBoxLayout()
        title = QLabel("GPC-DTwin")
        title.setObjectName("BrandTitle")
        subtitle = QLabel("Materials Analytics · v0.8")
        subtitle.setObjectName("BrandSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        brand.addWidget(mark)
        brand.addLayout(titles, 1)
        layout.addLayout(brand)
        layout.addSpacing(12)

        nav_host = QWidget()
        nav_layout = QVBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 4, 4, 4)
        nav_layout.setSpacing(8)
        labels = [
            "O   Overview",
            "D   Data Explorer",
            "Q   Quality Check",
            "V   Visual Analytics",
            "S   Statistical Analysis",
            "M   Predictive Models",
            "T   Digital Twin",
            "3D  3D Explorer",
            "ND  NDT & Durability",
            "OP  Optimization",
            "AL  Active Learning",
            "⚙   Settings",
        ]
        self.nav_buttons: list[NavButton] = []
        for index, label in enumerate(labels):
            button = NavButton(label)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
        nav_layout.addStretch()
        coverage = QLabel("FA · GGBS · SF\nMechanical · NDT · Durability")
        coverage.setObjectName("BrandSubtitle")
        coverage.setWordWrap(True)
        nav_layout.addWidget(coverage)

        nav_scroll = ResponsiveScrollArea(nav_host)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(nav_scroll, 1)
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setMinimumHeight(88)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 14, 24, 14)

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

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_project)
        export_button = QPushButton("Export CSV")
        export_button.clicked.connect(self.export_csv)
        import_button = QPushButton("Import CSV")
        import_button.setObjectName("PrimaryButton")
        import_button.clicked.connect(self.import_csv)
        layout.addWidget(refresh_button)
        layout.addWidget(export_button)
        layout.addWidget(import_button)
        return topbar

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        import_action = QAction("Import CSV…", self)
        import_action.triggered.connect(self.import_csv)
        export_action = QAction("Export active dataset…", self)
        export_action.triggered.connect(self.export_csv)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(import_action)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        data_menu = self.menuBar().addMenu("Data")
        check_action = QAction("Run quality check", self)
        check_action.triggered.connect(self.context.run_audit)
        reload_action = QAction("Reload database", self)
        reload_action.triggered.connect(self.refresh_project)
        data_menu.addAction(check_action)
        data_menu.addAction(reload_action)

        analysis_menu = self.menuBar().addMenu("Analysis")
        actions = [
            ("Open predictive models", 5),
            ("Open digital twin", 6),
            ("Open 3D explorer", 7),
            ("Open NDT and durability", 8),
            ("Open optimization", 9),
            ("Open active learning", 10),
        ]
        for label, index in actions:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, i=index: self.navigate(i))
            analysis_menu.addAction(action)

    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        title, subtitle = self.PAGE_META[index]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)

    def apply_theme(self, name: str) -> None:
        theme_name = "light" if name.lower() == "light" else "dark"
        QApplication.instance().setStyleSheet(stylesheet(theme_name))
        self.settings.setValue("theme", theme_name.title())

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import compatible dataset", "", "CSV data (*.csv)"
        )
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "Replace active dataset?",
            "Importing a CSV replaces all records in the active local database. "
            "The selected CSV will not be modified. Continue?",
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
