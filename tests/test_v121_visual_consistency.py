from pathlib import Path

import numpy as np

from gpc_dtwin.columns import quantity_label
from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.modeling_service import ModelingService
from gpc_dtwin.services.visualization_3d_service import Visualization3DService


def test_response_quantity_labels_include_engineering_units():
    assert quantity_label("Observed", "compressive_strength_mpa") == "Observed (MPa)"
    assert quantity_label("Prediction interval width", "slump_mm") == "Prediction interval width (mm)"
    assert quantity_label("Prediction error", "upv_m_s") == "Prediction error (m/s)"


def test_specimen_colour_scale_is_locked_across_mix_changes():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = Visualization3DService()
    m1 = service.specimen_field(
        dataframe, mix_id="M1", analysis="Compression cube", field_type="Applied stress",
        resolution=7, load_ratio_percent=75.0,
    )
    m2 = service.specimen_field(
        dataframe, mix_id="M2", analysis="Compression cube", field_type="Applied stress",
        resolution=7, load_ratio_percent=75.0,
    )
    assert m1.color_min == m2.color_min == 0.0
    assert np.isclose(m1.color_max, m2.color_max)
    assert m1.color_max > max(m1.summary["maximum"], m2.summary["maximum"])
    assert "compatible mixes" in m1.color_scale_basis
    assert {"color_scale_min", "color_scale_max", "color_scale_basis"}.issubset(m1.field.columns)


def test_twin_response_maps_carry_fixed_colour_scales():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    predictors = [
        "fa_percent_numeric", "ggbs_percent_numeric", "aas_b_ratio",
        "mechanical_test_age_days", "curing_regime",
    ]
    ranking = ModelingService().compare_models(
        dataframe, "compressive_strength_mpa", predictors, include_review_records=True
    )
    twin = DigitalTwinService().build_twin(
        dataframe, "compressive_strength_mpa", predictors,
        include_review_records=True, ranking=ranking,
    )
    first = DigitalTwinService.response_map(
        twin.artifact, "ggbs_percent_numeric", "aas_b_ratio", resolution=15
    )
    scales = first.attrs["figure_color_scales"]
    assert scales == twin.artifact["metadata"]["figure_color_scales"]
    assert scales["estimated_response"] == twin.artifact["metadata"]["response_training_range"]
    assert scales["relative_uncertainty"][0] == 0.0
    assert scales["interval_width"][0] == 0.0


def test_model_and_twin_tables_are_peer_tabs_to_charts():
    root = Path(__file__).resolve().parents[1]
    modeling = (root / "src/gpc_dtwin/ui/pages/modeling_page.py").read_text(encoding="utf-8")
    twin = (root / "src/gpc_dtwin/ui/pages/digital_twin_page.py").read_text(encoding="utf-8")
    assert '"Comparison table"' in modeling
    assert '"Ranking chart"' in modeling
    assert '"Feature influence table"' in modeling
    assert '"Feature influence chart"' in modeling
    assert '"Calibration table"' in twin
    assert '"Response charts"' in twin
