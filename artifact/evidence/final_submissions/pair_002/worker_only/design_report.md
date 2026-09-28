# UGS-SYNTH-D01 v1.1 - Underground Gas Storage Surface Facility

## Design report

Synthetic benchmark deliverable (case `UGS-SYNTH-D01`, version `1.1.0-development`). All data are deterministic benchmark assumptions, not vendor data or production engineering criteria. SI units are used throughout: metres, MPa, degC, kg/s, MW, MWh and MBCU; angles in degrees counter-clockwise. The site coordinate system is the plan frame defined in `site.json` (x east, y north, flat terrain at elevation 0).

---

## 1. Purpose, scope and objectives

The facility connects a single grid tie point (`GRID-TIE`) to six public well-group interfaces (`WG-01`..`WG-06`). It must:

* inject grid gas into the wells at three pressure levels;
* withdraw well gas to the grid, conditioned to the project gas-delivery limits;
* meter all gas exchanged at `GRID-TIE`;
* remain serviceable after the loss of any one compressor (injection) or any one separator / dehydration unit (withdrawal), retaining at least 70 % of the affected scenario flow;
* minimise the benchmark lifecycle cost (LCC) among feasible designs.

Excluded scope (per `project_requirements.json`): reservoir model, well completion, full electrical/control systems, firewater synthesis, structural/civil/building detailed design, full process-safety study, code compliance and vendor procurement. Electric power, instrument air and firewater are externally available abstract services at the `POWER-TIE`, `INSTRUMENT-AIR-TIE` and `FIREWATER-TIE` boundaries; their distribution networks are out of scope and their capacity is assumed sufficient.

### Operating scenarios (published)

| Scenario | Service | h/y | Q (kg/s) | Source | P_source (MPa) | T_source (degC) | Water (mg/Sm3) | Free liquid | P_sink req. (MPa) | Sink |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| INJ-LOW | injection | 900 | 120 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 8.5 | WG-01, WG-02, WG-03, WG-04, WG-05, WG-06 |
| INJ-MID | injection | 1300 | 100 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 11.0 | WG-01, WG-02, WG-03, WG-04, WG-05, WG-06 |
| INJ-HIGH | injection | 600 | 75 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 13.5 | WG-01, WG-02, WG-03, WG-04, WG-05, WG-06 |
| WDR-HIGH | withdrawal | 500 | 120 | well_groups | 12.0 | 20 | 220 | 0.01 | 6.0 | GRID-TIE |
| WDR-MID | withdrawal | 900 | 100 | well_groups | 8.0 | 20 | 220 | 0.01 | 6.0 | GRID-TIE |
| WDR-LOW | withdrawal | 800 | 70 | well_groups | 4.5 | 20 | 220 | 0.01 | 6.0 | GRID-TIE |

Total operating hours: 5000 h/y.

Project delivery limits: free-liquid loading <= 1.0e-4 kg liquid/kg gas, water content <= 50 mg/Sm3, temperature within -10..60 degC.

---

## 2. Design basis and assumptions

The calculation rules of `engineering_calculation_basis.md` (v1.1) and the geometry rules of `engineering_geometry_basis.md` (v1.1) are applied exactly. Key modelling conventions:

* Gas properties: Z and viscosity from the published proxy correlations (with catalogue clamping); density from the real-gas expression; constant cp = 2450 J/(kg K) and k = 1.3.
* Pipe pressure loss: Darcy-Weisbach with Swamee-Jain friction for Re >= 2300 and 64/Re otherwise, evaluated by the published fixed-point procedure at the representative mean pressure (max 8 updates, 1e-5 MPa convergence). No minor losses or elevation correction.
* Compressor: `T_out = T_in (1 + (r^((k-1)/k)-1)/eta)`, `W = m cp T_in (r^((k-1)/k)-1)/(eta eta_driver)` with T_in in kelvin.
* Regulator: `T_out = T_in - JT (P_in - P_out)` with JT = 1.2 K/MPa.
* Header: `dP = pressure_drop_at_capacity (m/capacity)^2`.
* Mixing: equal-pressure-weighted lowest-pressure rule; split conserves gas flow.

