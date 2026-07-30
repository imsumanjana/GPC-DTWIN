# Data Schema

The compatible CSV contains 44 fields grouped into these areas:

- Record identity: record ID, record group, dataset origin, data block, data locator
- Mix identity: mix ID and FA:GGBS:SF label
- Binder composition: FA, GGBS, and silica-fume percentages and quantities
- Aggregate and activator quantities
- Activator ratio, AAS:B ratio, and superplasticizer dosage
- Curing regime, temperature, duration, and test age
- Exposure conditions
- Workability, mechanical, NDT, and durability measurements
- Data status and notes

The exact header order is provided in `data/templates/GPC_Dataset_Template.csv`.

## Status values

- IMPORTED
- IMPORTED_WITH_DERIVED_VALUES
- VERIFIED
- VERIFIED_WITH_ASSUMPTION
- REQUIRES_REVIEW
- CONFLICTING
- EXCLUDED

Blank cells are permitted where a measurement does not apply to a record group. Required values are checked according to the record group.
