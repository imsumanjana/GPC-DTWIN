import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt

from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.ui.main_window import MainWindow
from gpc_dtwin.ui.scrolling import ResponsiveScrollArea


@pytest.mark.gui
def test_main_window_loads_with_twelve_scrollable_pages(qtbot, tmp_path):
    context = ApplicationContext(database_path=tmp_path / "gui.sqlite3")
    context.bootstrap()
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.resize(1080, 720)
    window.show()
    assert window.stack.count() == 12
    assert window.windowTitle().startswith("GPC-DTwin v0.8")
    assert len(window.page_containers) == 12
    assert all(isinstance(item, ResponsiveScrollArea) for item in window.page_containers)
    assert all(
        item.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        and item.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        for item in window.page_containers
    )