Engineering assumptions adopted for this design (in addition to the brief):

1. **Liquid line hydraulics:** the brief does not publish a liquid density. A condensate density of 700 kg/m3 is assumed for drain-line velocity checks (flow rates are ~0.6 kg/s, so velocities are ~0.05 m/s, far below the 3 m/s limit - the design is insensitive to this value).
2. **Shared compressor bank:** the three reciprocating compressors serve both injection compression and the withdrawal boost through shared suction (`HDR-CS`) and discharge (`HDR-CD`) headers. Paths not used by a scenario are isolated by valves; valving itself is outside the modelled equipment scope.
3. **Metering:** one metering string per flow direction satisfies the published metering rule (active capacity 160 kg/s >= 120 kg/s peak scenario flow). No metering n-1 is required by the brief and none is provided.
4. **Regulation philosophy:** the withdrawal pressure regulator `REG-W` upstream of the treatment trains limits the treatment pressure to 6.5 MPa and sets the grid-tie delivery pressure; for WDR-LOW (source 4.5 MPa) the regulator passes through and the compressor bank provides the boost, delivering 6.20 MPa.
5. **Dehydration regeneration / water disposal** are outside the process model, as stated in the brief.
6. All process piping is at the `ground` routing level; no catalogue corridor is used.
7. **Road ends:** road centrelines use butted (square) ends so that the paved geometry of the `ROAD-ENTRANCE` link terminates exactly on the site boundary rather than projecting outside it; interior road ends are also butted.
8. **Access distances:** the published `road_access_buffer_m` (7 m) and `crane_access_buffer_m` (4.5 m) are applied to the shortest boundary-to-boundary distance between the required maintenance envelope and the nearest paved road, as defined in `engineering_geometry_basis.md`. Roads are nevertheless placed 0.5-2.7 m from the relevant envelopes.

---

## 3. Process architecture

### 3.1 Functional decomposition

```
                          +-------------------------- INJECTION --------------------------+
  GRID-TIE -- MTR-I -- HDR-CS -- [ C-1 C-2 (C-3 stby) ] -- HDR-CD -- COOL -- HDR-W -- 6 x WG
                          +--------------------------- BOOST ----------------------------+

  6 x WG -- HDR-W -- REG-W -- HDR-R -- ( SEP-1 -> DEH-1 ), ( SEP-2 -> DEH-2 ) -- HDR-T
                                                                                   |
                                            HDR-T -- HDR-M -- MTR-O -- GRID-TIE <----+
                                            HDR-T -- HDR-CS -- compressors -- HDR-CD -- HDR-M   (boost)

  liquid:  SEP-1.liquid_out -> DRN-1 -> LIQUID-DRAIN-OUTFALL
           SEP-2.liquid_out -> DRN-2 -> LIQUID-DRAIN-OUTFALL
```

The design uses two service paths that share the well-side manifold `HDR-W` and the grid-side meters, consistent with the rule that only `gas_bidirectional` ports carry gas in either direction:

* **Injection path** (grid -> wells): `GRID-TIE -> MTR-I -> HDR-CS -> compressors -> HDR-CD -> COOL -> HDR-W -> 6 well pipelines`.
* **Withdrawal path** (wells -> grid): `6 well pipelines -> HDR-W -> REG-W -> HDR-R -> two parallel treatment trains (SEP + DEH) -> HDR-T -> HDR-M -> MTR-O -> GRID-TIE`. The WDR-LOW scenario is boosted: `HDR-T -> HDR-CS -> compressors -> HDR-CD -> HDR-M -> MTR-O -> GRID-TIE`.

### 3.2 Shared compression

A single 3-unit compressor bank (2 x C60 duty + 1 x C40) is manifolded between `HDR-CS` (suction) and `HDR-CD` (discharge). This topology avoids duplicating a second compression bank, since the WDR-LOW scenario (source 4.5 MPa) requires a boost to reach the 6.0 MPa grid tie, and saves ~13 MBCU of installed capital and maintenance relative to separate banks.

### 3.3 Headers and branches used

