# P0 verification record

Date: 18 October 2026. This record describes **software and CAD checks only**.

## Executed successfully

- Default mesh build with `tools/build.py`.
- 12 Python unit tests: default dimensions; positive-volume watertight single-body shell and cradle; left/right mirroring; size-window and non-finite-value rejection; minimum/maximum window builds; sampled bore containment; through-hole topology; intended elastic interference volume; exported cutaway volume; customization tokens in native CAD.
- Node-based tests against the actual inline photo-tool script: calibrated 28 × 22 mm example; export disabled until repeat-photo confirmation; left-ear metadata; out-of-envelope rejection; tiny/empty scale rejection; incomplete landmark rejection; static absence of remote uploads/persistent image storage.
- Five illustrations generated from exported mesh geometry or explicitly labeled schematic projections.
- PDF generated and inspected via extracted text and selected rendered pages. Default dossier contains 14 pages at the time of this check.

## Geometry facts from executed default build

- Rigid envelope: 18 × 24 × 12 mm.
- Complete envelope: approximately 20.4 × 30.6 × 12 mm.
- Body volume: 2,840.70 mm³; cradle volume: 342.42 mm³.
- Estimated mass: 2.933 g from assumed material densities.
- Both separate part meshes are watertight and positive volume. Their intentional interference means the undeformed assembled meshes overlap; this is an elastic-fit hypothesis, not a rigid Boolean assembly.

## Not performed / not established

- No physical printing, fitting, human testing, acoustic measurement, FEM/BEM simulation, diaphragm development, clinical efficacy testing, material biological testing, durability test, mold trial, or supplier quotation.
- No shortest-distance wall certification, production edge fillet implementation, enforced outlet/canal standoff, anatomical ear registration, or safe-retention verification.
- Native OpenSCAD source was not independently rendered. Python-generated STL geometry is the tested reference.
- Photo-tool logic was tested with a minimal DOM mock under Node, **not full browser automation**. Image decoding, camera permissions, mobile layout, touch interaction, and file download behavior were not tested on physical phones.
- The provisional photo-size window is not anthropometric validation. The second-photo confirmation is a human attestation, not automated repeatability detection.
- Positive insertion gain, a safe clinical output, $1 custom production, regulatory compliance, and lifespan are not established.

Re-run instructions are in `../README.md`. Passing these tests does not make the object suitable for human wear.
