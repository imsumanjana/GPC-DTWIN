# GPC-DTwin 1.1.5 Release Notes

## Regression correction

- Fixed the `object too deep for desired array` failure in grouped statistical regression.
- Deduplicated grouping fields when a group identifier is also selected as a predictor.
- Normalized cross-validation group arrays to one dimension.
- Hardened numeric and categorical preprocessing for missing values and empty folds.

## Universal automatic parameter exclusion

- Response-incompatible selected fields are excluded automatically rather than terminating a valid workflow.
- A warning popup lists every excluded parameter after a successful run.
- Requested, used, and omitted fields are recorded in analytical metadata where applicable.
- Applied to statistical regression, predictive models, digital twins, 3D surfaces, durability estimators, optimization surrogates, and active learning.
- Predictor lists in regression and Digital Twin disable unavailable fields when the response changes.

## Figure export quality popup

- Every user-triggered figure export now opens a preview and quality selector.
- Available quality options: 150, 300, 600, 1200, and 2400 dpi.
- Every output remains square at 6 × 6 inches.
- Batch figure export asks for one common format and quality before saving all tabs.
- High-resolution selections display an export-time and memory warning.

Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169

## Previous release details

# GPC-DTwin 1.1.4 Release Notes

## Tab-line correction

- Removed the full-width separator line from every primary and nested tab row.
- Retained the short blue accent beneath the selected tab.
- Removed the negative tab offset that could visually expose a line above a tab row.

## Compact analytical toolbars

- Added one reusable, horizontally scrollable result toolbar.
- Combined metrics, view selectors, map selectors, and result actions into one row.
- Replaced text-heavy export and save buttons with icon-only controls.
- Added complete tooltips and accessible names to every compact action.
- Applied the compact toolbar to Predictive Models, Digital Twin, 3D Explorer,
  NDT and Durability, Optimization, and Active Learning.
- Narrow windows receive horizontal toolbar scrolling instead of wrapped or compressed controls.

Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169

## Previous release details

# GPC-DTwin 1.1.3 Release Notes

## Unified Data Explorer

- Data Explorer, Quality Check, Visual Analysis, and Statistical Analysis now share one primary workspace.
- The four functions are available through separate tabs.
- The sidebar no longer repeats the three analytical data pages.
- Data-menu shortcuts open the requested Data Explorer tab directly.
- Existing saved page indexes are migrated to the new ten-workspace navigation layout.
- All four tabs continue to use the same active dataset and existing services.

## Predictive-model compatibility correction

- Predictor availability is evaluated for the currently selected response.
- Fields with no usable response-overlapping values are disabled automatically.
- Unavailable selected predictors are omitted instead of stopping model comparison.
- Used and omitted predictors are recorded in result metadata and shown in the interface.
- A clear message remains when none of the selected predictors can support the response.
- Grouped cross-validation, saved models, diagnostics, and prediction workflows are preserved.

Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169

## Previous release details

# GPC-DTwin 1.1.2 Release Notes

## Workspace header and tab-line correction

Version 1.1.2 corrects the page hierarchy identified during Windows UI review.

- Keeps the main top-bar title and subtitle as the single workspace identity.
- Removes the repeated title-and-description block inside all thirteen workspaces.
- Removes the unwanted rule drawn above primary and nested tab rows.
- Restores one subtle baseline below each tab row.
- Retains the selected-tab accent, scrollable response maps, figure tabs, and chart-style controls.
- Keeps the Quality Check action accessible at the top right without repeating its title.
- Retains the Qt event-loop compatibility correction from version 1.1.1.

## Interface result

The hierarchy is now:

1. main application top bar;
2. workspace tabs or primary controls;
3. workspace content.

There is no second header directly beneath the main top bar.

Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169

## Previous 1.1.1 release detail


# GPC-DTwin 1.1.1 Release Notes

## Qt event-loop compatibility correction

Version 1.1.1 removes an invalid reference to `QEvent.Type.Destroy`, which is
not available in the supported PyQt6/Qt runtime. The chart-style overlay now
discovers event enum members defensively and responds only to supported
resize, show, polish, and parent-change events.

The patch also:

- prevents repeated exceptions in the Qt event loop;
- safely ignores events received while a native chart canvas is closing;
- tolerates Qt wrappers whose native objects have already been deleted;
- preserves the complete v1.1 chart styling, export, scrolling, optimization,
  digital-twin, and reporting capabilities.


## Previous 1.1 feature summary


Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169

## Application-wide publication graphics

Version 1.1.1 promotes the chart controls introduced in 1.0.2 into a persistent application-wide
publication-graphics system.

### Style presets and persistence

- Adds Publication Colour, Publication Monochrome, Presentation, High Contrast, and Minimal presets.
- Adds locally stored custom named presets.
- Persists style overrides at chart, workspace, or application scope.
- Allows a chart to return to its workspace style.
- Allows all saved chart, workspace, and application overrides to be reset from the chart icon dialog.

### Expanded chart controls

- Adds title visibility, title alignment, title padding, label padding, and annotation styling.
- Adds outside-left, outside-right, above, below, and custom anchored legend positions.
- Adds legend frame colour, border colour, border width, columns, opacity, size, and boldness.
- Adds reusable series palettes, including colour-blind, high-contrast, pastel, and monochrome choices.
- Adds axis margins, layout padding, and colour-bar visibility.

### Figure management

- Makes multi-figure tabs reorderable and non-stretching.
- Adds compact expand, export-current, and export-all actions to tabbed figure groups.
- Adds an export preview that reports the fixed dimensions and common clipping risks.
- Retains square 6 × 6 inch export at 600 dpi and 3600 × 3600 raster output.
- Makes Digital Twin response-map canvases square on screen at a natural 720 × 720 pixel size.
- Adds horizontal and vertical response-map scrolling when the available viewport is smaller.

## Interface corrections

- Removes the full-width horizontal rule beneath tab bars throughout the application.
- Keeps only the selected-tab accent so page hierarchy remains clear without a misplaced divider.
- Preserves natural chart and control dimensions rather than compressing oversized content.

## Optimization compatibility

- Adapts predictor fields separately for each objective, constraint, and inverse-design target.
- Automatically omits a selected predictor when that response family contains no usable values for it.
- Records used and omitted predictors in the surrogate-validation table and saved metadata.
- Allows mixed-response searches such as compressive and flexural strength even when AAS:B is
  available only for one response family.

## Native Windows stability

- Replaces the application-wide chart event filter with timer-based canvas discovery.
- Detaches chart helpers before native Qt and Matplotlib widgets are destroyed.
- Reuses Optimization canvases instead of deleting native widgets while paint events may be queued.
- Enables software rendering and Python native fault diagnostics by default.
- Pins the PyQt wrapper and Qt runtime to matching 6.11.0 builds.
- Installs a tested dependency lock and uses single-worker ensemble fitting for deterministic GUI stability.
- Writes native launch diagnostics to `.runtime/native-crash.log`.
- Adds an explicit diagnostic message for Windows exit code `-1073741819`.

## Stability retained

- Retains explicit response-map row and column coordinates.
- Retains 100 × 100 response-map support.
- Retains one-dimensional response fallback for unsuitable two-axis combinations.
- Retains pandas 3.x active-learning compatibility and Windows-safe SQLite restoration.
