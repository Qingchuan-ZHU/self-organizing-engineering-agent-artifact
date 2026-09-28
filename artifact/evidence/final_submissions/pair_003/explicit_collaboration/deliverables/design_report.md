# UGS-SYNTH-D01 - Underground gas storage station design report

Case: `UGS-SYNTH-D01` (benchmark family `UGS-SYNTH`, case version 1.1.0-development). All data are deterministic synthetic benchmark assumptions from `brief/`; they are not vendor data and not production engineering criteria.

Units: metres (m), megapascal (MPa), degree Celsius (degC), kilograms per second (kg/s), megawatt (MW), megawatt-hour (MWh), megabenchmark-cost-unit (MBCU).

## 1. Scope, objective and design basis

The project is a bidirectional underground gas storage station connecting six well-group laterals on the west side of the site with the transmission grid tie on the east side. The primary objective is to minimise benchmark lifecycle cost (LCC) among feasible designs.

The design basis is the published v1.1 calculation basis, geometry basis and network semantics together with the equipment, piping, safety, maintenance and economic catalogs. The deliverables define: physical topology and boundary interfaces, equipment instances with catalog model IDs and stated capacities, equipment positions and orientations, pipeline paths with diameters, classes and installation levels, scenario-specific operating paths, flows and setpoints, quantities, and the LCC basis, breakdown and result.

Scope covered: process architecture, equipment selection and count, train architecture, process topology, operating philosophy, pipe sizing and class, layout, routing, maintenance access, roads and access. Excluded scope is listed in section 9.

## 2. Normal operating scenarios

| Scenario | Service | Flow (kg/s) | Source | Sink requirement | Hours/year |
|---|---|---:|---|---|---:|
| INJ-LOW | injection | 120 | GRID-TIE 6.5 MPa, 25 degC | WG-01... 8.5 MPa | 900 |
| INJ-MID | injection | 100 | GRID-TIE 6.5 MPa, 25 degC | WG-01... 11.0 MPa | 1300 |
| INJ-HIGH | injection | 75 | GRID-TIE 6.5 MPa, 25 degC | WG-01... 13.5 MPa | 600 |
| WDR-HIGH | withdrawal | 120 | well_groups 12.0 MPa, 20 degC | GRID-TIE 6.0 MPa | 500 |
| WDR-MID | withdrawal | 100 | well_groups 8.0 MPa, 20 degC | GRID-TIE 6.0 MPa | 900 |
| WDR-LOW | withdrawal | 70 | well_groups 4.5 MPa, 20 degC | GRID-TIE 6.0 MPa | 800 |

Annual hours sum to 5000 h, equal to `operating_hours_per_year`.

Delivery limits applied at every sink interface: free-liquid loading <= 1e-4 kg liquid/kg gas, water content <= 50 mg/Sm3 and temperature within -10 degC to +60 degC.

## 3. Process architecture

The station has two physically separate one-way process paths that share the well-group manifold and the site:

**Injection path (GRID-TIE to the six well groups)**

`GRID-TIE -> PL-IF -> IMTR-1 -> PL-IM-1o -> HDR-IM2 -> {PL-IS-1 -> ICOMP-1 -> PL-ID-1 | PL-IS-2 -> ICOMP-2 -> PL-ID-2} -> HDR-IC -> PL-IC -> COOL-1 -> PL-IR -> HDR-WELL -> PL-WG-01..06 -> WG-01..WG-06`

**Withdrawal path (six well groups to GRID-TIE)**

`WG-01..06 -> PL-WG-01..06 -> HDR-WELL -> PL-WF -> HDR-WA -> {PL-TA-1 -> SEP-A -> PL-TA-2 -> DEH-A -> PL-TA-3 | ...B... | ...C...} -> HDR-WB -> {PL-PC-R -> REG-1 -> PL-PC-R2 | PL-PC-C1 -> WCOMP-1 -> PL-PC-C1o | PL-PC-C2 -> WCOMP-2 -> PL-PC-C2o} -> HDR-WC -> PL-WM-1i -> WMTR-1 -> PL-TIE-W -> GRID-TIE`

Separator liquid side streams: `SEP-A/B/C liquid_out -> PL-DA-1/DB-1/DC-1 -> DRN-A/B/C drain_in`, and each drum discharges to `LIQUID-DRAIN-OUTFALL` through PL-DA-2/DB-2/DC-2.

