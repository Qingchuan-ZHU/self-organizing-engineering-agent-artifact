# UGS-SYNTH-D01 v1.1 - Underground Gas Storage Facility Design Report

Case `UGS-SYNTH-D01` (`case_version` 1.1.0-development). All data are the synthetic benchmark values published with the case; **no vendor data, production criteria, code or regulatory content is used**. Units are SI as declared in the brief (MPa, degC, kg/s, m, MBCU).

## 1. Purpose and scope

A single gas-storage station exchanges gas with the grid at `GRID-TIE` and with six well groups `WG-01..WG-06`, in two services:

* **Injection** - grid gas is metered, compressed, aftercooled and delivered to the six well groups.
* **Withdrawal** - well-group gas is separated, dehydrated, then either let down by a regulator (high/mid well pressure) or boosted (low well pressure), metered and returned to the grid.

Scope covers process architecture, equipment selection and counting, train architecture, process topology, operating philosophy, pipe sizing/class, layout, routing, maintenance access and roads, quantities and the lifecycle-cost (LCC) basis. Reservoir, wells, full electrical/control/firewater networks and detailed civil/structural design are excluded as published.

## 2. Design basis and assumptions

* Gas properties, pipe pressure loss, compressor/regulator/cooler/separation behaviour and the LCC rules follow `engineering_calculation_basis.md` exactly (Z and viscosity proxies, Darcy / Swamee-Jain friction factor, fixed-point outlet-pressure solution, `PVF = (1-(1+i)^-N)/i`).
* Geometry (footprints, safety separation matrix, maintenance envelopes, roads, route exclusions, same-level overlap rule) follows `engineering_geometry_basis.md` and `network_semantics.md`.
* Gas-delivery limits: free-liquid loading <= 0.0001 kg/kg, water <= 50 mg/Sm3, temperature -10..60 degC.

Key engineering assumptions:

* **Liquid-drain velocity** uses an assumed liquid density of 1000 kg/m3, because the basis supplies only a gas-density law; this is conservative for the 3 m/s drain limit.
* **Valve lineups / inactive branches.** The station shares headers between services, so a physical loop exists. Each published scenario is executed with an explicit valve lineup: only the active path carries flow and all other branches are isolated (standard operating philosophy). Scenario mass and pressure balances below are computed on the active path only.
* **Pipe bores** were selected to minimise benchmark LCC (energy dominates LCC, so larger bores that reduce compression load are preferred) subject to the published gas (25 m/s) and liquid-drain (3 m/s) velocity limits. A conventional ~15 m/s sizing gives an LCC of about 105.4 MBCU; the selected LCC-optimal sizing is 103.49 MBCU.
* Liquid-drain lines are used only by the closed-drain network; the drain domain is assumed at <= 1 MPa with the idealised integral letdown at each separator outlet.

## 3. System architecture and process connections

Four gas headers provide all branching/merging (arbitrary zero-cost junctions are not used):

* **H-GS** (grid-side header, HDR120) - ties the two metering legs, the two boosting compressors' suctions, the injection compressor suctions and the regulator outlet.
* **H-CH** (injection discharge header, HDR120) - collects the injection compressor discharges and feeds the aftercooler.
* **H-WS** (well-side header, HDR120) - collects/fans out the six well lines and connects the aftercooler outlet and the three separator feeds.
* **H-TS** (treated header, HDR120) - collects the three dehydration outlets and feeds the regulator and the two booster suctions.

Metering is mandatory at `GRID-TIE`. Because the catalogue meters are one-way (gas_in -> gas_out), two meters are installed on the two opposite-direction legs of the boundary: `MTR-INJ` on GRID-TIE -> H-GS (injection) and `MTR-WDR` on H-GS -> GRID-TIE (withdrawal). Each is rated 120 kg/s, so in every scenario all exchanged gas passes through active metered capacity equal to the full flow.

External utility boundaries (`POWER-TIE`, `FIREWATER-TIE`, `INSTRUMENT-AIR-TIE`) are abstract `utility_in` boundaries and are not process-connected. `ROAD-ENTRANCE` connects only to the road network. `LIQUID-DRAIN-OUTFALL` terminates the closed-drain network.

### Connection list

