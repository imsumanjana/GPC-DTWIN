"""Three-dimensional Digital-Twin response surfaces and physics-informed specimen views."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm
from matplotlib.figure import Figure

from gpc_dtwin.columns import (
    BINDER_PERCENT_COLUMNS, COLUMN_LABELS, MODEL_NUMERIC_PREDICTORS, quantity_label,
)
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.physics_spatial_service import (
    PhysicsSpatialService,
    SpecimenPhysicsResult,
)


SURFACE_MODES = (
    "Estimated response",
    "Relative uncertainty",
    "Prediction interval width",
    "Reliability landscape",
)

CUTAWAY_MODES = (
    "Full volume",
    "Front half",
    "Center slice",
    "Octant cutaway",
)

CAMERA_PRESETS = {
    "Isometric": (28.0, -52.0),
    "Front": (8.0, -90.0),
    "Side": (8.0, 0.0),
    "Top": (88.0, -90.0),
}


@dataclass
class Surface3DResult:
    artifact: dict[str, Any]
    surface: pd.DataFrame
    overlay: pd.DataFrame
    x_field: str
    y_field: str
    response: str
    mode: str
    summary: dict[str, float]


# Backward-compatible public name used by the UI/tests.
SpecimenFieldResult = SpecimenPhysicsResult


class Visualization3DService:
    """Visualize the active Digital Twin; never retrain an independent twin in this layer."""

    def __init__(self) -> None:
        self.twin_service = DigitalTwinService()
        self.physics_service = PhysicsSpatialService()

    @staticmethod
    def surface_modes() -> list[str]:
        return list(SURFACE_MODES)

    @staticmethod
    def cutaway_modes() -> list[str]:
        return list(CUTAWAY_MODES)

    @staticmethod
    def camera_presets() -> dict[str, tuple[float, float]]:
        return dict(CAMERA_PRESETS)

    def build_surface(
        self,
        artifact: dict[str, Any],
        dataframe: pd.DataFrame,
        x_field: str,
        y_field: str,
        resolution: int = 35,
        mode: str = "Estimated response",
        x_range: tuple[float, float] | None = None,
        y_range: tuple[float, float] | None = None,
        balance_field: str | None = None,
    ) -> Surface3DResult:
        if mode not in SURFACE_MODES:
            raise ValueError(f"Unsupported surface mode: {mode}")
        if artifact is None:
            raise ValueError("Build or load a Digital Twin before opening the 3D response surface.")
        self.twin_service._validate_artifact(artifact)
        if x_field == y_field:
            raise ValueError("Select different X and Y axes.")
        candidates = self.twin_service.map_axis_candidates(artifact)
        if x_field not in candidates or y_field not in candidates:
            raise ValueError("Both 3D axes must be numeric predictors of the active Digital Twin.")
        response = str(artifact["metadata"]["response"])
        surface = self.twin_service.response_map(
            artifact, x_field=x_field, y_field=y_field, resolution=resolution,
            x_range=x_range, y_range=y_range, balance_field=balance_field,
        )
        overlay = self._build_overlay(
            artifact, dataframe, response, x_field, y_field, mode, balance_field
        )
        return Surface3DResult(
            artifact=artifact,
            surface=surface,
            overlay=overlay,
            x_field=x_field,
            y_field=y_field,
            response=response,
            mode=mode,
            summary=self.surface_summary(surface),
        )

    def _build_overlay(
        self,
        artifact: dict[str, Any],
        dataframe: pd.DataFrame,
        response: str,
        x_field: str,
        y_field: str,
        mode: str,
        balance_field: str | None = None,
    ) -> pd.DataFrame:
        if not all(column in dataframe.columns for column in (x_field, y_field)):
            return pd.DataFrame()
        frame = dataframe.copy()
        frame[x_field] = pd.to_numeric(frame[x_field], errors="coerce")
        frame[y_field] = pd.to_numeric(frame[y_field], errors="coerce")
        frame = frame.dropna(subset=[x_field, y_field])
        if frame.empty:
            return pd.DataFrame()

        # A response surface is a cross-section through the active twin: all
        # predictors other than the plotted axes (and a closure-balancing
        # binder) are held at fitted defaults. Overlay only observations that
        # belong to that same cross-section. Plotting every response record can
        # place 7-day, 28-day, oven-cured, or otherwise different conditions on
        # one surface and falsely make the surface appear inconsistent.
        metadata = artifact["metadata"]
        predictors = list(metadata.get("predictors", []))
        defaults = metadata.get("input_defaults", {}) or {}
        numeric_ranges = metadata.get("numeric_training_ranges", {}) or {}
        try:
            plan = self.twin_service.composition_plan(
                artifact, x_field, y_field, balance_field
            )
        except ValueError:
            plan = {"enabled": False, "mode": "defaults"}

        free_fields = {x_field, y_field}
        if plan.get("enabled"):
            if plan.get("mode") == "two_binder_axes":
                free_fields.update(BINDER_PERCENT_COLUMNS)
            elif plan.get("mode") == "one_binder_axis":
                free_fields.update(plan.get("axis_binders", []))
                if plan.get("balance_binder"):
                    free_fields.add(str(plan["balance_binder"]))

        match = pd.Series(True, index=frame.index)
        for predictor in predictors:
            if predictor in free_fields or predictor not in frame.columns:
                continue
            default = defaults.get(predictor)
            if default is None:
                continue
            if predictor in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(frame[predictor], errors="coerce")
                try:
                    target = float(default)
                except (TypeError, ValueError):
                    continue
                limits = numeric_ranges.get(predictor, [target, target])
                try:
                    span = abs(float(limits[1]) - float(limits[0]))
                except (TypeError, ValueError, IndexError):
                    span = 0.0
                atol = max(span * 1e-6, 1e-9)
                match &= values.notna() & np.isclose(
                    values.to_numpy(dtype=float), target, atol=atol, rtol=1e-9
                )
            else:
                match &= frame[predictor].astype("string").eq(str(default)).fillna(False)
        frame = frame.loc[match].copy()
        if frame.empty:
            return pd.DataFrame()

        overlay = pd.DataFrame({
            x_field: frame[x_field].to_numpy(dtype=float),
            y_field: frame[y_field].to_numpy(dtype=float),
        })
        for column in ("record_id", "mix_id"):
            if column in frame.columns:
                overlay[column] = frame[column].astype(str).to_numpy()
        if mode == "Estimated response" and response in frame.columns:
            observed = pd.to_numeric(frame[response], errors="coerce")
            overlay["z_value"] = observed.to_numpy(dtype=float)
            overlay["z_source"] = "Observed"
        else:
            predictions = self.twin_service.predict_dataframe(artifact, frame)
            field = self._mode_field(mode)
            if field == "reliability_code":
                values = predictions["reliability_class"].map(
                    {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}
                )
            else:
                values = pd.to_numeric(predictions[field], errors="coerce")
            overlay["z_value"] = values.to_numpy(dtype=float)
            overlay["z_source"] = "Estimated"
        return overlay.dropna(subset=["z_value"]).reset_index(drop=True)

    @staticmethod
    def _mode_field(mode: str) -> str:
        return {
            "Estimated response": "predicted_mean",
            "Relative uncertainty": "normalized_uncertainty_percent",
            "Prediction interval width": "interval_width",
            "Reliability landscape": "reliability_code",
        }[mode]

    @staticmethod
    def _mode_label(mode: str, response: str, response_label: str) -> str:
        return {
            "Estimated response": response_label,
            "Relative uncertainty": "Relative uncertainty (%)",
            "Prediction interval width": quantity_label("Prediction interval width", response),
            "Reliability landscape": "Reliability class",
        }[mode]

    @staticmethod
    def surface_summary(surface: pd.DataFrame) -> dict[str, float]:
        mean = pd.to_numeric(surface["predicted_mean"], errors="coerce")
        uncertainty = pd.to_numeric(surface["normalized_uncertainty_percent"], errors="coerce")
        reliability = surface["reliability_class"].astype("string")
        if "composition_valid" in surface.columns:
            valid = surface["composition_valid"].fillna(False).astype(bool)
        else:
            valid = pd.Series(True, index=surface.index)
        valid_count = int(valid.sum())
        total_count = int(len(surface))
        supported = (reliability[valid].isin(["A", "B"]).mean() * 100.0) if valid_count else 0.0
        return {
            "minimum_estimate": float(mean[valid].min()),
            "maximum_estimate": float(mean[valid].max()),
            "mean_estimate": float(mean[valid].mean()),
            "mean_uncertainty_percent": float(uncertainty[valid].mean()),
            "supported_area_percent": float(supported),
            "map_nodes": float(valid_count),
            "valid_map_nodes": float(valid_count),
            "total_map_nodes": float(total_count),
            "invalid_composition_points": float(total_count - valid_count),
        }

    def surface_figure(
        self,
        result: Surface3DResult,
        show_overlay: bool = True,
        show_wireframe: bool = False,
        show_projection: bool = True,
        elevation: float = 28.0,
        azimuth: float = -52.0,
        colormap: str = "viridis",
    ) -> Figure:
        surface = result.surface
        x_values = np.sort(surface[result.x_field].unique())
        y_values = np.sort(surface[result.y_field].unique())
        shape = (len(y_values), len(x_values))
        grid_x, grid_y = np.meshgrid(x_values, y_values)
        mode_field = self._mode_field(result.mode)
        if mode_field == "reliability_code":
            values = surface["reliability_class"].map(
                {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}
            ).to_numpy(dtype=float)
        else:
            values = pd.to_numeric(surface[mode_field], errors="coerce").to_numpy(dtype=float)
        grid_z = values.reshape(shape)

        figure = Figure(figsize=(10.8, 7.2), constrained_layout=True)
        axis = figure.add_subplot(111, projection="3d")
        response_label = COLUMN_LABELS.get(result.response, result.response)
        value_label = self._mode_label(result.mode, result.response, response_label)
        scale_key = {
            "Estimated response": "estimated_response",
            "Relative uncertainty": "relative_uncertainty",
            "Prediction interval width": "interval_width",
        }.get(result.mode)
        if scale_key is not None:
            value_min, value_max = self.twin_service._fixed_color_limits(
                surface, scale_key, grid_z,
                include_zero=result.mode in {"Relative uncertainty", "Prediction interval width"},
            )
        else:
            value_min, value_max = float(np.nanmin(grid_z)), float(np.nanmax(grid_z))
        if result.mode == "Reliability landscape":
            norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], ncolors=256)
            surface_plot = axis.plot_surface(
                grid_x, grid_y, grid_z, cmap="RdYlGn", norm=norm,
                linewidth=0.15, antialiased=True, alpha=0.95,
            )
        else:
            surface_plot = axis.plot_surface(
                grid_x, grid_y, grid_z, cmap=colormap, vmin=value_min, vmax=value_max,
                linewidth=0.15, antialiased=True, alpha=0.95,
            )
        if show_wireframe:
            step = max(1, len(x_values) // 12)
            axis.plot_wireframe(
                grid_x, grid_y, grid_z, rstride=step, cstride=step,
                linewidth=0.35, color="black", alpha=0.28,
            )
        if show_projection:
            finite = grid_z[np.isfinite(grid_z)]
            if finite.size:
                span = max(float(np.ptp(finite)), 1e-9)
                offset = float(np.nanmin(finite) - 0.12 * span)
                projection_levels = (
                    [1, 2, 3, 4]
                    if result.mode == "Reliability landscape"
                    else np.linspace(value_min, value_max, 16)
                )
                axis.contourf(
                    grid_x, grid_y, grid_z, zdir="z", offset=offset,
                    levels=projection_levels,
                    cmap="RdYlGn" if result.mode == "Reliability landscape" else colormap,
                    vmin=None if result.mode == "Reliability landscape" else value_min,
                    vmax=None if result.mode == "Reliability landscape" else value_max,
                    extend="both" if result.mode == "Estimated response" else "max",
                    alpha=0.48,
                )
                axis.set_zlim(offset, float(np.nanmax(finite) + 0.04 * span))
        if show_overlay and not result.overlay.empty:
            axis.scatter(
                result.overlay[result.x_field], result.overlay[result.y_field],
                result.overlay["z_value"], s=34, c="white", edgecolors="black",
                linewidths=0.65, alpha=0.92, depthshade=False,
                label=str(result.overlay["z_source"].iloc[0]),
            )
            axis.legend(loc="upper left")
        colorbar = figure.colorbar(surface_plot, ax=axis, shrink=0.66, pad=0.08)
        colorbar.set_label(value_label)
        if result.mode == "Reliability landscape":
            colorbar.set_ticks([1, 2, 3, 4])
            colorbar.set_ticklabels(["D", "C", "B", "A"])
        axis.set_xlabel(COLUMN_LABELS.get(result.x_field, result.x_field), labelpad=10)
        axis.set_ylabel(COLUMN_LABELS.get(result.y_field, result.y_field), labelpad=10)
        axis.set_zlabel(value_label, labelpad=10)
        axis.set_title(f"{result.mode} · {response_label}", pad=18)
        axis.view_init(elev=float(elevation), azim=float(azimuth))
        axis.grid(True, alpha=0.25)
        invalid_points = int(surface.attrs.get("invalid_composition_points", 0) or 0)
        if invalid_points:
            axis.text2D(
                0.02, 0.02,
                "Blank region = invalid FA + GGBS + SF composition",
                transform=axis.transAxes, fontsize=8, alpha=0.8,
            )
        return figure

    # --- Physics-informed specimen interface -------------------------------------------------
    def specimen_analyses(self) -> list[str]:
        return self.physics_service.analysis_names()

    def specimen_fields(self, analysis: str) -> list[str]:
        return self.physics_service.field_names(analysis)

    def specimen_field(
        self,
        dataframe: pd.DataFrame,
        mix_id: str,
        analysis: str,
        field_type: str,
        resolution: int = 13,
        load_ratio_percent: float = 75.0,
        acid_type: str = "H2SO4",
        exposure_days: float = 28.0,
        effective_diffusivity_mm2_day: float = 1.0,
        twin_artifact: dict[str, Any] | None = None,
    ) -> SpecimenFieldResult:
        result = self.physics_service.build_field(
            dataframe=dataframe,
            mix_id=mix_id,
            analysis=analysis,
            field_type=field_type,
            resolution=resolution,
            load_ratio_percent=load_ratio_percent,
            acid_type=acid_type,
            exposure_days=exposure_days,
            effective_diffusivity_mm2_day=effective_diffusivity_mm2_day,
            twin_artifact=twin_artifact,
        )
        color_min, color_max, color_basis = self.physics_service.field_color_limits(
            dataframe, analysis, field_type, acid_type=acid_type, twin_artifact=twin_artifact
        )
        result.color_min = float(color_min)
        result.color_max = float(color_max)
        result.color_scale_basis = color_basis
        # Persist the comparison scale with every exported specimen-field row so the
        # visual normalization can be reproduced outside the application.
        result.field["color_scale_min"] = result.color_min
        result.field["color_scale_max"] = result.color_max
        result.field["color_scale_basis"] = result.color_scale_basis
        return result

    @staticmethod
    def _cutaway_mask(result: SpecimenFieldResult, mode: str) -> np.ndarray:
        field = result.field
        length, width, height = result.dimensions_mm
        if mode == "Full volume":
            return np.ones(len(field), dtype=bool)
        if mode == "Front half":
            return field["y_mm"].to_numpy(dtype=float) <= width / 2.0
        if mode == "Center slice":
            unique = np.sort(field["z_mm"].unique())
            center = unique[np.argmin(np.abs(unique - height / 2.0))]
            return np.isclose(field["z_mm"].to_numpy(dtype=float), center)
        if mode == "Octant cutaway":
            return ~(
                (field["x_mm"].to_numpy(dtype=float) > length / 2.0)
                & (field["y_mm"].to_numpy(dtype=float) < width / 2.0)
                & (field["z_mm"].to_numpy(dtype=float) > height / 2.0)
            )
        raise ValueError(f"Unsupported cutaway mode: {mode}")

    def specimen_figure(
        self,
        result: SpecimenFieldResult,
        cutaway_mode: str = "Octant cutaway",
        elevation: float = 28.0,
        azimuth: float = -52.0,
        colormap: str = "plasma",
    ) -> Figure:
        mask = self._cutaway_mask(result, cutaway_mode)
        shown = result.field.loc[mask]
        figure = Figure(figsize=(9.8, 7.2), constrained_layout=True)
        axis = figure.add_subplot(111, projection="3d")
        scatter = axis.scatter(
            shown["x_mm"], shown["y_mm"], shown["z_mm"],
            c=shown["field_value"], cmap=colormap,
            vmin=result.color_min, vmax=result.color_max,
            s=20 if len(shown) < 2500 else 9, alpha=0.72,
            linewidths=0, depthshade=True,
        )
        length, width, height = result.dimensions_mm
        if result.geometry == "cylinder":
            self._draw_cylinder(axis, diameter=length, length=height)
        else:
            self._draw_box(axis, length, width, height)
        colorbar = figure.colorbar(scatter, ax=axis, shrink=0.68, pad=0.08)
        colorbar.set_label(result.field_label)
        axis.set_xlabel("X (mm)")
        axis.set_ylabel("Y (mm)")
        axis.set_zlabel("Z (mm)")
        axis.set_xlim(0, length)
        axis.set_ylim(0, width)
        axis.set_zlim(0, height)
        axis.set_box_aspect((length, width, height))
        axis.set_title(
            f"Physics-informed specimen · {result.mix_id} · {result.field_type}", pad=18
        )
        axis.view_init(elev=float(elevation), azim=float(azimuth))
        axis.grid(True, alpha=0.20)
        return figure

    @staticmethod
    def _draw_box(axis, length: float, width: float, height: float) -> None:
        vertices = np.array([
            [0, 0, 0], [length, 0, 0], [length, width, 0], [0, width, 0],
            [0, 0, height], [length, 0, height], [length, width, height], [0, width, height],
        ])
        edges = (
            (0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        )
        for start, end in edges:
            axis.plot(
                [vertices[start, 0], vertices[end, 0]],
                [vertices[start, 1], vertices[end, 1]],
                [vertices[start, 2], vertices[end, 2]],
                color="black", linewidth=0.8, alpha=0.60,
            )

    @staticmethod
    def _draw_cylinder(axis, diameter: float, length: float) -> None:
        radius = diameter / 2.0
        theta = np.linspace(0, 2 * np.pi, 80)
        cx = radius + radius * np.cos(theta)
        cy = radius + radius * np.sin(theta)
        for z in (0.0, length):
            axis.plot(cx, cy, np.full_like(theta, z), color="black", linewidth=0.8, alpha=0.60)
        for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            x = radius + radius * np.cos(angle)
            y = radius + radius * np.sin(angle)
            axis.plot([x, x], [y, y], [0.0, length], color="black", linewidth=0.6, alpha=0.40)

    @staticmethod
    def export_dataframe(dataframe: pd.DataFrame, destination: Path | str) -> Path:
        path = Path(destination)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(path, index=False, encoding="utf-8-sig")
        return path