Design logic:

- **Compression in two directions.** Compressor ports are one-way, so the injection and withdrawal services require physically separate compressor sets. 2 x C60 cover the maximum injection flow of 120 kg/s; a third unit (C40, model C40) provides the compression n-1 capability required for INJ-LOW (84 kg/s retained with one unit out). Two C60 units cover WDR-LOW (70 kg/s) and its 49 kg/s n-1 requirement.
- **Withdrawal treatment in three parallel trains.** SEP70 (16 MPa) and DEHY70 (16 MPa) are the lowest-cost units rated for the 12 MPa WDR-HIGH source; three trains are required because two trains cannot retain 0.7 x 120 = 84 kg/s after a separator or dehydration outage.
- **Pressure control.** WDR-HIGH and WDR-MID have source pressure above the 6 MPa delivery requirement and are handled by a single REG180 regulator (Joule-Thomson cooling of 1.2 K/MPa is small enough to stay inside the -10 degC to +60 degC delivery band). WDR-LOW is below the delivery pressure and uses the two C60 booster compressors. The regulator and the booster compressors are alternative parallel branches of the same path.
- **Injection aftercooling.** Single-stage compression of INJ-HIGH raises the gas to about 96 degC, above the 60 degC delivery limit, so one COOL120 aftercooler is installed on the common discharge; the outlet is controlled to 40 degC.
- **Metering.** GRID-TIE allows two physical connections and both are used: one for the injection import and one for the withdrawal export. Each direction has a single custody meter run (MTR160, 160 kg/s rated), i.e. 133 % of the maximum published scenario flow of 120 kg/s, so meter capacity is never the constraint and no split/merge manifold is needed for the measured stream.
- **No process heating, filtration or extra separation is required**: separator removal of 99.95 % of the incoming 0.01 kg/kg free-liquid loading leaves 5e-6 kg/kg, well inside the 1e-4 limit, and no published scenario delivers gas below -10 degC.

## 4. Equipment selection and stated capacities

| Tag | Catalog model | Category | Duty / capacity | Position (x, y) m | Orientation |
|---|---|---|---|---|---|
| HDR-WELL | HDR120 | header | well-group manifold, 120 kg/s, 10 branch ports | (95.0, 225.0) | 0 deg |
| HDR-WA | HDR120 | header | treatment feed manifold, 120 kg/s | (150.0, 225.0) | 0 deg |
| SEP-A | SEP70 | separator | withdrawal separator, 70 kg/s gas, 2.0 kg/s liquid | (195.0, 140.0) | 0 deg |
| SEP-B | SEP70 | separator | withdrawal separator, 70 kg/s gas, 2.0 kg/s liquid | (195.0, 225.0) | 0 deg |
| SEP-C | SEP70 | separator | withdrawal separator, 70 kg/s gas, 2.0 kg/s liquid | (195.0, 310.0) | 0 deg |
| DEH-A | DEHY70 | dehydration | dehydration, 70 kg/s, outlet 35 mg/Sm3 | (225.0, 140.0) | 0 deg |
| DEH-B | DEHY70 | dehydration | dehydration, 70 kg/s, outlet 35 mg/Sm3 | (225.0, 225.0) | 0 deg |
| DEH-C | DEHY70 | dehydration | dehydration, 70 kg/s, outlet 35 mg/Sm3 | (225.0, 310.0) | 0 deg |
| DRN-A | DRN-S | closed_drain | closed drain drum, 2.0 kg/s | (200.0, 127.0) | 0 deg |
| DRN-B | DRN-S | closed_drain | closed drain drum, 2.0 kg/s | (200.0, 200.0) | 0 deg |
| DRN-C | DRN-S | closed_drain | closed drain drum, 2.0 kg/s | (200.0, 297.0) | 0 deg |
| HDR-WB | HDR120 | header | treated-gas collection manifold, 120 kg/s | (265.0, 225.0) | 0 deg |
| REG-1 | REG180 | regulator | withdrawal pressure control, 180 kg/s | (300.0, 225.0) | 0 deg |
| WCOMP-1 | C60 | compressor | withdrawal booster, 60 kg/s, ratio <= 2.4 | (330.0, 150.0) | 0 deg |
| WCOMP-2 | C60 | compressor | withdrawal booster, 60 kg/s, ratio <= 2.4 | (330.0, 110.0) | 0 deg |
| HDR-WC | HDR120 | header | pressure-control discharge manifold, 120 kg/s | (390.0, 225.0) | 0 deg |
| WMTR-1 | MTR160 | meter | custody meter run, 120 kg/s | (430.0, 205.0) | 0 deg |
| IMTR-1 | MTR160 | meter | custody meter run, 120 kg/s | (530.0, 105.0) | 0 deg |
| HDR-IM2 | HDR120 | header | compressor suction manifold, 120 kg/s | (560.0, 120.0) | 0 deg |
| ICOMP-1 | C60 | compressor | injection compressor, 60 kg/s, ratio <= 2.4 | (600.0, 90.0) | 0 deg |
| ICOMP-2 | C60 | compressor | injection compressor, 60 kg/s, ratio <= 2.4 | (600.0, 120.0) | 0 deg |
| ICOMP-3 | C40 | compressor | injection stand-by/n-1 compressor, 40 kg/s | (601.5, 150.0) | 0 deg |
| HDR-IC | HDR120 | header | compressor discharge manifold, 120 kg/s | (640.0, 120.0) | 0 deg |
| COOL-1 | COOL120 | cooler | injection aftercooler, 120 kg/s, duty <= 32 MW | (670.0, 160.0) | 0 deg |

