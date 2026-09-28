# UGS-SYNTH-D01 — surface facilities design report

**Case** UGS-SYNTH-D01 (UGS-SYNTH benchmark family), case version 1.1.0-development. All case data is synthetic benchmark data.

This report is the narrative deliverable; the machine-readable design definition is in `deliverables/design.json`, the rule-by-rule verification output in `deliverables/verification.md` and `deliverables/checks.csv`, the plan-view drawing in `deliverables/layout.svg`. Everything in this report is reproduced from those files by `tools/make_report.py`.

## 1 Purpose, scope and basis

The project delivers an underground-gas-storage surface facility that connects the GRID-TIE boundary to six well groups and provides the six published operating scenarios (three injection, three withdrawal) at the published gas-quality, pressure and metering requirements. The design covers process architecture, equipment selection and count, train architecture, topology, operating philosophy, pipe sizing and classing, layout, routing, maintenance access and roads, as listed in the project scope. Reservoir behaviour, well completion, electrical/control systems, civil structures, procurement and code compliance are excluded by the case.

**Objective.** Among feasible designs, minimise the benchmark lifecycle cost (LCC). The LCC of the proposed design is **89.285 MBCU** (section 9).

### 1.1 Published requirements used

* gas delivery limits: water content ≤ 50 mg/Sm3, free-liquid mass fraction ≤ 0.0001 kg/kg, temperature within -10…60 degC;
* GRID-TIE metering is mandatory, all exchanged gas must pass through active meter capacity ≥ the scenario flow;
* compression N-1: for every scenario whose sink pressure exceeds its source pressure, ≥ 70 % of the scenario flow must remain deliverable with any one compressor unavailable;
* withdrawal treatment N-1: for every withdrawal scenario, ≥ 70 % of the scenario flow must remain deliverable with any one separator or dehydration unit unavailable;
* operating hours 5000 h/a in total; well-group interface limits 0…25 kg/s each; GRID-TIE limit 160 kg/s; liquid outfall limit 10.0 kg/s.

## 2 Operating scenarios

| scenario | service | flow (kg/s) | source | p source (MPa) | T source (degC) | water (mg/Sm3) | free liquid (kg/kg) | p sink required (MPa) | hours (h/a) |
|---|---|---|---|---|---|---|---|---|---|
| INJ-LOW | injection | 120 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 8.5 | 900 |
| INJ-MID | injection | 100 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 11.0 | 1300 |
| INJ-HIGH | injection | 75 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 13.5 | 600 |
| WDR-HIGH | withdrawal | 120 | well_groups | 12.0 | 20 | 220 | 0.01 | 6.0 | 500 |
| WDR-MID | withdrawal | 100 | well_groups | 8.0 | 20 | 220 | 0.01 | 6.0 | 900 |
| WDR-LOW | withdrawal | 70 | well_groups | 4.5 | 20 | 220 | 0.01 | 6.0 | 800 |

## 3 System architecture and process connections

The facility is a single station with two process chains that share the well-side manifold and the compressor set:

**Injection chain (GRID-TIE → wells).** GRID-TIE → injection custody meter `MTR-INJ-01` → compressor suction header `HDR-INJ-SUC-01` → three parallel compressors (`CMP-INJ-01/02/03`, the station compressor set) → discharge header `HDR-INJ-DIS-01` → aftercooler `COOL-INJ-01` → injection trunk `P-113` → well manifold `WH-01` → six well-group branches `P-131…P-136`.

**Withdrawal chain (wells → GRID-TIE).** six well groups → well manifold `WH-01` → three withdrawal trunks `P-114/115/116` (one per train) → inlet separators `SEP-WDR-01/02/03` → dehydration units `DEHY-WDR-01/02/03` → treated-gas header `HDR-TRT-OUT-01` → delivery header `HDR-DLV-01` → pressure regulator `REG-WDR-01` → withdrawal custody meter `MTR-WDR-01` → GRID-TIE. In WDR-HIGH and WDR-MID the treated gas reaches the delivery header through the bypass `P-123`. In WDR-LOW it is boosted by the same station compressor set: the treated gas is routed to the compressor suction header through the boost feed line `P-143` (`HDR-TRT-OUT-01` → `HDR-INJ-SUC-01`), compressed, and returned to the delivery header through the boost discharge line `P-144` (`HDR-INJ-DIS-01` → `HDR-DLV-01`).

**Liquid system.** Each separator's `liquid_out` discharges through its own closed drain (`DRN-WDR-01/02/03`) and drain line to the public outfall `LIQUID-DRAIN-OUTFALL` (three separate discharge lines, `P-140/141/142`). The separators' liquid side streams are conveyed at the idealised closed-drain pressure domain (≤ 1 MPa), which the published model represents as an integral letdown at the separator `liquid_out`.

**Boundary interfaces used** (from `site.json`): GRID-TIE (2 connections: one injection meter inlet line, one withdrawal meter outlet line), the six well groups (one connection each, through `WH-01`), LIQUID-DRAIN-OUTFALL (3 of 8 available connections) and ROAD-ENTRANCE (road network). POWER-TIE, FIREWATER-TIE and INSTRUMENT-AIR-TIE are abstract utility boundaries; no distribution network is in scope and no process piping connects to them.

### 3.1 Architecture decisions and the rules behind them

* **Two custody meters.** Equipment ports are directional: a meter conveys gas only from `gas_in` to `gas_out`, and injection and withdrawal are opposite directions through the same boundary. Two catalogued meters are therefore installed in anti-parallel, one per flow direction, so that all exchanged gas passes through active meter capacity in every scenario (each MTR120 is rated exactly the 120 kg/s peak scenario flow, which the published tolerance convention treats as equal to the limit).

* **No treatment on the injection chain.** The injection gas arrives at 40 mg/Sm3 water and zero free liquid, i.e. inside both delivery limits, so separation/dehydration would add pressure loss and cost without changing the delivered quality.

* **One compressor set serves both services.** Compressor suction and discharge are one-way ports (`gas_in` / `gas_out`), so a machine can never be reversed; nothing in the published rules requires separate machinery for injection and for the low-pressure withdrawal boost, and the two services are seasonal and never simultaneous. The station set is therefore shared: in WDR-LOW the treated gas is routed to the compressor suction header (`P-143`) and the compressor discharge to the delivery header (`P-144`), and those lines are isolated while injection or a high-pressure withdrawal scenario runs. A dedicated two-machine boost set was costed as the alternative: 13.0 MBCU of equipment plus 3.1 MBCU of maintenance present value for no functional benefit. The well manifold `WH-01` is likewise a catalogued header shared by both directions, and the operating plan selects the active branches scenario by scenario; the published semantics explicitly allow cyclic physical networks and require only that every declared scenario satisfies the port, mass-balance, pressure, capacity, temperature and delivery rules.

* **Aftercooling is a delivery requirement, not a choice.** At the highest injection ratio the compressor discharge reaches ≈ 95 degC, above the 60 degC delivery limit; the aftercooler holds the injection gas at 50 degC, a 10 degC margin to the limit, at a duty of at most ≈ 13 MW against its 32 MW rating. The boost service runs at a ratio of ≈ 1.5 (discharge ≈ 55 degC) and does not pass through the aftercooler.

