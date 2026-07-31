from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tab_bars_have_no_full_width_separator_line():
    source = (ROOT / "src/gpc_dtwin/ui/theme.py").read_text(encoding="utf-8")
    assert "QTabBar {{ border: 0; background: transparent; }}" in source
    assert "QTabBar {{ border: 0; border-bottom:" not in source
    assert "QTabBar::tab:selected" in source
    assert "border-bottom: 2px solid" in source


def test_compact_toolbar_is_single_row_and_horizontally_scrollable():
    source = (ROOT / "src/gpc_dtwin/ui/widgets.py").read_text(encoding="utf-8")
    assert "class CompactToolbar(QScrollArea)" in source
    assert "ScrollBarAsNeeded" in source
    assert "ScrollBarAlwaysOff" in source
    assert "QHBoxLayout(self.content)" in source
    assert "CompactToolbarButton" in source


def test_major_analysis_pages_use_compact_icon_toolbars():
    pages = ROOT / "src/gpc_dtwin/ui/pages"
    names = (
        "modeling_page.py",
        "digital_twin_page.py",
        "visualization_3d_page.py",
        "ndt_durability_page.py",
        "optimization_page.py",
        "active_learning_page.py",
    )
    for name in names:
        source = (pages / name).read_text(encoding="utf-8")
        assert "CompactToolbar" in source, name
        assert "QStyle.StandardPixmap" in source, name
