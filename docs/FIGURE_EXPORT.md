# Figure Export

Every chart export uses a shared square export engine.

## Fixed output

- Size: 6 × 6 inches
- Resolution: 600 dpi
- Raster dimensions: 3600 × 3600 pixels
- Supported formats: PNG, PDF, SVG, TIF, and TIFF

The active chart style is reapplied immediately before saving. The interactive figure size and dpi are
restored after export.

## Preview

Open the chart palette icon, select the Export tab, and choose **Preview export**. The preview shows the
fixed output dimensions and reports common clipping risks. Outside legends and custom anchors should be
checked visually before saving.

## Tabbed figure export

A tabbed figure group provides compact actions for the current tab and for every tab. Export-all asks for
a folder and a common output format, then saves one square 600 dpi file per tab using a safe filename.
