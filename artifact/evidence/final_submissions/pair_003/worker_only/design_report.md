# UGS-SYNTH-D01 — Underground Gas Storage Surface Facility

## Design report

| | |
|---|---|
| Case | `UGS-SYNTH-D01`, basis version 1.1.0-development |
| Objective | Minimum benchmark lifecycle cost (LCC) among feasible designs |
| Deliverable status | Final design, all public requirements verified |
| Result | **LCC = 87.5201 MBCU** (equipment 28.950 + piping 1.5549 + civil/access 0.1362 + energy PV 46.5602 + maintenance PV 10.3189) |
| Validation | 0 open findings across 14 independent check groups (geometry, safety separation, maintenance access, roads, routing, port rules, hydraulics, pipe class, equipment envelopes, delivery quality, metering, boundary limits, design completeness, N-1 reliability) |

All quantities are SI: metres, kg/s, MPa, °C, MW, MWh, MBCU. Every number in this
report is reproducible from `calc/` (`python calc/validate.py`, `python calc/export.py`);
the complete machine-readable design is `data/design.json`.

---

## 1. Design basis and assumptions

### 1.1 Governing documents

The design is computed strictly against the published synthetic benchmark basis:

* `engineering_calculation_basis.md` — gas properties, pipe hydraulics, equipment
  models, scenario/mixing rules, reliability definitions, LCC basis.
* `engineering_geometry_basis.md` — placement, footprints, separation, maintenance
  envelopes, roads, pipeline routes, exclusion zones, tolerances.
* `network_semantics.md` — port compatibility/direction, connection cardinality,
  header/junction rules, metering, liquid handling.
* `project_requirements.json`, `operating_scenarios.json`, `well_group_interfaces.json`,
  `site.json`, `safety_requirements.json`, `maintenance_requirements.json`,
  `economic_assumptions.json`, `piping_catalog.json`, `equipment_catalog/*.json`.

All tolerances of the calculation basis are applied when comparing a computed value
with a published limit.

### 1.2 Key assumptions (stated so the design can be recalculated)

| # | Assumption | Basis / justification |
|---|---|---|
| A1 | Equipment footprints and maintenance envelopes are axis-aligned rectangles because every installed model uses `orientation_deg` of 0° or 90° (the only catalogued options). | geometry basis |
| A2 | The routine maintenance envelope is the footprint inflated on all sides by `clearance_m`; the heavy-maintenance removal envelope is an added rectangle of `[extent × transverse width]` centred on the footprint on the catalogued `side` (rotated with the equipment). | geometry basis |
| A3 | Process branching/merging is performed only through catalogued header (`HDR…`) branch ports, because ordinary ports allow one physical connection and arbitrary zero-cost junctions are excluded. | network semantics |
| A4 | Scenario flow paths are selected by an isolation-valve line-up. Valves are not catalogued equipment in this benchmark and are therefore modelled as the *scenario-specific active path*: only the pipelines and equipment listed for a scenario carry flow. Compressor-station isolation is by the catalogued station **bypass line** (`PL-26`). | network semantics ("scenario operating paths"); this is the only way to obtain the required bidirectional station service |
| A5 | The undesignated liquid let-down into the closed-drain domain is the idealised integral let-down of `network_semantics.md`; no liquid let-down equipment, flashing or transient behaviour is modelled. | network semantics |
| A6 | Liquid velocity in the drain lines uses a synthetic liquid density of 1000 kg/m³ (liquid properties are not published). This is conservative (real condensate is lighter, hence faster). | engineering judgement |
| A7 | Injection delivery temperature is controlled to 58 °C by the after-cooler, i.e. 2 °C inside the 60 °C limit. The optimum without margin is exactly 60 °C; 58 °C costs 0.03 MBCU and removes limit-risk. | calc sensitivity study |
| A8 | Where several parallel units operate in a bank, flow is split equally unless a different split is stated in §4. Merged pressure is the lowest incoming pressure, merged temperature/water/free-liquid are gas-flow-weighted (calculation basis). | calculation basis |
| A9 | No minor losses, elevation correction, heat transfer or liquid hold-up are modelled for pipelines, as the calculation basis prescribes. | calculation basis |
| A10 | Well-group flow is metered only at `GRID-TIE` (the only mandatory metering boundary). | project requirements |

### 1.3 Excluded scope (per `project_requirements.json`)

Reservoir model, well completion, full electrical/control systems, firewater synthesis,
structural design, buildings, complete civil design, full process safety study,
regulatory/code compliance, vendor procurement. Electric power, instrument air and
firewater are abstract services assumed available in sufficient quantity; only
catalogued equipment energy appears in the LCC.

---

## 2. Battery limits and external interfaces

| Interface | Type | Port type | Position (m) | Connections used / allowed | Flow limit |
|---|---|---|---|---|---|
| `GRID-TIE` | process | `gas_bidirectional` | (700, 225) | 2 / 2 | 160 kg/s |
| `WG-01 … WG-06` | well group | `gas_bidirectional` | (12, 45/117/189/261/333/405) | 1 / 1 each | 25 kg/s each |
| `LIQUID-DRAIN-OUTFALL` | drain | `drain_in` | (680, 120) | 3 / 8 | 10 kg/s |
| `ROAD-ENTRANCE` | road | `road_access` | (0, 225) | road network only | — |
| `POWER-TIE`, `FIREWATER-TIE`, `INSTRUMENT-AIR-TIE` | utility | `utility_in` | (660, 35), (620, 35), (580, 35) | no process piping | abstract |

