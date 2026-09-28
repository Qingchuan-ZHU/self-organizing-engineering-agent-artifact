# UGS-SYNTH-D01 deliverables

| File | Content |
|---|---|
| `design_report.md` | Design report: basis, architecture, equipment, layout, safety, maintenance access, piping, operating philosophy, quantities, LCC, assumptions and limitations. |
| `design.json` | Machine-readable design: boundaries, equipment instances with model IDs, positions, orientations and ports; every pipeline with endpoints, route, per-segment level, diameter and class; roads; scenario operating paths, flows and setpoints; quantities and the complete LCC breakdown. |
| `validation_report.md` | Automated check list and results against the published tolerances. |
| `layout.svg` | Scaled plan view of the site layout: boundaries, no-build zones, roads, pipelines by installation level, equipment footprints with maintenance envelopes. |

Model source (read-only inputs are `brief/`):

- `project/ugs_lib.py` - published calculation basis: gas properties, pressure-loss fixed-point convention and geometry primitives.
- `project/ugs_design.py` - the proposed design: equipment instances, pipelines and routes, roads, scenario paths and n-1 cases.
- `project/ugs_solve.py` - process solver (mass, pressure, temperature and quality propagation, parallel-unit merge and split).
- `project/ugs_validate.py` - geometry, port, scenario, metering, reliability and LCC checks.
- `project/ugs_build.py` - regenerates the deliverables from the model.

Working tree: the read-only published inputs are in `brief/`; the five model modules listed above sit in the parent directory of this `deliverables/` folder (that whole folder may also be delivered flat, with the modules beside `deliverables/`). The modules locate `brief/` by searching the module directory, its parents and the working directory, so run them from wherever they were delivered.

To reproduce: `python3 ugs_validate.py` (prints the check summary and the LCC) and `python3 ugs_build.py` (rewrites the deliverables).

Headline result: **LCC = 106.071 MBCU**; 670 automated checks, 0 failures.

Scenario performance:

| Scenario | Flow (kg/s) | Control setpoint (MPa) | Delivered (MPa) | Power (MW) |
|---|---:|---:|---:|---:|
| INJ-LOW | 120 | 8.6332 | 8.5500 | 8.108 |
| INJ-MID | 100 | 11.1146 | 11.0500 | 13.027 |
| INJ-HIGH | 75 | 13.6003 | 13.5500 | 13.722 |
| WDR-HIGH | 120 | 6.1740 | 6.0500 | 2.160 |
| WDR-MID | 100 | 6.1450 | 6.0500 | 1.800 |
| WDR-LOW | 70 | 6.1109 | 6.0500 | 6.609 |
