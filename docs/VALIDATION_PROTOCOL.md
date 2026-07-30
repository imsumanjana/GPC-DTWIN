# v0.1 Validation Protocol

## Data ingestion

- Confirm the required 44-column schema.
- Confirm unique non-empty record identifiers.
- Confirm all source rows are imported.
- Confirm source CSV is not modified.

## Deterministic audit

- Binder percentages should sum to 100% when all three are present.
- Negative values are invalid for physical quantities.
- Group-specific response fields must be present.
- Durability percentages are recalculated from source masses and strengths.
- Conflicting status flags are surfaced as audit issues.
- Reported mix labels are compared with numeric percentages.
- Source-document, table, and page fields must be present.

## GUI acceptance

- All pages open without exceptions.
- The table displays all imported rows and columns.
- Filters update the visible row count.
- Verification status can be changed and persists after restart.
- Charts render and export.
- Theme selection persists.