`GRID-TIE` uses exactly its two permitted connections: one import line to the injection
meter (`PL-32`) and one export line from the withdrawal meter (`PL-31`).

---

## 3. Process architecture

### 3.1 Concept

A single, bidirectional, single-train station between `GRID-TIE` and the six well
groups, with wet-gas treatment installed only where it is needed (withdrawal) and
the after-cooler installed only where it is needed (injection):

```
                     ┌──────────────── INJECTION ────────────────┐
 GRID-TIE ─ PL-32 ─ MI ─ PL-33 ─ HCS ─┬─ C1 ─┐
                                      ├─ C2 ─┼─ HCD ─ PL-27 ─ COOL ─ PL-28 ─ HM ─ 6 well lines
                                      └─ C3 ─┘
                     ┌─────────────── WITHDRAWAL ────────────────┐
 6 well lines ─ HM ─ PL-07 ─ HSI ─┬─ SEP1 ─┐┌─ DH1 ─┐
                                  ├─ SEP2 ─┼┼─ DH2 ─┼─ HCS ─ [compressor bank or
                                  └─ SEP3 ─┘└─ DH3 ─┘   bypass PL-26] ─ HCD ─
                                     ─ PL-29 ─ REG ─ PL-30 ─ MW ─ PL-31 ─ GRID-TIE
```

* **`HM`** — well-group manifold (`HDR180`): six branches to the well groups, one
  branch to the injection supply (`PL-28`), one to the withdrawal trunk (`PL-07`).
* **`HSI` / `HSD`** — separator inlet manifold and combined separator-outlet /
  dehydration-inlet manifold.
* **`HCS` / `HCD`** — compressor suction and discharge manifolds.
* **`MI` / `MW`** — mandatory import and export fiscal meters at `GRID-TIE`.
* **`REG`** — withdrawal delivery regulator (the only pressure-control device).
* **`COOL`** — injection after-cooler, on the injection branch only.
* **`D1 … D3`** — closed drains; each separator `liquid_out` is individually connected
  to a closed drain and each drain discharges to `LIQUID-DRAIN-OUTFALL`.

### 3.2 Why this architecture

* The three treatment duties are **service-specific**: injection gas needs no
  separation (free liquid 0) and no dehydration (40 mg/Sm³ is already inside the
  50 mg/Sm³ limit) but does need cooling (compressor discharge 50–95 °C); withdrawal
  gas needs separation (0.01 kg/kg → 5 × 10⁻⁶ kg/kg) and dehydration (220 → 35 mg/Sm³)
  but never needs *heating* (the free JT cooling of the 12→6 MPa let-down leaves the
  gas at ≈13 °C, well inside the −10 °C limit). Placing each duty only in the branch
  where it is required removes three unnecessary pressure drops from the other service.
* The compressor station doubles as the withdrawal booster (**WDR-LOW** needs
  4.5 → 6.0 MPa). It is therefore built with a **bypass line** (`PL-26`) that is open in
  WDR-MID / WDR-HIGH so the station is not in the flow path when no compression is
  required. No separate booster compressor is installed.
* All parallel banks contain **three** units. A single unit is not large enough for the
  largest scenario (max catalogue gas capacity 120 kg/s) and N-1 reliability requires
  at least three units in each of the separator, dehydration and compression banks (§7).

---

## 4. Operating philosophy and scenario plans

### 4.1 Fixed setpoints

| Setpoint | Value | Reason |
|---|---|---|
| Injection after-cooler outlet | **58 °C** | keeps delivery ≤ 60 °C with margin; minimises cooler power |
| Injection compressor discharge pressure | solved per scenario | compressor discharge is set so that the *worst* well branch receives exactly the required sink pressure → minimum compression energy |
| Injection compressor flow split | equal across running units | catalogue `efficiency_proxy` is flow-independent, so equal split = minimum energy for identical units; the two efficient `C60` units are always the ones loaded |
| Withdrawal regulator outlet (WDR-MID/HIGH) | solved per scenario | regulator outlet is set so that the delivery pressure at `GRID-TIE` equals exactly 6.0 MPa |
| Withdrawal booster discharge (WDR-LOW) | solved per scenario | compressor discharge is set so the regulator trims only, minimising energy |
| Dehydration outlet water | 35 mg/Sm³ (model value) | catalogue `normal_outlet_water_mg_sm3` |

### 4.2 Scenario operating plans

