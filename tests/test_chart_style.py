from __future__ import annotations

from matplotlib.figure import Figure

from gpc_dtwin.chart_style import ChartStyle, apply_chart_style, style_for_figure


def test_default_chart_style_uses_times_new_roman_and_legends():
    figure = Figure(figsize=(6, 6), constrained_layout=True)
    axis = figure.add_subplot(111)
    axis.plot([0, 1, 2], [1, 3, 2])
    axis.set_title("Response")
    axis.set_xlabel("Input")
    axis.set_ylabel("Output")

    apply_chart_style(figure)

    assert "Times New Roman" in axis.title.get_fontfamily()
    assert "Times New Roman" in axis.xaxis.label.get_fontfamily()
    assert axis.get_legend() is not None
    assert axis.lines[0].get_linewidth() == ChartStyle().line_width
    assert style_for_figure(figure).font_family == "Times New Roman"


def test_custom_chart_style_controls_lines_ticks_grid_and_legend():
    figure = Figure(figsize=(6, 6), constrained_layout=True)
    axis = figure.add_subplot(111)
    axis.plot([0, 1], [0, 1], label="Estimate")
    style = ChartStyle(
        title_size=18,
        label_size=13,
        tick_size=11,
        legend_size=12,
        legend_location="upper left",
        legend_columns=1,
        line_width=3.2,
        line_style=":",
        marker_size=8.0,
        spine_width=1.7,
        tick_width=1.4,
        tick_length=7.0,
        tick_direction="inout",
        x_tick_rotation=25,
        major_grid=True,
        grid_width=1.1,
        grid_alpha=0.4,
    )
    apply_chart_style(figure, style)

    assert axis.lines[0].get_linewidth() == 3.2
    assert axis.lines[0].get_linestyle() == ":"
    assert axis.get_legend() is not None
    assert axis.get_legend()._loc == 2  # upper left
    assert all(spine.get_linewidth() == 1.7 for spine in axis.spines.values())
    assert style_for_figure(figure).x_tick_rotation == 25


def test_errorbar_legend_is_not_duplicated_by_child_artists():
    figure = Figure(figsize=(6, 6), constrained_layout=True)
    axis = figure.add_subplot(111)
    axis.errorbar([1, 2, 3], [2, 3, 4], yerr=[0.2, 0.3, 0.2], fmt="o")
    axis.plot([1, 3], [1, 3], linestyle="--", label="Reference")
    apply_chart_style(figure)
    labels = axis.get_legend_handles_labels()[1]
    assert "Estimate ± interval" in labels
    assert labels.count("Estimate ± interval") == 1
    assert len(labels) <= 2

def test_default_style_preserves_unconnected_errorbar_markers():
    figure = Figure(figsize=(6, 6))
    axis = figure.add_subplot(111)
    container = axis.errorbar(
        [1, 2, 3], [2, 3, 4], yerr=[0.2, 0.3, 0.2], fmt="o",
        label="Estimate ± interval",
    )

    apply_chart_style(figure, ChartStyle())

    marker_line = container.lines[0]
    assert str(marker_line.get_linestyle()).lower() in {"none", ""}

