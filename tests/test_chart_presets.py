from __future__ import annotations

from gpc_dtwin.chart_presets import BUILT_IN_PRESETS, preset_names, preset_style
from gpc_dtwin.chart_style import ChartStyle


def test_builtin_presets_are_complete_and_independent():
    required = {
        "Publication colour", "Publication monochrome", "Presentation",
        "High contrast", "Minimal",
    }
    assert required.issubset(set(preset_names()))
    first = preset_style("Publication colour")
    second = preset_style("Publication colour")
    assert isinstance(first, ChartStyle)
    assert first is not second
    first.title_size = 99
    assert second.title_size != 99


def test_monochrome_and_presentation_presets_have_expected_purpose():
    mono = BUILT_IN_PRESETS["Publication monochrome"]
    presentation = BUILT_IN_PRESETS["Presentation"]
    assert mono.series_palette == "Monochrome"
    assert mono.major_grid is False
    assert presentation.title_size > ChartStyle().title_size
    assert presentation.line_width > ChartStyle().line_width