| Scenario | h/yr | Service | Source → sink | Flow | Active path (valve position) |
|---|---:|---|---|---:|---|
| `INJ-LOW` | 900 | injection | GRID-TIE 6.5 MPa / 25 °C → six well groups ≥ 8.5 MPa | 120 kg/s | `PL-32, MI, PL-33, HCS, {C1,C2}, HCD, PL-27, COOL, PL-28, HM`, six well lines. Bypass `PL-26` **closed**, treatment bank **isolated** |
| `INJ-MID` | 1300 | injection | same source → ≥ 11.0 MPa | 100 kg/s | as `INJ-LOW` |
| `INJ-HIGH` | 600 | injection | same source → ≥ 13.5 MPa | 75 kg/s | as `INJ-LOW` |
| `WDR-HIGH` | 500 | withdrawal | six well groups 12.0 MPa / 20 °C / 220 mg/Sm³ / 0.01 kg·kg⁻¹ → GRID-TIE ≥ 6.0 MPa | 120 kg/s | six well lines, `HM, PL-07, HSI, {SEP1..3}, HSD, {DH1..3}, HCS, PL-26` (**bypass open**, compressors isolated), `HCD, PL-29, REG, PL-30, MW, PL-31`. Cooler branch `PL-27/PL-28` isolated |
| `WDR-MID` | 900 | withdrawal | well groups 8.0 MPa → GRID-TIE ≥ 6.0 MPa | 100 kg/s | as `WDR-HIGH` |
| `WDR-LOW` | 800 | withdrawal | well groups 4.5 MPa → GRID-TIE ≥ 6.0 MPa | 70 kg/s | as `WDR-HIGH` but bypass **closed** and `{C1,C2}` **running** (wet-gas path through the compressor bank) |

Total operating hours = 900 + 1300 + 600 + 500 + 900 + 800 = **5000 h/yr** ✔.

### 4.3 Computed scenario results

| Scenario | Flow | Compressor(s) running | Pressure ratio | Discharge P / T | Cooler duty | Regulator outlet | Delivery P | Delivery T | Water | Free liquid | Total power |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `INJ-LOW` | 120.0 kg/s | C1, C2 @ 60.0 each | 1.3274 | 8.581 MPa / 50.2 °C | 0 MW (discharge already below 58 °C) | — | 8.504 MPa (worst well) | 50.2 °C | 40 | 0 | 7.709 MW |
| `INJ-MID` | 100.0 | C1, C2 @ 50.0 | 1.7101 | 11.063 / 74.1 °C | 3.950 MW | — | 11.000 MPa | 58.0 °C | 40 | 0 | 12.674 MW |
| `INJ-HIGH` | 75.0 | C1, C2 @ 37.5 | 2.0928 | 13.549 / 94.3 °C | 6.661 MW | — | 13.500 MPa | 58.0 °C | 40 | 0 | 13.488 MW |
| `WDR-HIGH` | 120.0 | none (bypass) | — | — | — | 6.0407 MPa | 6.000 MPa | 13.25 °C | 35 | 5 × 10⁻⁶ | 2.160 MW (dehy.) |
| `WDR-MID` | 100.0 | none (bypass) | — | — | — | 6.0347 MPa | 6.000 MPa | 18.03 °C | 35 | 5 × 10⁻⁶ | 1.800 MW (dehy.) |
| `WDR-LOW` | 70.0 | C1, C2 @ 35.0 | 1.4081 | 6.037 MPa / 50.1 °C | — | 6.0281 MPa | 6.000 MPa | 50.11 °C | 35 | 5 × 10⁻⁶ | 6.640 MW |

All delivery limits are met in every scenario (`fl ≤ 1 × 10⁻⁴`; water ≤ 50 mg/Sm³;
−10 °C ≤ T ≤ 60 °C; sink pressure ≥ required). The full pressure/temperature profile
of every scenario (per pipeline, header, and equipment) is in `data/design.json`
(`scenarios[].path`).

### 4.4 Energy

| Scenario | h/yr | Power MW | MWh/yr |
|---|---:|---:|---:|
| INJ-LOW | 900 | 7.709 | 6 938 |
| INJ-MID | 1300 | 12.674 | 16 476 |
| INJ-HIGH | 600 | 13.488 | 8 093 |
| WDR-HIGH | 500 | 2.160 | 1 080 |
| WDR-MID | 900 | 1.800 | 1 620 |
| WDR-LOW | 800 | 6.640 | 5 312 |
| **Total** | **5000** | | **39 519** |

---

## 5. Equipment selection, count and stated capacities

| Tag | Model | Category | Count | Duty / rating used | Selection driver |
|---|---|---|---|---:|---|
| `C1`,`C2` | `C60` (2 off) | compressor | 2 | 60 kg/s, PR ≤ 2.4, 32 MW | best efficiency-per-cost of the feasible banks (η = 0.80) and the largest model that still allows a cheap third N-1 unit; 2 × 60 = 120 kg/s covers the INJ-LOW flow with two running units |
| `C3` | `C40` | compressor | 1 | 40 kg/s, PR ≤ 2.4, 20 MW | cheapest unit that closes the N-1 case (after loss of one C60, C60+C40 = 100 kg/s ≥ 84 kg/s). Normally idle |
| `SEP1…3` | `SEP70` (3 off) | separator | 3 | 70 kg/s, 16 MPa, feed liquid ≤ 0.05, liquid ≤ 2.0 kg/s | only separator rated 16 MPa (source up to 12 MPa); three units required for N-1 (2 × 70 = 140 ≥ 84 kg/s) |
| `DH1…3` | `DEHY70` (3 off) | dehydration | 3 | 70 kg/s, 16 MPa, water out 35 mg/Sm³ | only dehydrator rated 16 MPa; three units required for N-1 (2 × 70 = 140 ≥ 84 kg/s) |
| `HM` | `HDR180` | header | 1 | 180 kg/s, 14 branches, 16 MPa | eight connections needed (6 wells + 2 trunk lines) |
| `HSI`,`HSD`,`HCS`,`HCD` | `HDR120` (4 off) | header | 4 | 120 kg/s, 10 branches, 16 MPa | bank manifolds (3–8 connections each); 12–16 MPa service |
| `COOL` | `COOL120` | cooler | 1 | 120 kg/s, 32 MW duty, min outlet 35 °C | sized for the 120 kg/s injection case; 16 MPa rating |
| `REG` | `REG120` | regulator | 1 | 120 kg/s, 16 MPa | withdrawal delivery pressure control; sized for 120 kg/s at 12 MPa |
| `MI`,`MW` | `MTR120` (2 off) | meter | 2 | 60…120 kg/s, 16 MPa | mandatory `GRID-TIE` metering; one per flow direction (meter ports are one-way); capacity 120 kg/s = 1.0 × maximum scenario flow |
| `D1…3` | `DRN-S` (3 off) | closed drain | 3 | 0.8 kg/s, 1 MPa | one closed drain per separator (each `liquid_out` must connect to a drain); max removed liquid 0.400 kg/s |