| # | From | To | Service | DN | Class | Level | Length (m) |
|---|------|----|---------|----|-------|-------|-----------|
| 1 | N-MTRINJ-GRID A(613,240) | B(700,225) | gas | DN700 | CS-WET-100 | ground | 102.0 |
| 2 | N-MTRINJ-GS A(617,240) | B(563,201) | gas | DN700 | CS-WET-100 | ground | 93.0 |
| 3 | N-GS-MTRWDR A(563,199) | B(613,210) | gas | DN500 | CS-WET-100 | ground | 61.0 |
| 4 | N-MTRWDR-GRID A(617,210) | B(700,225) | gas | DN500 | CS-WET-100 | ground | 98.0 |
| 5 | N-GS-CI1 A(557,199.25) | B(352.5,140) | gas | DN500 | CS-WET-100 | ground | 263.8 |
| 6 | N-GS-CI2 A(558.5,198.5) | B(382.5,140) | gas | DN500 | CS-WET-100 | ground | 234.5 |
| 7 | N-GS-CI3 A(557,200.75) | B(414,140) | gas | DN150 | CS-WET-100 | ground | 203.8 |
| 8 | N-CI1-CH A(367.5,140) | B(452,199.25) | gas | DN450 | CS-DRY-160 | ground | 143.8 |
| 9 | N-CI2-CH A(397.5,140) | B(452,200.75) | gas | DN450 | CS-DRY-160 | ground | 115.2 |
| 10 | N-CI3-CH A(426,140) | B(453,201.5) | gas | DN150 | CS-DRY-160 | ground | 88.5 |
| 11 | N-CH-COOL A(458,201) | B(479,240) | gas | DN600 | CS-DRY-160 | ground | 60.0 |
| 12 | N-COOL-WS A(491,240) | B(353,200) | gas | DN600 | CS-DRY-160 | ground | 178.0 |
| 13 | N-WS-WG1 A(347,199.25) | B(12,45) | gas | DN300 | CS-WET-160 | ground | 489.2 |
| 14 | N-WS-WG2 A(348,201.5) | B(12,117) | gas | DN300 | CS-WET-160 | ground | 420.5 |
| 15 | N-WS-WG3 A(350,201.5) | B(12,189) | gas | DN300 | CS-WET-160 | ground | 351.0 |
| 16 | N-WS-WG4 A(347,200.75) | B(12,261) | gas | DN300 | CS-WET-160 | ground | 395.2 |
| 17 | N-WS-WG5 A(348.5,198.5) | B(12,333) | gas | DN300 | CS-WET-160 | ground | 471.0 |
| 18 | N-WS-WG6 A(352,201.5) | B(12,405) | gas | DN300 | CS-WET-160 | ground | 543.5 |
| 19 | N-WS-SEP1 A(353,201) | B(364,292) | gas | DN300 | CS-WET-160 | ground | 102.0 |
| 20 | N-WS-SEP2 A(353,199) | B(448,292) | gas | DN350 | CS-WET-160 | ground | 188.0 |
| 21 | N-WS-SEP3 A(351.5,198.5) | B(531,292) | gas | DN350 | CS-WET-160 | ground | 273.5 |
| 22 | N-SEP1-DEH1 A(372,292) | B(395,292) | gas | DN300 | CS-WET-160 | ground | 23.0 |
| 23 | N-SEP2-DEH2 A(456,292) | B(480,292) | gas | DN250 | CS-WET-160 | ground | 24.0 |
| 24 | N-SEP3-DEH3 A(539,292) | B(563,292) | gas | DN300 | CS-WET-160 | ground | 24.0 |
| 25 | N-DEH1-TS A(405,292) | B(457,261.25) | gas | DN300 | CS-DRY-160 | ground | 83.2 |
| 26 | N-DEH2-TS A(490,292) | B(458,263.5) | gas | DN300 | CS-DRY-160 | ground | 61.5 |
| 27 | N-DEH3-TS A(573,292) | B(463,263) | gas | DN350 | CS-DRY-160 | ground | 139.0 |
| 28 | N-TS-REG A(463,262) | B(602.5,180) | gas | DN350 | CS-DRY-160 | ground | 221.5 |
| 29 | N-REG-GS A(607.5,180) | B(563,200) | gas | DN400 | CS-WET-100 | ground | 64.5 |
| 30 | N-TS-CW1 A(461.5,260.5) | B(507.5,140) | gas | DN400 | CS-DRY-160 | ground | 166.5 |
| 31 | N-TS-CW2 A(463,261) | B(542.5,140) | gas | DN400 | CS-DRY-160 | ground | 200.5 |
| 32 | N-CW1-GS A(522.5,140) | B(560,201.5) | gas | DN400 | CS-WET-100 | ground | 99.5 |
| 33 | N-CW2-GS A(557.5,140) | B(562,201.5) | gas | DN250 | CS-WET-100 | ground | 67.5 |
| 34 | N-SEP1-DRN1 A(368,290) | B(594,140) | liquid | DN150 | CS-WET-100 | ground | 376.0 |
| 35 | N-SEP2-DRN2 A(452,290) | B(594,155) | liquid | DN150 | CS-WET-100 | ground | 277.0 |
| 36 | N-SEP3-DRN3 A(535,290) | B(594,170) | liquid | DN150 | CS-WET-100 | ground | 179.0 |
| 37 | N-DRN1-OUT A(596,140) | B(680,120) | liquid | DN150 | CS-WET-100 | ground | 104.0 |
| 38 | N-DRN2-OUT A(596,155) | B(680,120) | liquid | DN150 | CS-WET-100 | ground | 119.0 |
| 39 | N-DRN3-OUT A(596,170) | B(680,120) | liquid | DN150 | CS-WET-100 | ground | 134.5 |

