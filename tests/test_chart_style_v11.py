from __future__ import annotations

from matplotlib.figure import Figure

from gpc_dtwin.chart_style import ChartStyle, apply_chart_style, style_for_figure


def test_chart_style_round_trip_preserves_v11_fields():
    style = ChartStyle(
        title_alignment="left", annotation_size=13, legend_location="custom",
        legend_anchor_x=1.2, legend_anchor_y=0.7, series_palette="Monochrome",
        axes_margin_x=0.1, colorbar_visible=False,
    )
    restored = ChartStyle.from_json(style.to_json())
    assert restored.title_alignment == "left"
    assert restored.annotation_size == 13
    assert restored.legend_anchor_x == 1.2
    assert restored.series_palette == "Monochrome"
    assert restored.colorbar_visible is False


def test_outside_legend_and_title_alignment_are_applied():
    figure = Figure(figsize=(6, 6), constrained_layout=True)
    axis = figure.add_subplot(111)
    axis.plot([0, 1], [1, 2], label="Series")
    axis.set_title("Aligned title")
    style = ChartStyle(title_alignment="left", legend_location="outside right")
    apply_chart_style(figure, style)
    legend = axis.get_legend()
    assert legend is not None
    assert axis.get_title(loc="left") == "Aligned title"
    assert style_for_figure(figure).legend_location == "outside right"