No filter is installed: the separator alone reduces the free-liquid loading to
5 × 10⁻⁶ kg/kg (limit 1 × 10⁻⁴) and the dehydrator feed limit (1 × 10⁻⁴ kg/kg) is met
from the separator outlet, so a filter would add pressure drop and capex with no duty.

**Alternatives evaluated (full LCC recomputation, same optimum pipe selection):**

| Compressor bank | Equipment capex | Energy PV | LCC | Verdict |
|---|---:|---:|---:|---|
| **2 × C60 + 1 × C40** | 28.95 | 46.56 | **87.5201** | selected |
| 3 × C60 | 30.85 | 46.56 | 89.8131 | +2.29 |
| 1 × C80 + 1 × C60 + 1 × C40 | 31.25 | 45.38 | 89.1294 | +1.61 |
| 2 × C80 + 1 × C40 | 33.55 | 45.01 | 91.5558 | +4.04 |
| 3 × C80 | 37.75 | 45.01 | 96.6398 | +9.12 |

Header up-rating also increases LCC (HCS → `HDR180` 87.6088; HCS+HCD 87.7179; all four
manifolds 88.0026), so all bank manifolds remain `HDR120`.

---

## 6. Layout, safety and maintenance access

### 6.1 Equipment schedule

| Tag | Model | (x, y) m | Orient. | Footprint bbox (m) |
|---|---|---:|---:|---|
| HM | HDR180 | (70, 250) | 0° | [67.0, 248.5]–[73.0, 251.5] |
| SEP1/2/3 | SEP70 | (200, 200/216/232) | 0° | [196, y−2]–[204, y+2] |
| HSI | HDR120 | (150, 216) | 0° | [147.0, 214.5]–[153.0, 217.5] |
| HSD | HDR120 | (270, 216) | 0° | [267.0, 214.5]–[273.0, 217.5] |
| DH1/2/3 | DEHY70 | (330, 200/216/232) | 0° | [325, y−2.5]–[335, y+2.5] |
| HCS | HDR120 | (505, 210) | 0° | [502.0, 208.5]–[508.0, 211.5] |
| HCD | HDR120 | (505, 300) | 0° | [502.0, 298.5]–[508.0, 301.5] |
| C1/C2/C3 | C60/C60/C40 | (480, 250), (510, 250), (538, 250) | 90° | [475–484], [506–514], [534.5–541.5] × [242.5–257.5], [244–256] |
| COOL | COOL120 | (505, 330) | 90° | [502.0, 324.0]–[508.0, 336.0] |
| REG | REG120 | (600, 300) | 0° | [597.5, 298.5]–[602.5, 301.5] |
| MI | MTR120 | (655, 215) | 90° | [654.0, 213.0]–[656.0, 217.0] |
| MW | MTR120 | (655, 260) | 0° | [653.0, 259.0]–[657.0, 261.0] |
| D1/D2/D3 | DRN-S | (400, 130/140/150) | 0° | [399, y−1]–[401, y+1] |

Plant rows run west→east in flow order (well manifold → treatment → compression →
metering → `GRID-TIE`), giving short branch runs and a single east-west road spine.

### 6.2 Safety separation


Safety-category separations are verified boundary-to-boundary against
`safety_requirements.json` for all 210 equipment pairs; **0 violations**. Measured
minimum distances (requirement → actual): compressor↔hydrocarbon-treatment 10 → 31.0 m
(HCS/C2); compressor↔drain 12 → 118.3 m; compressor↔compressor 6 → 20.5 m;
compressor↔pressure-control 8 → 70.3 m; compressor↔metering 6 → 111.5 m;
hydrocarbon-treatment↔hydrocarbon-treatment 5 → 11.0 m (DH1/DH2); hydrocarbon-treatment
↔drain 8 → 79.1 m; hydrocarbon-treatment↔pressure-control 6 → 89.5 m;
hydrocarbon-treatment↔metering 5 → 146.0 m; drain↔drain 4 → 8.0 m; metering↔pressure-
control 4 → 62.9 m; metering↔metering 4 → 42.0 m.

### 6.3 Maintenance envelopes and access

* Each instance has a routine clearance envelope and, for the three compressors, an
  added heavy-maintenance removal envelope on the (local) east side, which rotates with
  the 90° orientation to face **north** — i.e. towards the compression-station access
  road. All envelopes are inside the site, clear of exclusion zones and clear of every
  other equipment footprint.