| Header | Model | Service | Branches used |
|---|---|---|---|
| HDR-W | HDR120 | well manifold / injection supply / withdrawal take-off | 8 |
| HDR-R | HDR120 | regulator outlet, split to 2 treatment trains | 3 |
| HDR-T | HDR120 | combine 2 treatment trains, feed grid or boost | 4 |
| HDR-M | HDR120 | select grid feed (direct or boosted) | 3 |
| HDR-CS | HDR120 | compressor suction manifold (injection feed / boost feed) | 5 |
| HDR-CD | HDR120 | compressor discharge manifold (cooler / boost discharge) | 5 |

---

## 4. Equipment selection and capacities

| Tag | Model | Category | Safety category | x (m) | y (m) | Orient. (deg) | Capacity | Capex (MBCU) | Maint. (MBCU/y) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| HDR-W | HDR120 | header | hydrocarbon_treatment | 150 | 225 | 0 | 120 kg/s | 0.25 | 0.012 |
| REG-W | REG180 | regulator | pressure_control | 215 | 225 | 0 | 180 kg/s | 0.46 | 0.022 |
| HDR-R | HDR120 | header | hydrocarbon_treatment | 265 | 225 | 0 | 120 kg/s | 0.25 | 0.012 |
| SEP-1 | SEP120 | separator | hydrocarbon_treatment | 330 | 170 | 0 | 120 kg/s | 1.15 | 0.075 |
| DEH-1 | DEHY120 | dehydration | hydrocarbon_treatment | 425 | 170 | 0 | 120 kg/s | 2.7 | 0.135 |
| SEP-2 | SEP120 | separator | hydrocarbon_treatment | 330 | 280 | 0 | 120 kg/s | 1.15 | 0.075 |
| DEH-2 | DEHY120 | dehydration | hydrocarbon_treatment | 425 | 280 | 0 | 120 kg/s | 2.7 | 0.135 |
| HDR-T | HDR120 | header | hydrocarbon_treatment | 490 | 225 | 0 | 120 kg/s | 0.25 | 0.012 |
| HDR-M | HDR120 | header | hydrocarbon_treatment | 535 | 225 | 0 | 120 kg/s | 0.25 | 0.012 |
| MTR-O | MTR160 | meter | metering | 620 | 225 | 0 | 160 kg/s | 0.38 | 0.02 |
| MTR-I | MTR160 | meter | metering | 620 | 300 | 0 | 160 kg/s | 0.38 | 0.02 |
| HDR-CS | HDR120 | header | hydrocarbon_treatment | 440 | 320 | 0 | 120 kg/s | 0.25 | 0.012 |
| HDR-CD | HDR120 | header | hydrocarbon_treatment | 440 | 430 | 0 | 120 kg/s | 0.25 | 0.012 |
| COOL | COOL120 | cooler | hydrocarbon_treatment | 300 | 425 | 0 | 120 kg/s | 0.92 | 0.05 |
| C-1 | C60 | compressor | compressor | 350 | 380 | 90 | 60 kg/s gas (15-60) | 6.5 | 0.16 |
| C-2 | C60 | compressor | compressor | 440 | 380 | 90 | 60 kg/s gas (15-60) | 6.5 | 0.16 |
| C-3 | C40 | compressor | compressor | 525 | 380 | 90 | 40 kg/s gas (10-40) | 4.6 | 0.12 |
| DRN-1 | DRN-L | closed_drain | drain | 330 | 140 | 0 | 2.0 kg/s | 0.14 | 0.007 |
| DRN-2 | DRN-L | closed_drain | drain | 330 | 305 | 0 | 2.0 kg/s | 0.14 | 0.007 |

Model counts: C40 x 1, C60 x 2, COOL120 x 1, DEHY120 x 2, DRN-L x 2, HDR120 x 6, MTR160 x 2, REG180 x 1, SEP120 x 2.

### 4.1 Compressor operating envelopes

| Model | Capacity (kg/s) | Min stable (kg/s) | Max ratio | Max suction (MPa) | Max discharge (MPa) | Max T_disch (degC) | Max power (MW) | eta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C40 | 40 | 10 | 2.4 | 12 | 16 | 150.0 | 20.0 | 0.76 |
| C60 | 60 | 15 | 2.4 | 14 | 16 | 150.0 | 32.0 | 0.8 |

