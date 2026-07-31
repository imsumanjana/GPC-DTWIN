from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from gpc_dtwin.ui.pages.analytics_page import AnalyticsPage
from gpc_dtwin.ui.pages.audit_page import AuditPage
from gpc_dtwin.ui.pages.database_page import DatabasePage
from gpc_dtwin.ui.pages.statistics_page import StatisticsPage


class DataWorkspacePage(QWidget):
    """Unified data workspace containing records, checks, plots, and statistics."""

    TAB_LABELS = (
        "Data Explorer",
        "Quality Check",
        "Visual Analysis",
        "Statistical Analysis",
    )

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("DataWorkspaceTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.tabBar().setExpanding(False)

        self.data_explorer_page = DatabasePage(context)
        self.quality_check_page = AuditPage(context)
        self.visual_analysis_page = AnalyticsPage(context)
        self.statistical_analysis_page = StatisticsPage(context)

        self.workspace_pages = (
            self.data_explorer_page,
            self.quality_check_page,
            self.visual_analysis_page,
            self.statistical_analysis_page,
        )

        for label, page in zip(self.TAB_LABELS, self.workspace_pages, strict=True):
            self.tabs.addTab(page, label)

        root.addWidget(self.tabs, 1)

    def set_current_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(max(0, min(int(index), self.tabs.count() - 1)))

    def current_tab(self) -> int:
        return self.tabs.currentIndex()
