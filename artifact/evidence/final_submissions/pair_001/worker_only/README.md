# UGS-SYNTH-D01 v1.1 — design package

Complete engineering design, feasibility checking and lifecycle-cost (LCC)
calculation for the synthetic underground-gas-storage case `UGS-SYNTH-D01`
(benchmark family `UGS-SYNTH`, version `1.1.0-development`).

Everything is recomputed from the read-only assumptions in `brief/`; no value
is hard-coded from a hidden answer.

## Reproduce

```
python project/run.py
```

This rebuilds the physical model, re-runs every check, and regenerates all
artefacts in `design/` plus the report in `report/`.

## Deliverables

| Deliverable (from `brief/final_delivery_contract.json`) | Where |
|---|---|
| Design report (basis, assumptions, results, limitations) | `report/design_report.md` |
| System architecture and process connections | report §2 + `design/equipment_instances.json` |
| Equipment selection and stated capacities | report §3 + `design/equipment_instances.json` |
| Operating philosophy and scenario plans | report §4 + `design/scenarios_operating.json` |
| Site layout, safety provisions, maintenance access | report §5 + `design/layout_roads.json` |
| Piping and network definition | report §6 + `design/pipelines.json` |
| Quantities and lifecycle-cost basis | report §7 + `design/quantities_lcc.json` |
| Feasibility checks (geometry, hydraulics, N-1, classes) | `design/check_summary.json` |

## Source layout

```
project/
  run.py                     entry point
  src/
    build_outputs.py         writes JSON artefacts + report
    ugssynth/
      data.py                loads the brief catalogues/site/scenarios
      physics.py             gas properties + pipe/compressor/regulator correlations
      geometry.py            plan-view polygon/segment helpers
      model.py               equipment instances, pipe routes, roads
      engine.py              network build, checks, scenario solver, LCC, optimiser
  design/*.json              machine-readable design artefacts
  report/design_report.md    human-readable design report
```

## Method summary

1. **Model** — equipment instances are placed as rotated rectangles on the
   `site.json` plan; every gas/liquid connection is an explicit point-to-point
   pipe (with waypoints) between equipment ports and the published boundaries.
   Branching/merging uses catalogued HDR180 headers; the two GRID-TIE
   connections, the well-group limits and the outfall limits are respected.
2. **Checks** — footprints inside the site, outside `equipment_exclusion`
   interiors, non-overlapping, and meeting every published category separation;
   maintenance envelopes inside the site, clear of footprints and serving the
   published road/crane access buffers; routes inside the site and clear of
   `pipeline_exclusion` interiors and footprints; no same-level overlap.
3. **Hydraulics** — gas properties, Swamee–Jain friction and the fixed-point
   outlet-pressure convention are applied per pipe; compressor work, pressure
   ratio, discharge temperature and driver power use the published formulas;
   every capacity, velocity, pressure, temperature, water and free-liquid limit
   is asserted for all six scenarios, plus the compressor and withdrawal
   treatment N-1 reliability rules.
4. **Optimisation** — pipe diameters are chosen by a greedy LCC minimiser
   (upsizing reduces the compressor pressure ratio and saves energy present
   value); the compressor set is the minimum-capex combination that meets the
   compression N-1 rule.

Result: **LCC ≈ 90.28 MBCU** (see `design/quantities_lcc.json`).
