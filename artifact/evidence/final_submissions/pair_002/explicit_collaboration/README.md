# UGS-SYNTH-D01 — underground gas storage surface facilities

Design package for the UGS-SYNTH-D01 v1.1 benchmark case. Everything here is
derived from the published brief data; no external data is used.

## Result

**LCC = 89.285 MBCU** — equipment CAPEX 29.390, piping CAPEX 1.894,
civil/access 0.254, energy PV 47.270 (40 122 MWh/a), maintenance PV 10.476 —
with **6 678 published-rule checks evaluated and 0 failures** (all six operating
scenarios plus every single-unit-outage case).

## Deliverables

| file | content |
|---|---|
| `DESIGN_REPORT.md` | design report: basis, architecture, equipment selection, layout, piping, operating philosophy, quantities, lifecycle cost, assumptions and limitations |
| `deliverables/design.json` | machine-readable design: equipment instances and catalog model IDs, positions/orientations/ports, physical topology, pipeline routes (vertices, diameter, pipe class and installation level per segment), road network, and every scenario plan (flows, split, setpoints, computed node pressures/temperatures/quality, energy) |
| `deliverables/verification.md` | rule-by-rule verification summary (scenario setpoints, N-1 demonstration, LCC, quantities, checks by area) |
| `deliverables/checks.csv` | the full list of evaluated checks with result and detail |
| `deliverables/layout.svg` | plan view (site, exclusion zones, corridors, equipment footprints, roads, pipeline routes by installation level, legend) |
| `deliverables/diameters.json` | optimised pipeline diameters |

## Tools

The tools implement the published v1.1 calculation and geometry basis and run
with the standard library only.

| file | content |
|---|---|
| `tools/ugs_basis.py` | gas properties, pipe hydraulics (published fixed-point convention), equipment models, polygon geometry, cost factors |
| `tools/ugs_check.py` | design model, connection/geometry/road/route verification, hydraulic march primitives |
| `tools/ugs_operate.py` | operating plan for every scenario (normal and single-unit-outage), scenario march and limit checks |
| `tools/ugs_cost.py` | pipeline service conformance, quantities, lifecycle-cost assembly |
| `tools/build.py` | builds, verifies and writes `design.json`, `verification.md`, `checks.csv`, `layout.svg` |
| `tools/optimize.py` | coordinate-descent optimisation of pipeline diameters against the LCC (all scenarios, including outage cases, constrained by the velocity limits) |
| `tools/make_report.py` | regenerates `DESIGN_REPORT.md` |
| `tools/crosscheck.py` | independent re-derivation of hydraulics, geometry, costs and mass balance from `design.json` |

## Reproduce

```
python tools/build.py          # writes the deliverables/ artefacts (prints PASS/FAIL + LCC)
python tools/optimize.py       # re-optimises pipeline diameters (writes deliverables/diameters.json)
python tools/make_report.py    # regenerates DESIGN_REPORT.md
python tools/crosscheck.py     # independent cross-checks of the exported design
```

## Design in one paragraph

GRID-TIE is connected to six well groups through one custody meter per flow
direction, a shared three-machine compressor set (2 × C60 + 1 × C40, sized by the
compression N-1 rule), a single aftercooler and a buried injection trunk that
also acts as the well manifold feeder. Withdrawal gas is collected in three
parallel trunks, separated (3 × SEP70) and dehydrated (3 × DEHY70) in three
independent trains that satisfy the treatment N-1 rule, then delivered through a
pressure regulator and the withdrawal meter; the low-pressure withdrawal
scenario (WDR-LOW) is boosted by the same compressor set through two valved
cross-connections. Separator liquids drain through one closed drain per train to
the public outfall. The plant is served by a road network connected to
ROAD-ENTRANCE with crane access to the compressor removal envelopes.
