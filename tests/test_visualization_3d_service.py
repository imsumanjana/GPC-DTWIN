from pathlib import Path

import numpy as np

from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.modeling_service import ModelingService
from gpc_dtwin.services.visualization_3d_service import Visualization3DService


def _surface_result():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    predictors = [
        "fa_percent_numeric", "ggbs_percent_numeric", "aas_b_ratio",
        "mechanical_test_age_days", "curing_regime",
    ]
    ranking = ModelingService().compare_models(
        dataframe, "compressive_strength_mpa", predictors,
        include_review_records=True,
    )
    twin = DigitalTwinService().build_twin(
        dataframe, "compressive_strength_mpa", predictors,
        include_review_records=True, ranking=ranking,
    )
    service = Visualization3DService()
    result = service.build_surface(
        twin.artifact,
        dataframe,
        x_field="ggbs_percent_numeric",
        y_field="aas_b_ratio",
        resolution=18,
        mode="Estimated response",
    )
    return dataframe, service, twin, result


def test_response_surface_uses_active_twin_without_retraining():
    _, _, twin, result = _surface_result()
    assert result.artifact is twin.artifact
    assert len(result.surface) == 18 * 18
    assert result.response == "compressive_strength_mpa"
    assert result.summary["map_nodes"] == 18 * 18
    assert result.summary["minimum_estimate"] <= result.summary["maximum_estimate"]
    assert not result.overlay.empty


def test_response_surface_figures_cover_all_modes():
    dataframe, service, twin, _ = _surface_result()
    for mode in service.surface_modes():
        result = service.build_surface(
            twin.artifact, dataframe, "ggbs_percent_numeric", "aas_b_ratio",
            resolution=15, mode=mode,
        )
        figure = service.surface_figure(result)
        assert len(figure.axes) >= 2


def test_physics_specimen_fields_are_theory_based_and_deterministic():
    dataframe, service, twin, _ = _surface_result()
    first = service.specimen_field(
        dataframe, mix_id="M3", analysis="Flexural beam", field_type="Failure index",
        resolution=9, load_ratio_percent=75.0, twin_artifact=twin.artifact,
    )
    second = service.specimen_field(
        dataframe, mix_id="M3", analysis="Flexural beam", field_type="Failure index",
        resolution=9, load_ratio_percent=75.0, twin_artifact=twin.artifact,
    )
    assert first.geometry == "beam"
    assert "Theory calculated" in first.field_source
    assert np.allclose(first.field["field_value"], second.field["field_value"])
    assert first.summary["maximum"] <= 0.7500001
    assert first.summary["minimum"] >= 0.0
    figure = service.specimen_figure(first, cutaway_mode="Center slice")
    assert len(figure.axes) >= 2


def test_acid_field_is_diffusion_based_and_calibrated_to_strength_loss():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = Visualization3DService()
    result = service.specimen_field(
        dataframe, mix_id="M3", analysis="Acid degradation cube",
        field_type="Strength retention", resolution=11, acid_type="H2SO4",
        exposure_days=28.0, effective_diffusivity_mm2_day=1.0,
    )
    assert result.geometry == "cube"
    assert "Diffusion theory" in result.field_source
    retention = result.field["local_strength_retention"].mean()
    expected = 44.71 / 47.30
    assert abs(retention - expected) < 1e-4
    assert result.field["acid_penetration_fraction"].between(0, 1).all()


def test_3d_data_exports_to_csv(tmp_path: Path):
    dataframe, service, twin, result = _surface_result()
    surface_path = service.export_dataframe(result.surface, tmp_path / "surface.csv")
    assert surface_path.exists()
    specimen = service.specimen_field(
        dataframe, mix_id="M2", analysis="Compression cube", field_type="Stress utilisation",
        resolution=9, twin_artifact=twin.artifact,
    )
    specimen_path = service.export_dataframe(specimen.field, tmp_path / "specimen.csv")
    assert specimen_path.exists()