### 4.2 Why these models

* **Compressors** - the compression n-1 rule requires, for INJ-LOW (120 kg/s), that 84 kg/s remains deliverable after the loss of any one unit. A 3-unit bank is therefore required, and {C60, C60, C40} is the minimum-capex combination meeting it (removing either C60 leaves 100 kg/s; removing the C40 leaves 120 kg/s). The C80 was rejected: its higher capital cost outweighs the small efficiency gain at the modelled duty.
* **Separators** - SEP120 is used because, with the upstream regulator holding pressure at 6.5 MPa, its 10 MPa rating is adequate and its 120 kg/s capacity gives the required n-1 margin from a 2-train arrangement (one train = 120 kg/s >= 84 kg/s). A single stage at the published 0.9995 removal efficiency reduces the free-liquid loading from 1.0e-2 to 5.0e-6, already below the 1.0e-4 delivery limit, so no filter is required.
* **Dehydration** - DEHY120 sets outlet water to 35 mg/Sm3 (<= 50). Two trains give the required n-1 margin; the upstream regulator keeps the unit pressure (10 MPa rating) in range.
* **Cooler** - COOL120 is required to bring the compressor discharge (up to 95 degC at INJ-HIGH) below the 60 degC delivery limit; the outlet is controlled to 45 degC.
* **Regulator** - REG180 (180 kg/s) covers the 120 kg/s peak in one unit; no regulator n-1 is required by the brief.
* **Meters** - MTR160 provides 160 kg/s of active metering capacity per direction, exceeding the 1.0 x scenario-flow requirement.
* **Drains** - DRN-L (2.0 kg/s) is sized so a single drain can carry the n-1 liquid rate (0.84 kg/s) as well as the normal 0.60 kg/s.

---

## 5. Physical process topology and pipelines

33 pipelines are installed, total length 5227.5 m. All are at the `ground` routing level.