* Required maintenance area = 1 589.88 m² (net of footprints).
* **Road access** (≤ 7 m) is provided for every model whose catalogue flags
  `road_access_required` (three compressors, three separators). **Crane access**
  (≤ 4.5 m, compressors) is provided by the compression-station spur `R3`:
  C1 2.5 m, C2 2.5 m, C3 3.6 m (road paved edge 274 m vs envelope extremities
  269.5 / 269.5 / 265.6 m). Separator envelopes are 2.0 m from the paved edge of spur
  `R4`.
* Neither the compressors nor the separators require crane access beyond those values;
  the remaining models require no road access.

### 6.4 Roads

| Road | Centreline | Width | Length | Purpose |
|---|---|---:|---:|---|
| `R1` | (2.5, 225) → (690, 225) | 5 m | 687.5 m | main access road from `ROAD-ENTRANCE`; runs between the two equipment rows |
| `R2` | (470, 225) → (470, 270) | 8 m | 45 m | north spur to the compression station |
| `R3` | (456, 270) → (564, 270) | 8 m | 108 m | compressor road/crane access |
| `R4` | (188, 225) → (188, 195) | 8 m | 30 m | separator maintenance access |

Total centreline length **870.5 m**. The paved geometry of all roads lies inside the
site, is clear of equipment footprints and of the `FUTURE-EXPANSION` / `GRID-FACILITY`
road-exclusion zones, and the four paved areas form one connected network containing
`ROAD-ENTRANCE`.

---

## 7. Reliability (N-1) verification

Requirements: compressor N-1 for every scenario with `required_sink_pressure >
source_pressure` (INJ-LOW/MID/HIGH, WDR-LOW), separator and dehydration N-1 for every
withdrawal scenario; retained flow ≥ 0.7 × scenario flow with all delivery limits
still met.

| Outage case | Retained flow | Required | Delivered P | Delivery quality |
|---|---:|---:|---:|---|
| Compressor out, INJ-LOW (C2 + C3 running) | 84.0 kg/s (70 %) | ≥ 84 | 8.502 MPa ≥ 8.5 | T 50.8 °C, water 40, fl 0 |
| Compressor out, INJ-MID | 70.0 (70 %) | ≥ 70 | 11.001 MPa | T 58.0 °C |
| Compressor out, INJ-HIGH | 52.5 (70 %) | ≥ 52.5 | 13.500 MPa | T 58.0 °C |
| Compressor out, WDR-LOW | 49.0 (70 %) | ≥ 49 | 6.000 MPa | T 49.7 °C, water 35, fl 5e-6 |
| Separator out, WDR-HIGH (2 of 3) | 84.0 (70 %) | ≥ 84 | 6.000 MPa | water 35, fl 4.6e-6 |
| Dehydration out, WDR-HIGH (2 of 3) | 84.0 (70 %) | ≥ 84 | 6.000 MPa | water 35, fl 5e-6 |
| Separator + dehydration out, WDR-LOW | 49.0 (70 %) | ≥ 49 | 6.000 MPa | water 35, fl 5e-6 |

Capacity argument: 3 × SEP70 = 210 kg/s (loss of one → 140 ≥ 84); 3 × DEHY70 = 210
(→ 140 ≥ 84); 2 × C60 + 1 × C40 = 160 kg/s (loss of a C60 → 100 ≥ 84; loss of the C40
→ 120 ≥ 84). Every retained unit also stays inside its own envelope (min. stable flow
15 kg/s for C60, 10 for C40; feed liquid, liquid rate and pressure ratings rechecked).

Reliability **without** redundancy was tested and rejected: two compressors of the
largest catalogue model (2 × C80 = 160 kg/s) still retain only 80 kg/s < 84 kg/s after
one failure, so at least three compressor units are structurally required. Likewise two
`SEP70`/`DEHY70` units retain only 70 kg/s < 84 kg/s, which is why the treatment banks
also have three units.

---

## 8. Piping and network definition

### 8.1 Sizing method

Diameters and pipe classes are chosen by a local-search optimiser over the **exact**
LCC (`calc/optimize.py`): for each pipeline every catalogue diameter is substituted,
the six operating scenarios (and the N-1 cases for the velocity envelope) are
re-solved, and the LCC is compared. The optimiser is not allowed to violate the
25 m/s gas / 3 m/s liquid velocity limits, and each pipe class is set to the cheapest
class rated for the maximum pressure seen anywhere in the scenario set
(`CS-WET-100` ≤ 10 MPa, `CS-WET-160` ≤ 16 MPa; both are wet- *and* dry-gas compatible).
The converged selection is written directly into `calc/design.py` (and mirrored in
`data/pipe_sizes.json`), so the design is reproducible without re-running the optimiser.

Typical converged values (velocity in the governing scenario):

| Line | DN | Class | Max P | Max v |
|---|---|---:|---:|---:|
| Well branch PL-01 (longest) | DN350 | CS-WET-160 | 13.5 MPa | 3.9 m/s |
| Well branch PL-04 (shortest) | DN250 | CS-WET-160 | 13.5 | 7.5 |
| Injection import PL-32 / PL-33 | DN700 | CS-WET-100 | 6.5 | 6.9 |
| Injection cooler line PL-28 | DN600 | CS-WET-160 | 13.5 | 7.8 |
| Station bypass PL-26 | DN350 | CS-WET-160 | 11.8 | 19.1 |
| Compressor suction PL-20/21 | DN600 | CS-WET-100 | 6.5 | 4.7 |
| Compressor suction/discharge PL-22/25 (trim unit) | DN200 | CS-WET-100/160 | 6.5 / 13.5 | 17.0 |
| Delivery PL-31 | DN500 | CS-WET-100 | 6.0 | 14.0 |
| Drain lines PL-34…39 | DN150 | CS-WET-100 | 1.0 | 4.5e-4 |

