# Optimization and Inverse Design

## Purpose

The Optimization workspace turns fitted response models into material-selection tools. It supports
multi-objective trade-offs and target-based scenario ranking while retaining prediction uncertainty,
training-range checks, and surrogate validation metrics.

## Surrogate inputs

Select the fields considered by the response surrogates. Decision variables should also be available
as surrogate inputs when the underlying response data support them. Other selected fields remain fixed
at fitted median or modal values during a search.

Available methods:

- Gaussian Process
- Forest Ensemble

A separate surrogate is fitted for each unique objective, constraint, or target response. Grouped
cross-validation by mix identity is used when enough groups are available.

### Response-specific predictor adaptation

Different test families may legitimately leave some fields blank. For example, AAS:B may be recorded
for variable-activator compressive-strength tests but absent from flexural-strength rows. GPC-DTwin
therefore checks predictor availability separately for each response:

- usable predictors are retained for that response surrogate;
- predictors containing no usable value in that response subset are omitted only from that surrogate;
- the search continues when at least one predictor remains;
- used and omitted predictors are recorded in the Surrogate validation table and saved metadata.

The software does not impute an entirely absent response-specific field. It removes that unsupported
field transparently while retaining it for other responses where measurements exist.

## Pareto optimizer

### Objectives

Each response can be maximized or minimized. Positive weights are used only to rank a recommended
compromise; Pareto dominance itself is not replaced by a weighted sum.

### Constraints

A response may be constrained to be at least or at most a selected threshold. Feasible scenarios
dominate infeasible scenarios. When no feasible scenario is available, the search returns the least
violating front for review.

### Decision variables

Each variable has an editable lower and upper bound. Bounds should remain within a domain supported
by the active dataset. When binder closure is enabled, FA, GGBS, and SF must all be decision variables
and their bounds must permit a total of 100%.

### Search procedure

The search uses Latin-hypercube initialization, simulated binary crossover, polynomial mutation,
constraint-aware NSGA-II non-dominated sorting, and crowding-distance selection. Prediction
uncertainty can be included as a penalty so that remote or weakly supported scenarios are less
competitive.

### Outputs

- Pareto solution table
- final population table
- surrogate-validation table
- response-specific used and omitted predictors
- constraint violation
- feasibility status
- compromise score
- response estimates and intervals
- reliability class
- Pareto figure
- normalized solution-profile figure

## Inverse design

Targets use one of three relations:

- At least
- At most
- Closest

The ranking combines normalized target deviation, target weights, uncertainty penalty, reliability
penalty, and range penalty. A diversity filter selects alternatives that are not merely repeated copies
of the highest-ranked scenario.

## Reliability

Reliability classes summarize the worst class across all fitted responses used in a scenario:

- A — close to available observations with low uncertainty
- B — supported with moderate uncertainty
- C — limited nearby support
- D — outside the fitted range, remote from observations, or highly uncertain

Reliability does not replace physical testing. It indicates how strongly the active dataset supports a
computed scenario.

## Saved runs

Saved files are stored in `models/optimizations` and include:

- a Joblib run file,
- JSON metadata,
- solution CSV,
- surrogate-validation CSV.

The Run Library can load or delete these files.
