"""Built-in publication and presentation chart presets."""

from __future__ import annotations

from collections import OrderedDict

from gpc_dtwin.chart_style import ChartStyle


BUILT_IN_PRESETS: "OrderedDict[str, ChartStyle]" = OrderedDict([
    ("Publication colour", ChartStyle(
        font_family="Times New Roman", title_size=15, label_size=12,
        tick_size=10, legend_size=10, line_width=1.8,
        series_palette="Colour blind", major_grid=True, grid_alpha=0.22,
    )),
    ("Publication monochrome", ChartStyle(
        font_family="Times New Roman", title_size=15, label_size=12,
        tick_size=10, legend_size=10, line_width=1.8,
        series_palette="Monochrome", major_grid=False,
        figure_background="#ffffff", axes_background="#ffffff",
        text_color="#000000", axis_color="#000000",
    )),
    ("Presentation", ChartStyle(
        font_family="Times New Roman", title_size=20, label_size=16,
        tick_size=13, legend_size=13, annotation_size=12,
        line_width=2.8, marker_size=8.0, spine_width=1.4,
        tick_width=1.3, tick_length=6.0, series_palette="High contrast",
        major_grid=True, grid_alpha=0.20,
    )),
    ("High contrast", ChartStyle(
        font_family="Times New Roman", title_size=16, label_size=13,
        tick_size=11, legend_size=11, line_width=2.2,
        series_palette="High contrast", major_grid=True, grid_alpha=0.35,
        figure_background="#ffffff", axes_background="#ffffff",
        text_color="#000000", axis_color="#000000", grid_color="#555555",
    )),
    ("Minimal", ChartStyle(
        font_family="Times New Roman", title_size=14, label_size=11,
        tick_size=9, legend_size=9, line_width=1.5,
        legend_frame=False, major_grid=False, minor_grid=False,
        spine_width=0.8, tick_length=3.0, series_palette="Colour blind",
    )),
])


def preset_names() -> tuple[str, ...]:
    return tuple(BUILT_IN_PRESETS)


def preset_style(name: str) -> ChartStyle:
    style = BUILT_IN_PRESETS.get(name)
    return ChartStyle.from_dict(style.to_dict()) if style is not None else ChartStyle()
