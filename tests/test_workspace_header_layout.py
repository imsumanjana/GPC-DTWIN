from __future__ import annotations

import ast
from pathlib import Path


PAGE_FILES = (
    "overview_page.py",
    "database_page.py",
    "audit_page.py",
    "analytics_page.py",
    "statistics_page.py",
    "modeling_page.py",
    "digital_twin_page.py",
    "visualization_3d_page.py",
    "ndt_durability_page.py",
    "optimization_page.py",
    "active_learning_page.py",
    "reporting_page.py",
    "settings_page.py",
)


def _is_direct_section_header_add(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    call = statement.value
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "addWidget":
        return False
    if not call.args or not isinstance(call.args[0], ast.Call):
        return False
    nested = call.args[0]
    return isinstance(nested.func, ast.Name) and nested.func.id == "SectionHeader"


def test_workspace_pages_do_not_repeat_the_main_header():
    pages = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin" / "ui" / "pages"

    for filename in PAGE_FILES:
        tree = ast.parse((pages / filename).read_text(encoding="utf-8"))
        page_class = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        initializer = next(
            node
            for node in page_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        assert not any(
            _is_direct_section_header_add(statement)
            for statement in initializer.body
        ), filename


def test_tab_style_places_the_rule_below_not_above_the_tabs():
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "gpc_dtwin"
        / "ui"
        / "theme.py"
    ).read_text(encoding="utf-8")

    assert "QTabWidget {{ border: 0; background: transparent; }}" in source
    assert "border-top: 0;" in source
    assert "QTabBar {{ border: 0; border-bottom: 1px solid" in source
