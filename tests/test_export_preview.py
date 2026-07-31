from __future__ import annotations

from matplotlib.figure import Figure

from gpc_dtwin.chart_style import ChartStyle, apply_chart_style
from gpc_dtwin.figure_export import (
    EXPORT_DPI_OPTIONS,
    analyze_export_layout,
    export_profile,
)


def test_export_profiles_are_square_for_every_quality_option():
    for dpi in EXPORT_DPI_OPTIONS:
        profile = export_profile(dpi)
        assert profile.size_inches == 6.0
        assert profile.dpi == dpi
        assert profile.pixel_size == 6 * dpi


def test_export_layout_reports_outside_legend():
    figure = Figure(figsize=(6, 6))
    axis = figure.add_subplot(111)
    axis.plot([0, 1], [0, 1], label="Estimate")
    apply_chart_style(figure, ChartStyle(legend_location="outside right"))
    warnings = analyze_export_layout(figure)
    assert any("outside" in warning.lower() for warning in warnings)