Footprint areas, port coordinates, maintenance envelopes and catalog costs for every instance are in `deliverables/design.json` (`equipment`).

## 5. Site layout, safety and maintenance access

Equipment is arranged in an east-west process corridor inside the 700 m x 450 m site, avoiding the FUTURE-EXPANSION (550-700 m, 320-450 m), GRID-FACILITY (620-700 m, 0-75 m) and DRAINAGE-CHANNEL (300-320 m, 0-90 m) no-build zones:

- well manifold at x = 95 m with the six laterals fanning west to the well-group boundaries;
- three treatment trains (SEP70 + DEHY70) in a north-south row at x = 195-230 m, trains at y = 140 m, 225 m and 310 m, each with its own closed-drain drum at x = 200 m;
- withdrawal pressure control (REG180 and the two C60 boosters) at x = 300-337 m;
- withdrawal custody metering at x = 430 m and the export line to GRID-TIE along y = 225 m;
- injection chain in the south-east: metering manifold at x = 500-560 m, compressors at x = 592-608 m, discharge manifold at x = 640 m, aftercooler at x = 670 m, with a DN700 cooled-gas return line to the well manifold.

| Platform separation check | Result |
|---|---|
| equipment pairs checked against the published separation matrix | 276 |
| minimum required separation used | 12 m (compressor to drain) |
| separation violations | 0 |

Maintenance: every instance has a routine clearance envelope clear of other footprints, the site boundary and equipment-exclusion interiors; the five compressors also have crane-removal envelopes on their heavy-maintenance side. Roads:

| Road | Width (m) | Length (m) | Function |
|---|---:|---:|---|
| RD-MAIN | 6 | 675.0 | site access road from ROAD-ENTRANCE |
| RD-SEP | 5 | 200.0 | separator maintenance access |
| RD-WCOMP | 5 | 90.0 | withdrawal compressor crane access |
| RD-ICOMP | 5 | 100.0 | injection compressor crane access |

The road network is connected and contains `ROAD-ENTRANCE` at (0, 225). Every compressor's maintenance envelope lies within 4.5 m of a paved road (crane access) and every separator's envelope lies within 7.0 m of a paved road. The road network is clear of all equipment footprints and of the road-exclusion zone interiors.

Process safety provisions represented in this synthetic model: platform separation distances, closed liquid drainage from every separator to the outfall, dry/wet pipe-class segregation of the gas services, and relief/flare, firewater and gas detection listed as out-of-scope abstract or non-modelled items.

## 6. Piping and network definition

40 pipelines connect 24 equipment instances and the eight process boundaries (GRID-TIE, the six well-group laterals WG-01..WG-06 and LIQUID-DRAIN-OUTFALL). Each pipeline is defined by its endpoints (node and port), straight-segment route with per-segment installation level, nominal diameter, pipe class and total length in `deliverables/design.json` (`connections`).

Pipe class usage:

