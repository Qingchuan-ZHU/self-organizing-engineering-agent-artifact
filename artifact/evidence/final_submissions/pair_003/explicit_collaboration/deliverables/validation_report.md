# Validation report - UGS-SYNTH-D01

Every check below is computed from the model in `project/` against the published tolerances of `engineering_calculation_basis.md` (mass flow 1e-5 kg/s, pressure 1e-5 MPa, temperature 1e-4 degC, geometry 1e-6 m, same-level overlap 1e-6 m, velocity 1e-6 m/s, power 1e-6 MW, water 1e-5 mg/Sm3, free liquid 1e-9, LCC 1e-8 MBCU).

| Check area | Checks | Failures |
|---|---:|---:|
| delivery | 63 | 0 |
| equipment | 24 | 0 |
| liquid | 12 | 0 |
| maintenance | 24 | 0 |
| maintenance-access | 13 | 0 |
| metering | 12 | 0 |
| path-coverage | 40 | 0 |
| pipeline | 41 | 0 |
| ports | 127 | 0 |
| reliability | 12 | 0 |
| roads | 2 | 0 |
| safety-separation | 276 | 0 |
| scenario | 24 | 0 |
| **total** | **670** | **0** |

Checks performed:

- **equipment**: every footprint inside the site boundary, outside equipment-exclusion zone interiors, with no positive-area overlap with another footprint.
- **safety-separation**: every equipment pair separated by at least the published matrix value (boundary-to-boundary distance of the rotated footprints).
- **maintenance**: routine clearance envelopes and heavy-maintenance removal envelopes inside the site, outside equipment-exclusion interiors and clear of all other footprints.
- **maintenance-access**: road-access distance <= 7.0 m and crane-access distance <= 4.5 m from the required envelope.
- **roads**: width >= 4 m, paved geometry inside the site, outside road-exclusion interiors, clear of equipment footprints, a single connected network containing ROAD-ENTRANCE.
- **pipeline**: endpoints meet the declared ports, segments non-degenerate, routes inside the site, not entering pipeline-exclusion interiors or equipment footprints, and no same-level positive-length overlap between or within pipelines.
- **ports**: every connection uses a compatible port-type pair in the allowed physical direction, port connection cardinality limits, header branch limits, every separator liquid_out connected to a closed drain, and the outfall connection limit.
- **scenario**: delivered pressure at every sink >= the required sink pressure; well-group boundary flow within limits.
- **delivery**: free-liquid loading, water content and temperature at every sink within the project delivery limits.
- **path-coverage**: every gas pipeline appears in at least one scenario operating path (the six liquid-drain services are checked separately, as the published basis excludes liquid letdown).
- **liquid**: separator side streams within the separator liquid-rate limit and the drain drum capacity, total outfall flow within the outfall limit, and drain-line liquid velocities within 3.0 m/s on all six drain pipelines using the published gas-density proxy at the 1 MPa drain-domain limit (no liquid density is published).
- **metering**: all gas exchanged at GRID-TIE passes through active custody meter capacity >= the scenario flow, and the installed meter capacity covers the whole GRID-TIE boundary flow limit.
- **reliability**: each required n-1 case re-solved at 70 % of scenario flow with one unit out, checking retained flow, delivery pressure and delivery quality.

Check results by area (every individual result is also listed in `design.json` under `validation_checks`; failures, if any, are listed below):

No failures.