* **Delivery pressure control.** The regulator holds the GRID-TIE delivery pressure at the published requirement in every withdrawal scenario: the setpoints are chosen so that the delivered pressure equals 6.000 MPa. (The case's tolerance convention treats a value within 1e-5 MPa of a limit as equal to it, so delivering the requirement itself satisfies a minimum, an exact and an upper-bound reading of `required_sink_pressure_mpa`; the short well-group branches deliver marginally more than the worst branch.) In WDR-LOW the shared compressors raise the pressure to ≈ 6.39 MPa so that the regulator has a definite control drop (≈ 0.3 MPa) across it.

## 4 Equipment selection and stated capacities

| tag | model | category | x (m) | y (m) | orient. (deg) | rating | duty in the design |
|---|---|---|---|---|---|---|---|
| WH-01 | HDR180 | header | 30 | 225 | 0 | 180 kg/s, 14 branches | - |
| MTR-INJ-01 | MTR120 | meter | 640 | 92 | 90 | 120 kg/s, ≤ 16 MPa | - |
| HDR-INJ-SUC-01 | HDR180 | header | 620 | 110 | 0 | 180 kg/s, 14 branches | - |
| CMP-INJ-01 | C60 | compressor | 620 | 132 | 90 | 60 kg/s, ratio ≤ 2.4, ≤ 32 MW, p_disch ≤ 16 MPa | max 55.00 kg/s |
| CMP-INJ-02 | C60 | compressor | 570 | 132 | 90 | 60 kg/s, ratio ≤ 2.4, ≤ 32 MW, p_disch ≤ 16 MPa | max 55.00 kg/s |
| CMP-INJ-03 | C40 | compressor | 520 | 131 | 90 | 40 kg/s, ratio ≤ 2.4, ≤ 20 MW, p_disch ≤ 16 MPa | max 10.00 kg/s |
| HDR-INJ-DIS-01 | HDR180 | header | 620 | 168 | 0 | 180 kg/s, 14 branches | - |
| COOL-INJ-01 | COOL120 | cooler | 600 | 190 | 90 | 120 kg/s, ≤ 32 MW duty | max 120.00 kg/s |
| SEP-WDR-01 | SEP70 | separator | 430 | 210 | 0 | 70 kg/s, removal 0.9995, ≤ 16 MPa | max 40.00 kg/s |
| SEP-WDR-02 | SEP70 | separator | 430 | 240 | 0 | 70 kg/s, removal 0.9995, ≤ 16 MPa | max 40.00 kg/s |
| SEP-WDR-03 | SEP70 | separator | 430 | 270 | 0 | 70 kg/s, removal 0.9995, ≤ 16 MPa | max 40.00 kg/s |
| DEHY-WDR-01 | DEHY70 | dehydration | 475 | 210 | 0 | 70 kg/s, outlet 35 mg/Sm3, ≤ 16 MPa | max 40.00 kg/s |
| DEHY-WDR-02 | DEHY70 | dehydration | 475 | 240 | 0 | 70 kg/s, outlet 35 mg/Sm3, ≤ 16 MPa | max 40.00 kg/s |
| DEHY-WDR-03 | DEHY70 | dehydration | 475 | 270 | 0 | 70 kg/s, outlet 35 mg/Sm3, ≤ 16 MPa | max 40.00 kg/s |
| HDR-TRT-OUT-01 | HDR180 | header | 510 | 240 | 0 | 180 kg/s, 14 branches | - |
| HDR-DLV-01 | HDR180 | header | 585 | 240 | 0 | 180 kg/s, 14 branches | - |
| REG-WDR-01 | REG120 | regulator | 620 | 240 | 0 | 120 kg/s, ≤ 16 MPa | - |
| MTR-WDR-01 | MTR120 | meter | 650 | 240 | 0 | 120 kg/s, ≤ 16 MPa | - |
| DRN-WDR-01 | DRN-S | closed_drain | 560 | 36 | 0 | 0.8 kg/s liquid, ≤ 1 MPa | max 0.40 kg/s |
| DRN-WDR-02 | DRN-S | closed_drain | 580 | 40 | 0 | 0.8 kg/s liquid, ≤ 1 MPa | max 0.40 kg/s |
| DRN-WDR-03 | DRN-S | closed_drain | 600 | 44 | 0 | 0.8 kg/s liquid, ≤ 1 MPa | max 0.40 kg/s |

Installed equipment CAPEX 29.390 MBCU, installed annual maintenance 1.067 MBCU/a. The duty column gives the maximum flow in **normal operation**; the higher flows of the single-unit-outage plans (which load the remaining units harder) are listed in tables 7.1 and 7.3 and stay within every rating.

### 4.1 Sizing logic

**Station compressor set (`CMP-INJ-01/02/03`: 2 × C60 + 1 × C40).** The binding N-1 case is INJ-LOW: with one machine unavailable the station must still deliver 70 % of 120 kg/s = 84 kg/s at the required pressure. Two installed machines cannot meet this (the largest catalogued machine is 80 kg/s), so at least three machines are required; the cheapest set whose total capacity minus the largest single unit is ≥ 84 kg/s is 2 × C60 + 1 × C40 (160 − 60 = 100 kg/s). The same set serves the WDR-LOW boost duty through the boost feed and discharge lines (70 kg/s normal, 49 kg/s after one machine is out), and the largest required pressure ratio (≈ 2.11 at INJ-HIGH) stays inside the C60/C40 limit of 2.4. An independent enumeration of every catalogued C40/C60/C60H/C80 multiset of size 2-4 subject to capacity, ratio and N-1 limits confirms that this is the cheapest compliant set for both services.

**Load sharing.** Duty is loaded on the most efficient machines first and within an efficiency class in proportion to capacity, up to 95 % of rated capacity, so the two C60 carry the load and the C40 is only loaded when it is needed (the minimum-stable flow of every running machine is respected: in INJ-LOW the C40 runs at its 10 kg/s minimum; in INJ-MID, INJ-HIGH and WDR-LOW it is idle).

**Separators (3 × SEP70).** The withdrawal gas enters at up to 12 MPa, which rules out the 10 MPa-rated SEP40/SEP120 models. With one separator out the remaining two must carry the scenario flow (the design does so up to the full 120 kg/s, i.e. 60 kg/s per unit ≤ 70 kg/s); the 0.9995 removal efficiency of a single unit already brings the free liquid from 0.01 to 5 × 10⁻⁶ kg/kg, well inside the 10⁻⁴ limit, so no filter is required.

**Dehydration (3 × DEHY70).** Only the DEHY models change water content (220 → 35 mg/Sm3). DEHY40 is limited to 10 MPa and DEHY120 is rated 10 MPa, both below the 12 MPa withdrawal pressure, so DEHY70 (16 MPa) is the only usable model; three units are needed for the same N-1 reason as the separators.

**Aftercooler (1 × COOL120).** One aftercooler carries the full injection flow (120 kg/s = its rated flow, which the published tolerance convention treats as equal to the limit) at a duty of at most ≈ 13 MW against its 32 MW rating. Cooler redundancy is not a published N-1 requirement and the boost service needs no cooling, so a second unit and an outlet header would be pure cost.

**Headers (5 × HDR180).** Every fan-out/merge of more than two physical ports passes through a catalogued header: compressor suction header, compressor discharge header, well manifold, treated-gas header and delivery header. All are rated 180 kg/s, 16 MPa and 14 branches. This is the one place where margin is retained deliberately rather than sized at rating, and the choice is costed: replacing all five by HDR120 (rated exactly the 120 kg/s station throughput, so every declared flow equals its rating within the published tolerance) would lower the LCC by 0.59 MBCU - 0.55 MBCU of CAPEX and 0.20 MBCU of maintenance present value, less 0.16 MBCU of extra energy from the higher header pressure drop. It is not adopted because the well manifold needs 10 physical branch connections (6 well groups, 3 withdrawal trunks, 1 injection trunk), which is the complete HDR120 branch count with no spare port, and because the two compressor manifold headers and the two delivery-side headers carry the full station flow at the extreme of every scenario. The retained margin is therefore a conscious, costed robustness choice rather than an oversight; it is 0.7 % of the LCC.

**Metering and regulation.** Each custody meter is MTR120 (exactly the maximum scenario flow of 120 kg/s, which the published tolerance convention treats as equal to the limit) and the delivery regulator is REG120.

**Drains.** One DRN-S (0.8 kg/s liquid) per separator; the largest liquid production is 0.60 kg/s (120 kg/s withdrawal through two trains), so each drain stays below 75 % of its rating and the three discharge lines stay far below the 10 kg/s outfall limit.

## 5 Site layout, safety provisions and maintenance access

The site is the 700 m × 450 m boundary of `site.json`. The well manifold `WH-01` sits close to the well groups at (30, 225) with six L-shaped well branches; the two process chains are laid out in bands: the injection chain (meter, suction header, three compressors, discharge header, aftercooler) occupies the south band around y ≈ 90…196, and the withdrawal chain (three trains, treated-gas header, delivery header, regulator, meter) occupies the north band around y ≈ 210…280, ordered west to east so that the withdrawal chain runs in the direction of its flow. The two boost lines (`P-143` from the treated-gas header down to the compressor suction header, `P-144` from the compressor discharge header to the delivery header) close the boost path. The plan view is `deliverables/layout.svg`; coordinates are in `deliverables/design.json`.

All equipment footprints are inside the site and clear of the three no-build zones (FUTURE-EXPANSION, DRAINAGE-CHANNEL, GRID-FACILITY). Every category pair in the published separation matrix is checked on the *boundary-to-boundary* distance of the rotated footprints; the layout meets all of them (the closest pair is the compressor suction header against CMP-INJ-01 at 13.00 m against a 10 m requirement - see the table below). Routine clearance envelopes (2.0…3.1 m) and the heavy-maintenance removal envelopes of the compressors are inside the site, clear of the equipment-exclusion zones and clear of every other footprint.

The tightest boundary-to-boundary separations in the layout are (all pairs at or below the sixth-smallest margin, so ties are included):

| pair | categories | achieved distance (m) | required (m) | margin (m) |
|---|---|---|---|---|
| HDR-INJ-SUC-01 / CMP-INJ-01 | hydrocarbon_treatment / compressor | 13.000 | 10 | +3.000 |
| DRN-WDR-01 / DRN-WDR-02 | drain / drain | 18.111 | 4 | +14.111 |
| DRN-WDR-02 / DRN-WDR-03 | drain / drain | 18.111 | 4 | +14.111 |
| HDR-INJ-DIS-01 / COOL-INJ-01 | hydrocarbon_treatment / hydrocarbon_treatment | 20.156 | 5 | +15.156 |
| MTR-INJ-01 / HDR-INJ-SUC-01 | metering / hydrocarbon_treatment | 21.593 | 5 | +16.593 |
| CMP-INJ-01 / HDR-INJ-DIS-01 | compressor / hydrocarbon_treatment | 27.000 | 10 | +17.000 |

**Roads.** A public entrance road runs from ROAD-ENTRANCE along the south of the withdrawal band; three spurs serve the areas that require access at each side of the road:
* `RD-01` (width 8 m): Main site access road from ROAD-ENTRANCE, running along the south of the withdrawal train area.
* `RD-02` (width 8 m): Access spine on the east side of the site.
* `RD-03` (width 6 m): Injection compressor maintenance road (crane access for heavy maintenance).
* `RD-05` (width 6 m): Separator maintenance road.

Only the compressors require road and crane access and only the separators require road access (per the catalogued maintenance flags); the crane-access distances from the compressor removal envelopes to the paved road boundaries are within the published 4.5 m buffer and the separator envelopes are within the 7 m road-access buffer. All paved geometry is inside the site, outside the road-exclusion zones and clear of every equipment footprint, and every road section is connected to the section carrying ROAD-ENTRANCE.

## 6 Piping and network definition

Every connection is a physical pipeline with an explicit route, diameter, pipe class and installation level (`ground`, `buried`, `rack_low`, `rack_high`); level changes occur only at shared segment endpoints and add no modelled length, loss or cost. Table 6.1 lists the pipelines; the complete vertex lists are in `deliverables/design.json`.

| tag | from | to | DN | class | level(s) | length (m) | service / purpose |
|---|---|---|---|---|---|---|---|
| P-101 | GRID-TIE | MTR-INJ-01.gas_in | 700 | CS-DRY-160 | ground | 195.0 | GRID-TIE to injection custody meter. |
| P-102 | MTR-INJ-01.gas_out | HDR-INJ-SUC-01.branch_02 | 700 | CS-DRY-160 | ground | 34.1 | Injection meter to compressor suction header. |
| P-103 | HDR-INJ-SUC-01.branch_01 | CMP-INJ-03.suction | 200 | CS-DRY-160 | ground | 111.2 | Suction header to injection compressor 3. |
| P-104 | HDR-INJ-SUC-01.branch_05 | CMP-INJ-02.suction | 500 | CS-DRY-160 | ground | 62.2 | Suction header to injection compressor 2. |
| P-105 | HDR-INJ-SUC-01.branch_09 | CMP-INJ-01.suction | 500 | CS-DRY-160 | ground | 13.8 | Suction header to injection compressor 1. |
| P-106 | CMP-INJ-01.discharge | HDR-INJ-DIS-01.branch_07 | 400 | CS-DRY-160 | ground, rack_low | 27.0 | Injection compressor 1 discharge (rack crossing over the unit access road). |
| P-107 | CMP-INJ-02.discharge | HDR-INJ-DIS-01.branch_11 | 450 | CS-DRY-160 | ground, rack_low | 75.0 | Injection compressor 2 discharge (rack crossing over the unit access road). |
| P-108 | CMP-INJ-03.discharge | HDR-INJ-DIS-01.branch_03 | 250 | CS-DRY-160 | rack_high | 131.5 | Injection compressor 3 discharge (elevated rack). |
| P-109 | HDR-INJ-DIS-01.branch_08 | COOL-INJ-01.gas_in | 600 | CS-DRY-160 | ground | 33.0 | Discharge header to the injection aftercooler. |
| P-113 | COOL-INJ-01.gas_out | WH-01.branch_08 | 600 | CS-DRY-160 | buried | 620.0 | Injection trunk from the aftercooler outlet to the well-group manifold. |
| P-114 | WH-01.branch_06 | SEP-WDR-03.gas_in | 300 | CS-WET-160 | buried | 437.6 | Withdrawal trunk, train C. |
| P-115 | WH-01.branch_10 | SEP-WDR-02.gas_in | 300 | CS-WET-160 | buried | 408.4 | Withdrawal trunk, train B. |
| P-116 | WH-01.branch_14 | SEP-WDR-01.gas_in | 300 | CS-WET-160 | buried | 406.9 | Withdrawal trunk, train A. |
| P-117 | SEP-WDR-01.gas_out | DEHY-WDR-01.gas_in | 300 | CS-WET-160 | ground | 36.0 | Separator to dehydration, train A. |
| P-118 | SEP-WDR-02.gas_out | DEHY-WDR-02.gas_in | 300 | CS-WET-160 | ground | 36.0 | Separator to dehydration, train B. |
| P-119 | SEP-WDR-03.gas_out | DEHY-WDR-03.gas_in | 400 | CS-WET-160 | ground | 36.0 | Separator to dehydration, train C. |
| P-120 | DEHY-WDR-01.gas_out | HDR-TRT-OUT-01.branch_04 | 350 | CS-DRY-160 | ground | 56.0 | Dehydration to treated-gas header, train A. |
| P-121 | DEHY-WDR-02.gas_out | HDR-TRT-OUT-01.branch_08 | 300 | CS-DRY-160 | ground | 27.0 | Dehydration to treated-gas header, train B. |
| P-122 | DEHY-WDR-03.gas_out | HDR-TRT-OUT-01.branch_12 | 350 | CS-DRY-160 | ground | 56.0 | Dehydration to treated-gas header, train C. |
| P-123 | HDR-TRT-OUT-01.branch_06 | HDR-DLV-01.branch_08 | 350 | CS-DRY-160 | rack_low | 69.4 | Delivery bypass around the compressor boost path (WDR-HIGH and WDR-MID). |
| P-143 | HDR-TRT-OUT-01.branch_03 | HDR-INJ-SUC-01.branch_08 | 500 | CS-DRY-160 | ground | 233.5 | Treated gas to the compressor suction header: feeds the boost service (WDR-LOW) through the injection compressor set. |
| P-144 | HDR-INJ-DIS-01.branch_02 | HDR-DLV-01.branch_09 | 450 | CS-DRY-160 | ground | 136.6 | Boost-service discharge from the compressor discharge header to the delivery header. |
| P-128 | HDR-DLV-01.branch_02 | REG-WDR-01.gas_in | 450 | CS-DRY-160 | ground | 30.6 | Delivery header to pressure regulator. |
| P-129 | REG-WDR-01.gas_out | MTR-WDR-01.gas_in | 450 | CS-DRY-160 | ground | 25.5 | Regulator to withdrawal custody meter. |
| P-130 | MTR-WDR-01.gas_out | GRID-TIE | 450 | CS-DRY-160 | ground | 63.0 | Withdrawal custody meter to GRID-TIE. |
| P-131 | WH-01.branch_09 | WG-06 | 300 | CS-WET-160 | ground | 197.2 | Well-group branch WG-06. |
| P-132 | WH-01.branch_05 | WG-05 | 300 | CS-WET-160 | ground | 123.8 | Well-group branch WG-05. |
| P-133 | WH-01.branch_01 | WG-04 | 250 | CS-WET-160 | ground | 50.2 | Well-group branch WG-04. |
| P-134 | WH-01.branch_11 | WG-03 | 250 | CS-WET-160 | ground | 50.5 | Well-group branch WG-03. |
| P-135 | WH-01.branch_07 | WG-02 | 300 | CS-WET-160 | ground | 124.5 | Well-group branch WG-02. |
| P-136 | WH-01.branch_03 | WG-01 | 300 | CS-WET-160 | ground | 198.5 | Well-group branch WG-01. |
| P-137 | SEP-WDR-01.liquid_out | DRN-WDR-01.drain_in | 150 | CS-WET-100 | buried | 325.0 | Separator train A liquid drain line. |
| P-138 | SEP-WDR-02.liquid_out | DRN-WDR-02.drain_in | 150 | CS-WET-100 | buried | 379.0 | Separator train B liquid drain line. |
| P-139 | SEP-WDR-03.liquid_out | DRN-WDR-03.drain_in | 150 | CS-WET-100 | buried | 433.0 | Separator train C liquid drain line. |
| P-140 | DRN-WDR-01.drain_out | LIQUID-DRAIN-OUTFALL | 150 | CS-WET-100 | buried | 203.0 | Closed drain 1 discharge to outfall. |
| P-141 | DRN-WDR-02.drain_out | LIQUID-DRAIN-OUTFALL | 150 | CS-WET-100 | buried | 179.0 | Closed drain 2 discharge to outfall. |
| P-142 | DRN-WDR-03.drain_out | LIQUID-DRAIN-OUTFALL | 150 | CS-WET-100 | buried | 195.0 | Closed drain 3 discharge to outfall. |

**Class selection.** All pipelines that can convey wet gas (water > 50 mg/Sm3 or free liquid > 10⁻⁴ kg/kg) are classed CS-WET-160: the six well branches and the three withdrawal trunks (wet at up to 12 MPa) and the separator-to-dehydration runs. From the dehydration outlet to the GRID-TIE the gas is dry, so CS-DRY-160 is used; it has both a lower roughness (1.5 × 10⁻⁵ m versus 4.5 × 10⁻⁵ m) and a lower cost multiplier than the wet class. The injection chain is dry gas throughout and uses CS-DRY-160. All gas pipelines are rated 16 MPa, above the highest pressure anywhere in the design, and their temperature range covers the service temperatures. Liquid-drain lines use CS-WET-100, the only class that is both liquid-drain compatible and rated above the 1 MPa drain domain.

**Sizing.** Diameters were optimised against the LCC: every pipeline was sized between the diameter that satisfies the 25 m/s gas velocity limit and the diameter at which the capital cost of further upsizing exceeds the present value of the compressor energy it saves. Because the compressor energy is the dominant cost, the main lines are deliberately larger than the velocity minimum (for example the 620 m injection trunk is DN600, the GRID-TIE suction line DN700). Liquid-drain lines are DN150; at the maximum liquid flow of 0.6 kg/s they run far below the 3 m/s liquid-drain limit.

**Routing rules applied.** Every segment stays inside the site, avoids the interior of the FUTURE-EXPANSION and DRAINAGE-CHANNEL pipeline-exclusion zones, and never crosses an equipment footprint interior (the only footprint contact is at the port itself). No two same-level segments overlap by a positive length, so no co-routing corridor declaration is needed; pipelines that would otherwise cross at the same level are separated by level (for example the compressor discharge manifolds sit on ground, rack_low and rack_high risers where they cross the unit access road). The long trunk lines and all drain lines are buried, which also keeps them clear of road construction.

## 7 Operating philosophy and scenario plans

Each published scenario is operated along the physical path described in section 3, with the flows, splits and setpoints listed in table 7.1. The plan is a steady-state plan: boundary flows, per-unit flows, compressor discharge pressures, aftercooler outlet temperatures and the delivery regulator setpoint.

| scenario | setpoints | well-group flows (kg/s) | unit flows (kg/s) |
|---|---|---|---|
| INJ-LOW | aftercooler 50 degC; compressor discharge 8.5757 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | CMP-INJ-01:55.00, CMP-INJ-02:55.00, CMP-INJ-03:10.00, COOL-INJ-01:120.00 |
| INJ-LOW/N-1 CMP-INJ-01 out | aftercooler 50 degC; compressor discharge 8.5737 MPa | WG-01:14.00, WG-02:14.00, WG-03:14.00, WG-04:14.00, WG-05:14.00, WG-06:14.00 | CMP-INJ-02:57.00, CMP-INJ-03:27.00, COOL-INJ-01:84.00 |
| INJ-LOW/N-1 CMP-INJ-02 out | aftercooler 50 degC; compressor discharge 8.5737 MPa | WG-01:14.00, WG-02:14.00, WG-03:14.00, WG-04:14.00, WG-05:14.00, WG-06:14.00 | CMP-INJ-01:57.00, CMP-INJ-03:27.00, COOL-INJ-01:84.00 |
| INJ-LOW/N-1 CMP-INJ-03 out | aftercooler 50 degC; compressor discharge 8.5551 MPa | WG-01:14.00, WG-02:14.00, WG-03:14.00, WG-04:14.00, WG-05:14.00, WG-06:14.00 | CMP-INJ-01:42.00, CMP-INJ-02:42.00, COOL-INJ-01:84.00 |
| INJ-MID | aftercooler 50 degC; compressor discharge 11.0585 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | CMP-INJ-01:50.00, CMP-INJ-02:50.00, COOL-INJ-01:100.00 |
| INJ-MID/N-1 CMP-INJ-01 out | aftercooler 50 degC; compressor discharge 11.0498 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-02:57.00, CMP-INJ-03:13.00, COOL-INJ-01:70.00 |
| INJ-MID/N-1 CMP-INJ-02 out | aftercooler 50 degC; compressor discharge 11.0498 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:57.00, CMP-INJ-03:13.00, COOL-INJ-01:70.00 |
| INJ-MID/N-1 CMP-INJ-03 out | aftercooler 50 degC; compressor discharge 11.0466 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, COOL-INJ-01:70.00 |
| INJ-HIGH | aftercooler 50 degC; compressor discharge 13.5466 MPa | WG-01:12.50, WG-02:12.50, WG-03:12.50, WG-04:12.50, WG-05:12.50, WG-06:12.50 | CMP-INJ-01:37.50, CMP-INJ-02:37.50, COOL-INJ-01:75.00 |
| INJ-HIGH/N-1 CMP-INJ-01 out | aftercooler 50 degC; compressor discharge 13.5419 MPa | WG-01:8.75, WG-02:8.75, WG-03:8.75, WG-04:8.75, WG-05:8.75, WG-06:8.75 | CMP-INJ-02:52.50, COOL-INJ-01:52.50 |
| INJ-HIGH/N-1 CMP-INJ-02 out | aftercooler 50 degC; compressor discharge 13.5413 MPa | WG-01:8.75, WG-02:8.75, WG-03:8.75, WG-04:8.75, WG-05:8.75, WG-06:8.75 | CMP-INJ-01:52.50, COOL-INJ-01:52.50 |
| INJ-HIGH/N-1 CMP-INJ-03 out | aftercooler 50 degC; compressor discharge 13.5407 MPa | WG-01:8.75, WG-02:8.75, WG-03:8.75, WG-04:8.75, WG-05:8.75, WG-06:8.75 | CMP-INJ-01:26.25, CMP-INJ-02:26.25, COOL-INJ-01:52.50 |
| WDR-HIGH | regulator outlet 6.0355 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-01:40.00, DEHY-WDR-02:40.00, DEHY-WDR-03:40.00, DRN-WDR-01:0.40, DRN-WDR-02:0.40, DRN-WDR-03:0.40, SEP-WDR-01:40.00, SEP-WDR-02:40.00, SEP-WDR-03:40.00 |
| WDR-HIGH/N-1 SEP-WDR-01 out | regulator outlet 6.0356 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-02:60.00, DEHY-WDR-03:60.00, DRN-WDR-02:0.60, DRN-WDR-03:0.60, SEP-WDR-02:60.00, SEP-WDR-03:60.00 |
| WDR-HIGH/N-1 DEHY-WDR-01 out | regulator outlet 6.0356 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-02:60.00, DEHY-WDR-03:60.00, DRN-WDR-02:0.60, DRN-WDR-03:0.60, SEP-WDR-02:60.00, SEP-WDR-03:60.00 |
| WDR-HIGH/N-1 SEP-WDR-02 out | regulator outlet 6.0356 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-01:60.00, DEHY-WDR-03:60.00, DRN-WDR-01:0.60, DRN-WDR-03:0.60, SEP-WDR-01:60.00, SEP-WDR-03:60.00 |
| WDR-HIGH/N-1 DEHY-WDR-02 out | regulator outlet 6.0356 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-01:60.00, DEHY-WDR-03:60.00, DRN-WDR-01:0.60, DRN-WDR-03:0.60, SEP-WDR-01:60.00, SEP-WDR-03:60.00 |
| WDR-HIGH/N-1 SEP-WDR-03 out | regulator outlet 6.0356 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-01:60.00, DEHY-WDR-02:60.00, DRN-WDR-01:0.60, DRN-WDR-02:0.60, SEP-WDR-01:60.00, SEP-WDR-02:60.00 |
| WDR-HIGH/N-1 DEHY-WDR-03 out | regulator outlet 6.0356 MPa | WG-01:20.00, WG-02:20.00, WG-03:20.00, WG-04:20.00, WG-05:20.00, WG-06:20.00 | DEHY-WDR-01:60.00, DEHY-WDR-02:60.00, DRN-WDR-01:0.60, DRN-WDR-02:0.60, SEP-WDR-01:60.00, SEP-WDR-02:60.00 |
| WDR-MID | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-01:33.33, DEHY-WDR-02:33.33, DEHY-WDR-03:33.33, DRN-WDR-01:0.33, DRN-WDR-02:0.33, DRN-WDR-03:0.33, SEP-WDR-01:33.33, SEP-WDR-02:33.33, SEP-WDR-03:33.33 |
| WDR-MID/N-1 SEP-WDR-01 out | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-02:50.00, DEHY-WDR-03:50.00, DRN-WDR-02:0.50, DRN-WDR-03:0.50, SEP-WDR-02:50.00, SEP-WDR-03:50.00 |
| WDR-MID/N-1 DEHY-WDR-01 out | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-02:50.00, DEHY-WDR-03:50.00, DRN-WDR-02:0.50, DRN-WDR-03:0.50, SEP-WDR-02:50.00, SEP-WDR-03:50.00 |
| WDR-MID/N-1 SEP-WDR-02 out | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-01:50.00, DEHY-WDR-03:50.00, DRN-WDR-01:0.50, DRN-WDR-03:0.50, SEP-WDR-01:50.00, SEP-WDR-03:50.00 |
| WDR-MID/N-1 DEHY-WDR-02 out | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-01:50.00, DEHY-WDR-03:50.00, DRN-WDR-01:0.50, DRN-WDR-03:0.50, SEP-WDR-01:50.00, SEP-WDR-03:50.00 |
| WDR-MID/N-1 SEP-WDR-03 out | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-01:50.00, DEHY-WDR-02:50.00, DRN-WDR-01:0.50, DRN-WDR-02:0.50, SEP-WDR-01:50.00, SEP-WDR-02:50.00 |
| WDR-MID/N-1 DEHY-WDR-03 out | regulator outlet 6.0310 MPa | WG-01:16.67, WG-02:16.67, WG-03:16.67, WG-04:16.67, WG-05:16.67, WG-06:16.67 | DEHY-WDR-01:50.00, DEHY-WDR-02:50.00, DRN-WDR-01:0.50, DRN-WDR-02:0.50, SEP-WDR-01:50.00, SEP-WDR-02:50.00 |
| WDR-LOW | regulator outlet 6.0262 MPa; boost discharge 6.3415 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-01:23.33, DEHY-WDR-02:23.33, DEHY-WDR-03:23.33, DRN-WDR-01:0.23, DRN-WDR-02:0.23, DRN-WDR-03:0.23, SEP-WDR-01:23.33, SEP-WDR-02:23.33, SEP-WDR-03:23.33 |
| WDR-LOW/N-1 SEP-WDR-01 out | regulator outlet 6.0262 MPa; boost discharge 6.3416 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-02:35.00, DEHY-WDR-03:35.00, DRN-WDR-02:0.35, DRN-WDR-03:0.35, SEP-WDR-02:35.00, SEP-WDR-03:35.00 |
| WDR-LOW/N-1 DEHY-WDR-01 out | regulator outlet 6.0262 MPa; boost discharge 6.3416 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-02:35.00, DEHY-WDR-03:35.00, DRN-WDR-02:0.35, DRN-WDR-03:0.35, SEP-WDR-02:35.00, SEP-WDR-03:35.00 |
| WDR-LOW/N-1 SEP-WDR-02 out | regulator outlet 6.0262 MPa; boost discharge 6.3416 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-01:35.00, DEHY-WDR-03:35.00, DRN-WDR-01:0.35, DRN-WDR-03:0.35, SEP-WDR-01:35.00, SEP-WDR-03:35.00 |
| WDR-LOW/N-1 DEHY-WDR-02 out | regulator outlet 6.0262 MPa; boost discharge 6.3416 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-01:35.00, DEHY-WDR-03:35.00, DRN-WDR-01:0.35, DRN-WDR-03:0.35, SEP-WDR-01:35.00, SEP-WDR-03:35.00 |
| WDR-LOW/N-1 SEP-WDR-03 out | regulator outlet 6.0262 MPa; boost discharge 6.3416 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-01:35.00, DEHY-WDR-02:35.00, DRN-WDR-01:0.35, DRN-WDR-02:0.35, SEP-WDR-01:35.00, SEP-WDR-02:35.00 |
| WDR-LOW/N-1 DEHY-WDR-03 out | regulator outlet 6.0262 MPa; boost discharge 6.3416 MPa | WG-01:11.67, WG-02:11.67, WG-03:11.67, WG-04:11.67, WG-05:11.67, WG-06:11.67 | CMP-INJ-01:35.00, CMP-INJ-02:35.00, DEHY-WDR-01:35.00, DEHY-WDR-02:35.00, DRN-WDR-01:0.35, DRN-WDR-02:0.35, SEP-WDR-01:35.00, SEP-WDR-02:35.00 |
| WDR-LOW/N-1 CMP-INJ-01 out | regulator outlet 6.0230 MPa; boost discharge 6.3324 MPa | WG-01:8.17, WG-02:8.17, WG-03:8.17, WG-04:8.17, WG-05:8.17, WG-06:8.17 | CMP-INJ-02:49.00, DEHY-WDR-01:16.33, DEHY-WDR-02:16.33, DEHY-WDR-03:16.33, DRN-WDR-01:0.16, DRN-WDR-02:0.16, DRN-WDR-03:0.16, SEP-WDR-01:16.33, SEP-WDR-02:16.33, SEP-WDR-03:16.33 |
| WDR-LOW/N-1 CMP-INJ-02 out | regulator outlet 6.0230 MPa; boost discharge 6.3316 MPa | WG-01:8.17, WG-02:8.17, WG-03:8.17, WG-04:8.17, WG-05:8.17, WG-06:8.17 | CMP-INJ-01:49.00, DEHY-WDR-01:16.33, DEHY-WDR-02:16.33, DEHY-WDR-03:16.33, DRN-WDR-01:0.16, DRN-WDR-02:0.16, DRN-WDR-03:0.16, SEP-WDR-01:16.33, SEP-WDR-02:16.33, SEP-WDR-03:16.33 |
| WDR-LOW/N-1 CMP-INJ-03 out | regulator outlet 6.0230 MPa; boost discharge 6.3306 MPa | WG-01:8.17, WG-02:8.17, WG-03:8.17, WG-04:8.17, WG-05:8.17, WG-06:8.17 | CMP-INJ-01:24.50, CMP-INJ-02:24.50, DEHY-WDR-01:16.33, DEHY-WDR-02:16.33, DEHY-WDR-03:16.33, DRN-WDR-01:0.16, DRN-WDR-02:0.16, DRN-WDR-03:0.16, SEP-WDR-01:16.33, SEP-WDR-02:16.33, SEP-WDR-03:16.33 |

### 7.1 Scenario results

| scenario | sink pressure (MPa) | required (MPa) | delivery temperature (degC) | water (mg/Sm3) | free liquid (kg/kg) | energy (MWh) |
|---|---|---|---|---|---|---|
| INJ-LOW | 8.5000 | 8.5 | 50.00 | 40.0 | 0.00e+00 | 6932.8 |
| INJ-MID | 11.0000 | 11 | 50.00 | 40.0 | 0.00e+00 | 16531.9 |
| INJ-HIGH | 13.5000 | 13.5 | 50.00 | 40.0 | 0.00e+00 | 8117.2 |
| WDR-HIGH | 6.0000 | 6 | 13.09 | 35.0 | 5.00e-06 | 1080.0 |
| WDR-MID | 6.0000 | 6 | 17.88 | 35.0 | 5.00e-06 | 1620.0 |
| WDR-LOW | 6.0000 | 6 | 53.45 | 35.0 | 5.00e-06 | 5839.7 |

### 7.2 Pressure and temperature profile of two representative scenarios

**INJ-LOW** (120.00 kg/s from GRID-TIE at 6.50 MPa)

| node | inlet p (MPa) | outlet p (MPa) | temperature (degC) | flow (kg/s) |
|---|---|---|---|---|
| GRID-TIE | 6.5000 | 6.5000 | 25.00 | 120.00 |
| MTR-INJ-01 | 6.4966 | 6.4766 | 25.00 | 120.00 |
| HDR-INJ-SUC-01 | 6.4760 | 6.4715 | 25.00 | 120.00 |
| CMP-INJ-01 | 6.4712 | 8.5757 | 50.02 | 55.00 |
| HDR-INJ-DIS-01 | 8.5729 | 8.5685 | 50.15 | 120.00 |
| COOL-INJ-01 | 8.5674 | 8.5324 | 50.00 | 120.00 |
| WH-01 | 8.5123 | 8.5079 | 50.00 | 120.00 |
| WG-01 | 8.5000 | 8.5000 | 50.00 | 20.00 |
| WG-06 | 8.5000 | 8.5000 | 50.00 | 20.00 |

**WDR-HIGH** (120.00 kg/s from well_groups at 12.00 MPa)

| node | inlet p (MPa) | outlet p (MPa) | temperature (degC) | flow (kg/s) |
|---|---|---|---|---|
| WG-01 | 12.0000 | 12.0000 | 20.00 | 20.00 |
| WH-01 | 11.9949 | 11.9905 | 20.00 | 120.00 |
| SEP-WDR-01 | 11.9492 | 11.9192 | 20.00 | 40.00 |
| DEHY-WDR-01 | 11.9155 | 11.8355 | 20.00 | 40.00 |
| HDR-TRT-OUT-01 | 11.8331 | 11.8286 | 20.00 | 120.00 |
| HDR-DLV-01 | 11.8051 | 11.8006 | 20.00 | 120.00 |
| REG-WDR-01 | 11.7978 | 6.0355 | 13.09 | 120.00 |
| MTR-WDR-01 | 6.0311 | 6.0111 | 13.09 | 120.00 |
| GRID-TIE | 6.0000 | 6.0000 | 13.09 | 120.00 |

### 7.3 Reliability: single-unit-outage plans

| case | failed unit | retained flow (kg/s) | retained fraction | delivery requirement met |
|---|---|---|---|---|
| INJ-LOW | CMP-INJ-01 | 84.00 | 0.700 | 8.500 MPa min well-group |
| INJ-LOW | CMP-INJ-02 | 84.00 | 0.700 | 8.500 MPa min well-group |
| INJ-LOW | CMP-INJ-03 | 84.00 | 0.700 | 8.500 MPa min well-group |
| INJ-MID | CMP-INJ-01 | 70.00 | 0.700 | 11.000 MPa min well-group |
| INJ-MID | CMP-INJ-02 | 70.00 | 0.700 | 11.000 MPa min well-group |
| INJ-MID | CMP-INJ-03 | 70.00 | 0.700 | 11.000 MPa min well-group |
| INJ-HIGH | CMP-INJ-01 | 52.50 | 0.700 | 13.500 MPa min well-group |
| INJ-HIGH | CMP-INJ-02 | 52.50 | 0.700 | 13.500 MPa min well-group |
| INJ-HIGH | CMP-INJ-03 | 52.50 | 0.700 | 13.500 MPa min well-group |
| WDR-HIGH | SEP-WDR-01 | 120.00 | 1.000 | 6.000 MPa at GRID-TIE, T 13.2 degC, water 35.0 mg/Sm3 |
| WDR-HIGH | DEHY-WDR-01 | 120.00 | 1.000 | 6.000 MPa at GRID-TIE, T 13.2 degC, water 35.0 mg/Sm3 |
| WDR-HIGH | SEP-WDR-02 | 120.00 | 1.000 | 6.000 MPa at GRID-TIE, T 13.2 degC, water 35.0 mg/Sm3 |
| WDR-HIGH | DEHY-WDR-02 | 120.00 | 1.000 | 6.000 MPa at GRID-TIE, T 13.2 degC, water 35.0 mg/Sm3 |
| WDR-HIGH | SEP-WDR-03 | 120.00 | 1.000 | 6.000 MPa at GRID-TIE, T 13.2 degC, water 35.0 mg/Sm3 |
| WDR-HIGH | DEHY-WDR-03 | 120.00 | 1.000 | 6.000 MPa at GRID-TIE, T 13.2 degC, water 35.0 mg/Sm3 |
| WDR-MID | SEP-WDR-01 | 100.00 | 1.000 | 6.000 MPa at GRID-TIE, T 18.0 degC, water 35.0 mg/Sm3 |
| WDR-MID | DEHY-WDR-01 | 100.00 | 1.000 | 6.000 MPa at GRID-TIE, T 18.0 degC, water 35.0 mg/Sm3 |
| WDR-MID | SEP-WDR-02 | 100.00 | 1.000 | 6.000 MPa at GRID-TIE, T 18.0 degC, water 35.0 mg/Sm3 |
| WDR-MID | DEHY-WDR-02 | 100.00 | 1.000 | 6.000 MPa at GRID-TIE, T 18.0 degC, water 35.0 mg/Sm3 |
| WDR-MID | SEP-WDR-03 | 100.00 | 1.000 | 6.000 MPa at GRID-TIE, T 18.0 degC, water 35.0 mg/Sm3 |
| WDR-MID | DEHY-WDR-03 | 100.00 | 1.000 | 6.000 MPa at GRID-TIE, T 18.0 degC, water 35.0 mg/Sm3 |
| WDR-LOW | SEP-WDR-01 | 70.00 | 1.000 | 6.000 MPa at GRID-TIE, T 54.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | DEHY-WDR-01 | 70.00 | 1.000 | 6.000 MPa at GRID-TIE, T 54.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | SEP-WDR-02 | 70.00 | 1.000 | 6.000 MPa at GRID-TIE, T 54.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | DEHY-WDR-02 | 70.00 | 1.000 | 6.000 MPa at GRID-TIE, T 54.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | SEP-WDR-03 | 70.00 | 1.000 | 6.000 MPa at GRID-TIE, T 54.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | DEHY-WDR-03 | 70.00 | 1.000 | 6.000 MPa at GRID-TIE, T 54.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | CMP-INJ-01 | 49.00 | 0.700 | 6.000 MPa at GRID-TIE, T 52.7 degC, water 35.0 mg/Sm3 |
| WDR-LOW | CMP-INJ-02 | 49.00 | 0.700 | 6.000 MPa at GRID-TIE, T 52.6 degC, water 35.0 mg/Sm3 |
| WDR-LOW | CMP-INJ-03 | 49.00 | 0.700 | 6.000 MPa at GRID-TIE, T 52.6 degC, water 35.0 mg/Sm3 |

All compressor-outage cases retain at least the required 70 % of the scenario flow (INJ-LOW 84 kg/s, INJ-MID 70, INJ-HIGH 52.5, WDR-LOW 49) at the required delivery pressure and quality; the two withdrawal trains that remain in a separator or dehydration outage carry the **full** scenario flow, i.e. more than the 70 % required. The delivery limits are re-checked in every outage case.

## 8 Quantities

* equipment: {'HDR180': 5, 'MTR120': 2, 'C60': 2, 'C40': 1, 'COOL120': 1, 'SEP70': 3, 'DEHY70': 3, 'REG120': 1, 'DRN-S': 3}
* gas and liquid pipelines: 5820 m total; by level: buried 3587 m, ground 2012 m, rack_high 132 m, rack_low 89 m
* pipeline length by diameter: DN150 1714 m, DN200 111 m, DN250 232 m, DN300 1996 m, DN350 181 m, DN400 63 m, DN450 331 m, DN500 310 m, DN600 653 m, DN700 229 m
* road centreline length: 1189.5 m
* equipment footprint area: 775 m2
* required maintenance-envelope area (envelope area minus footprint area): 1590 m2

## 9 Lifecycle cost

The LCC follows the published basis exactly: equipment CAPEX (sum over installed instances), piping CAPEX (segment length × diameter installed cost × pipe-class multiplier × routing-level multiplier), civil/access CAPEX (road centreline × rate, footprint area × foundation rate, maintenance-envelope area × rate, and pipeline length × routing-level civil rate), the present value of the annual energy cost and the present value of the annual maintenance cost, with PVF = 9.818147 (8 %, 20 years).

| component | MBCU |
|---|---|
| equipment CAPEX | 29.3900 |
| piping CAPEX | 1.8942 |
| civil / access CAPEX | 0.2541 |
| energy, present value (40122 MWh/a) | 47.2704 |
| maintenance, present value (1.067 MBCU/a) | 10.4760 |
| **LCC** | **89.2846** |

Civil/access breaks down as roads 0.1784, foundations 0.0031, maintenance envelopes 0.0016, pipeline civil 0.0710 MBCU.

Annual energy is dominated by the shared compressor set: 31582 MWh/a over the three injection scenarios (including the aftercooler power), 4832 MWh/a on the WDR-LOW boost duty, plus 3708 MWh/a of dehydration energy (0.018 MW per kg/s of withdrawal gas). The rejected dedicated-boost alternative would have added roughly the same boost duty at a slightly higher ratio, on top of its 13.0 MBCU of additional equipment.

Because the present value of energy is more than half of the LCC, the design was optimised on two levels: (i) equipment selection and count, solved as the cheapest compliant set subject to the N-1 rules and the equipment pressure/ratio limits; and (ii) pipe diameters, solved by coordinate descent over groups of parallel branches and then over every individual pipeline against the full LCC (piping CAPEX + pipeline civil + energy present value), with the velocity limit enforced in the single-unit-outage cases as well as in normal operation (`tools/optimize.py`). The diameter optimisation is worth **2.79 MBCU**: relative to the smallest diameters that merely satisfy the velocity and delivery limits, the chosen (larger) diameters add 0.56 MBCU of piping CAPEX but remove 2 840 MWh/a of compressor energy, worth 3.34 MBCU of present value. Changing to higher-efficiency but larger machines (for example 2 × C80 + 1 × C40 instead of 2 × C60 + 1 × C40) was evaluated and rejected: the extra capital and maintenance exceed the energy saving at these duty points.

## 10 Verification

`tools/build.py` re-derives every rule in the v1.1 basis from the brief data and the design definition: 6678 individual checks were evaluated, of which **0 failed**. The checks cover port compatibility and connection cardinality, footprint containment and exclusion zones, the full separation matrix, clearance and removal envelopes, road geometry, connectivity and access buffers, every pipeline route against site/exclusion/footprint/overlap rules, and for every scenario (normal and outage) the mass balance, hydraulic march with the published fixed-point convention, equipment limits, velocity limits, pipe-class rating and compatibility, metering capacity, drain capacity and the delivery limits at the sink interfaces. The full list is `deliverables/checks.csv`.

Reproduce with:

```
python tools/build.py          # writes deliverables/design.json, verification.md, checks.csv, layout.svg
python tools/optimize.py       # re-runs the diameter optimisation
python tools/make_report.py    # regenerates this report
```

## 11 Assumptions and known limitations

1. **Valve isolation is not modelled.** The catalogued world contains no valves, so the physical network of section 6 is fixed and the scenario plans assume that isolating valves (outside the catalogued scope, as in any real station) select the path of each scenario. For this design those valves are: the injection custody meter and the `P-143` boost feed line are closed during withdrawal (otherwise the discharge header would be connected back to the wells through `P-109`/`COOL-INJ-01`/`P-113` and to the grid through the injection meter); the `P-144` boost discharge line and the compressor branch are closed during injection and during the two high-pressure withdrawal scenarios (which use the `P-123` bypass); and the well manifold `WH-01` is manifolded between the injection chain and the three withdrawal trains, with the active branch set selected per scenario. The published semantics explicitly allow cyclic physical networks and require only that every declared scenario satisfies the port, mass-balance, pressure, capacity, temperature and delivery rules.

2. **Delivery pressure setpoints equal the requirement.** `required_sink_pressure_mpa` is read as the pressure at which the sink accepts gas; the case makes compression necessary exactly when the sink pressure requirement exceeds the source pressure, so it cannot be an upper bound. The design delivers exactly the requirement (the published tolerance convention treats a value within 1e-5 MPa of a limit as equal to it), which satisfies a minimum, an exact and an upper-bound reading simultaneously.

3. **Liquid density.** No liquid density is published; the drain-velocity check assumes 800 kg/m³. The largest drain flow gives ≈ 0.04 m/s in DN150, so the conclusion is insensitive to this assumption.

4. **No heat transfer in pipelines.** The basis models no heat loss, so delivered temperatures equal the last machine setpoint: 50.0 degC for injection after the aftercooler (limit 60 degC), 13.1/17.9 degC for the high- and mid-pressure withdrawal scenarios after the regulator's JT cooling, and 53.4 degC for WDR-LOW, where the gas leaves the shared compressors at ≈ 54 degC and the regulator - the only cooling device in that path - removes only ≈ 0.4 K.

5. **Aftercooler and cooler loads** are computed at the mixed compressor-discharge temperature; the cooler duty/power and the dehydration energy are included in the LCC.

6. **Simplified operating plans.** Steady-state plans only: no start-up, shutdown, transients, blowdown or pressure-equalisation sequences are modelled, and no scenario is required to operate two simultaneous unrelated outages.

7. **Safety provisions** are those the case publishes: the separation matrix, the maintenance envelopes, road/crane access and the GRID-TIE/LIQUID-DRAIN-OUTFALL flow and connection limits. No code compliance, fire protection, ESD or hazardous-area design is in scope.

8. **Excluded scope** (from the project requirements): reservoir model, well completion, full electrical and control systems, firewater synthesis, structural and civil detail, process safety study, regulatory compliance and vendor procurement. Equipment costs and ratings are the synthetic catalogue values, not vendor data.

