# UGS-SYNTH-D01 — surface facility design (v1.1 development case)

Deliverable package for the UGS-SYNTH-D01 synthetic benchmark case.

**Design result: LCC = 87.5201 MBCU**, fully validated against the published
benchmark basis (0 open findings in 14 check groups).

## Contents

| Path | Description |
|---|---|
| `design_report.md` | **Main deliverable** — design basis, assumptions, architecture, operating philosophy, equipment selection, layout, safety/maintenance, piping, quantities, LCC, validation, limitations |
| `data/design.json` | Complete machine-readable design (equipment + absolute port coordinates, roads, every pipeline route and size, scenario operating paths with pressures/temperatures/flows/setpoints, N-1 cases, LCC, quantities, validation) |
| `data/pipe_sizes.json` | Frozen optimised diameter/class selection per pipeline (also written directly into `calc/design.py`, so the design is reproducible without the optimiser) |
| `results/validation.json` | Findings of all 14 check groups |
| `results/scenario_results.json` | Full solved traces for the 6 operating scenarios and all N-1 cases |
| `results/lcc.json` | Lifecycle-cost breakdown |
| `results/quantities.json` | Quantity take-off |
| `calc/` | Calculation code (see below) |

## Reproducing

```bash
cd calc
python validate.py      # runs every check, writes results/*.json, prints the LCC
python export.py        # writes data/design.json
python optimize.py 2    # optional: re-run the pipe diameter/class local search
```

No third-party packages are required (Python standard library only).

## Code map

| Module | Responsibility |
|---|---|
| `ugslib.py` | Brief data loading, tolerances, geometry primitives, gas properties, Darcy/Swamee–Jain pressure loss with the prescribed fixed-point iteration, compressor/cooler/regulator models, present-value factor |
| `design.py` | The design: equipment instances and positions, ports, all 39 pipeline routes and sizes, roads |
| `checks.py` | Geometry, safety separation, maintenance envelope, road network, maintenance access and pipeline route validators |
| `model.py` | Scenario solver (per-scenario flow path, pressure/temperature/water/free-liquid propagation, bank mixing, setpoint solves) |
| `lcc.py` | Lifecycle cost and quantity take-off per the calculation basis |
| `optimize.py` | Local-search optimiser over pipe diameters and classes against the exact LCC |
| `validate.py` | 14 validation groups, LCC, quantities; writes `results/` |
| `export.py` | Writes the complete machine-readable design to `data/design.json` |

## Headline design

* **Architecture** — single bidirectional station between `GRID-TIE` and six well groups;
  separation + dehydration in the withdrawal branch only, after-cooling in the injection
  branch only, with a compressor-station bypass for the withdrawal scenarios that need
  no compression.
* **Equipment** — 2 × `C60` + 1 × `C40` compressors, 3 × `SEP70`, 3 × `DEHY70`,
  1 × `COOL120`, 1 × `REG120`, 2 × `MTR120`, 3 × `DRN-S`, `HDR180` well manifold and
  4 × `HDR120` bank manifolds (21 instances).
* **Piping** — 39 pipelines, 5 601.5 m total, DN150–DN700, ground level,
  CS-WET-100 / CS-WET-160.
* **Roads** — 870.5 m centreline in 4 roads serving `ROAD-ENTRANCE`, the compressors
  (road + crane access) and the separators (road access).
