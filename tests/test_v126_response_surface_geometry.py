from __future__ import annotations

from pathlib import Path

from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.modeling_service import ModelingService
from gpc_dtwin.services.visualization_3d_service import Visualization3DService


PREDICTORS = [
    "fa_percent_numeric",
    "ggbs_percent_numeric",
    "sf_percent_numeric",
    "aas_b_ratio",
    "mechanical_test_age_days",
    "curing_regime",
]


def _artifact():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    ranking = ModelingService().compare_models(
        dataframe,
        "compressive_strength_mpa",
        PREDICTORS,
        algorithms=["Ridge Regression"],
        include_review_records=True,
    )
    twin = DigitalTwinService().build_twin(
        dataframe,
        "compressive_strength_mpa",
        PREDICTORS,
        method="Ridge Regression",
        include_review_records=True,
        ranking=ranking,
    )
    return dataframe, twin.artifact


def test_reference_twin_prefers_rectangular_supported_surface_axes():
    _, artifact = _artifact()
    x_field, y_field = DigitalTwinService.preferred_response_axes(artifact)
    assert x_field == "ggbs_percent_numeric"
    assert y_field == "aas_b_ratio"
    supported, _ = DigitalTwinService.response_axis_pair_support(artifact, x_field, y_field)
    assert supported is True


def test_reference_twin_records_one_binder_composition_degree_of_freedom():
    _, artifact = _artifact()
    metadata = artifact["metadata"]
    assert metadata["binder_composition_rank"] == 1
    assert metadata["binder_composition_unique_points"] >= 10
    assert metadata["numeric_training_unique_counts"]["sf_percent_numeric"] == 1


def test_preferred_surface_has_no_invalid_composition_triangle():
    dataframe, artifact = _artifact()
    x_field, y_field = DigitalTwinService.preferred_response_axes(artifact)
    result = Visualization3DService().build_surface(
        artifact, dataframe, x_field, y_field, resolution=18
    )
    assert result.summary["invalid_composition_points"] == 0
    assert result.summary["valid_map_nodes"] == result.summary["total_map_nodes"]
    assert result.surface.attrs["fixed_binder"] == "sf_percent_numeric"
    assert "held at 10%" in result.surface.attrs["binder_closure_rule"]


def test_observed_overlay_is_filtered_to_same_surface_cross_section():
    dataframe, artifact = _artifact()
    service = Visualization3DService()
    result = service.build_surface(
        artifact, dataframe, "ggbs_percent_numeric", "aas_b_ratio", resolution=18
    )
    # The full response dataset contains records at multiple ages/conditions. The
    # overlay must be a subset matching the defaults used by the surface.
    full_response_rows = dataframe["compressive_strength_mpa"].notna().sum()
    assert 0 < len(result.overlay) < full_response_rows


def test_ui_uses_preferred_axes_and_reports_pair_support_error():
    root = Path(__file__).resolve().parents[1]
    twin_page = (root / "src/gpc_dtwin/ui/pages/digital_twin_page.py").read_text(encoding="utf-8")
    explorer_page = (root / "src/gpc_dtwin/ui/pages/visualization_3d_page.py").read_text(encoding="utf-8")
    assert "preferred_response_axes" in twin_page
    assert "composition_error" in twin_page
    assert "preferred_response_axes" in explorer_page
    assert "composition_error" in explorer_page
