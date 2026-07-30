"""Consistent square figure export at 600 dots per inch."""

from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure


EXPORT_DPI = 600
EXPORT_SIZE_INCHES = 6.0
SUPPORTED_FIGURE_SUFFIXES = {".png", ".pdf", ".svg", ".tif", ".tiff"}


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
        raise ValueError(
            "Unsupported figure format. Use PNG, PDF, SVG, TIFF, or TIF."
        )
    if dpi != EXPORT_DPI:
        raise ValueError(f"Figure export is fixed at {EXPORT_DPI} dpi.")
    if size_inches <= 0:
        raise ValueError("Figure size must be positive.")

    destination.parent.mkdir(parents=True, exist_ok=True)
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
