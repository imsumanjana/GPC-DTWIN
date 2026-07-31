# Figure Export

Every user-triggered figure export opens a preview and quality popup before the file is written.

## Output geometry

- Canvas: 6 × 6 inches
- Aspect ratio: square
- Quality options: 150, 300, 600, 1200, and 2400 dpi
- Raster dimensions: 900 × 900, 1800 × 1800, 3600 × 3600, 7200 × 7200, or 14400 × 14400 pixels
- Formats: PNG, PDF, SVG, TIFF, and TIF where supported

The preview reports the selected pixel dimensions and warns that 1200 and 2400 dpi exports may require substantial memory and time. Interactive figure dimensions are restored after saving.

## Single-figure export

The export dialog provides format and DPI selectors together with a square preview and clipping guidance. The selected quality is passed to the common export engine.

## Tabbed and batch export

Exporting the current figure tab opens the same preview and quality popup. Exporting all tabs asks for the destination folder, common format, and common quality once, then writes one square file per tab.

## Automated report figures

Report generation remains reproducible and uses the default 600 dpi profile unless a future report-specific option is introduced.
