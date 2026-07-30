# 3D Explorer

The 3D Explorer provides two complementary views of compatible geopolymer-concrete data.

## Response surface

The response-surface view fits an uncertainty-aware surrogate model and evaluates it across two
selected numeric variables. Available surface modes are:

- Estimated response
- Relative uncertainty
- Prediction interval width
- Reliability landscape

The fitted grid can include observation overlays, a surface mesh, and a contour projection.
Camera presets and manual elevation and azimuth controls are provided. Grid data can be exported
as CSV, and figures can be exported as PNG, PDF, SVG, or TIFF.

### Reliability interpretation

- **A**: close to available observations with low uncertainty
- **B**: supported with moderate uncertainty
- **C**: limited nearby support
- **D**: outside the fitted range or weakly supported

The displayed surface is a model estimate. Reliability and uncertainty should be considered before
using a region for material selection.

## Specimen field

The specimen-field view creates a normalized field inside a 150 mm cube using aggregate property
values for the selected mix. It supports full-volume, half-volume, center-slice, and octant-cutaway
views.

The field is an estimated visual representation. It is not a spatial scan, internal tomography result,
or measured crack map. Coordinate-based NDT or imaging data are required for a measured internal
field.

## Recommended use

1. Review data quality before fitting a surface.
2. Select variables with adequate numeric coverage.
3. Prefer regions with reliability A or B.
4. Compare estimated response and uncertainty surfaces together.
5. Export the grid when independent calculations or reporting are required.