| Class | Rating | Service |
|---|---|---|
| CS-WET-160 | 16 MPa, -20 to 120 degC | wet hydrocarbon gas: well laterals, raw gas to the separators and within trains up to the dehydration outlet |
| CS-DRY-160 | 16 MPa, -20 to 120 degC | dry gas above 10 MPa: compressor discharges, treatment outlets, injection return line |
| CS-WET-100 | 10 MPa, -20 to 100 degC | dry gas below 10 MPa and liquid drains: metering, regulator and booster outlet, GRID-TIE tie lines, drain services |

Installation levels: `rack_low` for east-west main runs, `ground` for north-south branch runs and `buried` for the liquid-drain services. No section declares a public corridor, so no two same-level sections overlap: all plan crossings are between different installation levels or are single-point crossings of zero overlap length.

## 7. Operating philosophy and scenario plans

Normal operation:

- **Injection (INJ-LOW/MID/HIGH).** Gas enters at GRID-TIE, is metered in the injection custody meter run, split equally to ICOMP-1/ICOMP-2, compressed to the discharge pressure required to hold the well-group setpoint, cooled to 40 degC in COOL-1 and distributed equally to the six well laterals. Both C60 units run; the load is actively balanced by a suction-side flow controller because the two suction runs have different lengths. ICOMP-3 is a stand-by unit, started automatically when one C60 trips or is taken out for maintenance; running the two C60 units alone also minimises compression energy because they have the higher efficiency proxy (0.80 versus 0.76). At INJ-LOW the two C60 units operate at their catalog rated flow of 60 kg/s each; ICOMP-3 can be started to create rated-capacity margin at a small energy penalty, but the published scenarios do not require it.
- **Withdrawal (WDR-HIGH/MID).** Gas from all six laterals mixes in the well manifold, is split equally between the three treatment trains, separated to 5e-6 kg/kg free liquid, dehydrated to 35 mg/Sm3, recombined, and let down through REG-1 whose outlet setpoint is trimmed to hold 6.0 MPa at GRID-TIE. The booster compressors are not required and run at zero flow.
- **Withdrawal (WDR-LOW).** The source pressure of 4.5 MPa is below the delivery requirement, so - with the regulator bypassed at zero flow - the gas is split equally between WCOMP-1 and WCOMP-2, boosted to the required discharge pressure, recombined and metered to GRID-TIE.
- **Metering.** In every scenario all exchanged gas passes through the single custody meter run of the relevant direction (160 kg/s rated against at most 120 kg/s).

Scenario setpoints and delivered conditions (computed with the published fixed-point pressure-loss convention, 8-update limit and 1e-5 MPa convergence):

| Scenario | Flow (kg/s) | Control setpoint (MPa) | Delivered P (MPa) | Delivered T (degC) | Water (mg/Sm3) | Free liquid | Equipment power (MW) |
|---|---:|---:|---:|---:|---:|---:|---:|
| INJ-LOW | 120 | compressor discharge = 8.6332 | 8.5500 | 40.00 | 40.00 | 0.00e+00 | 8.108 |
| INJ-MID | 100 | compressor discharge = 11.1146 | 11.0500 | 40.00 | 40.00 | 0.00e+00 | 13.027 |
| INJ-HIGH | 75 | compressor discharge = 13.6003 | 13.5500 | 40.00 | 40.00 | 0.00e+00 | 13.722 |
| WDR-HIGH | 120 | regulator outlet = 6.1740 | 6.0500 | 13.21 | 35.00 | 5.00e-06 | 2.160 |
| WDR-MID | 100 | regulator outlet = 6.1450 | 6.0500 | 17.97 | 35.00 | 5.00e-06 | 1.800 |
| WDR-LOW | 70 | compressor discharge = 6.1109 | 6.0500 | 49.94 | 35.00 | 5.00e-06 | 6.609 |

Per-scenario element flows, pressures, temperatures and qualities (the complete operating paths) are tabulated in `deliverables/design.json` (`scenarios[].operating_path`).

Reliability (n-1) demonstration, at 70 % of each scenario's flow with the same delivery limits:

