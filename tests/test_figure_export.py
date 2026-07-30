from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure
from PIL import Image

from gpc_dtwin.figure_export import EXPORT_DPI, EXPORT_SIZE_INCHES, save_square_figure


def test_square_600_dpi_png_and_canvas_restoration(tmp_path):
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


def test_all_figure_actions_use_common_export_helper():
    root = Path(__file__).resolve().parents[1] / "src" / "gpc_dtwin"
    savefig_locations = []
    helper_imports = 0
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "save_square_figure" in text and path.name != "figure_export.py":
            helper_imports += 1
        if ".savefig(" in text and path.name != "figure_export.py":
            savefig_locations.append(str(path.relative_to(root)))
    assert helper_imports >= 8
    assert savefig_locations == []
