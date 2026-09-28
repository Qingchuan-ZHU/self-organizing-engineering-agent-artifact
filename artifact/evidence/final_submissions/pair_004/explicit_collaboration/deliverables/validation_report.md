# Validation report - UGS-SYNTH-D01 v1.1 proposed design

Every check below is computed from the delivered design by re-running the
published calculation basis; no result is asserted or cached. The geometry
rows are produced directly by the layout checker, and the process rows by
re-solving every scenario and every reliability case.

## 1. Geometry, layout and routing

| Check | Result | Evidence |
|---|---|---|
| equipment footprint inside the site boundary | pass | 21 instances checked against the site polygon |
| footprints outside equipment-exclusion interiors | pass | 3 no-build zones tested |
| no positive-area overlap between footprints | pass | 210 footprint pairs tested |
| minimum separation matrix satisfied for every equipment pair | pass | closest pair DRN-1/DRN-2: 8.00 m against 4.0 m required |
| required maintenance envelopes inside site, clear of exclusions and footprints | pass |  |
| road width at least 4 m | pass |  |
| paved road geometry inside the site boundary | pass |  |
| paved road geometry outside road-exclusion interiors | pass |  |
| paved road geometry clear of equipment footprints | pass |  |
| road network connected and containing ROAD-ENTRANCE | pass | 4 paved parts in 1 component(s), centreline length 1406 m |
| road-access and crane-access buffers to required maintenance envelopes | pass | INJ-C1 0.50 m, INJ-C2 0.50 m, INJ-C3 2.40 m, SEP-1 3.00 m, SEP-2 3.00 m, SEP-3 3.00 m |
| pipeline endpoints coincide with their port coordinates (1e-6 m) | pass |  |
| every route segment longer than the geometry tolerance | pass | 36 pipelines, 77 segments, 5424 m total |
| route segments within the site boundary | pass | 77 segments tested against the site polygon |
| route segments outside pipeline-exclusion interiors | pass |  |
| route segments do not cross equipment-footprint interiors | pass |  |
| declared corridors contain their segments and allow their levels | pass | no segment declares a corridor in this design |
| no positive-length same-level route overlap (including self-overlap) | pass |  |
| port connection cardinality within published limits | pass | 69 connected ports tested |
| port-type compatibility of every physical connection | pass |  |

Geometry exceptions: none

## 2. Process, hydraulic and limit checks per scenario

| Scenario | Exceptions |
|---|---|
| INJ-LOW | none |
| INJ-MID | none |
| INJ-HIGH | none |
| WDR-HIGH | none |
| WDR-MID | none |
| WDR-LOW | none |

Checks applied in every scenario:

* mass balance at every active equipment item (tolerance 1e-5 kg/s)
* convergence of the published fixed-point pressure-loss calculation (1e-5 MPa)
* gas velocity (published limit) on every gas pipeline, and the drain velocity limit
  on liquid-drain lines using the published gas-density formulation
* pipe class pressure rating, temperature range, dry/wet and liquid-drain compatibility
* compressor capacity, minimum stable flow, pressure ratio, suction/discharge pressure,
  suction/discharge temperature and driver power limits
* separator/filter, dehydration, cooler, regulator, meter, header and closed-drain
  capacity, pressure and duty limits, liquid side-stream rates, feed liquid limits
* closed-drain domain pressure against the model pressure limit
* well-group and grid-tie boundary flow limits and the outfall flow limit
* delivery pressure, temperature, water content and free-liquid loading at every sink
* active GRID-TIE meter rated capacity against the scenario flow

## 3. Reliability (N-1) cases

