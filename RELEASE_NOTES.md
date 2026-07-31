# GPC-DTwin 1.0.1 Release Notes

GPC-DTwin 1.0 is the first stable release of the desktop materials-analytics platform. It combines
structured experimental-data management, quality checks, statistical analysis, predictive models,
uncertainty-aware digital twins, 3D visualization, NDT fusion, durability assessment, optimization,
inverse design, active learning, and reproducible reporting in one local application.

## Maintenance corrections in 1.0.1

- Active-learning experiment plans remain editable under pandas 3.x when numeric laboratory results are entered into initially blank response fields.
- SQLite database restoration uses the SQLite backup API, avoiding Windows access-denied errors caused by replacing an active database file.
- Automated tests suppress only the known upstream joblib/NumPy shape deprecation warning.


## Release guarantees

- Compatible 44-field CSV import and export.
- Local SQLite persistence with backup and restore.
- Square 600 dpi analytical-figure export.
- Scrollable workspaces and control panels.
- Stable per-user storage in packaged Windows builds.
- Automated service, interface, health, archive, and wording checks.
- Copyright and ORCID attribution throughout the application and generated reports.

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169