Endpoint coordinates A and B are the world locations of the two ports (equipment port offsets rotated by the equipment orientation; boundary interfaces at their published points). Complete vertex lists are in `design_output.json` (`pipelines[].segments`).

### Header port assignment

| Header | Port -> connection |
|--------|--------------------|
| H-GS | branch_02=N-MTRINJ-GS, branch_10=N-GS-MTRWDR, branch_06=N-REG-GS, branch_04=N-GS-CI1, branch_07=N-GS-CI2, branch_08=N-GS-CI3, branch_05=N-CW1-GS, branch_09=N-CW2-GS |
| H-CH | branch_04=N-CI1-CH, branch_08=N-CI2-CH, branch_01=N-CI3-CH, branch_02=N-CH-COOL |
| H-WS | branch_06=N-COOL-WS, branch_04=N-WS-WG1, branch_01=N-WS-WG2, branch_05=N-WS-WG3, branch_08=N-WS-WG4, branch_07=N-WS-WG5, branch_09=N-WS-WG6, branch_02=N-WS-SEP1, branch_10=N-WS-SEP2, branch_03=N-WS-SEP3 |
| H-TS | branch_04=N-DEH1-TS, branch_01=N-DEH2-TS, branch_02=N-DEH3-TS, branch_06=N-TS-REG, branch_03=N-TS-CW1, branch_10=N-TS-CW2 |

## 4. Equipment selection and capacities

| Tag | Model | Category | Capacity (kg/s) | x (m) | y (m) | Orient. (deg) |
|-----|-------|----------|-----------------|-------|-------|---------------|
| MTR-INJ | MTR120 | meter | 120 | 615 | 240 | 0 |
| MTR-WDR | MTR120 | meter | 120 | 615 | 210 | 0 |
| H-GS | HDR120 | header | 120 | 560 | 200 | 0 |
| H-CH | HDR120 | header | 120 | 455 | 200 | 0 |
| H-WS | HDR120 | header | 120 | 350 | 200 | 0 |
| H-TS | HDR120 | header | 120 | 460 | 262 | 0 |
| COOL-1 | COOL120 | cooler | 120 | 485 | 240 | 0 |
| C-I1 | C60 | compressor | 60 | 360 | 140 | 0 |
| C-I2 | C60 | compressor | 60 | 390 | 140 | 0 |
| C-I3 | C40 | compressor | 40 | 420 | 140 | 0 |
| C-W1 | C60 | compressor | 60 | 515 | 140 | 0 |
| C-W2 | C60 | compressor | 60 | 550 | 140 | 0 |
| SEP-1 | SEP70 | separator | 70 | 368 | 292 | 0 |
| SEP-2 | SEP70 | separator | 70 | 452 | 292 | 0 |
| SEP-3 | SEP70 | separator | 70 | 535 | 292 | 0 |
| DEH-1 | DEHY70 | dehydration | 70 | 400 | 292 | 0 |
| DEH-2 | DEHY70 | dehydration | 70 | 485 | 292 | 0 |
| DEH-3 | DEHY70 | dehydration | 70 | 568 | 292 | 0 |
| REG-1 | REG120 | regulator | 120 | 605 | 180 | 0 |
| DRN-1 | DRN-S | closed_drain | 0.8 | 595 | 140 | 0 |
| DRN-2 | DRN-S | closed_drain | 0.8 | 595 | 155 | 0 |
| DRN-3 | DRN-S | closed_drain | 0.8 | 595 | 170 | 0 |

