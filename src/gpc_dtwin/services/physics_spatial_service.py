"""Physics-informed specimen fields for GPC-DTwin.

The service deliberately distinguishes calculated fields from measured spatial data.  Bulk
material capacities may come from the active Digital Twin when its response is compatible;
otherwise the corresponding experimental mix-level observations are used.  No CT/tomographic
or voxel-level measurement is inferred when such data are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from gpc_dtwin.columns import COLUMN_LABELS, MODEL_NUMERIC_PREDICTORS
from gpc_dtwin.services.digital_twin_service import DigitalTwinService


ANALYSES = (
    "Compression cube",
    "Splitting tensile cylinder",
    "Flexural beam",
    "Acid degradation cube",
)

FIELD_OPTIONS = {
    "Compression cube": (
        "Applied stress",
        "Stress utilisation",
        "Capacity margin",
    ),
    "Splitting tensile cylinder": (
        "Nominal tensile stress",
        "Nominal tensile utilisation",
    ),
    "Flexural beam": (
        "Bending stress",
        "Tensile utilisation",
        "Compressive utilisation",
        "Failure index",
    ),
    "Acid degradation cube": (
        "Acid penetration",
        "Damage index",
        "Residual strength",
        "Strength retention",
    ),
}

RESPONSE_FOR_ANALYSIS = {
    "Compression cube": "compressive_strength_mpa",
    "Splitting tensile cylinder": "split_tensile_strength_mpa",
    "Flexural beam": "flexural_strength_mpa",
    "Acid degradation cube": "compressive_strength_mpa",
}


@dataclass
class SpecimenPhysicsResult:
    mix_id: str
    analysis: str
    field_type: str
    field_label: str
    geometry: str
    dimensions_mm: tuple[float, float, float]
    capacity_value: float
    capacity_source: str
    field_source: str
    source_records: int
    field: pd.DataFrame
    summary: dict[str, float]
    assumptions: tuple[str, ...]


class PhysicsSpatialService:
    """Calculate theory-based specimen fields with explicit provenance."""

    @staticmethod
    def analysis_names() -> list[str]:
        return list(ANALYSES)

    @staticmethod
    def field_names(analysis: str) -> list[str]:
        if analysis not in FIELD_OPTIONS:
            raise ValueError(f"Unsupported specimen analysis: {analysis}")
        return list(FIELD_OPTIONS[analysis])

    @staticmethod
    def _mix_rows(dataframe: pd.DataFrame, mix_id: str) -> pd.DataFrame:
        if "mix_id" not in dataframe.columns:
            raise ValueError("The active dataset does not contain Mix ID information.")
        return dataframe.loc[dataframe["mix_id"].astype("string").eq(str(mix_id))].copy()

    @staticmethod
    def _experimental_capacity(
        dataframe: pd.DataFrame, mix_id: str, response: str
    ) -> tuple[float, int]:
        rows = PhysicsSpatialService._mix_rows(dataframe, mix_id)
        if response not in rows.columns:
            raise ValueError(f"{COLUMN_LABELS.get(response, response)} is unavailable.")
        values = pd.to_numeric(rows[response], errors="coerce").dropna()
        if values.empty:
            raise ValueError(
                f"No usable {COLUMN_LABELS.get(response, response)} values are available for {mix_id}."
            )
        return float(values.mean()), int(len(values))

    @staticmethod
    def _representative_twin_scenario(
        artifact: dict[str, Any], dataframe: pd.DataFrame, mix_id: str
    ) -> dict[str, Any]:
        metadata = artifact["metadata"]
        defaults = dict(metadata.get("input_defaults", {}))
        rows = PhysicsSpatialService._mix_rows(dataframe, mix_id)
        scenario: dict[str, Any] = {}
        for predictor in metadata.get("predictors", []):
            values = rows[predictor] if predictor in rows.columns else pd.Series(dtype=float)
            if predictor in MODEL_NUMERIC_PREDICTORS:
                numeric = pd.to_numeric(values, errors="coerce").dropna()
                scenario[predictor] = (
                    float(numeric.median()) if not numeric.empty else defaults.get(predictor)
                )
            else:
                text = values.dropna().astype(str)
                scenario[predictor] = (
                    str(text.mode().iloc[0]) if not text.empty else defaults.get(predictor)
                )
        return scenario

    @classmethod
    def _capacity(
        cls,
        dataframe: pd.DataFrame,
        mix_id: str,
        response: str,
        twin_artifact: dict[str, Any] | None,
    ) -> tuple[float, str, int]:
        if twin_artifact is not None:
            try:
                metadata = twin_artifact["metadata"]
                if metadata.get("response") == response:
                    scenario = cls._representative_twin_scenario(
                        twin_artifact, dataframe, mix_id
                    )
                    prediction = DigitalTwinService.predict_scenario(twin_artifact, scenario)
                    return (
                        float(prediction["predicted_mean"]),
                        f"Digital Twin · {metadata.get('method', 'model')}",
                        int(metadata.get("observations", 0)),
                    )
            except Exception:
                pass
        value, records = cls._experimental_capacity(dataframe, mix_id, response)
        return value, "Experimental mix-level mean", records

    @staticmethod
    def _summary(field: pd.DataFrame) -> dict[str, float]:
        values = pd.to_numeric(field["field_value"], errors="coerce").dropna()
        if values.empty:
            raise ValueError("The calculated specimen field contains no finite values.")
        mean = float(values.mean())
        std = float(values.std(ddof=0))
        return {
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "mean": mean,
            "standard_deviation": std,
            "coefficient_of_variation_percent": float(std / max(abs(mean), 1e-9) * 100.0),
            "field_nodes": float(len(values)),
        }

    def build_field(
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
    ) -> SpecimenPhysicsResult:
        if analysis not in ANALYSES:
            raise ValueError(f"Unsupported specimen analysis: {analysis}")
        if field_type not in FIELD_OPTIONS[analysis]:
            raise ValueError(f"Unsupported field for {analysis}: {field_type}")
        resolution = int(np.clip(resolution, 7, 24))
        load_ratio = float(np.clip(load_ratio_percent, 0.0, 150.0)) / 100.0

        if analysis == "Compression cube":
            return self._compression(
                dataframe, mix_id, field_type, resolution, load_ratio, twin_artifact
            )
        if analysis == "Splitting tensile cylinder":
            return self._splitting(
                dataframe, mix_id, field_type, resolution, load_ratio, twin_artifact
            )
        if analysis == "Flexural beam":
            return self._flexural(
                dataframe, mix_id, field_type, resolution, load_ratio, twin_artifact
            )
        return self._acid(
            dataframe,
            mix_id,
            field_type,
            resolution,
            acid_type,
            exposure_days,
            effective_diffusivity_mm2_day,
            twin_artifact,
        )

    def _compression(
        self, dataframe, mix_id, field_type, resolution, load_ratio, twin_artifact
    ) -> SpecimenPhysicsResult:
        capacity, capacity_source, records = self._capacity(
            dataframe, mix_id, "compressive_strength_mpa", twin_artifact
        )
        size = 150.0
        coords = np.linspace(0.0, size, resolution)
        x, y, z = np.meshgrid(coords, coords, coords, indexing="ij")
        stress = np.full_like(x, load_ratio * capacity, dtype=float)
        utilisation = stress / max(capacity, 1e-9)
        if field_type == "Applied stress":
            value = stress
            label = "Nominal compressive stress (MPa)"
        elif field_type == "Stress utilisation":
            value = utilisation
            label = "Compressive stress utilisation"
        else:
            value = 1.0 - utilisation
            label = "Capacity margin"
        field = pd.DataFrame({
            "x_mm": x.ravel(), "y_mm": y.ravel(), "z_mm": z.ravel(),
            "field_value": value.ravel(),
            "applied_stress_mpa": stress.ravel(),
            "capacity_mpa": capacity,
            "utilisation": utilisation.ravel(),
            "analysis_type": "Compression cube",
            "field_type": field_type,
            "field_source": "Theory calculated + bulk-capacity calibrated",
            "capacity_source": capacity_source,
        })
        return SpecimenPhysicsResult(
            mix_id=str(mix_id), analysis="Compression cube", field_type=field_type,
            field_label=label, geometry="cube", dimensions_mm=(150.0, 150.0, 150.0),
            capacity_value=capacity, capacity_source=capacity_source,
            field_source="Theory calculated + bulk-capacity calibrated",
            source_records=records, field=field, summary=self._summary(field),
            assumptions=(
                "150 × 150 × 150 mm cube.",
                "Ideal concentric uniaxial loading; nominal stress P/A is spatially uniform.",
                f"Applied load is {load_ratio * 100.0:.1f}% of the predicted/observed bulk compressive capacity.",
            ),
        )

    def _splitting(
        self, dataframe, mix_id, field_type, resolution, load_ratio, twin_artifact
    ) -> SpecimenPhysicsResult:
        capacity, capacity_source, records = self._capacity(
            dataframe, mix_id, "split_tensile_strength_mpa", twin_artifact
        )
        radius = 75.0
        length = 300.0
        xy = np.linspace(-radius, radius, resolution)
        zc = np.linspace(0.0, length, resolution)
        x, y, z = np.meshgrid(xy, xy, zc, indexing="ij")
        mask = x**2 + y**2 <= radius**2 + 1e-9
        nominal = np.full_like(x, load_ratio * capacity, dtype=float)
        nominal[~mask] = np.nan
        utilisation = nominal / max(capacity, 1e-9)
        if field_type == "Nominal tensile stress":
            value = nominal
            label = "Nominal splitting tensile stress (MPa)"
        else:
            value = utilisation
            label = "Nominal splitting tensile utilisation"
        field = pd.DataFrame({
            "x_mm": (x + radius).ravel(), "y_mm": (y + radius).ravel(), "z_mm": z.ravel(),
            "field_value": value.ravel(),
            "nominal_tensile_stress_mpa": nominal.ravel(),
            "capacity_mpa": capacity,
            "utilisation": utilisation.ravel(),
            "analysis_type": "Splitting tensile cylinder",
            "field_type": field_type,
            "field_source": "Theory calculated (standard nominal splitting relation)",
            "capacity_source": capacity_source,
        }).dropna(subset=["field_value"]).reset_index(drop=True)
        return SpecimenPhysicsResult(
            mix_id=str(mix_id), analysis="Splitting tensile cylinder", field_type=field_type,
            field_label=label, geometry="cylinder", dimensions_mm=(150.0, 150.0, 300.0),
            capacity_value=capacity, capacity_source=capacity_source,
            field_source="Theory calculated (standard nominal splitting relation)",
            source_records=records, field=field, summary=self._summary(field),
            assumptions=(
                "150 mm diameter × 300 mm length cylinder.",
                "Nominal splitting tensile relation f_t = 2P/(πLD).",
                "The display is a nominal specimen-level stress field, not a full elastic-contact/Hondros stress reconstruction.",
                f"Applied load is {load_ratio * 100.0:.1f}% of bulk splitting tensile capacity.",
            ),
        )

    def _flexural(
        self, dataframe, mix_id, field_type, resolution, load_ratio, twin_artifact
    ) -> SpecimenPhysicsResult:
        capacity, capacity_source, records = self._capacity(
            dataframe, mix_id, "flexural_strength_mpa", twin_artifact
        )
        length, width, depth, span = 500.0, 100.0, 100.0, 400.0
        support_left = (length - span) / 2.0
        support_right = support_left + span
        load_left = support_left + span / 3.0
        load_right = support_left + 2.0 * span / 3.0
        failure_load_n = capacity * width * depth**2 / span
        applied_load_n = load_ratio * failure_load_n
        reaction = applied_load_n / 2.0

        xc = np.linspace(0.0, length, max(resolution * 2, 15))
        yc = np.linspace(-width / 2.0, width / 2.0, resolution)
        zc = np.linspace(-depth / 2.0, depth / 2.0, resolution)
        x, y, z = np.meshgrid(xc, yc, zc, indexing="ij")
        m = np.zeros_like(x, dtype=float)
        region1 = (x >= support_left) & (x < load_left)
        region2 = (x >= load_left) & (x <= load_right)
        region3 = (x > load_right) & (x <= support_right)
        m[region1] = reaction * (x[region1] - support_left)
        m[region2] = reaction * (load_left - support_left)
        m[region3] = reaction * (support_right - x[region3])
        inertia = width * depth**3 / 12.0
        sigma = -(m * z / inertia)  # top fibres (positive z) in compression
        tensile_util = np.maximum(sigma, 0.0) / max(capacity, 1e-9)
        compressive_util = np.maximum(-sigma, 0.0) / max(capacity, 1e-9)
        failure_index = np.abs(sigma) / max(capacity, 1e-9)
        if field_type == "Bending stress":
            value = sigma
            label = "Longitudinal bending stress (MPa)"
        elif field_type == "Tensile utilisation":
            value = tensile_util
            label = "Tensile flexural utilisation"
        elif field_type == "Compressive utilisation":
            value = compressive_util
            label = "Compressive flexural utilisation"
        else:
            value = failure_index
            label = "Flexural failure index"
        field = pd.DataFrame({
            "x_mm": x.ravel(),
            "y_mm": (y + width / 2.0).ravel(),
            "z_mm": (z + depth / 2.0).ravel(),
            "field_value": value.ravel(),
            "bending_stress_mpa": sigma.ravel(),
            "capacity_mpa": capacity,
            "utilisation": failure_index.ravel(),
            "analysis_type": "Flexural beam",
            "field_type": field_type,
            "field_source": "Theory calculated (third-point bending) + bulk-capacity calibrated",
            "capacity_source": capacity_source,
        })
        return SpecimenPhysicsResult(
            mix_id=str(mix_id), analysis="Flexural beam", field_type=field_type,
            field_label=label, geometry="beam", dimensions_mm=(500.0, 100.0, 100.0),
            capacity_value=capacity, capacity_source=capacity_source,
            field_source="Theory calculated (third-point bending) + bulk-capacity calibrated",
            source_records=records, field=field, summary=self._summary(field),
            assumptions=(
                "100 × 100 × 500 mm beam with 400 mm support span.",
                "Symmetric third-point loading and Euler-Bernoulli elastic bending: σ = My/I.",
                f"Applied total load is {load_ratio * 100.0:.1f}% of the load corresponding to the bulk flexural capacity.",
            ),
        )

    @staticmethod
    def _slab_unpenetrated_fraction(
        coordinate_mm: np.ndarray,
        length_mm: float,
        diffusivity_mm2_day: float,
        time_days: float,
        terms: int = 25,
    ) -> np.ndarray:
        x = np.asarray(coordinate_mm, dtype=float)
        d = max(float(diffusivity_mm2_day), 1e-12)
        t = max(float(time_days), 0.0)
        if t <= 0:
            return np.ones_like(x)
        result = np.zeros_like(x, dtype=float)
        for n in range(terms):
            m = 2 * n + 1
            result += (
                4.0 / np.pi / m
                * np.sin(m * np.pi * x / length_mm)
                * np.exp(-d * (m * np.pi / length_mm) ** 2 * t)
            )
        return np.clip(result, 0.0, 1.0)

    @staticmethod
    def _calibrate_damage_beta(shape: np.ndarray, target_retention: float) -> float:
        target = float(np.clip(target_retention, 1e-6, 0.999999))
        values = np.asarray(shape, dtype=float)
        low, high = 0.0, 100.0
        for _ in range(80):
            mid = (low + high) / 2.0
            retention = float(np.mean(np.exp(-mid * values)))
            if retention > target:
                low = mid
            else:
                high = mid
        return (low + high) / 2.0

    def _acid(
        self,
        dataframe,
        mix_id,
        field_type,
        resolution,
        acid_type,
        exposure_days,
        diffusivity,
        twin_artifact,
    ) -> SpecimenPhysicsResult:
        acid_norm = str(acid_type).strip().lower()
        acid_label = "H2SO4" if "so4" in acid_norm else "HCl"
        rows = self._mix_rows(dataframe, mix_id)
        acid_rows = rows.loc[
            rows.get("acid_type", pd.Series(index=rows.index, dtype="string"))
            .astype("string")
            .str.lower()
            .eq(acid_label.lower())
        ].copy()
        initial = pd.to_numeric(
            acid_rows.get("initial_compressive_strength_mpa"), errors="coerce"
        ).dropna()
        residual = pd.to_numeric(
            acid_rows.get("residual_compressive_strength_mpa"), errors="coerce"
        ).dropna()
        if initial.empty or residual.empty:
            raise ValueError(
                f"Acid-degradation calibration for {mix_id} and {acid_label} requires initial and residual compressive-strength observations."
            )
        observed_initial = float(initial.mean())
        observed_residual = float(residual.mean())
        target_retention = float(np.clip(observed_residual / max(observed_initial, 1e-9), 0.0, 1.0))
        capacity, capacity_source, records = self._capacity(
            dataframe, mix_id, "compressive_strength_mpa", twin_artifact
        )

        size = 150.0
        coords = np.linspace(0.0, size, resolution)
        x, y, z = np.meshgrid(coords, coords, coords, indexing="ij")
        ux = self._slab_unpenetrated_fraction(x, size, diffusivity, exposure_days)
        uy = self._slab_unpenetrated_fraction(y, size, diffusivity, exposure_days)
        uz = self._slab_unpenetrated_fraction(z, size, diffusivity, exposure_days)
        penetration = np.clip(1.0 - ux * uy * uz, 0.0, 1.0)
        beta = self._calibrate_damage_beta(penetration, target_retention)
        local_retention = np.exp(-beta * penetration)
        local_residual = capacity * local_retention
        damage = 1.0 - local_retention

        if field_type == "Acid penetration":
            value = penetration * 100.0
            label = f"Modelled {acid_label} penetration indicator (%)"
        elif field_type == "Damage index":
            value = damage
            label = "Chemically induced damage index"
        elif field_type == "Residual strength":
            value = local_residual
            label = "Modelled local residual compressive capacity (MPa)"
        else:
            value = local_retention * 100.0
            label = "Modelled local strength retention (%)"

        field = pd.DataFrame({
            "x_mm": x.ravel(), "y_mm": y.ravel(), "z_mm": z.ravel(),
            "field_value": value.ravel(),
            "acid_penetration_fraction": penetration.ravel(),
            "damage_index": damage.ravel(),
            "local_strength_retention": local_retention.ravel(),
            "local_residual_strength_mpa": local_residual.ravel(),
            "capacity_mpa": capacity,
            "analysis_type": "Acid degradation cube",
            "field_type": field_type,
            "field_source": "Diffusion theory + experimentally calibrated global strength loss",
            "capacity_source": capacity_source,
            "acid_type": acid_label,
            "exposure_days": float(exposure_days),
            "effective_diffusivity_mm2_day": float(diffusivity),
            "calibrated_damage_beta": beta,
            "observed_strength_retention": target_retention,
        })
        return SpecimenPhysicsResult(
            mix_id=str(mix_id), analysis="Acid degradation cube", field_type=field_type,
            field_label=label, geometry="cube", dimensions_mm=(150.0, 150.0, 150.0),
            capacity_value=capacity, capacity_source=capacity_source,
            field_source="Diffusion theory + experimentally calibrated global strength loss",
            source_records=max(int(len(initial)), int(len(residual)), records),
            field=field, summary=self._summary(field),
            assumptions=(
                "150 × 150 × 150 mm cube with constant surface exposure on all six faces.",
                "Fickian diffusion in a rectangular solid; effective diffusivity is a user-controlled modelling assumption.",
                f"Effective diffusivity = {float(diffusivity):.4g} mm²/day; exposure = {float(exposure_days):.1f} days.",
                f"Damage magnitude calibrated so volume-average retention matches the available {acid_label} strength-retention observation ({target_retention * 100.0:.1f}%).",
                "The internal penetration profile is calculated, not spatially measured.",
            ),
        )
