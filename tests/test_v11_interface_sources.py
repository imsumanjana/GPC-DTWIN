from __future__ import annotations

from pathlib import Path


def test_v11_chart_manager_and_presets_are_icon_driven():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    dialog = (root / "ui" / "chart_style_dialog.py").read_text(encoding="utf-8")
    presets = (root / "chart_presets.py").read_text(encoding="utf-8")
    main = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'setText("🎨")' in dialog
    assert '"Apply to workspace"' in dialog
    assert '"Apply to application"' in dialog
    assert '"Reset saved styles"' in dialog
    assert "CUSTOM_PRESETS_KEY" in dialog
    assert "Publication monochrome" in presets
    assert "Presentation" in presets
    assert "ChartStyleOverlayManager" in main
    assert "Chart appearance" not in main  # no chart-style menu clutter


def test_v11_figure_tabs_are_reorderable_expandable_and_exportable():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    source = (root / "ui" / "figure_tabs.py").read_text(encoding="utf-8")
    assert "setMovable(True)" in source
    assert "setExpanding(False)" in source
    assert "expand_current" in source
    assert "export_current" in source
    assert "export_all" in source
    assert "save_square_figure" in source


def test_v11_export_preview_uses_fixed_export_engine():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    preview = (root / "ui" / "export_preview_dialog.py").read_text(encoding="utf-8")
    export = (root / "figure_export.py").read_text(encoding="utf-8")
    assert "ExportPreviewDialog" in preview
    assert "save_square_figure" in preview
    assert "analyze_export_layout" in export
    assert "EXPORT_DPI = 600" in export
    assert "EXPORT_SIZE_INCHES = 6.0" in export
