# v0.1 Architecture

```text
PyQt6 user interface
        │
        ▼
ApplicationContext (single project state and Qt signals)
        │
        ├── DataService ── CSV schema validation and normalisation
        ├── AuditService ─ deterministic research-data audit rules
        ├── AnalyticsService ─ reproducible Matplotlib figures
        └── SQLiteRepository ─ persistent 44-column project database
```

## Design rules

1. The bundled CSV is read-only source material.
2. Imported records are copied into a project SQLite database.
3. Record status updates affect SQLite only.
4. Every result retains source document, source table, and source page fields.
5. No predictive result is generated in v0.1.
6. GUI pages react to one central data-changed signal.
7. Scientific plots are implemented in the service layer and are independently testable.
