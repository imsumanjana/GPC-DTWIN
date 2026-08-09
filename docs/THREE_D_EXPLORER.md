# 3D Explorer

The 3D Explorer now has two deliberately different scientific roles:

1. **Response Surface** — visualization of the active Digital Twin in predictor/design space;
2. **Physics-Informed Specimen** — theory-based visualization in physical specimen coordinates.

## Response Surface

The Response Surface does **not train a new surrogate**. It requires an active Digital Twin and evaluates that exact artifact over two selected numeric axes. The header reports the active twin response, selected algorithm, prediction rank/status, and confidence level.

Available surface modes are:

- Estimated response
- Relative uncertainty
- Prediction interval width
- Reliability landscape

The grid can include observation overlays, a surface mesh, and a contour projection. Camera presets and manual elevation/azimuth controls are provided. Grid data can be exported as CSV and figures can be exported using the common high-resolution figure engine.

### Reliability interpretation

- **A** — close to available observations with low uncertainty;
- **B** — supported with moderate uncertainty;
- **C** — limited nearby support;
- **D** — outside the fitted range or weakly supported.

A high predicted response should therefore be considered together with uncertainty and reliability rather than interpreted as an optimum by itself.

## Physics-Informed Specimen

The old sine-wave/normalized synthetic cube has been removed. Specimen fields are now calculated from explicit mechanics or transport theory and carry provenance stating how the field was produced.

### Compression cube

Geometry: 150 × 150 × 150 mm cube.

Available fields:

- nominal applied compressive stress;
- compressive stress utilisation;
- capacity margin.

The first implementation deliberately uses ideal concentric uniaxial loading, so nominal `P/A` stress is spatially uniform. It does not invent non-uniform stress without a stated boundary/contact model.

### Splitting tensile cylinder

Geometry: 150 mm diameter × 300 mm length cylinder.

Available fields:

- nominal splitting tensile stress;
- nominal tensile utilisation.

The calculation uses the standard specimen-level relation `f_t = 2P/(πLD)`. It is explicitly labelled as a nominal field and is not presented as a full elastic-contact/Hondros reconstruction.

### Flexural beam

Geometry: 100 × 100 × 500 mm beam with 400 mm support span and symmetric third-point loading.

Available fields:

- longitudinal bending stress;
- tensile utilisation;
- compressive utilisation;
- flexural failure index.

The field is calculated from the bending moment distribution and `σ = My/I`. This produces a physically meaningful tensile/compressive gradient and neutral axis.

### Acid degradation cube

Geometry: 150 × 150 × 150 mm cube.

Available fields:

- acid penetration;
- damage index;
- residual strength;
- strength retention.

Penetration is calculated using a finite-slab Fickian diffusion solution. The effective diffusivity is an explicit user/model assumption. When matching initial and acid-exposed strength records are available, the global degradation magnitude is calibrated so the volume-average strength retention agrees with the experiment. The internal penetration profile remains a theory-calculated field, not a measured tomography result.

## Capacity source and field provenance

Bulk capacity can come from the active Digital Twin when its response matches the selected specimen analysis. Otherwise a mix-level experimental mean is used. Every specimen result reports:

- geometry and dimensions;
- capacity value and capacity source;
- field source;
- number of supporting records;
- modelling assumptions.

Typical provenance labels include **Theory calculated**, **Theory + Digital Twin**, and **Diffusion theory + experimentally calibrated global strength loss**.

No internal CT, voxel, crack, or spatial NDT measurement is claimed unless such coordinate-resolved measurements are actually imported in a future workflow.

## Comparison-safe colour scales (v1.2.1)

The 3D Response Surface reads fixed colour limits from the active Digital Twin. Estimated response, relative uncertainty, and interval-width colours therefore retain the same numerical meaning when the X/Y axes are changed.

Physics-Informed Specimen fields no longer normalize each mix independently. Stress/capacity fields use a scale derived from all compatible mixes in the active dataset; utilisation, damage, penetration, and retention fields use fixed physical bounds. The selected colour limits and their basis are also written into exported specimen-field CSV data.
