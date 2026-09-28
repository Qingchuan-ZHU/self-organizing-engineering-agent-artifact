# UGS-SYNTH-D01 v1.1 - Design deliverables

Underground gas storage station design for the synthetic benchmark case
`UGS-SYNTH-D01` (v1.1.0-development). All input data are the published benchmark
values in `../brief/`; nothing is vendor or production data.

## Deliverables

| Deliverable (final_delivery_contract.json) | Artifact |
|---|---|
| Design report (basis, assumptions, results, limitations) | `REPORT.md` |
| System architecture and process connections | `REPORT.md` s.3 + `design_output.json` (`pipelines`, `header_port_assignments`, `equipment_instances`) |
| Equipment selection and stated capacities | `REPORT.md` s.4 + `design_output.json.equipment_instances` |
| Operating philosophy and scenario plans | `REPORT.md` s.5 + `design_output.json.scenario_results` |
| Site layout, safety, maintenance access | `REPORT.md` s.6 + `ugs_design.py` (`INSTANCES`, `ROADS`) |
| Piping and network definition | `design_output.json.pipelines` (vertices, DN, class, level, length) |
| Quantities and lifecycle-cost basis | `REPORT.md` s.8-9 + `design_output.json.quantities`, `.lcc` |
| N-1 reliability verification | `design_output.json.n_minus_one` |
| Constraint check log | `design_output.json.checks` |

`design_output.json` is the machine-readable master; `REPORT.md` is derived from it.

## Result summary

* 22 equipment instances, 39 pipelines (7 240 m), 5 road sections (1 343 m).
* **LCC = 103.49 MBCU** (equipment 41.59, piping 2.00, civil 0.21, energy PV 46.39, maintenance PV 13.30).
* All geometry / safety / maintenance / road / hydraulic / equipment-limit / N-1 checks pass.

## Code organisation

| File | Role |
|---|---|
| `ugs_core.py` | gas-property + pipe-loss formulas and planar geometry primitives |
| `ugs_design.py` | equipment instances, roads, footprint/port helpers |
| `router.py` | orthogonal A* pipeline router (0.25 m grid, collision + overlap aware) |
| `nets.py` | the 39 physical connections (ports tied to header branch ports) |
| `ugs_analysis.py` | per-scenario hydraulic solver (pressures, temperatures, power, energy) |
| `ugs_lcc.py` | constraint checks, N-1 checks, LCC build-up |
| `nminus1.py` | full-hydraulic N-1 re-solves |
| `optimize_diams.py` | per-link pipe-bore coordinate descent to minimise LCC |
| `build_artifacts.py` | end-to-end build of `design_output.json` |
| `make_report.py` | generates `REPORT.md` from `design_output.json` |
| `validate_geom.py` / `validate_routes.py` / `validate_ports.py` | geometry, route and connection-cardinality validators |

## Reproduce

```
python project/build_routes.py        # regenerate routes.json (deterministic)
python project/optimize_diams.py      # regenerate diam_opt.json (deterministic)
python project/build_artifacts.py     # build design_output.json + run all checks
python project/make_report.py         # build REPORT.md
```