### 8.2 Pipeline schedule

| ID | From | To | DN | Class | Level | Length (m) | Service |
|---|---|---|---|---:|---|---:|---|
| PL-01 | HM.branch_11 | WG-01 | DN350 | CS-WET-160 | ground | 259.5 | gas |
| PL-02 | HM.branch_07 | WG-02 | DN300 | CS-WET-160 | ground | 189.5 | gas |
| PL-03 | HM.branch_03 | WG-03 | DN300 | CS-WET-160 | ground | 119.5 | gas |
| PL-04 | HM.branch_04 | WG-04 | DN250 | CS-WET-160 | ground | 67.0 | gas |
| PL-05 | HM.branch_08 | WG-05 | DN300 | CS-WET-160 | ground | 138.0 | gas |
| PL-06 | HM.branch_12 | WG-06 | DN300 | CS-WET-160 | ground | 209.0 | gas |
| PL-07 | HM.branch_05 | HSI.branch_05 | DN600 | CS-WET-160 | ground | 135.8 | gas |
| PL-08 | HSI.branch_04 | SEP1.gas_in | DN250 | CS-WET-160 | ground | 64.2 | gas |
| PL-09 | HSI.branch_08 | SEP2.gas_in | DN250 | CS-WET-160 | ground | 49.8 | gas |
| PL-10 | HSI.branch_07 | SEP3.gas_in | DN250 | CS-WET-160 | ground | 65.0 | gas |
| PL-11 | SEP1.gas_out | HSD.branch_04 | DN300 | CS-WET-160 | ground | 78.2 | gas |
| PL-12 | SEP2.gas_out | HSD.branch_08 | DN300 | CS-WET-160 | ground | 63.8 | gas |
| PL-13 | SEP3.gas_out | HSD.branch_03 | DN300 | CS-WET-160 | ground | 94.0 | gas |
| PL-14 | HSD.branch_02 | DH1.gas_in | DN250 | CS-WET-160 | ground | 69.0 | gas |
| PL-15 | HSD.branch_06 | DH2.gas_in | DN250 | CS-WET-160 | ground | 52.0 | gas |
| PL-16 | HSD.branch_10 | DH3.gas_in | DN250 | CS-WET-160 | ground | 69.0 | gas |
| PL-17 | DH1.gas_out | HCS.branch_04 | DN250 | CS-WET-160 | ground | 176.2 | gas |
| PL-18 | DH2.gas_out | HCS.branch_08 | DN250 | CS-WET-160 | ground | 172.2 | gas |
| PL-19 | DH3.gas_out | HCS.branch_07 | DN300 | CS-WET-160 | ground | 201.0 | gas |
| PL-20 | HCS.branch_01 | C1.suction | DN600 | CS-WET-100 | ground | 54.0 | gas |
| PL-21 | HCS.branch_05 | C2.suction | DN600 | CS-WET-100 | ground | 36.0 | gas |
| PL-22 | HCS.branch_09 | C3.suction | DN200 | CS-WET-100 | ground | 63.5 | gas |
| PL-23 | C1.discharge | HCD.branch_04 | DN500 | CS-WET-160 | ground | 63.8 | gas |
| PL-24 | C2.discharge | HCD.branch_07 | DN450 | CS-WET-160 | ground | 47.5 | gas |
| PL-25 | C3.discharge | HCD.branch_08 | DN200 | CS-WET-160 | ground | 94.8 | gas |
| PL-26 | HCS.branch_10 | HCD.branch_03 | DN350 | CS-WET-160 | ground | 171.0 | gas |
| PL-27 | HCD.branch_01 | COOL.gas_in | DN600 | CS-WET-160 | ground | 24.5 | gas |
| PL-28 | COOL.gas_out | HM.branch_01 | DN600 | CS-WET-160 | ground | 521.8 | gas |
| PL-29 | HCD.branch_02 | REG.gas_in | DN500 | CS-WET-160 | ground | 90.5 | gas |
| PL-30 | REG.gas_out | MW.gas_in | DN500 | CS-WET-100 | ground | 90.5 | gas |
| PL-31 | MW.gas_out | GRID-TIE | DN500 | CS-WET-100 | ground | 78.0 | gas |
| PL-32 | GRID-TIE | MI.gas_in | DN700 | CS-WET-100 | ground | 67.0 | gas |
| PL-33 | MI.gas_out | HCS.branch_06 | DN700 | CS-WET-100 | ground | 170.0 | gas |
| PL-34 | SEP1.liquid_out | D1.drain_in | DN150 | CS-WET-100 | ground | 267.0 | liquid drain |
| PL-35 | SEP2.liquid_out | D2.drain_in | DN150 | CS-WET-100 | ground | 273.0 | liquid drain |
| PL-36 | SEP3.liquid_out | D3.drain_in | DN150 | CS-WET-100 | ground | 279.0 | liquid drain |
| PL-37 | D1.drain_out | LIQUID-DRAIN-OUTFALL | DN150 | CS-WET-100 | ground | 289.0 | liquid drain |
| PL-38 | D2.drain_out | LIQUID-DRAIN-OUTFALL | DN150 | CS-WET-100 | ground | 299.0 | liquid drain |
| PL-39 | D3.drain_out | LIQUID-DRAIN-OUTFALL | DN150 | CS-WET-100 | ground | 349.0 | liquid drain |

