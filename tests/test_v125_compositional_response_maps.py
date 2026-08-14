from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

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


def _full_binder_twin():
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


def test_reference_data_block_two_binder_surface_when_composition_has_only_one_dof():
    _, artifact = _full_binder_twin()
    assert DigitalTwinService.binder_composition_rank(artifact) == 1
    supported, message = DigitalTwinService.response_axis_pair_support(
        artifact, "sf_percent_numeric", "fa_percent_numeric"
    )
    assert supported is False
    assert "one independent binder-composition direction" in message
    with pytest.raises(ValueError, match="dominated by extrapolation"):
        DigitalTwinService.response_map(
            artifact,
            "sf_percent_numeric",
            "fa_percent_numeric",
            resolution=15,
            x_range=(5.0, 15.0),
            y_range=(0.0, 100.0),
        )


def _two_dof_binder_twin():
    compositions = [
        (10, 80, 10), (20, 70, 10), (30, 60, 10), (40, 50, 10),
        (10, 70, 20), (20, 60, 20), (30, 50, 20), (40, 40, 20),
        (10, 60, 30), (20, 50, 30), (30, 40, 30), (40, 30, 30),
    ]
    frame = pd.DataFrame({
        "mix_id": [f"S{i+1}" for i in range(len(compositions))],
        "fa_percent_numeric": [row[0] for row in compositions],
        "ggbs_percent_numeric": [row[1] for row in compositions],
        "sf_percent_numeric": [row[2] for row in compositions],
    })
    frame["compressive_strength_mpa"] = (
        0.22 * frame["fa_percent_numeric"]
        + 0.48 * frame["ggbs_percent_numeric"]
        + 0.35 * frame["sf_percent_numeric"]
    )
    result = DigitalTwinService().build_twin(
        frame,
        "compressive_strength_mpa",
        ["fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"],
        method="Ridge Regression",
        include_review_records=True,
    )
    return frame, result.artifact


def test_two_binder_axes_work_when_future_data_supply_two_composition_dof():
    _, artifact = _two_dof_binder_twin()
    assert DigitalTwinService.binder_composition_rank(artifact) == 2
    surface = DigitalTwinService.response_map(
        artifact,
        "sf_percent_numeric",
        "fa_percent_numeric",
        resolution=15,
        x_range=(5.0, 35.0),
        y_range=(0.0, 100.0),
    )
    valid = surface["composition_valid"].astype(bool)
    invalid = ~valid
    assert surface.attrs["binder_closure_enabled"] is True
    assert surface.attrs["derived_binder"] == "ggbs_percent_numeric"
    assert invalid.any()
    total = (
        surface.loc[valid, "fa_percent_numeric"]
        + surface.loc[valid, "ggbs_percent_numeric"]
        + surface.loc[valid, "sf_percent_numeric"]
    )
    assert np.allclose(total.to_numpy(dtype=float), 100.0)
    assert surface.loc[invalid, "predicted_mean"].isna().all()


def test_one_binder_axis_uses_selected_balance_binder_and_holds_third_at_default():
    _, artifact = _full_binder_twin()
    defaults = artifact["metadata"]["input_defaults"]
    surface = DigitalTwinService.response_map(
        artifact,
        "sf_percent_numeric",
        "mechanical_test_age_days",
        resolution=15,
        x_range=(5.0, 15.0),
        y_range=(7.0, 28.0),
        balance_field="ggbs_percent_numeric",
    )
    assert surface.attrs["binder_closure_mode"] == "one_binder_axis"
    assert surface.attrs["balance_binder"] == "ggbs_percent_numeric"
    assert surface.attrs["fixed_binder"] == "fa_percent_numeric"
    assert np.allclose(
        surface["fa_percent_numeric"].to_numpy(dtype=float),
        float(defaults["fa_percent_numeric"]),
    )
    valid = surface["composition_valid"].astype(bool)
    total = (
        surface.loc[valid, "fa_percent_numeric"]
        + surface.loc[valid, "ggbs_percent_numeric"]
        + surface.loc[valid, "sf_percent_numeric"]
    )
    assert np.allclose(total.to_numpy(dtype=float), 100.0)


def test_default_balance_binder_is_deterministic_and_exposed_by_plan():
    _, artifact = _full_binder_twin()
    balance = DigitalTwinService.default_balance_binder(
        artifact, "sf_percent_numeric", "mechanical_test_age_days"
    )
    assert balance in {"fa_percent_numeric", "ggbs_percent_numeric"}
    plan = DigitalTwinService.composition_plan(
        artifact, "sf_percent_numeric", "mechanical_test_age_days", balance
    )
    assert plan["enabled"] is True
    assert plan["balance_binder"] == balance
    assert "100" in plan["rule"]


def test_one_dimensional_binder_response_curve_preserves_closure():
    _, artifact = _full_binder_twin()
    curve = DigitalTwinService.response_curve(
        artifact,
        "sf_percent_numeric",
        resolution=20,
        value_range=(5.0, 15.0),
        balance_field="ggbs_percent_numeric",
    )
    valid = curve["composition_valid"].astype(bool)
    total = (
        curve.loc[valid, "fa_percent_numeric"]
        + curve.loc[valid, "ggbs_percent_numeric"]
        + curve.loc[valid, "sf_percent_numeric"]
    )
    assert np.allclose(total.to_numpy(dtype=float), 100.0)


def test_3d_surface_uses_same_composition_aware_response_grid_for_supported_future_data():
    dataframe, artifact = _two_dof_binder_twin()
    result = Visualization3DService().build_surface(
        artifact,
        dataframe,
        "sf_percent_numeric",
        "fa_percent_numeric",
        resolution=15,
        x_range=(5.0, 35.0),
        y_range=(0.0, 100.0),
    )
    assert result.surface.attrs["derived_binder"] == "ggbs_percent_numeric"
    assert result.summary["invalid_composition_points"] > 0
    assert result.summary["valid_map_nodes"] < result.summary["total_map_nodes"]
    figure = Visualization3DService().surface_figure(result)
    assert figure.axes


def test_response_view_uis_expose_balance_binder_and_nonblocking_flat_range_guard():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    twin_page = (root / "src/gpc_dtwin/ui/pages/digital_twin_page.py").read_text(encoding="utf-8")
    explorer_page = (root / "src/gpc_dtwin/ui/pages/visualization_3d_page.py").read_text(encoding="utf-8")

    assert 'QLabel("Balance binder")' in twin_page
    assert "self.map_generate_button.setEnabled" in twin_page
    assert "self.map_range_warning.setText" in twin_page
    assert 'form.addRow("Balance binder", self.surface_balance_combo)' in explorer_page
    assert "self.surface_build_button.setEnabled" in explorer_page
    assert "self.surface_range_warning.setText" in explorer_page