Selection rationale:

* **Injection compression.** `INJ-LOW` is the binding reliability case (120 kg/s, 70% retained = 84 kg/s after the loss of one unit). Two `C60` units carry the full 120 kg/s in normal service (60 kg/s each, within capacity and above minimum stable flow); a single spare `C40` covers the N-1 requirement (a `C60` + the `C40` = 100 kg/s >= 84 kg/s). Two `C80` units cannot meet N-1 (80 < 84), so three units are required; the `2 x C60 + 1 x C40` set has the lowest capital cost.
* **Withdrawal boosting.** `WDR-LOW` (4.5 -> 6.0 MPa) needs N-1 of 49 kg/s, so two `C60` boosters (60 kg/s each) are the smallest compliant set.
* **Treatment.** Withdrawal gas carries 0.01 kg/kg free liquid and 220 mg/Sm3 water. A `SEP70` (16 MPa rated, 0.9995 removal) brings loading to 5e-6 (<= 1e-4) and a `DEHY70` (16 MPa rated, outlet 35 mg/Sm3) brings water to 35 (<= 50). N-1 needs each of 2 remaining trains to carry 42 kg/s (0.7 x 120 / 2), which exceeds the 40 kg/s `SEP40`/`DEHY40` sizes, and the 10 MPa `SEP120`/`DEHY120` are below the 11.9 MPa source - so three 70-size units of each are selected.
* **Aftercooler.** A single `COOL120` cools the combined injection discharge to 58 degC (<= 60 degC delivery limit); in `INJ-LOW` the compressor outlet is only ~50 degC and no cooling is needed.
* **Regulation.** One `REG120` (16 MPa rated) throttles WDR-HIGH / WDR-MID to the grid pressure.
* **Closed drains.** One `DRN-S` per separator (0.8 kg/s >= 0.42 kg/s worst case) discharging directly to `LIQUID-DRAIN-OUTFALL` (3 of <= 8 connections; <= 1.2 kg/s of <= 10 kg/s).

## 5. Operating philosophy and scenario plans

All six published scenarios are executed at full stated flow; well-group allocations are equal (`flow/6` <= 20 kg/s each, within the 25 kg/s boundary limit).

### Injection (GRID-TIE -> 6 well groups)

Path: `GRID-TIE -> MTR-INJ -> H-GS -> C-I1/C-I2 (parallel) -> H-CH -> COOL-1 -> H-WS -> 6 well lines`. Both `C60` units run in balanced load; the `C40` spare is isolated. The compressor discharge header pressure is set so the lowest well-group pressure equals the required sink pressure.

| Scenario | Flow (kg/s) | Source (MPa/degC) | Sink (MPa) | Per unit (kg/s) | Ratio | Outlet (degC) | P_CH (MPa) | Cooler out (degC) | Hours |
|----------|-------------|-------------------|------------|-----------------|-------|---------------|------------|-------------------|-------|
| INJ-LOW | 120 | 6.5/25 | 8.5 | 60 | 1.329 | 50.2 | 8.57 | 50.2 | 900 |
| INJ-MID | 100 | 6.5/25 | 11 | 50 | 1.711 | 74.2 | 11.06 | 58.0 | 1300 |
| INJ-HIGH | 75 | 6.5/25 | 13.5 | 37.5 | 2.094 | 94.3 | 13.55 | 58.0 | 600 |

