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

## Import and export

Use Import CSV to replace the active local dataset after confirmation. Use Export CSV to save the current database records. A blank compatible template is available in `data/templates`.

## Digital Twin

Select a response and predictors, choose Gaussian Process or Forest Ensemble, and build the twin.
Review cross-validated interval coverage before using scenario estimates. The Prediction tab shows
confidence bounds and reliability classes. The Response Maps tab varies two fitted numeric inputs and
keeps other inputs at fitted defaults. Saved twins are available in the Twin Library.