| Case | Result |
|---|---|
| compressor outage, INJ-LOW (120 kg/s), C60 lost | PASS - retained 84.0 kg/s delivered 8.5500 MPa  |
| compressor outage, INJ-LOW (120 kg/s), second C60 lost | PASS - retained 84.0 kg/s delivered 8.5500 MPa  |
| compressor outage, INJ-LOW (120 kg/s), C40 standby lost | PASS - retained 84.0 kg/s delivered 8.5500 MPa  |
| compressor outage, INJ-MID (100 kg/s) | PASS - retained 70.0 kg/s delivered 11.0500 MPa  |
| compressor outage, INJ-HIGH (75 kg/s) | PASS - retained 52.5 kg/s delivered 13.5500 MPa  |
| compressor outage, WDR-LOW (70 kg/s) | PASS - retained 49.0 kg/s delivered 6.0500 MPa  |
| separator outage, WDR-HIGH | PASS - retained 84.0 kg/s delivered 6.0500 MPa  |
| separator outage, WDR-MID | PASS - retained 70.0 kg/s delivered 6.0500 MPa  |
| separator outage, WDR-LOW | PASS - retained 49.0 kg/s delivered 6.0500 MPa  |
| dehydration outage, WDR-HIGH | PASS - retained 84.0 kg/s delivered 6.0500 MPa  |
| dehydration outage, WDR-MID | PASS - retained 70.0 kg/s delivered 6.0500 MPa  |
| dehydration outage, WDR-LOW | PASS - retained 49.0 kg/s delivered 6.0500 MPa  |

## 8. Quantities and lifecycle cost

| Quantity | Value |
|---|---:|
| equipment instances | 24 |
| pipelines | 40 |
| total pipeline length (m) | 6030.0 |
| pipeline length DN200 (m) | 1781.7 |
| pipeline length DN300 (m) | 1386.0 |
| pipeline length DN350 (m) | 1100.8 |
| pipeline length DN400 (m) | 360.8 |
| pipeline length DN500 (m) | 397.0 |
| pipeline length DN700 (m) | 1003.8 |
| pipeline length at buried level (m) | 1724.7 |
| pipeline length at ground level (m) | 2064.3 |
| pipeline length at rack_low level (m) | 2241.0 |
| road centreline length (m) | 1065.0 |
| equipment footprint area (m2) | 1033.0 |
| required maintenance-envelope area (m2, footprint excluded) | 2080.0 |
| annual energy (MWh/year) | 40452 |

LCC basis (per `engineering_calculation_basis.md` and `economic_assumptions.json`): PVF = (1-(1+i)^-N)/i with i = 0.08 and N = 20 years, giving PVF = 9.8181. No other score is combined with LCC.

| LCC component | MBCU |
|---|---:|
| equipment CAPEX | 42.370 |
| piping CAPEX | 2.131 |
| civil/access CAPEX - roads | 0.160 |
| civil/access CAPEX - foundations | 0.004 |
| civil/access CAPEX - maintenance areas | 0.002 |
| civil/access CAPEX - pipeline routing levels | 0.087 |
| energy present value | 47.660 |
| maintenance present value | 13.657 |
| **total LCC** | **106.071** |

Energy: 40452 MWh/year at 0.00012 MBCU/MWh = 4.854 MBCU/year, present value 47.660 MBCU (largest single contributor, dominated by injection compression). Maintenance: 1.391 MBCU/year, present value 13.657 MBCU.

## 9. Assumptions and known limitations

Assumptions:
- The published synthetic v1.1 calculation basis, geometry basis, network semantics and catalogs are the complete and authoritative calculation rules; no vendor data or external criteria are used.
- Scenario flows are distributed equally between the installed parallel units of a duty (six well laterals, two custody meter runs, three treatment trains) unless a scenario plan states otherwise.
- The withdrawal well-group laterals are treated as identical parallel sources at the published source pressure; the manifold pressure is therefore the lowest lateral outlet pressure, i.e. the worst-routed lateral.
- East-west main runs are installed at the 'rack_low' level and north-south branch runs at the 'ground' level; liquid-drain services are buried. Crossings between runs therefore occur between different installation levels (or as zero-length plan crossings), which the geometry basis permits.
- Gas left standing in idle parallel branches of a normally-unused duty (for example the regulator branch during WDR-LOW) is not modelled; idle branches carry zero flow and pass no state change.
- The injection C40 unit is a stand-by/n-1 unit: it is not required to cover any published normal scenario because the two C60 units cover the maximum injection flow of 120 kg/s, and it is started when one C60 is out of service (retained 100 kg/s vs 84 kg/s required).
- Liquid side streams are checked against catalog liquid-rate limits and drain drum capacities, but no liquid density, letdown or flashing model is available in the published basis. Drain-line velocities are therefore evaluated on every liquid pipeline with the published gas-density proxy at the 1 MPa drain-domain limit, which is far more conservative than any physical liquid density (about 0.05 m/s) and keeps every line inside the 3.0 m/s limit.
- Parallel units of a duty are given by an equal flow split and the running units are taken as perfectly balanced by flow control; at INJ-LOW the two C60 units therefore run at their catalog rated flow (60 kg/s each) and every main header carries its rated 120 kg/s.
- Roads and pipelines may cross in plan; the geometry basis restricts roads only with respect to the site boundary, road-exclusion zones and equipment footprints, and restricts pipelines with respect to the site boundary, pipeline-exclusion zones, equipment footprints and same-level overlap.

