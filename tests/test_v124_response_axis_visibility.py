from pathlib import Path


def test_response_views_expose_flat_numeric_predictors_and_manual_ranges():
    root = Path(__file__).resolve().parents[1]
    twin_service = (root / "src/gpc_dtwin/services/digital_twin_service.py").read_text(encoding="utf-8")
    twin_page = (root / "src/gpc_dtwin/ui/pages/digital_twin_page.py").read_text(encoding="utf-8")
    explorer_page = (root / "src/gpc_dtwin/ui/pages/visualization_3d_page.py").read_text(encoding="utf-8")

    assert "def fitted_axis_range" in twin_service
    assert "if np.isfinite(low) and np.isfinite(high):" in twin_service
    assert "explicit exploration minimum and maximum" in twin_service

    assert "self.map_x_min" in twin_page
    assert "self.map_x_max" in twin_page
    assert "self.map_y_min" in twin_page
    assert "self.map_y_max" in twin_page
    assert "including SF" in twin_page

    assert "self.surface_x_min_spin" in explorer_page
    assert "self.surface_x_max_spin" in explorer_page
    assert "self.surface_y_min_spin" in explorer_page
    assert "self.surface_y_max_spin" in explorer_page
    assert "SF = 10% remain selectable" in explorer_page
