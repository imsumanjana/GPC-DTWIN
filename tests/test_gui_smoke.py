import pytest

pytest.importorskip("PyQt6")

from gpc_dtwin.context import ApplicationContext
from gpc_dtwin.ui.main_window import MainWindow


@pytest.mark.gui
def test_main_window_loads_with_eight_pages(qtbot, tmp_path):
    context = ApplicationContext(database_path=tmp_path / "gui.sqlite3")
    context.bootstrap()
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()
    assert window.stack.count() == 8
    assert window.windowTitle().startswith("GPC-DTwin v0.4")
