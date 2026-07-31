from __future__ import annotations

from pathlib import Path

from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.optimization_service import (
    ObjectiveDefinition,
    OptimizationService,
    VariableDefinition,
)


def test_response_specific_blank_predictor_is_adapted():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = OptimizationService()
    variables = [
        VariableDefinition("fa_percent_numeric", 0.0, 90.0),
        VariableDefinition("ggbs_percent_numeric", 0.0, 90.0),
        VariableDefinition("sf_percent_numeric", 9.5, 10.5),
        VariableDefinition("aas_b_ratio", 0.40, 0.50),
    ]
    result = service.optimize(
        dataframe=dataframe,
        objectives=[
            ObjectiveDefinition("compressive_strength_mpa", "Maximize", 1.0),
            ObjectiveDefinition("flexural_strength_mpa", "Maximize", 0.8),
        ],
        constraints=[],
        variables=variables,
        predictors=[
            "fa_percent_numeric",
            "ggbs_percent_numeric",
            "sf_percent_numeric",
            "aas_b_ratio",
        ],
        method="Forest Ensemble",
        population_size=16,
        generations=1,
        uncertainty_weight=0.25,
        binder_closure=True,
        include_review_records=False,
        seed=17,
    )
    flexural = result.surrogate_summary.loc[
        result.surrogate_summary["response"] == "flexural_strength_mpa"
    ].iloc[0]
    assert "aas_b_ratio" in flexural["dropped_predictors"]
    assert "fa_percent_numeric" in flexural["used_predictors"]
    assert not result.pareto_solutions.empty


def test_tab_hierarchy_has_no_full_width_rule():
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "gpc_dtwin"
        / "ui"
        / "theme.py"
    ).read_text(encoding="utf-8")
    assert "QTabWidget {{ border: 0; background: transparent; }}" in source
    assert "border-top: 0;" in source
    assert "QTabBar {{ border: 0; background: transparent; }}" in source
    assert "QTabBar {{ border: 0; border-bottom:" not in source


def test_digital_twin_response_map_uses_square_scroll_host():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin" / "ui"
    page = (root / "pages" / "digital_twin_page.py").read_text(encoding="utf-8")
    tabs = (root / "figure_tabs.py").read_text(encoding="utf-8")
    assert "square_display=True" in page
    assert "natural_square_side=720" in page
    assert "scroll.setWidgetResizable(not self.square_display)" in tabs
    assert "canvas.setFixedSize(side, side)" in tabs
    assert "ScrollBarAsNeeded" in tabs


def test_native_shutdown_and_software_rendering_guards_are_present():
    root = Path(__file__).resolve().parents[1]
    app = (root / "src" / "gpc_dtwin" / "app.py").read_text(encoding="utf-8")
    manager = (
        root / "src" / "gpc_dtwin" / "ui" / "chart_style_dialog.py"
    ).read_text(encoding="utf-8")
    window = (
        root / "src" / "gpc_dtwin" / "ui" / "main_window.py"
    ).read_text(encoding="utf-8")
    runner = (root / "scripts" / "run.ps1").read_text(encoding="utf-8")
    assert 'os.environ.setdefault("QT_OPENGL", "software")' in app
    assert "app.aboutToQuit.connect(window.prepare_shutdown)" in app
    assert "QTimer(self)" in manager
    assert "application.installEventFilter" not in manager
    assert "def shutdown(self)" in manager
    assert "self.prepare_shutdown()" in window
    assert '$env:QT_OPENGL = "software"' in runner
    assert "-X faulthandler" in runner
    assert "-1073741819" in runner
    assert "3221225477" in runner


def test_qt_wrapper_and_runtime_are_pinned_to_the_same_release():
    root = Path(__file__).resolve().parents[1]
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    for text in (project, requirements):
        assert "PyQt6==6.11.0" in text
        assert "PyQt6-Qt6==6.11.0" in text


def test_setup_uses_the_pinned_release_stack_and_qt_probe():
    root = Path(__file__).resolve().parents[1]
    lock = (root / "requirements-lock.txt").read_text(encoding="utf-8")
    setup = (root / "scripts" / "setup.ps1").read_text(encoding="utf-8")
    assert "PyQt6==6.11.0" in lock
    assert "PyQt6-Qt6==6.11.0" in lock
    assert "pandas==3.0.5" in lock
    assert "-r ./requirements-lock.txt" in setup
    assert "QT_VERSION_STR == qVersion()" in setup
