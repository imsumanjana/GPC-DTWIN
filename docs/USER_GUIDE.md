# User Guide

## Starting the application

Run `scripts/run.ps1` after setup. The application opens the local database and loads the bundled
reference dataset when the database is empty.

## Interface behavior

The navigation panel collapses automatically on narrower windows and can be toggled from the top-left
button or View menu. Every workspace is placed inside a responsive scroll area. Dense control panels,
tables, figures, and long tab sets retain readable natural dimensions and expose scrollbars when needed.
The selected theme, last workspace, sidebar state, and window geometry are preserved.

## Data workflow

1. Import a compatible 44-field CSV from Data Explorer or the main toolbar.
2. Confirm replacement; the application creates an automatic database backup.
3. Run Quality Check and review critical, warning, and information findings.
4. Update verification states where appropriate.
5. Use Visual Analytics and Statistical Analysis for exploratory work.
6. Use Predictive Models, Digital Twin, NDT & Durability, Optimization, and Active Learning as required.
7. Use Reports & Provenance to create a report, manifest, or reproducibility bundle.

## Backup and restore

Use **File → Back up database** to create a manual SQLite backup. Use **File → Restore database** to
restore a compatible backup. The current database is backed up automatically before restoration.

## Reports & Provenance

The report builder accepts a title, project label, and prepared-by name. Optional content includes
analytical figures, a dataset preview, and a stored-artifact inventory. Generated report folders are
kept in the configured report library.

The bundle export writes a ZIP file to the selected location. Bundle verification recalculates file
fingerprints without importing or changing project data.

## Figure export

All figure-export buttons produce square output with selectable 150–2400 dpi quality through the common export engine. Raster
figures are 3600 × 3600 pixels.

## Application check

Open Settings and select **Run application check** to verify bundled resources, writable storage,
database access, schema compatibility, and figure export.

## Copyright and attribution

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169
