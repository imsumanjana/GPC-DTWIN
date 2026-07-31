"""Application-wide publication graphics styling for Matplotlib figures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from typing import Any

from matplotlib import colormaps
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.container import BarContainer, ErrorbarContainer
from matplotlib.figure import Figure
from matplotlib.text import Text


@dataclass(slots=True)
class ChartStyle:
    """Serializable appearance settings shared by display and export."""

    font_family: str = "Times New Roman"
    title_size: int = 15
    label_size: int = 12
    tick_size: int = 10
    legend_size: int = 10
    annotation_size: int = 10
    title_bold: bool = True
    label_bold: bool = False
    tick_bold: bool = False
    legend_bold: bool = False
    annotation_bold: bool = False
    title_visible: bool = True
    title_alignment: str = "center"
    title_pad: float = 8.0
    label_pad: float = 6.0

    legend_visible: bool = True
    legend_location: str = "best"
    legend_columns: int = 1
    legend_frame: bool = True
    legend_frame_alpha: float = 0.90
    legend_border_width: float = 0.8
    legend_anchor_x: float = 1.02
    legend_anchor_y: float = 1.00
    legend_face_color: str = "#ffffff"
    legend_edge_color: str = "#404040"

    line_width: float = 1.8
    line_style: str = "preserve"
    marker_style: str = "preserve"
    marker_size: float = 6.0
    marker_edge_width: float = 0.8
    series_alpha: float = 0.90
    series_color: str = ""
    series_palette: str = "Preserve"

    spine_width: float = 1.0
    tick_width: float = 1.0
    tick_length: float = 4.0
    tick_direction: str = "out"
    x_tick_rotation: int = 0
    y_tick_rotation: int = 0
    minor_ticks: bool = False
    axes_margin_x: float = 0.05
    axes_margin_y: float = 0.05

    major_grid: bool = True
    minor_grid: bool = False
    grid_style: str = "--"
    grid_width: float = 0.6
    grid_alpha: float = 0.25

    figure_background: str = "#ffffff"
    axes_background: str = "#ffffff"
    text_color: str = "#111111"
    axis_color: str = "#202020"
    grid_color: str = "#8a8a8a"
    colormap: str = "Preserve"
    colorbar_visible: bool = True
    layout_padding: float = 0.04

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> "ChartStyle":
        if not values:
            return cls()
        permitted = {field.name for field in fields(cls)}
        clean = {key: value for key, value in values.items() if key in permitted}
        return cls(**clean)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, value: str | None) -> "ChartStyle":
        if not value:
            return cls()
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return cls()
        return cls.from_dict(parsed if isinstance(parsed, dict) else None)


DEFAULT_CHART_STYLE = ChartStyle()


def _is_colorbar_axis(axis: Axes) -> bool:
    return bool(getattr(axis, "_colorbar", None)) or axis.get_label() == "<colorbar>"


def _axis_has_colorbar(figure: Figure, axis: Axes) -> bool:
    for candidate in figure.axes:
        colorbar = getattr(candidate, "_colorbar", None)
        if colorbar is not None and getattr(getattr(colorbar, "mappable", None), "axes", None) is axis:
            return True
    return False


def _meaningful_label(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text and not text.startswith("_"))


def _ensure_artist_labels(axis: Axes) -> None:
    """Supply restrained fallback labels so ordinary charts always support legends."""
    used: set[str] = set()
    for artist in [*axis.lines, *axis.collections, *axis.containers]:
        label = getattr(artist, "get_label", lambda: "")()
        if _meaningful_label(label):
            used.add(str(label))

    errorbar_children: set[object] = set()
    for container in axis.containers:
        if isinstance(container, ErrorbarContainer):
            stack = list(container.lines)
            while stack:
                item = stack.pop()
                if isinstance(item, (tuple, list)):
                    stack.extend(item)
                elif item is not None:
                    errorbar_children.add(item)

    line_index = 1
    for line in axis.lines:
        if line in errorbar_children or _meaningful_label(line.get_label()):
            continue
        x = list(line.get_xdata(orig=False))
        y = list(line.get_ydata(orig=False))
        if len(x) >= 2 and len(x) == len(y) and all(
            abs(float(a) - float(b)) < 1e-12 for a, b in zip(x, y)
        ):
            label = "Reference"
        elif str(line.get_linestyle()) in {"--", ":", "-."}:
            label = "Reference"
        else:
            label = "Series" if line_index == 1 else f"Series {line_index}"
            line_index += 1
        while label in used:
            label = f"{label} {line_index}"
            line_index += 1
        line.set_label(label)
        used.add(label)

    collection_index = 1
    for collection in axis.collections:
        if collection in errorbar_children or _meaningful_label(collection.get_label()):
            continue
        if _axis_has_colorbar(axis.figure, axis):
            continue
        label = "Observations" if isinstance(collection, PathCollection) else "Data"
        if label in used:
            collection_index += 1
            label = f"{label} {collection_index}"
        collection.set_label(label)
        used.add(label)

    for container in axis.containers:
        if _meaningful_label(container.get_label()):
            continue
        label = "Estimate ± interval" if isinstance(container, ErrorbarContainer) else "Values"
        if label in used:
            continue
        container.set_label(label)
        used.add(label)

    if not used and axis.patches and not _axis_has_colorbar(axis.figure, axis):
        axis.patches[0].set_label("Distribution")


def _legend_kwargs(style: ChartStyle) -> dict[str, Any]:
    common: dict[str, Any] = {
        "ncol": max(int(style.legend_columns), 1),
        "frameon": style.legend_frame,
        "framealpha": float(style.legend_frame_alpha),
        "prop": {
            "family": style.font_family,
            "size": style.legend_size,
            "weight": "bold" if style.legend_bold else "normal",
        },
    }
    positions: dict[str, tuple[str, tuple[float, float]]] = {
        "outside right": ("upper left", (1.02, 1.0)),
        "outside left": ("upper right", (-0.02, 1.0)),
        "outside top": ("lower center", (0.5, 1.02)),
        "outside bottom": ("upper center", (0.5, -0.12)),
        "custom": ("center", (float(style.legend_anchor_x), float(style.legend_anchor_y))),
    }
    if style.legend_location in positions:
        location, anchor = positions[style.legend_location]
        common.update(loc=location, bbox_to_anchor=anchor, borderaxespad=0.0)
    else:
        common.update(loc=style.legend_location)
    return common


def _style_legend(axis: Axes, style: ChartStyle) -> None:
    existing = axis.get_legend()
    if not style.legend_visible:
        if existing is not None:
            existing.remove()
        return
    if _is_colorbar_axis(axis) or _axis_has_colorbar(axis.figure, axis):
        if existing is not None:
            existing.remove()
        return
    _ensure_artist_labels(axis)
    handles, labels = axis.get_legend_handles_labels()
    filtered = [(handle, label) for handle, label in zip(handles, labels) if _meaningful_label(label)]
    if not filtered:
        return
    handles, labels = zip(*filtered)
    legend = axis.legend(handles, labels, **_legend_kwargs(style))
    if legend is not None:
        legend.set_in_layout(True)
        frame = legend.get_frame()
        frame.set_linewidth(style.legend_border_width)
        frame.set_facecolor(style.legend_face_color)
        frame.set_edgecolor(style.legend_edge_color)
        for text in legend.get_texts():
            text.set_color(style.text_color)


def _palette_values(name: str, count: int) -> list[Any]:
    if name == "Preserve" or count <= 0:
        return []
    if name == "Monochrome":
        return ["#111111"] * count
    cmap_name = {
        "Colour blind": "tab10",
        "Classic": "tab10",
        "Pastel": "Set2",
        "High contrast": "Dark2",
    }.get(name, name)
    try:
        cmap = colormaps[cmap_name]
    except KeyError:
        return []
    return [cmap(index / max(count - 1, 1)) for index in range(count)]


def _apply_series_palette(axis: Axes, style: ChartStyle) -> None:
    if style.series_color:
        colours = [style.series_color] * max(len(axis.lines), len(axis.collections), 1)
    else:
        colours = _palette_values(style.series_palette, len(axis.lines) + len(axis.collections))
    if not colours:
        return
    cursor = 0
    for line in axis.lines:
        line.set_color(colours[cursor % len(colours)])
        cursor += 1
    for collection in axis.collections:
        if getattr(collection, "get_array", lambda: None)() is not None:
            continue
        try:
            collection.set_color(colours[cursor % len(colours)])
            cursor += 1
        except (TypeError, ValueError):
            pass
    for container in axis.containers:
        if isinstance(container, BarContainer):
            colour = colours[cursor % len(colours)]
            for patch in container.patches:
                patch.set_facecolor(colour)
            cursor += 1


def apply_chart_style(
    figure: Figure,
    style: ChartStyle | dict[str, Any] | None = None,
    *,
    redraw: bool = False,
) -> Figure:
    """Apply a complete chart style to an existing Matplotlib figure."""
    if isinstance(style, dict):
        style = ChartStyle.from_dict(style)
    style = style or ChartStyle.from_dict(getattr(figure, "_gpc_chart_style", None))

    figure.set_facecolor(style.figure_background)
    try:
        if figure.get_constrained_layout():
            engine = figure.get_layout_engine()
            if engine is not None and hasattr(engine, "set"):
                engine.set(
                    w_pad=max(style.layout_padding, 0.0),
                    h_pad=max(style.layout_padding, 0.0),
                )
    except (AttributeError, TypeError, ValueError):
        pass

    for axis in figure.axes:
        colorbar_axis = _is_colorbar_axis(axis)
        if colorbar_axis:
            axis.set_visible(style.colorbar_visible)
            if not style.colorbar_visible:
                continue
        axis.set_facecolor(style.axes_background)

        title_location = style.title_alignment if style.title_alignment in {"left", "center", "right"} else "center"
        title_text = axis.get_title(loc="center") or axis.get_title(loc="left") or axis.get_title(loc="right")
        for location in ("left", "center", "right"):
            axis.set_title("", loc=location)
        title = axis.set_title(
            title_text, loc=title_location, pad=style.title_pad,
            fontfamily=style.font_family, fontsize=style.title_size,
            fontweight="bold" if style.title_bold else "normal",
            color=style.text_color,
        )
        title.set_visible(style.title_visible)

        axis_labels = [axis.xaxis.label, axis.yaxis.label]
        if hasattr(axis, "zaxis"):
            axis_labels.append(axis.zaxis.label)
        for label in axis_labels:
            label.set_fontfamily(style.font_family)
            label.set_fontsize(style.label_size)
            label.set_fontweight("bold" if style.label_bold else "normal")
            label.set_color(style.text_color)
        axis.xaxis.labelpad = style.label_pad
        axis.yaxis.labelpad = style.label_pad
        if hasattr(axis, "zaxis"):
            axis.zaxis.labelpad = style.label_pad

        tick_labels = [*axis.get_xticklabels(), *axis.get_yticklabels()]
        if hasattr(axis, "get_zticklabels"):
            tick_labels.extend(axis.get_zticklabels())
        for tick in tick_labels:
            tick.set_fontfamily(style.font_family)
            tick.set_fontsize(style.tick_size)
            tick.set_fontweight("bold" if style.tick_bold else "normal")
            tick.set_color(style.text_color)
        for tick in axis.get_xticklabels():
            tick.set_rotation(style.x_tick_rotation)
        for tick in axis.get_yticklabels():
            tick.set_rotation(style.y_tick_rotation)

        axis.tick_params(
            axis="both", which="major", width=style.tick_width,
            length=style.tick_length, direction=style.tick_direction,
            labelsize=style.tick_size, colors=style.axis_color,
        )
        if hasattr(axis, "zaxis"):
            axis.tick_params(
                axis="z", which="major", width=style.tick_width,
                length=style.tick_length, direction=style.tick_direction,
                labelsize=style.tick_size, colors=style.axis_color,
            )
        if style.minor_ticks:
            axis.minorticks_on()
        else:
            axis.minorticks_off()
        axis.tick_params(
            axis="both", which="minor", width=max(style.tick_width * 0.8, 0.1),
            length=max(style.tick_length * 0.6, 0.1), direction=style.tick_direction,
            colors=style.axis_color,
        )
        try:
            axis.margins(x=max(style.axes_margin_x, 0.0), y=max(style.axes_margin_y, 0.0))
        except (TypeError, ValueError):
            pass

        for spine in axis.spines.values():
            spine.set_linewidth(style.spine_width)
            spine.set_color(style.axis_color)

        if not colorbar_axis:
            if style.major_grid:
                axis.grid(
                    True, which="major", linestyle=style.grid_style,
                    linewidth=style.grid_width, alpha=style.grid_alpha, color=style.grid_color,
                )
            else:
                axis.grid(False, which="major")
            if style.minor_grid:
                axis.grid(
                    True, which="minor", linestyle=style.grid_style,
                    linewidth=max(style.grid_width * 0.75, 0.1),
                    alpha=max(style.grid_alpha * 0.75, 0.0), color=style.grid_color,
                )
            else:
                axis.grid(False, which="minor")

        for line in axis.lines:
            current_style = str(line.get_linestyle()).strip().lower()
            if style.line_style != "preserve" and current_style not in {"none", "", " "}:
                line.set_linestyle(style.line_style)
            line.set_linewidth(style.line_width)
            if style.marker_style != "preserve":
                line.set_marker("None" if style.marker_style == "none" else style.marker_style)
            line.set_markersize(style.marker_size)
            line.set_markeredgewidth(style.marker_edge_width)
            line.set_alpha(style.series_alpha)

        for collection in axis.collections:
            collection.set_alpha(style.series_alpha)
            if isinstance(collection, PathCollection):
                collection.set_linewidths(style.marker_edge_width)
            elif isinstance(collection, LineCollection):
                collection.set_linewidths(style.line_width)
            if hasattr(collection, "set_cmap") and style.colormap != "Preserve":
                try:
                    collection.set_cmap(style.colormap)
                except (TypeError, ValueError):
                    pass
        for patch in axis.patches:
            try:
                patch.set_linewidth(style.marker_edge_width)
            except (AttributeError, TypeError, ValueError):
                pass
        for image in axis.images:
            if style.colormap != "Preserve":
                try:
                    image.set_cmap(style.colormap)
                except (TypeError, ValueError):
                    pass

        _apply_series_palette(axis, style)
        for annotation in axis.texts:
            annotation.set_fontfamily(style.font_family)
            annotation.set_fontsize(style.annotation_size)
            annotation.set_fontweight("bold" if style.annotation_bold else "normal")
            annotation.set_color(style.text_color)
        _style_legend(axis, style)

    if figure._suptitle is not None:
        figure._suptitle.set_fontfamily(style.font_family)
        figure._suptitle.set_fontsize(style.title_size)
        figure._suptitle.set_fontweight("bold" if style.title_bold else "normal")
        figure._suptitle.set_color(style.text_color)
    for text in figure.findobj(match=Text):
        text.set_fontfamily(style.font_family)
        text.set_color(style.text_color)

    setattr(figure, "_gpc_chart_style", style.to_dict())
    if redraw and figure.canvas is not None:
        figure.canvas.draw_idle()
    return figure


def style_for_figure(figure: Figure) -> ChartStyle:
    return ChartStyle.from_dict(getattr(figure, "_gpc_chart_style", None))
