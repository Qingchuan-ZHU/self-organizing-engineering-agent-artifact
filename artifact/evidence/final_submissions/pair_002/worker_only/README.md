# UGS-SYNTH-D01 v1.1 — Underground gas storage surface facility

Engineering deliverable for benchmark case `UGS-SYNTH-D01` (version `1.1.0-development`);
synthetic benchmark data only, not vendor or production engineering criteria.

## Deliverables (in this directory)

| File | Content |
|---|---|
| `design_report.md` | **Main design report** — basis, architecture, equipment, operating philosophy, layout, piping, quantities, LCC, limitations. |
| `design.json` | Complete machine-readable design: interfaces, equipment instances (position, orientation, ports, envelopes, limits), pipelines (endpoints, diameter, class, level, route), roads, per-scenario operating points, quantities and LCC. |
| `verification.json` | Every constraint assertion evaluated, with pass/fail and detail. |
| `opt_diameters.json` | Result of the pipeline-diameter LCC optimisation. |
| `layout.svg` | Plan-view drawing (site, zones, footprints, maintenance envelopes, roads, pipelines). |

## Reproduce / re-verify

The model is pure Python 3 (standard library only; no third-party packages, no network).

```
python3 verify.py     # rebuild geometry, re-check every constraint, recompute LCC
python3 export.py     # regenerate design.json
python3 report.py     # regenerate design_report.md
python3 main.py       # human-readable diagnostic dump (geometry issues, pipe list, scenarios)
python3 optimize.py   # re-run the diameter optimisation (writes opt_diameters.json)
python3 draw.py       # regenerate layout.svg
```

Source modules:

| File | Role |
|---|---|
| `lib_geom.py` | Geometry primitives (rotated rectangles, convex-polygon intersection area, polygon distance). |
| `ugscat.py` | Loads `brief/*.json`; gas properties (Z, viscosity, density) and pipe pressure-loss model. |
| `design.py` | **The design itself** — equipment list with coordinates/orientations, pipeline list with routes, roads, scenario chains. |
| `solve.py` | Builds the port/pipe geometry and runs all layout & safety geometry checks. |
| `sim.py` | Steady-state scenario simulator (pressures, temperatures, powers, velocities). |
| `verify.py` | Full constraint verification + lifecycle cost. |
| `export.py`, `report.py`, `optimize.py` | Artefact generation and diameter optimisation. |

## Design in one paragraph

Grid gas enters at `GRID-TIE` and, for injection, passes through a metering string (`MTR-I`),
a shared suction header (`HDR-CS`), a three-unit compressor bank (2 × `C60` duty + 1 × `C40`
standby), a shared discharge header (`HDR-CD`), a cooler (`COOL`, outlet 45 °C) and the well
manifold (`HDR-W`) before being distributed at 25 kg/s-or-less to the six well groups. Well gas
returns through the same six pipelines to `HDR-W`, is regulated to 6.5 MPa (`REG-W`), split to
two parallel separator + dehydration trains (`SEP120` + `DEHY120`), recombined in `HDR-T`, and
delivered to the grid through `MTR-O` and `HDR-M`. The `WDR-LOW` scenario (4.5 MPa source) is
boosted through the same compressor bank. Liquid from each separator is routed through a closed
drain (`DRN-1`, `DRN-2`) to `LIQUID-DRAIN-OUTFALL`.

## Headline numbers

* Lifecycle cost (8 %, 20 y): **90.147 MBCU** (equipment 29.220, piping 1.810, civil 0.357,
  energy PV 48.372, maintenance PV 10.388).
* 19 equipment instances, 33 pipelines (5 227.5 m), 2 350 m of road.
* Annual energy 41 056 MWh; all six published scenarios delivered within their limits.
* Constraint checks: **577 / 577 pass**.
