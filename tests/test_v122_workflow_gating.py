from pathlib import Path


def test_feature_influence_table_and_chart_are_separate_tabs():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/gpc_dtwin/ui/pages/modeling_page.py").read_text(encoding="utf-8")
    assert '"Feature influence table"' in source
    assert '"Feature influence chart"' in source
    assert 'self.result_tabs.addTab(influence_table_widget, "Feature influence table")' in source
    assert 'self.result_tabs.addTab(influence_chart_widget, "Feature influence chart")' in source


def test_digital_twin_inherits_validated_prediction_configuration():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/gpc_dtwin/ui/pages/digital_twin_page.py").read_text(encoding="utf-8")
    assert "def _sync_from_prediction_ranking" in source
    assert "ranking = self.context.model_comparison" in source
    assert 'metadata.get("response", ranking.response)' in source
    assert 'getattr(ranking, "predictors", ())' in source
    assert 'metadata.get("include_review_records", False)' in source
    assert "self.response_combo.setEnabled(False)" in source
    assert "self.predictor_list.setEnabled(False)" in source
    assert "self.include_review.setEnabled(False)" in source


def test_main_navigation_enforces_prediction_twin_3d_prerequisites():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/gpc_dtwin/ui/main_window.py").read_text(encoding="utf-8")
    assert "def _page_is_available" in source
    assert "index == 3 and self.context.model_comparison is None" in source
    assert "index == 4 and self.context.active_twin_artifact is None" in source
    assert "self.context.model_comparison_changed.connect(self._update_workflow_access)" in source
    assert "self.context.active_twin_changed.connect(self._update_workflow_access)" in source


def test_dependent_tabs_are_disabled_until_upstream_artifact_exists():
    root = Path(__file__).resolve().parents[1]
    modeling = (root / "src/gpc_dtwin/ui/pages/modeling_page.py").read_text(encoding="utf-8")
    twin = (root / "src/gpc_dtwin/ui/pages/digital_twin_page.py").read_text(encoding="utf-8")
    assert "self.tabs.setTabEnabled(1, has_model)" in modeling
    assert "self.tabs.setTabEnabled(1, has_twin)" in twin
    assert "self.tabs.setTabEnabled(2, has_twin)" in twin


def test_new_prediction_ranking_invalidates_previous_active_twin():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/gpc_dtwin/context.py").read_text(encoding="utf-8")
    assert "had_twin = self.active_twin_artifact is not None" in source
    assert "self.active_twin_artifact = None" in source
    assert "if had_twin:" in source
    assert "self.active_twin_changed.emit()" in source
