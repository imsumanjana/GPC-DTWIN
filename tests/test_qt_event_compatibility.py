from pathlib import Path


def test_chart_overlay_does_not_reference_unsupported_destroy_event():
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "gpc_dtwin"
        / "ui"
        / "chart_style_dialog.py"
    ).read_text(encoding="utf-8")

    assert "QEvent.Type.Destroy" not in source
    assert "_CANVAS_REPOSITION_EVENT_TYPES" in source
    assert 'getattr(QEvent.Type, name, None)' in source
