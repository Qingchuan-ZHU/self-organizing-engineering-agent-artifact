# UGS-SYNTH-D01 — project deliverables

Design of the surface facility for the synthetic underground-gas-storage case
**UGS-SYNTH-D01** (benchmark family UGS-SYNTH, case version 1.1.0-development),
together with the complete operating plan, quantities and lifecycle-cost basis.

## Where to look first

| File | Content |
|---|---|
| `deliverables/design_report.md` | **Main deliverable.** Design basis, architecture, equipment selection, operating philosophy, layout/safety/maintenance, piping, quantities, lifecycle cost, verification, limitations. |
| `deliverables/equipment.json` | Every installed equipment instance: catalogue model, category, position, orientation, rotated footprint corners, maintenance envelopes, all ports with absolute positions and connections, capacities and costs. |
| `deliverables/pipelines.json` | Every physical pipeline: endpoint nodes/ports, plan-view route vertices, segment lengths, installation level, DN, internal diameter, pipe class with rating/roughness/compatibility, description. |
| `deliverables/topology.json` | Physical connection list and every external interface with its connection/flow limits. |
| `deliverables/site_and_roads.json` | Site boundary, no-build zones, routing corridors, road centrelines and paved polygons. |
| `deliverables/operating_plan.json` | Six mandatory scenarios and 30 single-unit n-1 contingency cases: ordered operating path, flows, setpoints, per-element pressures/temperatures/velocities, sink conditions, liquid side streams, energy. |
| `deliverables/quantities.json` | Equipment counts, piping lengths by DN/class/level, areas, road length, energy. |
| `deliverables/lifecycle_cost.json` | Full LCC breakdown (equipment, piping, civil/access, energy PV, maintenance PV) with per-item detail. |
| `deliverables/verification.json`, `deliverables/case_summary.json` | Machine-readable results of every automated check over all 36 operating cases (6 scenarios + 30 outages) and the geometry/topology rule set. |

## Reproducing the numbers

The calculation model is the pure-Python package in `model/`; it reads the
published case data from `../brief` (read-only) and writes `deliverables/`.
No third-party packages are required.

The scripts locate the published case data themselves (via `../brief`), so they
can be run from the project root or from `project/model`:

```
python project/model/checks.py            # geometry / topology / layout rule checks
python project/model/sweep.py             # lifecycle-cost optimisation of diameters
python project/model/run_case.py          # all scenarios + all n-1 cases + rule checks
python project/model/build_deliverables.py  # writes the JSON deliverables
python project/model/build_report.py      # writes deliverables/design_report.md
```

| Module | Responsibility |
|---|---|
| `catalog.py` | Loads the published catalogues, site, scenarios, economics. |
| `geometry.py` | Plan-view geometry: rotated footprints, polygons, distances, clipping, overlap tests. |
| `design.py` | **The design itself**: equipment list with positions/orientations, road centrelines, pipelines with routes, diameters, classes and levels. |
| `process.py` | Published gas-property proxies, Darcy/Swamee-Jain pressure loss with the published fixed-point convention, compressor relations, present-value factor. |
| `scenarios.py` | Element models (header, meter, regulator, cooler, compressor, separator, dehydrator, drain) and the ordered operating paths for injection and withdrawal. |
| `analysis.py` | Case driver: runs a scenario (or an outage case), solves the compressor discharge setpoint, and checks every published limit. |
| `checks.py` | Geometry, layout, separation, maintenance, road, pipeline, cardinality and compatibility rule checks. |
| `quantities.py` | Quantities and lifecycle-cost computation. |
| `sweep.py` | Coordinate-descent optimisation of the pipe diameters against LCC. |
| `run_case.py`, `build_deliverables.py`, `build_report.py` | Case matrix, deliverable writers. |

## Headline result

Lifecycle cost **91.1741 MBCU** (equipment CAPEX 30.49, piping CAPEX 1.85,
civil/access 0.17, energy present value 48.11, maintenance present value 10.55),
annual energy 40 833 MWh, 20 equipment instances, 36 pipelines, all published
limits met in all six mandatory scenarios and all 30 single-unit n-1 contingency
cases (compressor, separator and dehydrator outages in every affected scenario):
0 failures out of 12 158 individual checks.