| Pipe | From (port) | To (port) | Medium | DN | Class | Level | Length (m) |
|---|---|---|---|---|---|---|---:|
| G-TIE-IN | GRID-TIE.gas | MTR-I.gas_in | gas | DN700 | CS-WET-100 | ground | 145.3 |
| G-IN-1 | MTR-I.gas_out | HDR-CS.branch_03 | gas | DN700 | CS-WET-100 | ground | 205.0 |
| G-C1S | HDR-CS.branch_04 | C-1.suction | gas | DN600 | CS-WET-100 | ground | 180.2 |
| G-C2S | HDR-CS.branch_05 | C-2.suction | gas | DN600 | CS-WET-100 | ground | 51.0 |
| G-C3S | HDR-CS.branch_02 | C-3.suction | gas | DN250 | CS-WET-100 | ground | 176.5 |
| G-C1D | C-1.discharge | HDR-CD.branch_08 | gas | DN450 | CS-WET-160 | ground | 170.2 |
| G-C2D | C-2.discharge | HDR-CD.branch_07 | gas | DN450 | CS-WET-160 | ground | 41.0 |
| G-C3D | C-3.discharge | HDR-CD.branch_10 | gas | DN200 | CS-WET-160 | ground | 165.0 |
| G-CD-CL | HDR-CD.branch_04 | COOL.gas_in | gas | DN600 | CS-WET-160 | ground | 175.2 |
| G-CL-W | COOL.gas_out | HDR-W.branch_02 | gas | DN600 | CS-WET-160 | ground | 577.9 |
| G-W-1 | HDR-W.branch_01 | WG-01.gas | gas | DN250 | CS-WET-160 | ground | 232.2 |
| G-W-2 | HDR-W.branch_04 | WG-02.gas | gas | DN250 | CS-WET-160 | ground | 173.1 |
| G-W-3 | HDR-W.branch_05 | WG-03.gas | gas | DN250 | CS-WET-160 | ground | 149.1 |
| G-W-4 | HDR-W.branch_07 | WG-04.gas | gas | DN250 | CS-WET-160 | ground | 145.4 |
| G-W-5 | HDR-W.branch_03 | WG-05.gas | gas | DN250 | CS-WET-160 | ground | 192.2 |
| G-W-6 | HDR-W.branch_08 | WG-06.gas | gas | DN250 | CS-WET-160 | ground | 225.6 |
| G-W-REG | HDR-W.branch_06 | REG-W.gas_in | gas | DN600 | CS-WET-160 | ground | 59.5 |
| G-REG-R | REG-W.gas_out | HDR-R.branch_01 | gas | DN600 | CS-WET-100 | ground | 48.7 |
| G-R-S1 | HDR-R.branch_02 | SEP-1.gas_in | gas | DN400 | CS-WET-100 | ground | 84.8 |
| G-R-S2 | HDR-R.branch_03 | SEP-2.gas_in | gas | DN400 | CS-WET-100 | ground | 90.4 |
| G-S1-D1 | SEP-1.gas_out | DEH-1.gas_in | gas | DN400 | CS-WET-100 | ground | 83.5 |
| G-S2-D2 | SEP-2.gas_out | DEH-2.gas_in | gas | DN400 | CS-WET-100 | ground | 83.5 |
| G-D1-T | DEH-1.gas_out | HDR-T.branch_01 | gas | DN400 | CS-WET-100 | ground | 86.1 |
| G-D2-T | DEH-2.gas_out | HDR-T.branch_02 | gas | DN400 | CS-WET-100 | ground | 87.8 |
| G-T-M | HDR-T.branch_03 | HDR-M.branch_01 | gas | DN400 | CS-WET-100 | ground | 52.1 |
| G-M-TO | HDR-M.branch_03 | MTR-O.gas_in | gas | DN500 | CS-WET-100 | ground | 84.9 |
| G-TO-TIE | MTR-O.gas_out | GRID-TIE.gas | gas | DN500 | CS-WET-100 | ground | 78.0 |
| G-T-CS | HDR-T.branch_04 | HDR-CS.branch_07 | gas | DN600 | CS-WET-100 | ground | 117.0 |
| G-CD-M | HDR-CD.branch_01 | HDR-M.branch_02 | gas | DN500 | CS-WET-100 | ground | 317.5 |
| L-S1 | SEP-1.liquid_out | DRN-1.drain_in | liquid | DN150 | CS-WET-100 | ground | 30.9 |
| L-S2 | SEP-2.liquid_out | DRN-2.drain_in | liquid | DN150 | CS-WET-100 | ground | 52.0 |
| L-D1-O | DRN-1.drain_out | LIQUID-DRAIN-OUTFALL.drain | liquid | DN150 | CS-WET-100 | ground | 355.4 |
| L-D2-O | DRN-2.drain_out | LIQUID-DRAIN-OUTFALL.drain | liquid | DN150 | CS-WET-100 | ground | 510.3 |

Port-type compatibility: every connection uses one of the permitted pairs (gas_out->gas_in/gas_bidirectional, gas_bidirectional->gas_in/gas_bidirectional, liquid_out->drain_in, drain_out->drain_in). Closed-drain outlets discharge directly to the `LIQUID-DRAIN-OUTFALL` boundary (2 of the 8 permitted connections, 1.2 kg/s of the 10 kg/s limit).

---

## 6. Operating philosophy and scenario plans

### 6.1 Setpoints

* Injection cooler outlet: 45 degC (cooler `COOL`).
* Withdrawal grid pressure control (`REG-W`): 6.5 MPa (bypassed by pressure when the source is lower, as in WDR-LOW).
* Withdrawal boost (`WDR-LOW`): compressor discharge controlled to deliver 6.20 MPa at `GRID-TIE`.
* Injection: compressor discharge controlled to hold the lowest well-group pressure at the scenario requirement + 0.1 MPa.

### 6.2 Compressor dispatch and paths

