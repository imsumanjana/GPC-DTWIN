from dataclasses import replace
from pathlib import Path

import numpy as np

from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.visualization_3d_service import Visualization3DService


def _surface_result():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = Visualization3DService()
    result = service.build_surface(
        dataframe,
        response="compressive_strength_mpa",
        x_field="ggbs_percent_numeric",
        y_field="aas_b_ratio",
        method="Forest Ensemble",
        confidence_percent=95.0,
        resolution=18,
        include_review_records=True,
        mode="Estimated response",
    )
    return dataframe, service, result


def test_response_surface_builds_with_overlay_and_summary():
    _, _, result = _surface_result()
    assert len(result.surface) == 18 * 18
    assert not result.overlay.empty
    assert result.summary["map_nodes"] == 18 * 18
    assert np.isfinite(result.summary["minimum_estimate"])
    assert np.isfinite(result.summary["maximum_estimate"])
    assert 0.0 <= result.summary["supported_area_percent"] <= 100.0


def test_response_surface_figures_cover_all_modes():
    _, service, result = _surface_result()
    for mode in service.surface_modes():
        mode_result = replace(result, mode=mode)
        figure = service.surface_figure(mode_result, show_overlay=False)
        assert any(getattr(axis, "name", "") == "3d" for axis in figure.axes)


def test_specimen_field_is_deterministic_and_bounded():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = Visualization3DService()
    first = service.specimen_field(
        dataframe,
        mix_id="M2",
        property_field="compressive_strength_mpa",
        resolution=9,
    )
    second = service.specimen_field(
        dataframe,
        mix_id="M2",
        property_field="compressive_strength_mpa",
        resolution=9,
    )
    assert len(first.field) == 9 ** 3
    assert np.allclose(first.field["estimated_value"], second.field["estimated_value"])
    assert first.field["normalized_state"].between(0.0, 1.0).all()
    assert first.source_records >= 1
    assert 0.25 <= first.uniformity_index <= 0.95
    assert first.summary["minimum"] <= first.summary["mean"] <= first.summary["maximum"]
    figure = service.specimen_figure(first, cutaway_mode="Octant cutaway")
    assert any(getattr(axis, "name", "") == "3d" for axis in figure.axes)


def test_3d_data_exports_to_csv(tmp_path: Path):
    dataframe, service, result = _surface_result()
    surface_path = service.export_dataframe(result.surface, tmp_path / "surface")
    assert surface_path.exists()
    assert surface_path.suffix == ".csv"

    field = service.specimen_field(
        dataframe,
        mix_id="M3",
        property_field="upv_m_s",
        resolution=8,
    )
    field_path = service.export_dataframe(field.field, tmp_path / "field.csv")
    assert field_path.exists()