All 39 pipelines are installed at the **ground** level, so no routing-level civil cost
is incurred and no bounded corridor is required. Every route is an ordered,
axis-aligned polyline whose first and last vertices coincide (within 1e-6 m) with the
source and destination port coordinates; the full vertex lists are in
`data/design.json`. Verified route properties (0 findings): every segment longer than
the geometry tolerance; every segment inside the site boundary; no segment entering a
`pipeline_exclusion` interior (`FUTURE-EXPANSION`, `DRAINAGE-CHANNEL`); no segment
crossing any equipment footprint; no positive-length same-level overlap between any two
segments (nor self-overlap). Plan crossings between collinear-free segments are used to
distribute the six well branches, the three drain branches and the parallel bank
connections without any shared corridor.

**Liquid handling:** each of the three separators is individually piped to its own
closed drain (`DRN-S`); each drain discharges directly to `LIQUID-DRAIN-OUTFALL`
(3 of 8 permitted connections). Removed liquid is 0.400 kg/s per separator in
`WDR-HIGH` (drain rating 0.8 kg/s), and 1.1994 kg/s total at the outfall (limit
10 kg/s). The system is in the idealised 1 MPa closed-drain pressure domain.

---

## 9. Metrology and utility interfaces

* `MI` carries all gas exchanged inwards; `MW` carries all gas exchanged outwards.
  In each scenario the exchanged gas passes through exactly one `MTR120` whose rated
  capacity (120 kg/s) equals the maximum scenario flow — active meter capacity fraction
  = 1.00 ≥ 1.00 required. Meter pressure drop (0.020 MPa) is included in every pressure
  calculation.
* Electric power, instrument air and firewater are taken as abstract services at
  `POWER-TIE`, `INSTRUMENT-AIR-TIE` and `FIREWATER-TIE`; their distribution is out of
  scope and no piping is allocated to them.
* No liquid pumping is required: the liquid side streams are inside the idealised
  integral let-down boundary.

---

## 10. Quantities

| Item | Quantity |
|---|---:|
| Gas pipelines | 33 lines, 3 845.5 m |
| Liquid-drain pipelines | 6 lines, 1 756.0 m |
| **Total pipeline length** | **5 601.5 m** (all DN150–DN700, ground level) |
| DN150 / DN200 / DN250 / DN300 / DN350 / DN450 / DN500 / DN600 / DN700 | 1 756.0 / 158.25 / 784.5 / 1 093.0 / 430.5 / 47.5 / 322.75 / 772.0 / 237.0 m |
| Pipe classes | CS-WET-100 2 315.0 m (all ≤ 10 MPa service); CS-WET-160 3 286.5 m |
| Equipment instances | 21 (see §5) |
| Major equipment | 3 compressors, 3 separators, 3 dehydrators, 1 cooler, 1 regulator, 2 meters, 3 drains, 5 headers |
| Roads | 870.5 m centreline, 4 roads |
| Equipment footprint area | 775.0 m² |
| Required maintenance-envelope area (net) | 1 589.88 m² |
| Site area | 315 000 m² (700 × 450 m) |

---

## 11. Lifecycle cost

Basis: `PVF = (1 − 1.08⁻²⁰)/0.08 = 9.818147`; energy tariff 0.00012 MBCU/MWh;
project life 20 years; discount rate 8 %; no other score is combined with LCC.

| Component | Value (MBCU) | Share |
|---|---:|---:|
| Equipment CAPEX | 28.9500 | 33.1 % |
| Piping CAPEX | 1.5549 | 1.8 % |
| Civil / access CAPEX | 0.1362 | 0.2 % |
| Energy, present value (39 518.8 MWh/yr × 0.00012 × 9.818147) | 46.5602 | 53.2 % |
| Maintenance, present value (1.0510 MBCU/yr × 9.818147) | 10.3189 | 11.8 % |
| **Lifecycle cost** | **87.5201** | 100 % |

Civil/access CAPEX details — roads 870.5 m × 0.00015 = 0.1306; foundations
775.0 m² × 4 × 10⁻⁶ = 0.0031; maintenance area 1 589.88 m² × 1 × 10⁻⁶ = 0.0016;
pipeline civil 5 601.5 m at the ground rate (0 MBCU/m) = 0.0000.

Equipment CAPEX details — compressors C1/C2 13.000 + C3 4.600; separators 2.340;
dehydrators 5.550; headers (HDR180 + 4 × HDR120) 1.360; cooler 0.920; regulator 0.340;
meters 0.600; closed drains 0.240.

Annual maintenance = 0.440 (compressors) + 0.150 (separators) + 0.285 (dehydrators)
+ 0.064 (headers) + 0.050 (cooler) + 0.018 (regulator) + 0.032 (meters) + 0.012
(drains) = **1.0510 MBCU/yr**.

### 11.1 Optimisation history

| Stage | LCC (MBCU) |
|---|---:|
| Initial design (all bank lines DN250, trunk lines DN500, cooler 40 °C) | 89.35 |
| Converged diameter/class optimiser | 87.93 |
| Cooler setpoint 40 → 58 °C (limit 60 °C) | 87.51 |
| Re-optimisation after the withdrawal trunk was added to the traced set (raises the class of `PL-08…10`, `PL-14…16` to CS-WET-160) | **87.5201** |

