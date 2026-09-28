# UGS-SYNTH-D01 v1.1 - underground gas storage surface facilities design

Complete engineering design for the six published operating scenarios of benchmark case
`UGS-SYNTH-D01` (version `1.1.0-development`), covering process architecture, equipment
selection and count, operating philosophy, layout, safety provisions, maintenance access,
roads, the pipeline network, quantities and lifecycle cost.

All published inputs are synthetic benchmark assumptions taken from `brief/`; they are not
vendor data, production engineering criteria or code-compliance guidance.

## Headline results

| Item | Result |
|---|---|
| Lifecycle cost (published objective) | **87.9620 MBCU** (equipment 28.84 + piping 1.84 + civil/access 0.22 + energy PV 46.79 + maintenance PV 10.28) |
| Installed equipment | 21 instances across 9 catalogue models |
| Pipelines | 36 port-to-port pipelines, 5 424 m of pipe |
| Normal operating scenarios | 6 of 6 deliver the required flow, pressure, temperature, water and free-liquid limits with zero exceptions |
| Reliability (N-1) cases | 30 of 30 (compressor outages in every compression scenario, separator and dehydration outages in every withdrawal scenario) clean, each delivering at least 70 % of the scenario flow |
| Roads | 1 406 m of road centreline in one connected network containing ROAD-ENTRANCE |
| Validator self-check | 10 of 10 deliberate design mutations detected |

## Design in one paragraph

Gas enters at GRID-TIE (6.5 MPa, dry) through an inlet meter, is compressed by a three-unit
bank (2 x C60 + 1 x C40, sized so that 70 % of the largest flow is still deliverable with
any one unit out; the two C60 units carry normal duty and the C40 is held isolated for the
reliability cases), cooled to at most 58 degC, and distributed through a well manifold over
six hydraulically balanced DN300 flowlines to the well groups at exactly their required
pressure. In withdrawal service the same six flowlines gather into the same manifold and
are handled by the same compressor bank - running only in the low-pressure scenario and
passing unloaded otherwise - before three parallel separation + dehydration trains remove
liquid and water down to 35 mg/Sm3; a delivery regulator then holds the grid tie at exactly
6.000 MPa ahead of the outlet meter. Each separator has its own closed drain to the liquid
outfall. Four roads connect every heavy-maintenance envelope to the ROAD-ENTRANCE. The
layout, routes, classes and setpoints are all listed in the deliverables below.

## Repository layout

```
brief/                      published case data (read only)
project/tools/              calculation and reporting code
  engine.py                 catalogues, gas properties, pipe hydraulics, plan-view geometry
  design.py                 the proposed design: every equipment instance, pipeline route, road
  checks_geom.py            layout, separation, maintenance-access, road and route checks
  process.py                scenario cases, process propagation, setpoints, limit checks
  costing.py                quantities take-off and lifecycle-cost build-up
  selftest.py               validator self-check (deliberate mutation tests)
  report.py, report_template.py, build.py   deliverable generation
project/deliverables/       final deliverables (see the index in design_report.md)
```

Reproduce every number with:

```
python3 project/tools/build.py          # rewrites project/deliverables/
```

The build recomputes all hydraulics, checks and costs from `brief/` and is deterministic.

## Key deliverable files

| File | What it defines |
|---|---|
| `deliverables/design_report.md` | full design report: basis, architecture, equipment selection, operating philosophy, layout, piping, quantities, LCC, assumptions, limitations |
| `deliverables/equipment_register.json` / `.csv` | every instance: catalogue model, category, position, orientation, capacity, cost, maintenance flags, port coordinates |
| `deliverables/process_topology.json` | external interfaces, exclusion zones, corridors and every pipeline with endpoint ports, diameter, class, routing levels and route coordinates |
| `deliverables/scenario_operations.json` | per scenario: active equipment, setpoints, pipeline flows and hydraulics, equipment operating points, delivered conditions, energy |
| `deliverables/well_group_allocations.csv` | per-scenario well-group flow allocation |
| `deliverables/reliability_cases.json` | all 30 N-1 cases with retained flow, surviving capacity and results |
| `deliverables/quantities.json`, `deliverables/lcc.json` | quantities take-off and the lifecycle-cost breakdown |
| `deliverables/validation_report.md`, `validation_results.json` | every check performed, its outcome and the validator mutation self-check |
| `deliverables/layout.svg` | plan view: site, exclusion zones, corridors, roads, equipment and pipeline routes |

## Principal assumptions

The full list is in section 11 of the design report. The five that most affect the design
are: `required_sink_pressure_mpa` is treated as a minimum delivery pressure (the design
nevertheless delivers exactly the required pressure everywhere); isolation and check valves
are not catalogue components and are therefore specified as an operating line-up; the
compressor units run unloaded as passive pass-through elements in the two withdrawal
scenarios that need no pressure lift, with the share between them set by their bypass
line-up; the well flowlines and the three treatment trains are solved as passive hydraulic
balances while compressor duty sharing is a control setpoint; and liquid-drain velocity is
checked with the only published density formulation (the gas proxy) in the declared 1.0 MPa
drain domain, which is why the drain lines are DN200.
