"""Consistent square figure export, preview metadata, and layout checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from matplotlib.figure import Figure

from gpc_dtwin.chart_style import ChartStyle, apply_chart_style, style_for_figure


EXPORT_DPI = 600
EXPORT_SIZE_INCHES = 6.0
SUPPORTED_FIGURE_SUFFIXES = {".png", ".pdf", ".svg", ".tif", ".tiff"}


@dataclass(frozen=True, slots=True)
class ExportProfile:
    size_inches: float = EXPORT_SIZE_INCHES
    dpi: int = EXPORT_DPI

    @property
    def pixel_size(self) -> int:
        return int(round(self.size_inches * self.dpi))


def export_profile() -> ExportProfile:
    return ExportProfile()


def analyze_export_layout(figure: Figure) -> list[str]:
    """Return practical warnings before a fixed square export."""
    style = style_for_figure(figure)
    warnings: list[str] = []
    if style.legend_visible and style.legend_location.startswith("outside"):
        warnings.append("The legend is outside the axes; inspect the preview for clipping.")
    if style.legend_location == "custom":
        warnings.append("A custom legend anchor is active; inspect its final position.")
    if any(len(axis.get_title()) > 80 for axis in figure.axes):
        warnings.append("A long chart title may wrap or reduce plot area.")
    if len([axis for axis in figure.axes if axis.get_visible()]) > 4:
        warnings.append("The figure contains many axes; verify labels remain readable at square size.")
    if any(abs(float(tick.get_rotation())) > 60 for axis in figure.axes for tick in axis.get_xticklabels()):
        warnings.append("Strong tick rotation may require additional bottom margin.")
    if not warnings:
        warnings.append("No common clipping risks were detected.")
    return warnings


def save_square_figure(
    figure: Figure,
    destination: Path | str,
    *,
    dpi: int = EXPORT_DPI,
    size_inches: float = EXPORT_SIZE_INCHES,
) -> Path:
    """Save a square figure and restore its interactive canvas dimensions."""
    destination = Path(destination)
    suffix = destination.suffix.lower()
    if suffix not in SUPPORTED_FIGURE_SUFFIXES:
        raise ValueError("Unsupported figure format. Use PNG, PDF, SVG, TIFF, or TIF.")
    if dpi != EXPORT_DPI:
        raise ValueError(f"Figure export is fixed at {EXPORT_DPI} dpi.")
    if size_inches <= 0:
        raise ValueError("Figure size must be positive.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    apply_chart_style(figure, style_for_figure(figure))
    original_size = tuple(float(value) for value in figure.get_size_inches())
    original_dpi = float(figure.dpi)
    try:
        figure.set_size_inches(size_inches, size_inches, forward=False)
        figure.set_dpi(EXPORT_DPI)
        figure.savefig(
            destination,
            dpi=EXPORT_DPI,
            bbox_inches=None,
            pad_inches=0.0,
            facecolor=figure.get_facecolor(),
            edgecolor="none",
            transparent=False,
        )
    finally:
        figure.set_size_inches(*original_size, forward=False)
        figure.set_dpi(original_dpi)
    return destination