Known limitations and excluded scope:
- Excluded scope per project_requirements.json is not designed: reservoir model, well completion, full electrical system, full control system, full firewater synthesis, structural design, detailed buildings, complete civil design, full process safety study, regulatory/code compliance and vendor procurement. Electrical, instrument-air and firewater distribution are abstract external services.
- No elevation model exists (flat site, zero elevation); no minor losses, fittings, valves or instrument drops are included, consistent with the published pressure-loss convention.
- Transients, start-up/shutdown sequencing, blowdown, flare relief and surge analysis are outside the published basis and are not covered.
- Cyclic well-group pressure behaviour is represented only by the six published scenarios; within-scenario pressure variation with reservoir state is not modelled.
- Liquid water removed by the dehydration units, regeneration gas and water disposal are outside the case's process model and are not designed.
- Each GRID-TIE direction has one custody meter run. Meter proving or repair therefore requires the station to be off line; a second run per direction was evaluated and rejected because the published metering requirement is met by a single active run and LCC is the scored objective.
- Pipe sizing minimises LCC including the present value of pressure-loss-driven compression energy; the fastest internal velocity in the design is 21.5 m/s on the DN400 custody-meter feed and regulator-outlet lines (86 % of the 25 m/s limit), which is a deliberate trade of capital against energy rather than a constraint violation.
- REG180 was retained for the withdrawal pressure control in preference to the smaller REG120 (worth 0.16 MBCU of LCC, 0.15 %) so that the regulator is not exactly duty-matched to the 500 h peak-flow scenario.
- Costs are the synthetic catalog values only; no escalation, working capital, decommissioning or owner cost is included.

## 10. Appendices

### 10.1 Pipeline schedule