| Scenario | Active compressors | Flow per unit (kg/s) | Ratio | T_out (degC) | Bank power (MW) |
|---|---|---:|---:|---:|---:|
| INJ-LOW | C-1, C-2 | 60.0, 60.0 | 1.350 | 51.71 | 8.168 |
| INJ-MID | C-1, C-2 | 50.0, 50.0 | 1.730 | 75.28 | 12.826 |
| INJ-HIGH | C-1, C-2 | 37.5, 37.5 | 2.112 | 95.17 | 13.429 |
| WDR-HIGH | - (pressure let-down) | - | - | - | - |
| WDR-MID | - (pressure let-down) | - | - | - | - |
| WDR-LOW | C-1, C-2 | 35.0, 35.0 | 1.449 | 52.73 | 5.842 |

### 6.3 Per-scenario operating summary

| Scenario | Delivered pressure (MPa) | Delivered T (degC) | Delivered water (mg/Sm3) | Delivered free liquid | Energy (MW) |
|---|---:|---:|---:|---:|---:|
| INJ-LOW | 8.600 (min well) | 45.0 | 40 | 0.0e+00 | 8.237 |
| INJ-MID | 11.100 (min well) | 45.0 | 40 | 0.0e+00 | 13.085 |
| INJ-HIGH | 13.600 (min well) | 45.0 | 40 | 0.0e+00 | 13.752 |
| WDR-HIGH | 6.245 | 13.4 | 35 | 5.0e-06 | 2.160 |
| WDR-MID | 6.273 | 18.2 | 35 | 5.0e-06 | 1.800 |
| WDR-LOW | 6.200 | 52.7 | 35 | 5.0e-06 | 7.102 |

Notes:

* Injection gas is delivered dry and liquid-free (source 40 mg/Sm3, no free liquid), so no treatment is required; only cooling is applied.
* Withdrawal gas is separated (0.9995 efficiency) and dehydrated (35 mg/Sm3) before metering.
* Well-group allocations are equal shares of the scenario flow (Q/6 per well); the peak allocation is 20 kg/s against the 25 kg/s per-interface limit.

### 6.4 Reliability (n-1) provisions

* **Compression n-1** (applies to all three injection scenarios and to WDR-LOW): after any one compressor is unavailable, the remaining two units provide at least 100 kg/s, exceeding the 70 % requirement (84 / 70 / 52.5 / 49 kg/s for INJ-LOW / INJ-MID / INJ-HIGH / WDR-LOW).
* **Withdrawal treatment n-1**: each train is rated 120 kg/s; if one separator or one dehydration unit is unavailable, the surviving train alone provides 120 kg/s >= 84 kg/s.
* **Delivery limits remain applicable after any outage** - the surviving equipment preserves the water, free-liquid and temperature limits.

---

## 7. Site layout, safety and maintenance access

The plant is laid out on a 700 m x 450 m flat site. All footprints avoid the `FUTURE-EXPANSION`, `DRAINAGE-CHANNEL` and `GRID-FACILITY` no-build zones. A plan view is rendered in `layout.svg`.

### 7.1 Footprint separation

Boundary-to-boundary separations are verified against `safety_requirements.json` for every equipment pair (compressor/compressor 6 m, compressor/hydrocarbon-treatment 10 m, compressor/metering 6 m, compressor/pressure-control 8 m, compressor/drain 12 m, hydrocarbon-treatment/hydrocarbon-treatment 5 m, and so on). The layout is organised in a well-side header row (y = 225 m), two treatment trains (y = 170 m and y = 280 m) and an injection row (y ~ 320-445 m) with generous clearances.

### 7.2 Maintenance envelopes

* Every required routine-clearance envelope lies inside the site, avoids equipment-exclusion interiors and does not touch any other footprint.
* Heavy-maintenance removal envelopes (compressors only) are also clear of all other footprints and of the exclusion zones.
* Total required maintenance area: 1544.8 m2; total equipment footprint area: 803.0 m2.

### 7.3 Roads and access

A 2350 m single connected road network (6 m wide) links `ROAD-ENTRANCE` to the process area and provides access to every model that declares `road_access_required` (separators) and `crane_access_required` (compressors).