Because energy is 53 % of the LCC, the optimiser drives the main lines to
DN600/DN700 even though this increases pipe CAPEX: a 0.01 MPa reduction anywhere on
the pressurised path is worth ≈ 0.1 MBCU of present-value energy, whereas a DN600→
DN700 upgrade of 1 000 m of trunk line costs only 0.14 MBCU.

---

## 12. Verification summary

`python calc/validate.py` runs 14 independent check groups and reports **0 findings**:

| Check group | Findings |
|---|---:|
| Equipment footprints inside site / outside `equipment_exclusion` / mutually non-overlapping | 0 |
| Safety separation (all category pairs) | 0 |
| Maintenance envelopes (in-site, exclusions, other footprints) | 0 |
| Road access ≤ 7 m / crane access ≤ 4.5 m | 0 |
| Roads (width ≥ 4 m, in-site, road-exclusion, clear of footprints, connected, contains `ROAD-ENTRANCE`) | 0 |
| Pipeline routes (end-points, segment length, in-site, `pipeline_exclusion`, footprint crossing, same-level overlap, self-overlap, corridor rules) | 0 |
| Port connection cardinality (equipment ports = 1; `GRID-TIE` = 2; outfall = 3; well groups = 1) | 0 |
| Port type compatibility / flow direction | 0 |
| Gas velocity ≤ 25 m/s, liquid-drain velocity ≤ 3 m/s (including all N-1 cases) | 0 |
| Pipe class pressure rating and liquid-drain compatibility | 0 |
| Equipment envelopes (compressor suction/discharge P & T, ratios, power, min. stable flow, capacity; separator/dehydrator/cooler/regulator/meter/drain limits) | 0 |
| Delivery limits (pressure ≥ required, free liquid, water, temperature) in all scenarios and N-1 cases | 0 |
| Metering, boundary flow limits, outfall limits | 0 |
| Design completeness (every pipeline and every equipment instance appears in at least one scenario path) | 0 |

Scenario pressure-loss convergence: every pipeline pressure-loss fixed point converged
(≤ 8 updates, criterion 1e-5 MPa) in every scenario, including all N-1 cases.

---

## 13. Known limitations and open items

1. **Valve line-up is declared, not modelled.** The physical network is the union of
   the scenario paths. Isolation valves (compressor-station bypass, treatment-bank
   isolation, cooler-branch isolation) are assumed available and correctly sized; they
   are not catalogue equipment and carry no cost. This is the only interpretation under
   which the required bidirectional station service and the mandatory bypass can be
   represented with a physical connection topology that never violates the
   one-connection-per-port rule.
2. **Idealised liquid let-down.** No let-down valve, flash drum, pump or liquid
   property model exists in the basis; the closed-drain domain is assumed at ≤ 1 MPa
   and the drain network is checked only for capacity, pressure domain and outfall
   limits. Drain velocity is checked with an assumed 1000 kg/m³ liquid density.
3. **Delayed/no-flow cases.** The basis requires the full stated flow in normal
   operation; part-load turndown below the compressor minimum stable flow (15 kg/s for
   C60, 10 kg/s for C40) is not defined and is not claimed.
4. **Equal well-group allocation.** Every scenario splits flow equally over the six well
   groups (20.0 / 16.67 / 12.5 kg/s and below). A biased allocation would in principle
   reduce the injection discharge pressure slightly (the longest branch is the binding
   one), but the realisable saving is < 0.05 MBCU and equal allocation is the
   defensible operating assumption.
5. **Single pressure/temperature point per location.** The basis models one pressure
   and temperature per stream (no transient, no stratified flow, no pipeline heat
   transfer); no surge, no blowdown, no relief sizing and no depressurisation study is
   performed — outside the stated scope.
6. **Firewater, power and instrument air** are abstract services; no distribution
   network, motor control or firewater hydraulic model is provided (excluded scope).
7. **No regulatory or code compliance claim** is made: separation distances, road
   buffers and clearances are synthetic benchmark values, not code criteria.
8. **Cost basis is the synthetic catalogue.** No vendor pricing, escalation, currency,
   contingency, owner cost, commissioning, decommissioning or tax effects are included;
   LCC is exactly the sum of the five components in §11.

---

## 14. Reproduction

```
cd project/calc
python validate.py     # all checks, LCC and scenario results  -> ../results/*.json
python export.py       # full machine-readable design          -> ../data/design.json
python optimize.py 2   # re-run the pipe-size local search (optional)
```

Artifacts:

| File | Content |
|---|---|
| `data/design.json` | Complete design: equipment + absolute port coordinates, roads, all pipeline routes, scenario paths with pressures/temperatures/flows/setpoints, N-1 cases, LCC, quantities, validation results |
| `data/pipe_sizes.json` | Frozen optimised diameter/class selection per pipeline |
| `results/validation.json` | Findings of all 14 check groups |
| `results/scenario_results.json` | Full per-scenario solution traces (normal + N-1) |
| `results/lcc.json` | LCC breakdown |
| `results/quantities.json` | Quantity take-off |
| `calc/*.py` | Calculation library, geometry/route/safety checkers, scenario solver, LCC, optimiser, validator, exporter |
