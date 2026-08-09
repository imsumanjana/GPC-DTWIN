# GPC-DTwin Architecture

```text
Active experimental dataset / SQLite project state
                         │
                         ▼
                 ApplicationContext
                         │
          ┌──────────────┼────────────────┐
          │              │                │
          ▼              ▼                ▼
 Data / Audit       Analytics /       Predictive
 services           Statistics        Modelling
                                         │
                                  7 shared models
                                         │
                                grouped cross-validation
                                         │
                           dynamic ranking + stability
                                         │
                           #1 Recommended by default
                                         │
                                         ▼
                                  Digital Twin
                                         │
                           selected ranked algorithm
                           + empirical uncertainty
                           + interval calibration
                           + domain distance/ranges
                           + A/B/C/D reliability
                                         │
                         ┌───────────────┴────────────────┐
                         ▼                                ▼
                 3D Response Surface              Physics-Informed
                 (same active twin)                  Specimen
                                                    mechanics /
                                                    diffusion
```

## Shared model registry

`services/model_registry.py` is the single definition of the seven prediction algorithms and their preprocessing pipeline. `ModelingService` and `DigitalTwinService` both consume it.

## Predictive Modelling state

`ApplicationContext` stores the latest validated model comparison and active twin. A model comparison is considered compatible only when response, predictors, review-record policy, grouping, and active dataset state match. Dataset replacement, append, restore, or verification-state changes invalidate both shared states.

## Digital Twin state

The Digital Twin receives the current prediction ranking, selects rank #1 by default, allows a manual override, and adds algorithm-independent empirical uncertainty plus experimental-domain support metrics. A built/loaded twin becomes the `active_twin_artifact`.

## 3D visualization state

The 3D Response Surface consumes `active_twin_artifact` directly and never fits another surrogate. The Physics-Informed Specimen service is separate from plotting: `physics_spatial_service.py` calculates mechanics/transport fields and `visualization_3d_service.py` renders them.

## Data and provenance rules

1. The bundled reference CSV remains read-only source material.
2. Imported records are copied into the project SQLite database.
3. Verification/status updates affect the project database and invalidate stale model state.
4. Results retain response/predictor configuration, source data provenance, validation metrics, and model metadata.
5. Theory-calculated specimen fields are labelled as calculated; aggregate measurements are not presented as spatial scans.
6. Scientific plots are implemented in service layers and independently testable.
7. Figure export uses the common square, quality-selectable export engine.


### Workflow availability gates (v1.2.2)

The GUI now enforces the principal dependency chain: active data → validated Predictive Models comparison → Digital Twin → 3D Explorer. Downstream navigation and dependent result tabs remain disabled until their upstream artifact exists. Dataset or verification-state changes invalidate model/twin state and automatically return the interface to the nearest valid upstream workspace.
