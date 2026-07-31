# GPC-DTwin v1.1.5 Validation Summary

## Scope

This release adds persistent publication-graphics presets, chart/workspace/application style scopes,
advanced legend placement, export preview, enhanced tabbed figure management, square scrollable
Digital Twin maps, response-specific Optimization predictor adaptation, and native Windows shutdown
safeguards.

## Packaging-environment checks

- 79 Python source and test files passed syntax compilation.
- 78 non-GUI automated tests passed across the complete service and source-validation suite.
- The PyQt-dependent database-context and GUI checks remain included for the Windows environment.
- Built-in preset independence and expected preset behavior are tested.
- Chart-style JSON round trips include all 1.1.1 fields.
- Outside and custom legend placement paths are tested.
- Export-profile tests verify 6 × 6 inches, 600 dpi, and 3600 × 3600 raster dimensions.
- Response-map tests verify explicit grid dimensions, 100 × 100 generation, and one-dimensional fallback.
- A regression test verifies that AAS:B is omitted only from response families where it is blank,
  without cancelling the complete Optimization search.
- Source checks verify that no rule is drawn above tab rows and that the lower baseline is present.
- Source checks verify square fixed response-map canvases with horizontal and vertical scrollbars.
- Source checks verify timer-based chart discovery, orderly shutdown, software rendering, matching
  PyQt/Qt versions, the pinned dependency stack, single-worker ensembles, fault diagnostics, and
  access-violation reporting.
- Response-map, modelling, NDT, durability, Optimization, active-learning, reporting, and 3D services
  retain automated coverage.

## Windows interface checks included

The Windows release check requires the installed PyQt6 environment and verifies:

- all thirteen workspaces open successfully;
- all workspaces remain scrollable;
- chart canvases expose their palette icon;
- figure tabs are reorderable and do not stretch unnecessarily;
- square response-map hosts retain equal width and height;
- scrollbars appear when a square map exceeds the available viewport;
- figure groups expose expand, current-export, and export-all controls;
- chart canvases retain readable minimum dimensions;
- screenshots can be captured at 1024 × 720, 1366 × 768, and 1920 × 1080;
- the application health check confirms matching compiled and runtime Qt versions;
- the application closes without a native access-violation exit.

Run the complete Windows validation with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

## Copyright

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169


## 1.1.1 Qt compatibility regression

- No source reference to `QEvent.Type.Destroy`.
- Supported chart repositioning events are resolved with `getattr`.
- Deleted Qt wrappers are handled without propagating runtime exceptions.
- Windows GUI smoke execution is retained in `release_check.ps1`.


## 1.1.2 workspace hierarchy checks

- All thirteen workspace constructors were checked for duplicate direct page headers.
- The main top bar remains the sole workspace title and subtitle.
- The tab widget frame has no top rule.
- The tab bar retains one lower baseline and the selected-tab accent.
- The Windows GUI smoke test checks that no direct `SectionHeader` remains on a workspace root.


## 1.1.3 Data Explorer consolidation

- Ten primary workspaces are created.
- The Data Explorer contains four tabs: records, quality, visual analysis, and statistical analysis.
- Sidebar duplicates for the three merged pages are absent.
- Existing navigation settings are migrated from the former thirteen-page layout.

## 1.1.3 predictive-model correction

- Response-incompatible predictors are identified from response-overlapping rows.
- Unavailable fields are omitted without failing a valid model comparison.
- Omitted predictors are reported in result and artifact metadata.
- Predictors with valid overlap remain available for grouped cross-validation.


## 1.1.4 tab and toolbar checks

- Global tab styling contains no full-width tab-bar border.
- The active-tab accent remains available.
- Compact toolbars use one horizontal layout and horizontal overflow scrolling.
- Icon actions expose tooltips and accessible names.
- Six major analytical workspace modules use the compact toolbar.

## 1.1.5 regression and field-compatibility checks

- Grouped regression accepts the group identifier as a predictor without creating a two-dimensional group array.
- Response-incompatible acid, mass, and exposure fields are omitted from mechanical-strength regression.
- Digital Twin builds continue with compatible predictors and report omitted fields.
- Active-learning and durability workflows inherit the same response-aware exclusion policy.
- Warning and metadata paths preserve the list of omitted parameters.

## 1.1.5 figure-export quality checks

- Supported quality values are exactly 150, 300, 600, 1200, and 2400 dpi.
- Export profiles preserve a 6 × 6 inch square canvas at every quality.
- Raster pixel dimensions scale from 900 × 900 to 14400 × 14400.
- All interactive page-level figure actions route through the quality/preview dialog.
- Batch figure-tab export uses one selected DPI for every exported tab.
