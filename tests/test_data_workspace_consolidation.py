from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "gpc_dtwin" / "ui" / "main_window.py"
WORKSPACE = ROOT / "src" / "gpc_dtwin" / "ui" / "pages" / "data_workspace_page.py"


def test_main_navigation_exposes_one_data_workspace():
    source = MAIN.read_text(encoding="utf-8")
    assert '("D", "Data Explorer")' in source
    assert '("Q", "Quality Check")' not in source
    assert '("V", "Visual Analytics")' not in source
    assert '("S", "Statistical Analysis")' not in source
    assert "DataWorkspacePage(context)" in source


def test_data_workspace_contains_four_requested_tabs():
    source = WORKSPACE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "DataWorkspacePage"
        for node in tree.body
    )
    for label in (
        "Data Explorer",
        "Quality Check",
        "Visual Analysis",
        "Statistical Analysis",
    ):
        assert f'"{label}"' in source
