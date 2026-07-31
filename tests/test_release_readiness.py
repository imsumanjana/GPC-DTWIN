from __future__ import annotations

from pathlib import Path

from gpc_dtwin import __version__
from gpc_dtwin.health import run_health_check
from gpc_dtwin.paths import REFERENCE_DATASET


def test_release_version_and_local_health(tmp_path, monkeypatch):
    assert __version__ == "1.0.1"
    items = run_health_check(tmp_path / "health.sqlite3")
    assert all(item.passed for item in items), items


def test_interface_source_uses_scrollable_workspaces_and_no_direct_figure_export():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    main = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "scrollable_page(page" in main
    assert "toggle_sidebar" in main
    assert "resizeEvent" in main
    assert "QScrollArea" in main
    assert "save_square_figure" not in main

    direct = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if ".savefig(" in text and path.name != "figure_export.py":
            direct.append(str(path.relative_to(root)))
    assert direct == []
