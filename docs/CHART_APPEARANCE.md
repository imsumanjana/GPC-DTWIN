# Chart Appearance

Every analytical chart provides one palette icon in the upper-right corner of its interactive canvas.
The icon opens the complete appearance system. Chart controls are not added to the main menu bar or
workspace toolbars.

## Style scopes

A style can be applied at three persistent levels:

- **Chart** — only the selected figure; the override is remembered for the same chart identity.
- **Workspace** — all figures in the current analytical workspace, including figures created later.
- **Application** — all existing and future figures throughout GPC-DTwin.

**Use workspace style** removes the selected chart override. **Reset saved styles** removes chart,
workspace, and application overrides while retaining custom presets.

## Presets

Built-in presets are:

- Publication Colour
- Publication Monochrome
- Presentation
- High Contrast
- Minimal

Users can create and delete custom named presets from the same icon dialog. Presets are stored locally
through the application settings system.

## Typography

The default chart typeface is Times New Roman. Separate controls are available for:

- title, axis-label, tick-label, legend, and annotation sizes;
- boldness for each text role;
- title visibility and left, centre, or right alignment;
- title and axis-label padding.

## Legends

Ordinary plots receive a legend when a meaningful plotted element is available. Heatmaps, contour maps,
and scalar-mapped surfaces retain their colour bars as the appropriate legend.

Legend controls include:

- show or hide;
- standard in-axis positions;
- outside left, outside right, above, and below positions;
- custom X and Y anchor coordinates;
- number of columns;
- font size and boldness;
- frame visibility, opacity, face colour, edge colour, and border width.

## Series, axes, and layout

The icon dialog controls:

- line width and line style;
- marker type, size, edge width, and opacity;
- one-colour override or reusable series palettes;
- axis-spine width;
- tick width, length, direction, rotation, and minor ticks;
- horizontal and vertical axis margins;
- major and minor grid visibility, style, width, colour, and opacity;
- figure background, plot background, text colour, axis colour, colour map, colour-bar visibility,
  and layout padding.

Error-bar marker semantics are preserved: marker-only intervals are not joined by new connecting lines.

## Figure tabs

Multi-figure results use reorderable tabs with non-stretching tab labels. Each figure group provides
compact icon actions to:

- expand the active figure;
- export the active figure;
- export every tab to a selected directory and format.

One figure remains visible at a time, and the figure host scrolls when the available area is smaller than
the readable chart size.

## Export preview

The Export tab in the appearance dialog opens a square export preview. It reports:

- 6 × 6 inch output size;
- selectable 150, 300, 600, 1200, or 2400 dpi;
- 3600 × 3600 pixels for PNG and TIFF;
- common clipping risks, including outside legends, custom legend anchors, long titles, many axes, and
  strong tick rotation.
