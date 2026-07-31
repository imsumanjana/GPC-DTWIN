import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings, Qt

from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.metadata import ORGANIZATION_NAME, SETTINGS_APPLICATION
from gpc_dtwin.ui.main_window import MainWindow
from gpc_dtwin.ui.scrolling import ResponsiveScrollArea


@pytest.mark.gui
def test_main_window_loads_with_thirteen_scrollable_pages(qtbot, tmp_path):
    settings = QSettings(ORGANIZATION_NAME, SETTINGS_APPLICATION)
    settings.clear()
    context = ApplicationContext(database_path=tmp_path / "gui.sqlite3")
    context.bootstrap()
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.resize(1080, 720)
    window.show()
    assert window.stack.count() == 13
    assert window.windowTitle().startswith("GPC-DTwin v1.0")
    assert len(window.page_containers) == 13
    assert all(isinstance(item, ResponsiveScrollArea) for item in window.page_containers)
    assert all(
        item.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        and item.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        for item in window.page_containers
    )
    window.resize(1024, 720)
    qtbot.wait(20)
    assert window.sidebar.width() == 82
    window.resize(1480, 900)
    qtbot.wait(20)
    assert window.sidebar.width() == 276
