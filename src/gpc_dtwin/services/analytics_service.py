"""Reusable analytical figures for geopolymer-concrete datasets."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from gpc_dtwin.columns import BINDER_PERCENT_COLUMNS, COLUMN_LABELS


@dataclass(frozen=True)
class ChartDefinition:
    key: str
    title: str
    description: str
    supports_mix_filter: bool = False


class AnalyticsService:
    CHARTS = [
        ChartDefinition(
            "binder_composition", "Binder composition profile",
            "FA, GGBS, and silica-fume contents across the available mixes."
        ),
        ChartDefinition(
            "compressive_28d", "28-day compressive strength",
            "28-day compressive strength together with FA, GGBS, and SF composition."
        ),
        ChartDefinition(
            "strength_age", "Mechanical properties by age",
            "Compressive, split tensile, and flexural strength at 7 and 28 days.", True
        ),
        ChartDefinition(
            "strength_growth", "Strength gain from 7 to 28 days",
            "Absolute and relative compressive-strength growth by mix."
        ),
        ChartDefinition(
            "ambient_oven", "Ambient and oven curing comparison",
            "Mechanical-property comparison for mixes with both curing records."
        ),
        ChartDefinition(
            "workability_aasb", "Workability response to AAS:B ratio",
            "Slump variation with activator-to-binder ratio.", True
        ),
        ChartDefinition(
            "rebound_measured", "Rebound and measured strength",
            "Relationship between rebound-estimated and ambient compressive strength."
        ),
        ChartDefinition(
            "upv_ggbs", "UPV and binder composition",
            "Ultrasonic pulse velocity together with FA, GGBS, and SF composition."
        ),
        ChartDefinition(
            "acid_residual", "Residual strength after exposure",
            "Initial and residual compressive strength under available exposure media."
        ),
        ChartDefinition(
            "durability_heatmap", "Durability heatmap",
            "Strength loss and mass change across mix and exposure conditions."
        ),
        ChartDefinition(
            "property_heatmap", "Multi-property performance heatmap",
            "Min–max-normalised comparison of mechanical and non-destructive measurements."
        ),
    ]

    def definition(self, key: str) -> ChartDefinition:
        for definition in self.CHARTS:
            if definition.key == key:
                return definition
        raise KeyError(f"Unknown chart key: {key}")

    def create_figure(self, dataframe: pd.DataFrame, key: str, mix_id: str = "M2") -> Figure:
        if dataframe.empty:
            return self._empty_figure("No data available")
        creators = {
            "binder_composition": self._binder_composition,
            "compressive_28d": self._compressive_28d,
            "strength_age": lambda df: self._strength_age(df, mix_id),
            "strength_growth": self._strength_growth,
            "ambient_oven": self._ambient_oven,
            "workability_aasb": lambda df: self._workability_aasb(df, mix_id),
            "rebound_measured": self._rebound_measured,
            "upv_ggbs": self._upv_ggbs,
            "acid_residual": self._acid_residual,
            "durability_heatmap": self._durability_heatmap,
            "property_heatmap": self._property_heatmap,
        }
        if key not in creators:
            raise KeyError(f"Unknown chart key: {key}")
        return creators[key](dataframe.copy())

    @staticmethod
    def _figure() -> tuple[Figure, object]:
        figure = Figure(figsize=(9.2, 5.3), constrained_layout=True)
        axis = figure.add_subplot(111)
        return figure, axis

    @staticmethod
    def _empty_figure(message: str) -> Figure:
        figure, axis = AnalyticsService._figure()
        axis.text(0.5, 0.5, message, ha="center", va="center", transform=axis.transAxes)
        axis.set_axis_off()
        return figure

    @staticmethod
    def _group(df: pd.DataFrame, name: str) -> pd.DataFrame:
        if "record_group" not in df.columns:
            return pd.DataFrame()
        return df[df["record_group"] == name].copy()

    @staticmethod
    def _mix_sort_key(series: pd.Series) -> pd.Series:
        """Return a stable numeric ordering for labels such as M1 ... M10."""
        extracted = series.astype(str).str.extract(r"(\d+)", expand=False)
        return pd.to_numeric(extracted, errors="coerce")

    @classmethod
    def _binder_frame(cls, df: pd.DataFrame, group: str | None = None) -> pd.DataFrame:
        """Return one composition row per mix with FA, GGBS, and SF preserved together."""
        source = cls._group(df, group) if group else df.copy()
        required = ["mix_id", *BINDER_PERCENT_COLUMNS]
        if source.empty or not all(column in source.columns for column in required):
            return pd.DataFrame(columns=required)
        frame = source[required].copy()
        for column in BINDER_PERCENT_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["mix_id"]).drop_duplicates(subset=["mix_id"], keep="first")
        frame["_mix_order"] = cls._mix_sort_key(frame["mix_id"])
        frame = frame.sort_values(["_mix_order", "mix_id"], na_position="last").drop(columns="_mix_order")
        return frame.reset_index(drop=True)

    @staticmethod
    def _add_binder_lines(axis, frame: pd.DataFrame) -> None:
        """Plot FA, GGBS, and SF on one common percentage axis."""
        for column in BINDER_PERCENT_COLUMNS:
            if column not in frame.columns:
                continue
            values = pd.to_numeric(frame[column], errors="coerce")
            if values.notna().any():
                axis.plot(
                    frame["mix_id"], values,
                    marker="o", linewidth=1.4,
                    label=COLUMN_LABELS.get(column, column),
                )
        axis.set_ylabel("Binder content (%)")
        axis.set_ylim(0, 100)
        axis.grid(True, axis="y", alpha=0.20)

    def _binder_composition(self, df: pd.DataFrame) -> Figure:
        frame = self._binder_frame(df, "AMBIENT_28D_MECHANICAL")
        if frame.empty:
            frame = self._binder_frame(df)
        if frame.empty:
            return self._empty_figure("Binder-composition fields are unavailable")
        figure, axis = self._figure()
        self._add_binder_lines(axis, frame)
        axis.set_xlabel("Mix ID")
        axis.set_title("FA–GGBS–SF binder composition")
        axis.legend()
        return figure

    def _compressive_28d(self, df: pd.DataFrame) -> Figure:
        subset = self._group(df, "AMBIENT_28D_MECHANICAL")
        if subset.empty:
            return self._empty_figure("No 28-day ambient records")
        subset["compressive_strength_mpa"] = pd.to_numeric(subset["compressive_strength_mpa"], errors="coerce")
        subset["_mix_order"] = self._mix_sort_key(subset["mix_id"])
        subset = subset.dropna(subset=["compressive_strength_mpa"]).sort_values(
            ["_mix_order", "mix_id"], na_position="last"
        )
        figure, axis = self._figure()
        axis.plot(subset["mix_id"], subset["compressive_strength_mpa"], marker="o", label="Compressive strength")
        for _, row in subset.iterrows():
            axis.annotate(f"{row['compressive_strength_mpa']:.2f}", (row["mix_id"], row["compressive_strength_mpa"]),
                          xytext=(4, 5), textcoords="offset points", fontsize=8)
        axis.set_xlabel("Mix ID")
        axis.set_ylabel("Compressive strength (MPa)")
        axis.grid(True, alpha=0.25)
        binder = self._binder_frame(subset)
        if not binder.empty:
            binder_axis = axis.twinx()
            self._add_binder_lines(binder_axis, binder)
            handles1, labels1 = axis.get_legend_handles_labels()
            handles2, labels2 = binder_axis.get_legend_handles_labels()
            axis.legend(handles1 + handles2, labels1 + labels2, loc="best")
        return figure

    def _strength_age(self, df: pd.DataFrame, mix_id: str) -> Figure:
        groups = ["AMBIENT_7D_MECHANICAL", "AMBIENT_28D_MECHANICAL"]
        subset = df[(df.get("mix_id") == mix_id) & df.get("record_group", pd.Series(dtype=str)).isin(groups)].copy()
        if subset.empty:
            return self._empty_figure(f"No age records for {mix_id}")
        subset["mechanical_test_age_days"] = pd.to_numeric(subset["mechanical_test_age_days"], errors="coerce")
        subset = subset.sort_values("mechanical_test_age_days")
        figure, axis = self._figure()
        properties = [
            ("compressive_strength_mpa", "Compressive"),
            ("split_tensile_strength_mpa", "Split tensile"),
            ("flexural_strength_mpa", "Flexural"),
        ]
        for column, label in properties:
            values = pd.to_numeric(subset[column], errors="coerce")
            axis.plot(subset["mechanical_test_age_days"], values, marker="o", label=label)
        axis.set_xlabel("Test age (days)")
        axis.set_ylabel("Strength (MPa)")
        axis.set_title(str(mix_id))
        axis.legend()
        axis.grid(True, alpha=0.25)
        return figure

    def _strength_growth(self, df: pd.DataFrame) -> Figure:
        seven = self._group(df, "AMBIENT_7D_MECHANICAL")[["mix_id", "compressive_strength_mpa"]]
        twenty_eight = self._group(df, "AMBIENT_28D_MECHANICAL")[["mix_id", "compressive_strength_mpa"]]
        if seven.empty or twenty_eight.empty:
            return self._empty_figure("Age-paired records are unavailable")
        merged = seven.merge(twenty_eight, on="mix_id", suffixes=("_7d", "_28d"))
        for column in ("compressive_strength_mpa_7d", "compressive_strength_mpa_28d"):
            merged[column] = pd.to_numeric(merged[column], errors="coerce")
        merged = merged.dropna()
        merged["gain"] = merged["compressive_strength_mpa_28d"] - merged["compressive_strength_mpa_7d"]
        figure, axis = self._figure()
        axis.bar(merged["mix_id"], merged["gain"])
        axis.set_xlabel("Mix")
        axis.set_ylabel("Compressive-strength gain (MPa)")
        axis.grid(True, axis="y", alpha=0.25)
        return figure

    def _ambient_oven(self, df: pd.DataFrame) -> Figure:
        ambient = self._group(df, "AMBIENT_28D_MECHANICAL")
        oven = self._group(df, "OVEN_100C_24H_MECHANICAL")
        if ambient.empty or oven.empty:
            return self._empty_figure("Paired curing records are unavailable")
        merged = ambient.merge(oven, on="mix_id", suffixes=("_ambient", "_oven"))
        merged = merged.sort_values("mix_id")
        figure, axis = self._figure()
        x = np.arange(len(merged))
        width = 0.36
        ambient_values = pd.to_numeric(merged["compressive_strength_mpa_ambient"], errors="coerce")
        oven_values = pd.to_numeric(merged["compressive_strength_mpa_oven"], errors="coerce")
        axis.bar(x - width / 2, ambient_values, width, label="Ambient, 28 days")
        axis.bar(x + width / 2, oven_values, width, label="Oven, 100 °C for 24 h")
        axis.set_xticks(x, merged["mix_id"])
        axis.set_ylabel("Compressive strength (MPa)")
        axis.set_xlabel("Mix")
        axis.legend()
        axis.grid(True, axis="y", alpha=0.25)
        return figure

    def _workability_aasb(self, df: pd.DataFrame, mix_id: str) -> Figure:
        subset = self._group(df, "AASB_WORKABILITY_AND_28D_COMPRESSIVE")
        subset = subset[subset["mix_id"] == mix_id].copy()
        if subset.empty:
            return self._empty_figure(f"No AAS:B records for {mix_id}")
        subset["aas_b_ratio"] = pd.to_numeric(subset["aas_b_ratio"], errors="coerce")
        subset["slump_mm"] = pd.to_numeric(subset["slump_mm"], errors="coerce")
        subset = subset.sort_values("aas_b_ratio")
        figure, axis = self._figure()
        axis.plot(subset["aas_b_ratio"], subset["slump_mm"], marker="o")
        axis.set_xlabel("AAS:B ratio (–)")
        axis.set_ylabel("Slump (mm)")
        axis.set_title(str(mix_id))
        axis.grid(True, alpha=0.25)
        return figure

    def _rebound_measured(self, df: pd.DataFrame) -> Figure:
        ndt = self._group(df, "NON_DESTRUCTIVE_TESTS")[["mix_id", "rebound_estimated_strength_mpa"]]
        measured = self._group(df, "AMBIENT_28D_MECHANICAL")[["mix_id", "compressive_strength_mpa"]]
        if ndt.empty or measured.empty:
            return self._empty_figure("Paired NDT and mechanical records are unavailable")
        merged = ndt.merge(measured, on="mix_id")
        x = pd.to_numeric(merged["compressive_strength_mpa"], errors="coerce")
        y = pd.to_numeric(merged["rebound_estimated_strength_mpa"], errors="coerce")
        valid = x.notna() & y.notna()
        x, y, labels = x[valid], y[valid], merged.loc[valid, "mix_id"]
        figure, axis = self._figure()
        axis.scatter(x, y)
        if len(x) >= 2:
            minimum = min(x.min(), y.min())
            maximum = max(x.max(), y.max())
            axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1)
        for xv, yv, label in zip(x, y, labels):
            axis.annotate(str(label), (xv, yv), xytext=(4, 5), textcoords="offset points", fontsize=8)
        axis.set_xlabel("Measured compressive strength (MPa)")
        axis.set_ylabel("Rebound-estimated strength (MPa)")
        axis.grid(True, alpha=0.25)
        return figure

    def _upv_ggbs(self, df: pd.DataFrame) -> Figure:
        subset = self._group(df, "NON_DESTRUCTIVE_TESTS").copy()
        if subset.empty:
            return self._empty_figure("No UPV records")
        subset["upv_m_s"] = pd.to_numeric(subset["upv_m_s"], errors="coerce")
        subset["_mix_order"] = self._mix_sort_key(subset["mix_id"])
        subset = subset.dropna(subset=["upv_m_s"]).sort_values(["_mix_order", "mix_id"], na_position="last")
        figure, axis = self._figure()
        axis.plot(subset["mix_id"], subset["upv_m_s"], marker="o", label="UPV")
        for _, row in subset.iterrows():
            axis.annotate(f"{row['upv_m_s']:.0f}", (row["mix_id"], row["upv_m_s"]),
                          xytext=(4, 5), textcoords="offset points", fontsize=8)
        axis.set_xlabel("Mix ID")
        axis.set_ylabel("UPV (m/s)")
        axis.grid(True, alpha=0.25)
        binder = self._binder_frame(subset)
        if not binder.empty:
            binder_axis = axis.twinx()
            self._add_binder_lines(binder_axis, binder)
            handles1, labels1 = axis.get_legend_handles_labels()
            handles2, labels2 = binder_axis.get_legend_handles_labels()
            axis.legend(handles1 + handles2, labels1 + labels2, loc="best")
        return figure

    def _acid_residual(self, df: pd.DataFrame) -> Figure:
        subset = self._group(df, "ACID_DURABILITY_28D").copy()
        if subset.empty:
            return self._empty_figure("No durability records")
        subset["label"] = subset["mix_id"].astype(str) + " · " + subset["acid_type"].astype(str)
        initial = pd.to_numeric(subset["initial_compressive_strength_mpa"], errors="coerce")
        residual = pd.to_numeric(subset["residual_compressive_strength_mpa"], errors="coerce")
        figure, axis = self._figure()
        x = np.arange(len(subset))
        width = 0.36
        axis.bar(x - width / 2, initial, width, label="Initial")
        axis.bar(x + width / 2, residual, width, label="Residual")
        axis.set_xticks(x, subset["label"], rotation=30, ha="right")
        axis.set_ylabel("Compressive strength (MPa)")
        axis.legend()
        axis.grid(True, axis="y", alpha=0.25)
        return figure

    def _durability_heatmap(self, df: pd.DataFrame) -> Figure:
        subset = self._group(df, "ACID_DURABILITY_28D").copy()
        if subset.empty:
            return self._empty_figure("No durability records")
        strength = subset.pivot_table(
            index="mix_id", columns="acid_type", values="strength_loss_percent_derived", aggfunc="mean"
        )
        mass = subset.pivot_table(
            index="mix_id", columns="acid_type", values="mass_change_percent_derived", aggfunc="mean"
        )
        combined = pd.concat(
            [strength.add_prefix("Strength loss · "), mass.add_prefix("Mass change · ")], axis=1
        )
        figure, axis = self._figure()
        image = axis.imshow(combined.values.astype(float), aspect="auto")
        axis.set_xticks(range(len(combined.columns)), combined.columns, rotation=30, ha="right")
        axis.set_yticks(range(len(combined.index)), combined.index)
        axis.set_xlabel("Durability measure (%)")
        axis.set_ylabel("Mix")
        figure.colorbar(image, ax=axis, label="Percent")
        return figure

    def _property_heatmap(self, df: pd.DataFrame) -> Figure:
        mechanical = self._group(df, "AMBIENT_28D_MECHANICAL")[
            ["mix_id", "compressive_strength_mpa", "split_tensile_strength_mpa", "flexural_strength_mpa"]
        ]
        ndt = self._group(df, "NON_DESTRUCTIVE_TESTS")[
            ["mix_id", "upv_m_s", "rebound_estimated_strength_mpa"]
        ]
        if mechanical.empty or ndt.empty:
            return self._empty_figure("Required property groups are unavailable")
        merged = mechanical.merge(ndt, on="mix_id").set_index("mix_id")
        columns = [
            "compressive_strength_mpa", "split_tensile_strength_mpa", "flexural_strength_mpa",
            "upv_m_s", "rebound_estimated_strength_mpa"
        ]
        values = merged[columns].apply(pd.to_numeric, errors="coerce")
        spans = values.max() - values.min()
        normalised = (values - values.min()) / spans.replace(0, np.nan)
        normalised = normalised.fillna(0)
        figure, axis = self._figure()
        image = axis.imshow(normalised.values, aspect="auto", vmin=0, vmax=1)
        axis.set_xticks(range(len(columns)), [
            "Compressive", "Split tensile", "Flexural", "UPV", "Rebound"
        ], rotation=25, ha="right")
        axis.set_yticks(range(len(normalised.index)), normalised.index)
        axis.set_xlabel("Property (min–max normalised, –)")
        axis.set_ylabel("Mix")
        figure.colorbar(image, ax=axis, label="Normalised performance (–)")
        return figure