| Pipeline | From (node.port) | To (node.port) | DN | Class | Length (m) | Levels | Service |
|---|---|---|---|---|---:|---|---|
| PL-WG-01 | WG-01.gas | HDR-WELL.branch_07 | DN300 | CS-WET-160 | 260.0 | rack_low -> ground | well group lateral |
| PL-WG-02 | WG-02.gas | HDR-WELL.branch_04 | DN300 | CS-WET-160 | 187.2 | rack_low -> ground | well group lateral |
| PL-WG-03 | WG-03.gas | HDR-WELL.branch_08 | DN300 | CS-WET-160 | 116.8 | rack_low -> ground | well group lateral |
| PL-WG-04 | WG-04.gas | HDR-WELL.branch_01 | DN300 | CS-WET-160 | 115.5 | rack_low -> ground | well group lateral |
| PL-WG-05 | WG-05.gas | HDR-WELL.branch_05 | DN300 | CS-WET-160 | 189.5 | rack_low -> ground | well group lateral |
| PL-WG-06 | WG-06.gas | HDR-WELL.branch_09 | DN300 | CS-WET-160 | 263.5 | rack_low -> ground | well group lateral |
| PL-WF | HDR-WELL.branch_02 | HDR-WA.branch_08 | DN500 | CS-WET-160 | 49.0 | rack_low | wet gas feed to treatment |
| PL-TA-1 | HDR-WA.branch_03 | SEP-A.gas_in | DN350 | CS-WET-160 | 123.0 | ground -> rack_low | train A separator feed |
| PL-TB-1 | HDR-WA.branch_06 | SEP-B.gas_in | DN300 | CS-WET-160 | 38.0 | rack_low | train B separator feed |
| PL-TC-1 | HDR-WA.branch_09 | SEP-C.gas_in | DN350 | CS-WET-160 | 122.5 | ground -> rack_low | train C separator feed |
| PL-TA-2 | SEP-A.gas_out | DEH-A.gas_in | DN300 | CS-WET-160 | 21.0 | rack_low | train A wet gas |
| PL-TB-2 | SEP-B.gas_out | DEH-B.gas_in | DN300 | CS-WET-160 | 21.0 | rack_low | train B wet gas |
| PL-TC-2 | SEP-C.gas_out | DEH-C.gas_in | DN300 | CS-WET-160 | 21.0 | rack_low | train C wet gas |
| PL-TA-3 | DEH-A.gas_out | HDR-WB.branch_03 | DN350 | CS-DRY-160 | 120.0 | rack_low -> ground | train A dry gas |
| PL-TB-3 | DEH-B.gas_out | HDR-WB.branch_04 | DN300 | CS-DRY-160 | 32.0 | ground | train B dry gas |
| PL-TC-3 | DEH-C.gas_out | HDR-WB.branch_01 | DN350 | CS-DRY-160 | 116.5 | rack_low -> ground | train C dry gas |
| PL-DA-1 | SEP-A.liquid_out | DRN-A.drain_in | DN200 | CS-WET-100 | 15.0 | ground | train A separated liquid |
| PL-DB-1 | SEP-B.liquid_out | DRN-B.drain_in | DN200 | CS-WET-100 | 27.0 | ground | train B separated liquid |
| PL-DC-1 | SEP-C.liquid_out | DRN-C.drain_in | DN200 | CS-WET-100 | 15.0 | ground | train C separated liquid |
| PL-DA-2 | DRN-A.drain_out | LIQUID-DRAIN-OUTFALL.drain | DN200 | CS-WET-100 | 482.6 | buried | closed drain to outfall (train A) |
| PL-DB-2 | DRN-B.drain_out | LIQUID-DRAIN-OUTFALL.drain | DN200 | CS-WET-100 | 567.2 | buried | closed drain to outfall (train B) |
| PL-DC-2 | DRN-C.drain_out | LIQUID-DRAIN-OUTFALL.drain | DN200 | CS-WET-100 | 674.9 | buried | closed drain to outfall (train C) |
| PL-PC-R | HDR-WB.branch_02 | REG-1.gas_in | DN350 | CS-DRY-160 | 29.5 | ground | regulator feed (WDR-HIGH / WDR-MID) |
| PL-PC-C1 | HDR-WB.branch_06 | WCOMP-1.suction | DN350 | CS-DRY-160 | 129.5 | ground -> rack_low | withdrawal booster compressor 1 suction |
| PL-PC-C2 | HDR-WB.branch_10 | WCOMP-2.suction | DN350 | CS-DRY-160 | 168.5 | ground -> rack_low | withdrawal booster compressor 2 suction |
| PL-PC-R2 | REG-1.gas_out | HDR-WC.branch_08 | DN400 | CS-WET-100 | 84.5 | ground | regulated gas to metering |
| PL-PC-C1o | WCOMP-1.discharge | HDR-WC.branch_04 | DN350 | CS-DRY-160 | 123.8 | rack_low -> ground -> rack_low | withdrawal booster compressor 1 discharge |
| PL-PC-C2o | WCOMP-2.discharge | HDR-WC.branch_03 | DN350 | CS-DRY-160 | 167.5 | rack_low -> ground -> rack_low | withdrawal booster compressor 2 discharge |
| PL-WM-1i | HDR-WC.branch_02 | WMTR-1.gas_in | DN400 | CS-WET-100 | 56.0 | rack_low -> ground -> rack_low | custody meter run feed (withdrawal) |
| PL-TIE-W | WMTR-1.gas_out | GRID-TIE.gas | DN500 | CS-WET-100 | 288.0 | rack_low -> ground -> rack_low | GRID-TIE withdrawal export line (metered) |
| PL-IF | GRID-TIE.gas | IMTR-1.gas_in | DN700 | CS-WET-100 | 346.8 | ground -> rack_low -> ground -> rack_low | GRID-TIE injection import line (metered) |
| PL-IM-1o | IMTR-1.gas_out | HDR-IM2.branch_04 | DN400 | CS-WET-100 | 39.2 | rack_low -> ground | custody meter run outlet (injection) |
| PL-IS-1 | HDR-IM2.branch_07 | ICOMP-1.suction | DN400 | CS-WET-100 | 62.5 | ground -> rack_low | injection compressor 1 suction |
| PL-IS-2 | HDR-IM2.branch_06 | ICOMP-2.suction | DN400 | CS-WET-100 | 29.5 | rack_low | injection compressor 2 suction |
| PL-IS-3 | HDR-IM2.branch_02 | ICOMP-3.suction | DN300 | CS-WET-100 | 61.5 | ground -> rack_low | injection compressor 3 suction |
| PL-ID-1 | ICOMP-1.discharge | HDR-IC.branch_07 | DN400 | CS-DRY-160 | 59.5 | rack_low -> ground | injection compressor 1 discharge |
| PL-ID-2 | ICOMP-2.discharge | HDR-IC.branch_04 | DN400 | CS-DRY-160 | 29.5 | ground | injection compressor 2 discharge |
| PL-ID-3 | ICOMP-3.discharge | HDR-IC.branch_01 | DN300 | CS-DRY-160 | 59.0 | rack_low -> ground | injection compressor 3 discharge |
| PL-IC | HDR-IC.branch_02 | COOL-1.gas_in | DN500 | CS-DRY-160 | 60.0 | ground -> rack_low -> ground -> rack_low | compressor discharge to aftercooler |
| PL-IR | COOL-1.gas_out | HDR-WELL.branch_03 | DN700 | CS-DRY-160 | 657.0 | rack_low -> ground -> rack_low -> ground | cooled injection gas to well manifold |

