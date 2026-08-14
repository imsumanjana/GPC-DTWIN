import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QToolButton

from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.metadata import ORGANIZATION_NAME, SETTINGS_APPLICATION
from gpc_dtwin.ui.main_window import MainWindow
from gpc_dtwin.ui.figure_tabs import FigureTabs
from gpc_dtwin.ui.scrolling import ResponsiveScrollArea
from gpc_dtwin.ui.widgets import SectionHeader


@pytest.mark.gui
def test_main_window_loads_with_unified_data_workspace(qtbot, tmp_path):
    settings = QSettings(ORGANIZATION_NAME, SETTINGS_APPLICATION)
    settings.clear()
    context = ApplicationContext(database_path=tmp_path / "gui.sqlite3")
    context.bootstrap()
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.resize(1080, 720)
    window.show()
    assert window.stack.count() == 10
    assert all(
        not page.findChildren(
            SectionHeader,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        )
        for page in window.pages
    )
    assert window.windowTitle().startswith("GPC-DTwin v1.2.6")
    assert len(window.page_containers) == 10
    assert all(isinstance(item, ResponsiveScrollArea) for item in window.page_containers)
    assert all(
        item.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        and item.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        for item in window.page_containers
    )
    style_buttons = window.findChildren(QToolButton, "ChartStyleButton")
    assert len(style_buttons) >= 10
    assert all(button.toolTip() == "Chart appearance" for button in style_buttons)
    figure_tab_hosts = window.findChildren(FigureTabs)
    assert figure_tab_hosts
    data_workspace = window.pages[1]
    assert data_workspace.tabs.count() == 4
    assert [
        data_workspace.tabs.tabText(index)
        for index in range(data_workspace.tabs.count())
    ] == [
        "Data Explorer",
        "Quality Check",
        "Visual Analysis",
        "Statistical Analysis",
    ]
    assert len(window.nav_buttons) == 10
    assert all(
        button.label not in {"Quality Check", "Visual Analytics", "Statistical Analysis"}
        for button in window.nav_buttons
    )
    digital_page = window.pages[3]
    assert digital_page.map_figure_tabs.square_display is True
    assert digital_page.map_figure_tabs.natural_square_side == 720
    assert all(host.tabs.isMovable() for host in figure_tab_hosts)
    assert all(not host.tabs.tabBar().expanding() for host in figure_tab_hosts)
    figure_actions = window.findChildren(QToolButton, "FigureActionButton")
    assert len(figure_actions) >= len(figure_tab_hosts) * 3
    window.resize(1024, 720)
    qtbot.wait(20)
    assert window.sidebar.width() == 82
    window.resize(1480, 900)
    qtbot.wait(20)
    assert window.sidebar.width() == 276
    window.prepare_shutdown()
    assert window.chart_style_manager._shutting_down is True
