# Publication Graphics System

GPC-DTwin uses one styling engine for on-screen figures and exported figures. The same serialized
`ChartStyle` object is reapplied immediately before export, so the saved result follows the active
font, legend, line, marker, axis, tick, grid, colour, and layout settings.

## Precedence

When a chart canvas appears, the effective style is selected in this order:

1. saved chart override;
2. saved workspace override;
3. saved application style;
4. the built-in Times New Roman default.

This ordering allows one unusual chart to be adjusted without changing the rest of the workspace,
while a workspace or application preset can still provide consistency.

## Persistence

Application and workspace styles, chart overrides, and custom preset definitions are stored through
`QSettings`. No style controls are written into the analytical dataset, and style changes do not alter
model inputs or numerical outputs.

## Export policy

All figure exports use the shared `save_square_figure` function:

- 6 × 6 inch canvas;
- selectable 150–2400 dpi;
- 3600 × 3600 raster pixels;
- no tight-cropping step that would change the square aspect ratio;
- restoration of the original interactive canvas size and dpi after saving.

Supported suffixes are PNG, PDF, SVG, TIF, and TIFF.

## Tabbed outputs

Tabbed figure groups are movable, non-stretching, scroll-preserving, expandable, and able to export one
or all tabs. Each tab assigns a stable chart key so the active chart style can be remembered after the
figure is regenerated.