Full waypoint coordinates for every segment are in `deliverables/design.json` (`connections[].segments`).

### 10.2 Equipment counts and cost by catalog model

| Model | Category | Count | Unit CAPEX (MBCU) | Total CAPEX (MBCU) | Maintenance (MBCU/year) |
|---|---|---:|---:|---:|---:|
| C40 | compressor | 1 | 4.60 | 4.60 | 0.120 |
| C60 | compressor | 4 | 6.50 | 26.00 | 0.640 |
| COOL120 | cooler | 1 | 0.92 | 0.92 | 0.050 |
| DEHY70 | dehydration | 3 | 1.85 | 5.55 | 0.285 |
| DRN-S | closed_drain | 3 | 0.08 | 0.24 | 0.012 |
| HDR120 | header | 6 | 0.25 | 1.50 | 0.072 |
| MTR160 | meter | 2 | 0.38 | 0.76 | 0.040 |
| REG180 | regulator | 1 | 0.46 | 0.46 | 0.022 |
| SEP70 | separator | 3 | 0.78 | 2.34 | 0.150 |

### 10.3 Scenario energy breakdown

| Scenario | Hours | Compressors (MW) | Dehydration (MW) | Cooling electric (MW) | Scenario total (MW) | Energy (MWh) |
|---|---:|---:|---:|---:|---:|---:|
| INJ-LOW | 900 | 7.993 | 0.000 | 0.114 | 8.108 | 7297 |
| INJ-MID | 1300 | 12.728 | 0.000 | 0.299 | 13.027 | 16935 |
| INJ-HIGH | 600 | 13.369 | 0.000 | 0.353 | 13.722 | 8233 |
| WDR-HIGH | 500 | 0.000 | 2.160 | 0.000 | 2.160 | 1080 |
| WDR-MID | 900 | 0.000 | 1.800 | 0.000 | 1.800 | 1620 |
| WDR-LOW | 800 | 5.349 | 1.260 | 0.000 | 6.609 | 5287 |

Energy conventions applied (per the published basis): compressor values are driver power `W = m cp T_in (r^((k-1)/k)-1)/(eta eta_driver)`; dehydration energy is gas flow times `energy_mw_per_kg_s`; and the cooling figure is `duty x electric_power_fraction_of_duty` (3.5 % of duty), not the duty itself. Annual energy is the sum of these powers over each scenario's hours.

## 11. Verification

670 automated checks were run against the published tolerances; see `deliverables/validation_report.md`. All geometry, safety-separation, maintenance and access, road, pipeline, port, scenario, delivery, liquid-service, path-coverage, metering, reliability and cost checks pass.