### Withdrawal (6 well groups -> GRID-TIE)

Path: `6 well lines -> H-WS -> 3 x SEP70 -> 3 x DEHY70 -> H-TS -> REG120 (or 2 x C60 boosters) -> MTR-WDR -> GRID-TIE`. Removal produces an explicit liquid side stream per separator to its closed drain.

| Scenario | Flow (kg/s) | Source (MPa/degC) | Sink (MPa) | Device | Setpoint | Delivery (degC) | Hours |
|----------|-------------|-------------------|------------|--------|----------|-----------------|-------|
| WDR-HIGH | 120 | 12/20 | 6 | REG120 | 11.76 -> 6.08 MPa | 13.2 | 500 |
| WDR-MID | 100 | 8/20 | 6 | REG120 | 7.76 -> 6.06 MPa | 18.0 | 900 |
| WDR-LOW | 70 | 4.5/20 | 6 | 2 x C60 | boost to 6.04 MPa (r=1.389) | 48.9 | 800 |

Delivered quality in all withdrawal scenarios: water 35 mg/Sm3, free-liquid 5e-6 kg/kg, temperature 13-49 degC - all within the project limits. GRID-TIE is delivered at 6.00 MPa in every withdrawal case.

### Valve lineups (active branches per scenario)

The station re-uses its headers for both services, so a physical loop exists. Each scenario is run with the lineups below; every branch not listed as open is isolated.

| Scenario | Open branches | Isolated branches |
|----------|---------------|-------------------|
| INJ-LOW / INJ-MID / INJ-HIGH | GRID-TIE-MTR-INJ-H-GS; H-GS -> C-I1, C-I2 (suction); C-I1, C-I2 -> H-CH; H-CH -> COOL-1 -> H-WS; H-WS -> WG-01..06 | all withdrawal/booster/regulator branches; liquid branches (no flow) |
| WDR-HIGH / WDR-MID | WG-01..06 -> H-WS; H-WS -> SEP-1..3 -> DEH-1..3 -> H-TS; H-TS -> REG-1 -> H-GS -> MTR-WDR -> GRID-TIE | injection compressor branches; booster branches |
| WDR-LOW | WG-01..06 -> H-WS; H-WS -> SEP-1..3 -> DEH-1..3 -> H-TS; H-TS -> C-W1, C-W2 -> H-GS -> MTR-WDR -> GRID-TIE | injection compressor branches; regulator branch |

The three separator liquid branches (SEP-i -> DRN-i -> LIQUID-DRAIN-OUTFALL) are always physically connected; they carry flow only in the withdrawal scenarios.

### Reliability (N-1) verification

Full hydraulic re-solves confirm the retained flows below.

| Case | Units lost | Retained flow (kg/s) | Result |
|------|-----------|----------------------|--------|
| INJ-LOW injection | C-I1 | 84 | OK |
| INJ-LOW injection | C-I2 | 84 | OK |
| INJ-LOW injection | C-I3 | 84 | OK |
| INJ-MID injection | C-I1 | 70 | OK |
| INJ-MID injection | C-I2 | 70 | OK |
| INJ-MID injection | C-I3 | 70 | OK |
| INJ-HIGH injection | C-I1 | 52.5 | OK |
| INJ-HIGH injection | C-I2 | 52.5 | OK |
| INJ-HIGH injection | C-I3 | 52.5 | OK |
| WDR-HIGH treatment | 1 separator/dehydration | 84 | OK |
| WDR-MID treatment | 1 separator/dehydration | 70 | OK |
| WDR-LOW treatment | 1 separator/dehydration | 49 | OK |
| WDR-LOW boosting | 1 booster | 49 | OK |

Worst injection case (loss of a `C60` in `INJ-HIGH`) needs the spare `C40` at ratio 2.25 (limit 2.4) and 105 degC outlet (limit 150 degC) - within limits.

## 6. Site layout, safety, maintenance and roads

Site is 700 x 450 m flat. The process area occupies x 330-620 m, y 100-310 m; metering sits near `GRID-TIE` (700,225) and the six well lines run west to `WG-01..06` at x=12 m.