| Scenario | Failed unit | Requirement | Retained flow (kg/s) | Surviving capacity (kg/s) | Margin (kg/s) | Exceptions |
|---|---|---|---|---|---|---|
| INJ-LOW | INJ-C1 | compressor outage - compressor N-1 | 84.00 | 100.0 | 16.0 | none |
| INJ-LOW | INJ-C2 | compressor outage - compressor N-1 | 84.00 | 100.0 | 16.0 | none |
| INJ-LOW | INJ-C3 | compressor outage - compressor N-1 | 84.00 | 120.0 | 36.0 | none |
| INJ-MID | INJ-C1 | compressor outage - compressor N-1 | 70.00 | 100.0 | 30.0 | none |
| INJ-MID | INJ-C2 | compressor outage - compressor N-1 | 70.00 | 100.0 | 30.0 | none |
| INJ-MID | INJ-C3 | compressor outage - compressor N-1 | 70.00 | 120.0 | 50.0 | none |
| INJ-HIGH | INJ-C1 | compressor outage - compressor N-1 | 52.50 | 100.0 | 47.5 | none |
| INJ-HIGH | INJ-C2 | compressor outage - compressor N-1 | 52.50 | 100.0 | 47.5 | none |
| INJ-HIGH | INJ-C3 | compressor outage - compressor N-1 | 52.50 | 120.0 | 67.5 | none |
| WDR-LOW | INJ-C1 | compressor outage - compressor N-1 | 49.00 | 100.0 | 51.0 | none |
| WDR-LOW | INJ-C2 | compressor outage - compressor N-1 | 49.00 | 100.0 | 51.0 | none |
| WDR-LOW | INJ-C3 | compressor outage - compressor N-1 | 49.00 | 120.0 | 71.0 | none |
| WDR-HIGH | SEP-1 | treatment outage - withdrawal N-1 | 84.00 | 140.0 | 56.0 | none |
| WDR-HIGH | SEP-2 | treatment outage - withdrawal N-1 | 84.00 | 140.0 | 56.0 | none |
| WDR-HIGH | SEP-3 | treatment outage - withdrawal N-1 | 84.00 | 140.0 | 56.0 | none |
| WDR-HIGH | DEHY-1 | treatment outage - withdrawal N-1 | 84.00 | 140.0 | 56.0 | none |
| WDR-HIGH | DEHY-2 | treatment outage - withdrawal N-1 | 84.00 | 140.0 | 56.0 | none |
| WDR-HIGH | DEHY-3 | treatment outage - withdrawal N-1 | 84.00 | 140.0 | 56.0 | none |
| WDR-MID | SEP-1 | treatment outage - withdrawal N-1 | 70.00 | 140.0 | 70.0 | none |
| WDR-MID | SEP-2 | treatment outage - withdrawal N-1 | 70.00 | 140.0 | 70.0 | none |
| WDR-MID | SEP-3 | treatment outage - withdrawal N-1 | 70.00 | 140.0 | 70.0 | none |
| WDR-MID | DEHY-1 | treatment outage - withdrawal N-1 | 70.00 | 140.0 | 70.0 | none |
| WDR-MID | DEHY-2 | treatment outage - withdrawal N-1 | 70.00 | 140.0 | 70.0 | none |
| WDR-MID | DEHY-3 | treatment outage - withdrawal N-1 | 70.00 | 140.0 | 70.0 | none |
| WDR-LOW | SEP-1 | treatment outage - withdrawal N-1 | 49.00 | 140.0 | 91.0 | none |
| WDR-LOW | SEP-2 | treatment outage - withdrawal N-1 | 49.00 | 140.0 | 91.0 | none |
| WDR-LOW | SEP-3 | treatment outage - withdrawal N-1 | 49.00 | 140.0 | 91.0 | none |
| WDR-LOW | DEHY-1 | treatment outage - withdrawal N-1 | 49.00 | 140.0 | 91.0 | none |
| WDR-LOW | DEHY-2 | treatment outage - withdrawal N-1 | 49.00 | 140.0 | 91.0 | none |
| WDR-LOW | DEHY-3 | treatment outage - withdrawal N-1 | 49.00 | 140.0 | 91.0 | none |

Total N-1 cases: 30, total exceptions: 0

## 4. Validator self-check (mutation tests)

Ten deliberate mutations were applied to the delivered design; each breaks
exactly one published rule and must be reported as an exception. This shows
that the checks reported above are not vacuous.

| Deliberate mutation | Detected | Evidence |
|---|---|---|
| mass balance perturbed on one well flowline | yes | HDR-C: mass imbalance 1.000000 kg/s |
| two equipment footprints overlapped | yes | footprints overlap: SEP-1 / SEP-2 |
| delivery regulator moved inside the treatment separation distance | yes | separation REG-WDR/HDR-F = 5.500 m < required 6.0 m |
| pipeline routed through FUTURE-EXPANSION (pipeline exclusion) | yes | P02: segment 0 enters pipeline_exclusion FUTURE-EXPANSION |
| one pipeline laid along another on the same routing level | yes | same-level overlap 64.000 m: P04 seg1 / P05 seg1 (ground) |
| outlet metering line undersized to DN150 | yes | P32: gas velocity 201.308 > 25.0 m/s |
| wet-service line given a dry-only pipe class | yes | P11: wet gas but class CS-DRY-160 not wet compatible |
| compressor discharge pressure driven above the model limit | yes | INJ-C2: ratio 2.4723 > max 2.40 |
| dehydration outlet water raised above the 50 mg/Sm3 delivery limit | yes | GRID-TIE: water 80.0000 > 50.0 mg/Sm3 |
| aftercooler setpoint raised above the delivery temperature limit | yes | WG-06: temperature 70.00 outside [-10.0, 60.0] |

Mutations detected: 10 of 10.
