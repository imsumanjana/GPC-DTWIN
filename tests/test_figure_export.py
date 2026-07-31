from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure
from PIL import Image

from gpc_dtwin.figure_export import (
    EXPORT_DPI,
    EXPORT_DPI_OPTIONS,
    EXPORT_SIZE_INCHES,
    export_profile,
    save_square_figure,
)


def test_square_default_dpi_png_and_canvas_restoration(tmp_path):
    figure = Figure(figsize=(9.0, 4.0), dpi=100, constrained_layout=True)
    axis = figure.add_subplot(111)
    axis.plot([0, 1, 2], [0, 1, 0])
    original_size = tuple(figure.get_size_inches())
    original_dpi = figure.dpi

    destination = save_square_figure(figure, tmp_path / "square.png")
    with Image.open(destination) as image:
        expected_pixels = int(EXPORT_SIZE_INCHES * EXPORT_DPI)
        assert image.size == (expected_pixels, expected_pixels)
        dpi = image.info.get("dpi", (0, 0))
        assert abs(float(dpi[0]) - EXPORT_DPI) < 1.0
        assert abs(float(dpi[1]) - EXPORT_DPI) < 1.0

    assert tuple(figure.get_size_inches()) == original_size
    assert figure.dpi == original_dpi


def test_export_quality_profiles_cover_requested_dpi_values():
    assert EXPORT_DPI_OPTIONS == (150, 300, 600, 1200, 2400)
    for dpi in EXPORT_DPI_OPTIONS:
        profile = export_profile(dpi)
        assert profile.dpi == dpi
        assert profile.pixel_size == int(EXPORT_SIZE_INCHES * dpi)


def test_low_resolution_export_uses_selected_quality(tmp_path):
    figure = Figure(figsize=(4, 4), dpi=100)
    figure.add_subplot(111).plot([0, 1], [1, 0])
    destination = save_square_figure(figure, tmp_path / "quality_150.png", dpi=150)
    with Image.open(destination) as image:
        assert image.size == (900, 900)
        dpi = image.info.get("dpi", (0, 0))
        assert abs(float(dpi[0]) - 150) < 1.0


def test_all_interactive_figure_actions_use_quality_dialog():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    direct_savefig_locations = []
    quality_dialog_users = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "open_figure_export_dialog" in text and path.name != "export_preview_dialog.py":
            quality_dialog_users.append(str(path.relative_to(root)))
        if ".savefig(" in text and path.name != "figure_export.py":
            direct_savefig_locations.append(str(path.relative_to(root)))
    assert len(quality_dialog_users) >= 8
    assert direct_savefig_locations == []


def test_native_matplotlib_save_actions_use_quality_toolbar():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin" / "ui"
    raw_toolbar_users = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "NavigationToolbar2QT" in text and path.name != "export_preview_dialog.py":
            raw_toolbar_users.append(str(path.relative_to(root)))
    assert raw_toolbar_users == []