* Every footprint is inside the site, outside the `FUTURE-EXPANSION`, `DRAINAGE-CHANNEL` and `GRID-FACILITY` equipment-exclusion interiors, and no two footprints overlap.
* Minimum safety separation (footprint boundary to boundary) is satisfied for every category pair using the published matrix (compressor-compressor 6 m, compressor-hydrocarbon 10 m, compressor-drain 12 m, hydrocarbon-hydrocarbon 5 m, metering-metering 4 m, etc.).
* Routine clearance plus the removal envelope of the six heavy-maintenance compressors stay inside the site, outside exclusion interiors and clear of other equipment footprints.
* Roads (5 centreline sections, 6 m wide, total 1343 m) form one connected network containing `ROAD-ENTRANCE`. Every model with `road_access_required` is within 7 m and every `crane_access_required` model within 4.5 m of a paved road.

## 7. Piping and network definition

All 39 pipelines are installed at `ground` level (the ground routing level has zero pipeline civil cost); no two same-level segments overlap, no segment enters a pipeline-exclusion interior and none crosses an equipment footprint. Pipe class is chosen as the cheapest class rated for the highest pressure the line can see and compatible with the conveyed condition:

| Class | Rating (MPa) | Temperature (degC) | Compatible | Multiplier |
|-------|--------------|--------------------|------------|------------|
| CS-WET-100 | 10 | -20..100 | wet & dry & liquid | 1.00 |
| CS-DRY-160 | 16 | -20..120 | dry | 1.15 |
| CS-WET-160 | 16 | -20..120 | wet & dry & liquid | 1.18 |

Length by bore: DN150 1482 m, DN250 92 m, DN300 2964 m, DN350 822 m, DN400 531 m, DN450 259 m, DN500 657 m, DN600 238 m, DN700 195 m; total 7240 m.

## 8. Quantities

| Item | Quantity |
|------|----------|
| Equipment C40 | 1 |
| Equipment C60 | 4 |
| Equipment COOL120 | 1 |
| Equipment DEHY70 | 3 |
| Equipment DRN-S | 3 |
| Equipment HDR120 | 4 |
| Equipment MTR120 | 2 |
| Equipment REG120 | 1 |
| Equipment SEP70 | 3 |
| Pipelines | 39 |
| Total pipe length | 7240 m |
| Road centreline | 1343 m |
| Equipment footprint area | 997 m2 |
| Required maintenance area | 1976 m2 |

## 9. Lifecycle cost

PVF = (1-(1+0.08)^-20)/0.08 = 9.8181. Energy tariff 0.00012 MBCU/MWh.

| Component | Value (MBCU) |
|-----------|--------------|
| Equipment CAPEX | 41.590 |
| Piping CAPEX | 1.997 |
| Civil / access CAPEX | 0.207 |
| Energy present value | 46.394 |
| Maintenance present value | 13.304 |
| **LCC total** | **103.491** |

Annual energy 39378 MWh (4.725 MBCU/yr) dominated by injection compression; maintenance 1.355 MBCU/yr.

Per-scenario annual energy (MWh): INJ-LOW 6956, INJ-MID 16494, INJ-HIGH 8096, WDR-HIGH 1080, WDR-MID 1620, WDR-LOW 5132.

## 10. Verification

* Geometry/safety/maintenance/road checks: pass.
* Scenario hydraulic and equipment-limit checks: 205 passed, 0 failed.
* All pipe-loss fixed-point solutions converged (0 non-converged).
* All N-1 reliability cases pass (Section 5).

## 11. Known limitations

* All values follow the synthetic v1.1 deterministic basis; they are not vendor or production data.
* Liquid-drain velocity uses an assumed liquid density of 1000 kg/m3 (the basis provides only a gas density law).
* Inactive branches are treated as isolated by valves per the published operating philosophy; a scenario only carries flow on its active path.
* Compressor bank: 2 x C60 in normal service with one C40 spare provides compression N-1 for injection; 2 x C60 boosters provide N-1 for WDR-LOW.
* Pipe bores were selected to minimise lifecycle cost subject to the 25 m/s (gas) and 3 m/s (liquid) velocity limits.
* No elevation, minor losses, or heat transfer between equipment are modelled (per basis).
