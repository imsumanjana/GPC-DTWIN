# User Guide

## Overview

The Overview page presents record counts, mix coverage, measurement groups, review flags, quality findings, and summary charts.

## Data Explorer

Use the search field and Mix, Group, and Status filters to narrow the dataset. The Essential fields toggle hides extended metadata without deleting it. Select a row and assign a status to record the review outcome.

## Quality Check

The quality engine checks identifiers, duplicate records, binder totals, numerical ranges, required group values, dataset metadata, composition labels, and durability calculations. It reports findings without changing the stored data.

## Visual Analytics

Select a chart and, where applicable, a mix. Figures can be exported as PNG, PDF, SVG, or TIFF.

## Statistical Analysis

Descriptive statistics report count, central tendency, spread, quartiles, missing values, and coefficient of variation. Correlation supports Pearson and Spearman methods. Group comparison uses one-way ANOVA and reports F, p, and eta-squared. Regression uses grouped cross-validation by mix whenever enough distinct mixes are available.

## Predictive Models

Choose a response, predictors, and algorithms, then select Compare models. The ranking is based on cross-validated RMSE, with MAE used as the next comparison. Diagnostics show observed versus predicted values and residuals. Feature influence uses permutation importance.

The Prediction tab applies the selected model to a single scenario or all compatible rows in the active dataset. The Model library stores reusable model files and matching metadata in `models/trained`.

Records marked EXCLUDED are never used. Records marked REQUIRES_REVIEW or CONFLICTING are omitted by default and can be included explicitly.

## Digital Twin

Select a response and predictors, choose Gaussian Process or Forest Ensemble, and build the twin.
Review cross-validated interval coverage before using scenario estimates. The Prediction tab shows
confidence bounds and reliability classes. The Response Maps tab varies two fitted numeric inputs and
keeps other inputs at fitted defaults. Saved twins are available in the Twin Library.

## 3D Explorer

The Response Surface tab varies two numeric inputs across the fitted domain and displays estimated
response, relative uncertainty, prediction-interval width, or reliability class as a rotatable 3D
surface. Use the observation overlay to compare fitted terrain with available measurements. Camera
presets and manual view angles are provided.

The Specimen Field tab creates an estimated field inside a 150 mm cube using aggregate property
values for the selected mix. The view is a normalized visual representation, not a spatial scan or
internal tomography result. Surface grids, specimen fields, and figures can be exported.

## NDT and Durability

### NDT fusion

Choose the destructive-strength reference group, age, curing filter, and regression algorithm. Include
review-marked records only when their use is understood. Select Compare NDT input sets to rank UPV,
rebound, composition, and combined inputs. Use the view selector for observed-versus-estimated,
residual, and RMSE charts. Save the best model when its validation is acceptable.

### NDT estimate

Use the active best model or load a saved model. Enter available NDT and composition values. The
active model uses only the fields in its fitted input set. Review the reliability class and range note
with the estimated compressive strength.

### Durability profile

Set strength-retention and mass-stability weights, then select Calculate profile. The ranking table,
score chart, initial-versus-residual chart, retention heatmap, and mass-change heatmap can be exported.
The score formula is displayed beside the controls.

### Durability estimator

Select a response, method, confidence level, and predictor fields. Build the estimator and review
cross-validated RMSE, R², and interval coverage. Scenario estimates report confidence bounds and
reliability. The response-curve tool varies a numeric predictor over its fitted range.

## Import and export

Use Import CSV to replace the active local dataset after confirmation. Use Export CSV to save the current database records. A blank compatible template is available in `data/templates`.

## Optimization and Inverse Design

### Pareto optimizer

Select surrogate inputs, then configure objectives, optional constraints, and decision-variable bounds.
Use binder closure when FA, GGBS, and SF should total 100%. Choose the surrogate method, confidence
level, population, generation count, uncertainty penalty, and random seed before starting the search.

The Pareto Front tab displays ranked non-dominated solutions and a trade-off figure. Solution Profiles
shows normalized decision variables and objective responses. Final Population includes feasible and
constraint-limited candidates. Surrogate Validation reports cross-validated performance for every
response model used by the search.

The first solution is the highest-ranked compromise for the selected objective weights. Review its
response intervals, range flags, reliability class, and surrogate metrics before applying it.

### Inverse design

Enable one or more response targets, select At least, At most, or Closest, and assign a target weight.
Inverse design uses the surrogate inputs, decision-variable bounds, method, uncertainty penalty, and
binder-closure setting from the Pareto optimizer tab. The result table ranks diverse alternatives by
design loss and target satisfaction.

### Run library

Save either result type to retain fitted surrogates and result tables. Saved runs are stored in
`models/optimizations` and can be reloaded from the Run Library.

## Active Learning

Select a response, uncertainty method, predictors, experiment variables, bounds, and acquisition
strategy. The recommendation table reports uncertainty, reliability, novelty, expected improvement,
and acquisition score. Use Experiment Plan export to create a compatible CSV with blank measured
response fields. After testing, enter measured results, review the data status, append the completed
CSV, and evaluate the model update. Saved runs are stored in `models/active_learning`.

## Figure export and scrolling

All exported figures use a square 6 × 6 inch canvas at 600 dpi. Dense pages and control panels show
scrollbars when their natural dimensions exceed the available area.

