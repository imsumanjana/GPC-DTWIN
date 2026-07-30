# Figure Export

All figure-export actions use the same policy:

- square 6 × 6 inch canvas,
- 600 dpi,
- 3600 × 3600 pixels for PNG and TIFF,
- no tight bounding-box crop that would alter the square aspect ratio,
- restoration of the interactive canvas size after saving.

Supported formats are PNG, PDF, SVG, TIFF, and TIF where listed in the save dialog. Vector formats
retain a square page or viewport while rasterized elements use the configured export resolution.