| Road | Centreline | Width (m) | Length (m) |
|---|---|---:|---:|
| R-A | (0.0, 225.0) -> (100.0, 225.0) | 6 | 100 |
| R-B | (100.0, 110.0) -> (100.0, 430.0) | 6 | 320 |
| R-C | (100.0, 110.0) -> (620.0, 110.0) | 6 | 520 |
| R-D | (100.0, 178.0) -> (620.0, 178.0) | 6 | 520 |
| R-E | (100.0, 290.0) -> (545.0, 290.0) | 6 | 445 |
| R-F | (100.0, 365.0) -> (545.0, 365.0) | 6 | 445 |

---

## 8. Piping classes and installation levels

| Class | Max pressure (MPa) | T limits (degC) | Roughness (m) | Wet | Dry | Liquid drain | Multiplier |
|---|---:|---|---:|---|---|---|---:|
| CS-WET-100 | 10.0 | [-20, 100] | 4.5e-05 | True | True | True | 1.0 |
| CS-WET-160 | 16.0 | [-20, 120] | 4.5e-05 | True | True | True | 1.18 |
| CS-DRY-160 | 16.0 | [-20, 120] | 1.5e-05 | False | True | False | 1.15 |

All gas lines conveying the high-pressure injection/withdrawal gas use CS-WET-160 (16 MPa); post-regulation and suction-side lines use CS-WET-100 (10 MPa), which is compatible with both wet and dry gas. Liquid drain lines use CS-WET-100 (liquid-drain compatible).

Peak gas velocities remain well below the 25 m/s limit (highest ~21 m/s at G-T-M during WDR-HIGH). Pipe diameters were selected by a lifecycle-cost optimisation: the additional capital of the larger sizes is outweighed by the reduction in compression energy.

---

## 9. Quantities and lifecycle cost

### 9.1 Quantities

* Equipment instances: 19 (C40 x 1, C60 x 2, COOL120 x 1, DEHY120 x 2, DRN-L x 2, HDR120 x 6, MTR160 x 2, REG180 x 1, SEP120 x 2)
* Total installed pipeline length: 5227.5 m
* Road centreline length: 2350.0 m
* Equipment footprint area: 803.0 m2
* Required maintenance area: 1544.8 m2
* Annual energy consumption: 41056.3 MWh/y

### 9.2 Lifecycle-cost basis

* Present-value factor: PVF = (1 - 1.08^-20)/0.08 = 9.818147
* Energy tariff: 0.00012 MBCU/MWh; road: 0.00015 MBCU/m; foundation: 4e-06 MBCU/m2; maintenance area: 1e-06 MBCU/m2.

### 9.3 LCC result

| Component | Value (MBCU) |
|---|---:|
| Equipment CAPEX | 29.2200 |
| Piping CAPEX | 1.8104 |
| Civil / access CAPEX | 0.3573 |
| Energy present value | 48.3716 |
| Maintenance present value | 10.3876 |
| **Total LCC** | **90.1469** |

Annual energy by scenario (MW x h):

* INJ-LOW: 8.237 MW x 900 h = 7412.9 MWh
* INJ-MID: 13.085 MW x 1300 h = 17010.8 MWh
* INJ-HIGH: 13.752 MW x 600 h = 8251.2 MWh
* WDR-HIGH: 2.160 MW x 500 h = 1080.0 MWh
* WDR-MID: 1.800 MW x 900 h = 1620.0 MWh
* WDR-LOW: 7.102 MW x 800 h = 5681.4 MWh

---

## 10. Verification

An independent check script (`verify.py`) evaluates 577 assertions covering geometry, separation, maintenance envelopes, road access, port cardinality, pipe velocity and rating, equipment capacities and pressure/temperature limits, compressor envelopes, delivery quality limits, metering and the two n-1 rules. **577 of 577 pass, 0 fail.** Full results are in `verification.json`.

---

## 11. Known limitations

* Synthetic benchmark data only; no vendor quotations, no code compliance, no detailed mechanical, electrical, control, structural or civil design.
* Valve-level isolation of inactive shared-header branches is stated but not modelled as equipment; dynamic/transient behaviour, surge, hydrate formation and liquid flashing are out of scope per the brief.
* Water removed by dehydration, its regeneration stream and disposal are excluded.
* The stated grid-tie delivery requirement is a minimum pressure; the design controls the grid pressure to 6.2-6.5 MPa. No maximum grid pressure is imposed by the brief.

