"""Interactive three-dimensional response and specimen-field visualization services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.colors import BoundaryNorm

from gpc_dtwin.columns import (
    COLUMN_LABELS,
    MODEL_DEFAULT_PREDICTORS,
    MODEL_NUMERIC_PREDICTORS,
)
from gpc_dtwin.services.digital_twin_service import DigitalTwinService, TwinBuildResult


SURFACE_MODES = (
    "Estimated response",
    "Relative uncertainty",
    "Prediction interval width",
    "Reliability landscape",
)

SPECIMEN_PROPERTIES = (
    "compressive_strength_mpa",
    "upv_m_s",
    "rebound_estimated_strength_mpa",
    "residual_compressive_strength_mpa",
    "strength_loss_percent_derived",
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
    twin_result: TwinBuildResult
    surface: pd.DataFrame
    overlay: pd.DataFrame
    x_field: str
    y_field: str
    response: str
    mode: str
    summary: dict[str, float]


@dataclass
class SpecimenFieldResult:
    mix_id: str
    property_field: str
    property_label: str
    base_value: float
    source_records: int
    uniformity_index: float
    field: pd.DataFrame
    summary: dict[str, float]


class Visualization3DService:
    """Create 3D surfaces and estimated material-state fields from compatible data."""

    def __init__(self) -> None:
        self.twin_service = DigitalTwinService()

    @staticmethod
    def surface_modes() -> list[str]:
        return list(SURFACE_MODES)

    @staticmethod
    def specimen_properties() -> list[str]:
        return list(SPECIMEN_PROPERTIES)

    @staticmethod
    def cutaway_modes() -> list[str]:
        return list(CUTAWAY_MODES)

    @staticmethod
    def camera_presets() -> dict[str, tuple[float, float]]:
        return dict(CAMERA_PRESETS)

    @staticmethod
    def available_numeric_axes(dataframe: pd.DataFrame, response: str) -> list[str]:
        candidates: list[str] = []
        for column in MODEL_NUMERIC_PREDICTORS:
            if column == response or column not in dataframe.columns:
                continue
            values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
            if len(values) >= 3 and values.nunique() >= 2:
                candidates.append(column)
        return sorted(candidates, key=lambda value: COLUMN_LABELS.get(value, value))

    @staticmethod
    def _surface_predictors(
        dataframe: pd.DataFrame,
        response: str,
        x_field: str,
        y_field: str,
    ) -> list[str]:
        predictors: list[str] = []
        for column in (x_field, y_field, *MODEL_DEFAULT_PREDICTORS):
            if column == response or column in predictors or column not in dataframe.columns:
                continue
            series = dataframe[column]
            if column in MODEL_NUMERIC_PREDICTORS:
                usable = pd.to_numeric(series, errors="coerce").notna().sum()
            else:
                usable = series.notna().sum()
            if usable > 0:
                predictors.append(column)
        if x_field not in predictors or y_field not in predictors:
            raise ValueError("The selected surface axes do not contain enough usable values.")
        return predictors

    def build_surface(
        self,
        dataframe: pd.DataFrame,
        response: str,
        x_field: str,
        y_field: str,
        method: str = "Gaussian Process",
        confidence_percent: float = 95.0,
        resolution: int = 35,
        include_review_records: bool = False,
        mode: str = "Estimated response",
    ) -> Surface3DResult:
        if mode not in SURFACE_MODES:
            raise ValueError(f"Unsupported surface mode: {mode}")
        if x_field == y_field:
            raise ValueError("Select different X and Y axes.")

        predictors = self._surface_predictors(dataframe, response, x_field, y_field)
        twin_result = self.twin_service.build_twin(
            dataframe,
            response=response,
            predictors=predictors,
            method=method,
            confidence_percent=confidence_percent,
            include_review_records=include_review_records,
        )
        surface = self.twin_service.response_map(
            twin_result.artifact,
            x_field=x_field,
            y_field=y_field,
            resolution=resolution,
        )
        overlay = self._build_overlay(
            twin_result.artifact,
            dataframe,
            response,
            x_field,
            y_field,
            mode,
        )
        summary = self.surface_summary(surface)
        return Surface3DResult(
            twin_result=twin_result,
            surface=surface,
            overlay=overlay,
            x_field=x_field,
            y_field=y_field,
            response=response,
            mode=mode,
            summary=summary,
        )

    def _build_overlay(
        self,
        artifact: dict[str, Any],
        dataframe: pd.DataFrame,
        response: str,
        x_field: str,
        y_field: str,
        mode: str,
    ) -> pd.DataFrame:
        required = [x_field, y_field]
        if not all(column in dataframe.columns for column in required):
            return pd.DataFrame()
        frame = dataframe.copy()
        frame[x_field] = pd.to_numeric(frame[x_field], errors="coerce")
        frame[y_field] = pd.to_numeric(frame[y_field], errors="coerce")
        frame = frame.dropna(subset=[x_field, y_field])
        if frame.empty:
            return pd.DataFrame()

        predictions = self.twin_service.predict_dataframe(artifact, frame)
        overlay = pd.DataFrame({
            x_field: frame[x_field].to_numpy(dtype=float),
            y_field: frame[y_field].to_numpy(dtype=float),
        })
        if "record_id" in frame.columns:
            overlay["record_id"] = frame["record_id"].astype(str).to_numpy()
        if "mix_id" in frame.columns:
            overlay["mix_id"] = frame["mix_id"].astype(str).to_numpy()

        if mode == "Estimated response" and response in frame.columns:
            observed = pd.to_numeric(frame[response], errors="coerce")
            overlay["z_value"] = observed.to_numpy(dtype=float)
            overlay["z_source"] = "Observed"
        else:
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
    def _mode_label(mode: str, response_label: str) -> str:
        return {
            "Estimated response": response_label,
            "Relative uncertainty": "Relative uncertainty (%)",
            "Prediction interval width": "Prediction interval width",
            "Reliability landscape": "Reliability class",
        }[mode]

    @staticmethod
    def surface_summary(surface: pd.DataFrame) -> dict[str, float]:
        mean = pd.to_numeric(surface["predicted_mean"], errors="coerce")
        uncertainty = pd.to_numeric(
            surface["normalized_uncertainty_percent"], errors="coerce"
        )
        reliability = surface["reliability_class"].astype("string")
        supported = reliability.isin(["A", "B"]).mean() * 100.0
        return {
            "minimum_estimate": float(mean.min()),
            "maximum_estimate": float(mean.max()),
            "mean_estimate": float(mean.mean()),
            "mean_uncertainty_percent": float(uncertainty.mean()),
            "supported_area_percent": float(supported),
            "map_nodes": float(len(surface)),
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
        value_label = self._mode_label(result.mode, response_label)

        if result.mode == "Reliability landscape":
            norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], ncolors=256)
            surface_plot = axis.plot_surface(
                grid_x,
                grid_y,
                grid_z,
                cmap="RdYlGn",
                norm=norm,
                linewidth=0.15,
                antialiased=True,
                alpha=0.95,
            )
        else:
            surface_plot = axis.plot_surface(
                grid_x,
                grid_y,
                grid_z,
                cmap=colormap,
                linewidth=0.15,
                antialiased=True,
                alpha=0.95,
            )

        if show_wireframe:
            step = max(1, len(x_values) // 12)
            axis.plot_wireframe(
                grid_x,
                grid_y,
                grid_z,
                rstride=step,
                cstride=step,
                linewidth=0.35,
                color="black",
                alpha=0.28,
            )

        if show_projection:
            finite = grid_z[np.isfinite(grid_z)]
            if finite.size:
                span = max(float(np.ptp(finite)), 1e-9)
                offset = float(np.nanmin(finite) - 0.12 * span)
                axis.contourf(
                    grid_x,
                    grid_y,
                    grid_z,
                    zdir="z",
                    offset=offset,
                    levels=16 if result.mode != "Reliability landscape" else [1, 2, 3, 4],
                    cmap="RdYlGn" if result.mode == "Reliability landscape" else colormap,
                    alpha=0.48,
                )
                axis.set_zlim(offset, float(np.nanmax(finite) + 0.04 * span))

        if show_overlay and not result.overlay.empty:
            axis.scatter(
                result.overlay[result.x_field],
                result.overlay[result.y_field],
                result.overlay["z_value"],
                s=34,
                c="white",
                edgecolors="black",
                linewidths=0.65,
                alpha=0.92,
                depthshade=False,
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
        return figure

    @staticmethod
    def _property_values(dataframe: pd.DataFrame, mix_id: str, property_field: str) -> pd.Series:
        if property_field not in dataframe.columns:
            raise ValueError("The selected property is not available in the active dataset.")
        subset = dataframe.loc[
            dataframe.get("mix_id", pd.Series(index=dataframe.index, dtype="string"))
            .astype("string")
            .eq(str(mix_id)),
            property_field,
        ]
        values = pd.to_numeric(subset, errors="coerce").dropna()
        if values.empty:
            raise ValueError("No usable values are available for the selected mix and property.")
        return values

    @staticmethod
    def _uniformity_index(dataframe: pd.DataFrame, mix_id: str) -> float:
        subset = dataframe.loc[
            dataframe.get("mix_id", pd.Series(index=dataframe.index, dtype="string"))
            .astype("string")
            .eq(str(mix_id))
        ].copy()
        if subset.empty:
            return 0.55

        upv = pd.to_numeric(subset.get("upv_m_s"), errors="coerce").dropna()
        all_upv = pd.to_numeric(dataframe.get("upv_m_s"), errors="coerce").dropna()
        if not upv.empty and not all_upv.empty and float(all_upv.max()) > float(all_upv.min()):
            upv_score = (
                float(upv.mean()) - float(all_upv.min())
            ) / (float(all_upv.max()) - float(all_upv.min()))
        else:
            upv_score = 0.5

        destructive = pd.to_numeric(subset.get("compressive_strength_mpa"), errors="coerce").dropna()
        rebound = pd.to_numeric(
            subset.get("rebound_estimated_strength_mpa"), errors="coerce"
        ).dropna()
        if not destructive.empty and not rebound.empty:
            denominator = max(abs(float(destructive.mean())), 1e-9)
            disagreement = min(abs(float(destructive.mean()) - float(rebound.mean())) / denominator, 1.0)
        else:
            disagreement = 0.35

        score = 0.48 + 0.40 * upv_score - 0.22 * disagreement
        return float(np.clip(score, 0.25, 0.95))

    def specimen_field(
        self,
        dataframe: pd.DataFrame,
        mix_id: str,
        property_field: str,
        resolution: int = 11,
    ) -> SpecimenFieldResult:
        if property_field not in SPECIMEN_PROPERTIES:
            raise ValueError(f"Unsupported specimen property: {property_field}")
        resolution = int(np.clip(resolution, 7, 18))
        values = self._property_values(dataframe, mix_id, property_field)
        base_value = float(values.mean())
        uniformity = self._uniformity_index(dataframe, mix_id)

        coordinates = np.linspace(0.0, 150.0, resolution)
        x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        xn, yn, zn = x / 150.0, y / 150.0, z / 150.0
        radial = np.sqrt((xn - 0.5) ** 2 + (yn - 0.5) ** 2 + (zn - 0.5) ** 2)
        radial = radial / max(float(radial.max()), 1e-9)

        phase_seed = sum(ord(character) for character in f"{mix_id}:{property_field}") % 360
        phase = np.deg2rad(float(phase_seed))
        smooth_wave = np.sin(np.pi * xn) * np.sin(np.pi * yn) * np.sin(np.pi * zn)
        directional_wave = np.sin(2.0 * np.pi * (xn + 0.55 * yn + 0.30 * zn) + phase)
        pattern = 0.52 * (smooth_wave - float(smooth_wave.mean()))
        pattern += 0.28 * directional_wave
        pattern -= 0.20 * (radial - float(radial.mean()))

        variation_scale = 0.035 + (1.0 - uniformity) * 0.16
        physical_field = base_value * (1.0 + variation_scale * pattern)
        if base_value >= 0:
            physical_field = np.clip(physical_field, 0.0, None)

        minimum = float(np.min(physical_field))
        maximum = float(np.max(physical_field))
        span = maximum - minimum
        normalized = (
            np.zeros_like(physical_field)
            if span <= 1e-12
            else (physical_field - minimum) / span
        )
        field = pd.DataFrame({
            "x_mm": x.ravel(),
            "y_mm": y.ravel(),
            "z_mm": z.ravel(),
            "estimated_value": physical_field.ravel(),
            "normalized_state": normalized.ravel(),
        })
        mean = float(field["estimated_value"].mean())
        std = float(field["estimated_value"].std(ddof=0))
        summary = {
            "minimum": float(field["estimated_value"].min()),
            "maximum": float(field["estimated_value"].max()),
            "mean": mean,
            "standard_deviation": std,
            "coefficient_of_variation_percent": float(std / max(abs(mean), 1e-9) * 100.0),
            "field_nodes": float(len(field)),
        }
        return SpecimenFieldResult(
            mix_id=str(mix_id),
            property_field=property_field,
            property_label=COLUMN_LABELS.get(property_field, property_field),
            base_value=base_value,
            source_records=len(values),
            uniformity_index=uniformity,
            field=field,
            summary=summary,
        )

    @staticmethod
    def _cutaway_mask(field: pd.DataFrame, mode: str) -> np.ndarray:
        if mode == "Full volume":
            return np.ones(len(field), dtype=bool)
        if mode == "Front half":
            return field["y_mm"].to_numpy(dtype=float) <= 75.0
        if mode == "Center slice":
            unique = np.sort(field["z_mm"].unique())
            center = unique[len(unique) // 2]
            return np.isclose(field["z_mm"].to_numpy(dtype=float), center)
        if mode == "Octant cutaway":
            return ~(
                (field["x_mm"].to_numpy(dtype=float) > 75.0)
                & (field["y_mm"].to_numpy(dtype=float) < 75.0)
                & (field["z_mm"].to_numpy(dtype=float) > 75.0)
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
        mask = self._cutaway_mask(result.field, cutaway_mode)
        shown = result.field.loc[mask]
        figure = Figure(figsize=(9.8, 7.2), constrained_layout=True)
        axis = figure.add_subplot(111, projection="3d")
        scatter = axis.scatter(
            shown["x_mm"],
            shown["y_mm"],
            shown["z_mm"],
            c=shown["estimated_value"],
            cmap=colormap,
            s=20 if len(shown) < 1800 else 10,
            alpha=0.72,
            linewidths=0,
            depthshade=True,
        )
        self._draw_cube(axis, 150.0)
        colorbar = figure.colorbar(scatter, ax=axis, shrink=0.68, pad=0.08)
        colorbar.set_label(result.property_label)
        axis.set_xlabel("X (mm)")
        axis.set_ylabel("Y (mm)")
        axis.set_zlabel("Z (mm)")
        axis.set_xlim(0, 150)
        axis.set_ylim(0, 150)
        axis.set_zlim(0, 150)
        axis.set_box_aspect((1, 1, 1))
        axis.set_title(
            f"Estimated specimen field · {result.mix_id} · {result.property_label}",
            pad=18,
        )
        axis.view_init(elev=float(elevation), azim=float(azimuth))
        axis.grid(True, alpha=0.20)
        return figure

    @staticmethod
    def _draw_cube(axis, size: float) -> None:
        vertices = np.array([
            [0, 0, 0], [size, 0, 0], [size, size, 0], [0, size, 0],
            [0, 0, size], [size, 0, size], [size, size, size], [0, size, size],
        ])
        edges = (
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        )
        for start, end in edges:
            axis.plot(
                [vertices[start, 0], vertices[end, 0]],
                [vertices[start, 1], vertices[end, 1]],
                [vertices[start, 2], vertices[end, 2]],
                color="black",
                linewidth=0.8,
                alpha=0.60,
            )

    @staticmethod
    def export_dataframe(dataframe: pd.DataFrame, destination: Path | str) -> Path:
        path = Path(destination)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(path, index=False, encoding="utf-8-sig")
        return path
