from __future__ import annotations

from pathlib import Path

from gpc_dtwin import __version__
from gpc_dtwin.health import run_health_check
from gpc_dtwin.paths import REFERENCE_DATASET


def test_release_version_and_local_health(tmp_path, monkeypatch):
    assert __version__ == "1.1.3"
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


def test_chart_appearance_and_response_map_release_sources():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    style_source = (root / "chart_style.py").read_text(encoding="utf-8")
    dialog_source = (root / "ui" / "chart_style_dialog.py").read_text(encoding="utf-8")
    theme_source = (root / "ui" / "theme.py").read_text(encoding="utf-8")
    twin_source = (root / "services" / "digital_twin_service.py").read_text(encoding="utf-8")
    twin_page = (root / "ui" / "pages" / "digital_twin_page.py").read_text(encoding="utf-8")

    assert 'font_family: str = "Times New Roman"' in style_source
    assert 'STYLE_SETTINGS_KEY = "charts/style_json"' in dialog_source
    assert 'setText("🎨")' in dialog_source
    assert "border-top: 0" in theme_source
    assert 'predictions.insert(0, "grid_row"' in twin_source
    assert 'predictions.insert(0, "grid_column"' in twin_source
    assert "map_axis_candidates" in twin_source
    assert "response_curve" in twin_source
    assert "FigureTabs" in twin_page


def test_v11_publication_graphics_release_sources():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    presets = (root / "chart_presets.py").read_text(encoding="utf-8")
    dialog = (root / "ui" / "chart_style_dialog.py").read_text(encoding="utf-8")
    tabs = (root / "ui" / "figure_tabs.py").read_text(encoding="utf-8")
    preview = (root / "ui" / "export_preview_dialog.py").read_text(encoding="utf-8")
    assert "Publication colour" in presets
    assert "CUSTOM_PRESETS_KEY" in dialog
    assert "APPLICATION_STYLE_KEY" in dialog
    assert "WORKSPACE_STYLE_PREFIX" in dialog
    assert "CHART_STYLE_PREFIX" in dialog
    assert "setMovable(True)" in tabs
    assert "setExpanding(False)" in tabs
    assert "ExportPreviewDialog" in preview
