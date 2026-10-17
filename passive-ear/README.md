# PEBBLE P0 — passive earbud research package

**Independent concept. BENCH ONLY. Not a validated hearing aid; do not wear the supplied printed parts.**

A compact outer-ear body with an open acoustic taper and a compliant collar/fin. No batteries, electronics, behind-ear hook, or inserted canal nozzle. Inspired by the user's earbud-form brief and publicly described Amano work, not a reconstruction of Amano's mechanism.

![CAD-derived view](docs/images/cad-perspective.png)

## Open first

- **[Illustrated engineering dossier (PDF)](docs/PEBBLE-P0.pdf)**
- [Full documentation, ear-acoustics research, safety, cost, manufacturing, and test plan](docs/DESIGN.md)
- [Visual project page](index.html)
- [Local photo-sizing tool](phone/index.html)
- [Native editable CAD](cad/pebble.scad) · [Body STL](cad/shell.stl) · [Cradle STL](cad/cradle.stl)
- [Build report](cad/build-report.json) · [Verification record](docs/VERIFICATION.md)
- [Complete package](PEBBLE-P0-package.zip)

Default rigid body: **18 W × 24 H × 12 D mm**. Cradle/fin assembly envelope: 20.4 × 30.6 × 12 mm. Estimated mass: 2.93 g from assumed densities. The default dimensions are illustrative, not a patient's measurements.

## Reproduce

From the repository root, with Python 3.11+:

```sh
python -m venv .venv
.venv/bin/pip install -r passive-ear/requirements.txt
.venv/bin/python passive-ear/tools/build.py
.venv/bin/python passive-ear/tools/render.py
.venv/bin/python -m unittest discover -s passive-ear/tests -v
node passive-ear/tests/test_phone.cjs
.venv/bin/python passive-ear/tools/booklet.py
```

To customize the bench model from the phone tool's downloaded dimensions:

```sh
.venv/bin/python passive-ear/tools/build.py --fit /path/to/fit.json --output /path/to/custom-cad
```

Use an output folder outside `cad/` to keep the default figures and report consistent. `render.py` renders the default `cad/` folder only. `pebble.scad` is also independently editable in OpenSCAD; choose `part` = `assembly`, `shell`, `cradle`, `exploded`, or `section`. STL files have millimetre coordinates but no embedded unit declaration. There is no STEP file.

Serve the project and sizing page:

```sh
.venv/bin/python -m http.server 8080 --bind 0.0.0.0 --directory passive-ear
```

The photo tool also opens directly from disk in many browsers. It uses manual calibrated landmarks, not AI; no photograph is uploaded. It cannot infer hidden canal geometry or a safe insertion depth. Individual geometry changes require acoustic retesting.

## Important boundaries

- **No measured positive insertion gain.** The short passage is not established as speech-tuned; it may attenuate useful sound. CAD validates shape, not hearing benefit.
- **$1 = a speculative US-dollar, per-ear, high-volume factory cost target.** The illustrative budget is $0.80 at 100,000 units, based on unquoted assumptions. Unique custom 3D printing, clinical/regulatory work, shipping, and retail margin are not included. $1 custom delivered is not demonstrated.
- Production lip fillets, biological evaluation, safe depth/standoff, retention, cleaning, acoustic testing, and tooling design remain unfinished.
- The actual CAD includes an approximately 0.15 mm radial interference between the rigid and compliant parts; overlap represents an intended elastic fit, not two rigid parts to force together.
- All included product pictures are geometry-derived or labeled schematics. No AI photograph or patient image is used.
- The tests are geometric/software tests, not clinical, material, acoustic, or regulatory certification.

The repository's original profile README is preserved. This project is isolated under `passive-ear/`.
