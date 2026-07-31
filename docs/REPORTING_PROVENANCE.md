# Reports and Provenance

The Reports & Provenance workspace creates a portable record of the active project state.

## HTML report

A generated report directory contains:

- `GPC_DTwin_Report.html`
- `active_dataset.csv`
- `quality_findings.csv`
- `manifest.json`
- a `figures` folder when analytical figures are selected

The report summarizes data coverage, verification states, quality findings, stored analytical
artifacts, environment information, and the active dataset fingerprint.

## Manifest

The JSON manifest records:

- application name and version,
- generation time in UTC,
- copyright and ORCID attribution,
- Python and package versions,
- dataset and quality-finding fingerprints,
- record, field, mix, and measurement-group counts,
- selected report options,
- stored-artifact inventory,
- file sizes and SHA-256 values.

## Reproducibility bundle

A reproducibility bundle is a ZIP archive containing the complete report directory and a short
README. The verification tab recalculates each listed file fingerprint and compares it with the
manifest. A bundle passes only when every listed file has the expected size and SHA-256 value.

## Figures

Report figures use the shared export engine. Every exported figure is square, 6 × 6 inches, and
600 dpi. PNG output is 3600 × 3600 pixels.

## Attribution

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169
