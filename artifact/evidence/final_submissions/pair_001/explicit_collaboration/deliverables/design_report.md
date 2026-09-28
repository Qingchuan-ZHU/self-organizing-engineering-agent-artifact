# UGS-SYNTH-D01 — Underground gas storage surface facility design

**Case:** UGS-SYNTH-D01 (benchmark family UGS-SYNTH, case version 1.1.0-development)  
**Deliverable:** conceptual surface-facility design, operating plan and lifecycle-cost basis  
**Units:** SI; pressure MPa, temperature degC, flow kg/s, length m, area m2, power/duty MW, energy MWh, cost MBCU, gas water content mg/Sm3, free-liquid loading kg liquid/kg gas.

All data used are the published synthetic benchmark data (catalogue, site, scenarios, economics). Values are not vendor data or production engineering criteria.

---

## 1. Design basis

### 1.1 Duty

| Scenario | Service | Flow kg/s | Source | Source P (MPa) | Source T (degC) | Water (mg/Sm3) | Free liquid | Sink | Sink P (MPa) | Hours/y |
|---|---|---|---|---|---|---|---|---|---|---|
| INJ-LOW | injection | 120 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 6 well groups | 8.5 | 900 |
| INJ-MID | injection | 100 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 6 well groups | 11.0 | 1300 |
| INJ-HIGH | injection | 75 | GRID-TIE | 6.5 | 25 | 40 | 0.0 | 6 well groups | 13.5 | 600 |
| WDR-HIGH | withdrawal | 120 | well_groups | 12.0 | 20 | 220 | 0.01 | GRID-TIE | 6.0 | 500 |
| WDR-MID | withdrawal | 100 | well_groups | 8.0 | 20 | 220 | 0.01 | GRID-TIE | 6.0 | 900 |
| WDR-LOW | withdrawal | 70 | well_groups | 4.5 | 20 | 220 | 0.01 | GRID-TIE | 6.0 | 800 |

Operating hours per year: 5000 h (sum of scenario hours). Delivery limits: water <= 50 mg/Sm3, free liquid <= 0.0001 kg/kg, temperature -10 .. 60 degC. Well-group boundary: 25 kg/s per interface. GRID-TIE: all exchanged gas metered, active meter capacity >= scenario flow.

### 1.2 Reliability requirements

- Compression n-1 (scenarios with required sink pressure > source pressure): after loss of any one compressor, >= 70 % of scenario flow remains deliverable with the delivery limits still met.
- Withdrawal treatment n-1: after loss of any one separator or dehydrator, >= 70 % of the withdrawal scenario flow remains deliverable with the delivery limits still met.

### 1.3 Sizing philosophy

The plant is arranged as three identical parallel process trains (lanes) so that any single unit can be isolated without losing more than one third of the installed capacity. Compressor discharge pressure, injection aftercooler outlet temperature and the grid pressure-control setpoint are the only operating setpoints; everything else follows from the scenario boundary conditions. Pipe diameters were selected by minimising the benchmark lifecycle cost subject to the published velocity limits (larger diameter costs capital but reduces compression energy, which dominates the LCC).

### 1.4 Key design assumptions

- Three parallel process trains are used for the separator, dehydrator and compressor banks so that the published n-1 requirements are met with equipment that stays at moderate unit size.
- Scenario flows are split equally between the active trains and equally between the six well-group interfaces; the split is a design choice, not a published requirement. Well-group flow never exceeds 20 kg/s of the 25 kg/s boundary limit.
- Injection compressor discharge pressure is set 0.05 MPa above the pressure needed to satisfy the worst (longest) well-group branch, so that all six well-group interfaces receive at least their required pressure with margin.
- The injection aftercooler outlet setpoint is 40 degC so that the delivered gas is at least 20 K below the 60 degC delivery limit; the cooler is idle (zero duty) whenever the inlet temperature is below the setpoint, as on the withdrawal path.
- Grid pressure control holds the withdrawal delivery at 6.20 MPa at the pressure-control valve outlet, i.e. ~6.13-6.16 MPa at GRID-TIE, above the 6.0 MPa requirement, and avoids pushing high well pressure into the grid.
- Compressor discharge temperature is not limited by the delivery limit because the aftercooler is in series upstream of the well-group interfaces; the compressor's own 150 degC discharge limit is respected.
- Gas is treated as dry for pipe-class purposes when water content <= 50 mg/Sm3 and free-liquid loading <= 1e-4 kg/kg, following the published definition.
- Pressure losses use the published fixed-point convention with at most 8 updates; every pipeline in every case converges (reported in operating_plan.json).
- Plan-view crossings of two same-level pipelines at a discrete point are permitted by the published rules (only positive-length same-level overlap is prohibited); such crossings are resolved by local elevation changes in detailed design.
- Where a pipeline crosses a road, the crossing length is installed at buried level in the model; the design assumes a sleeved crossing as normal practice.
- Drain lines are installed buried; the separator liquid outlet is taken as already let down into the closed-drain pressure domain per the published semantics.
- Each scenario's active equipment set is defined by its operating path; every branch not listed is isolated by its block valve (compressor bypass closed during injection and in WDR-LOW, treatment trains isolated during injection, cooler branch isolated during withdrawal, grid-side branches isolated during injection).
- The benchmark publishes no liquid density, so drain-line velocities are reported over a density band from water (1000 kg/m3) to a deliberately pessimistic gas-density-like 8.2 kg/m3 at the closed-drain pressure: 0.022-0.027 m/s at 800-1000 kg/m3 and 2.63 m/s in the pessimistic case, all within the 3 m/s limit (see operating_plan.json, liquid_drain_velocity_check).

---

## 2. Equipment selection

| Instance | Model | Category | Safety category | Position (x,y) m | Orient. deg | Capacity kg/s | Capex MBCU | Maintenance MBCU/y |
|---|---|---|---|---|---|---|---|---|
| CMP-A | C60 | compressor | compressor | (480, 70) | 0 | 60 | 6.5 | 0.16 |
| CMP-B | C60 | compressor | compressor | (480, 140) | 0 | 60 | 6.5 | 0.16 |
| CMP-C | C60 | compressor | compressor | (480, 210) | 0 | 60 | 6.5 | 0.16 |
| COOL | COOL120 | cooler | hydrocarbon_treatment | (560, 190) | 90 | 120 | 0.92 | 0.05 |
| DEH-A | DEHY70 | dehydration | hydrocarbon_treatment | (380, 70) | 0 | 70 | 1.85 | 0.095 |
| DEH-B | DEHY70 | dehydration | hydrocarbon_treatment | (380, 140) | 0 | 70 | 1.85 | 0.095 |
| DEH-C | DEHY70 | dehydration | hydrocarbon_treatment | (380, 210) | 0 | 70 | 1.85 | 0.095 |
| DRN-A | DRN-S | closed_drain | drain | (280, 55) | 0 | 0.8 | 0.08 | 0.004 |
| DRN-B | DRN-S | closed_drain | drain | (280, 125) | 0 | 0.8 | 0.08 | 0.004 |
| DRN-C | DRN-S | closed_drain | drain | (280, 195) | 0 | 0.8 | 0.08 | 0.004 |
| H-DIS | HDR120 | header | hydrocarbon_treatment | (545, 140) | 0 | 120 | 0.25 | 0.012 |
| H-SITE | HDR120 | header | hydrocarbon_treatment | (250, 140) | 0 | 120 | 0.25 | 0.012 |
| H-SUC | HDR120 | header | hydrocarbon_treatment | (430, 140) | 0 | 120 | 0.25 | 0.012 |
| H-WELL | HDR120 | header | hydrocarbon_treatment | (90, 180) | 0 | 120 | 0.25 | 0.012 |
| MTR-A | MTR120 | meter | metering | (620, 225) | 90 | 120 | 0.3 | 0.016 |
| MTR-B | MTR120 | meter | metering | (620, 270) | 90 | 120 | 0.3 | 0.016 |
| REG | REG120 | regulator | pressure_control | (580, 205) | 0 | 120 | 0.34 | 0.018 |
| SEP-A | SEP70 | separator | hydrocarbon_treatment | (290, 70) | 0 | 70 | 0.78 | 0.05 |
| SEP-B | SEP70 | separator | hydrocarbon_treatment | (290, 140) | 0 | 70 | 0.78 | 0.05 |
| SEP-C | SEP70 | separator | hydrocarbon_treatment | (290, 210) | 0 | 70 | 0.78 | 0.05 |

Selection logic:

- Compression: three C60 units (60 kg/s, ratio 2.4, eta 0.80) - the minimum unit count that satisfies compression n-1 for INJ-LOW (2 x 60 = 120 kg/s >= 84 kg/s required). Larger units (C80) reduce specific energy but need the same three instances and a higher-capital driver; smaller units (C40) need four instances and cost more energy. Net LCC is lowest with 3 x C60.
- Aftercooling: one COOL120 (120 kg/s, 32 MW duty) on the common discharge of the compressor bank; required because the compressor discharge temperature reaches 51-95 degC depending on scenario (INJ-LOW 51.2, INJ-MID 74.8, INJ-HIGH 94.8 degC), above the 40 degC aftercooler setpoint and above the 60 degC delivery limit for INJ-MID and INJ-HIGH. No cooler n-1 requirement is published, and the retained flow in the n-1 compressor case (<= 120 kg/s) stays within capacity.
- Withdrawal separation: three SEP70 (70 kg/s, 16 MPa). A 10 MPa separator (SEP120/SEP40) cannot be used because the highest well-group pressure is 12 MPa and reducing it upstream would require an additional high-flow pressure-control station, which costs more than the units it would save; two SEP70 do not satisfy treatment n-1 (70 kg/s < 84 kg/s).
- Dehydration: three DEHY70 (70 kg/s, 16 MPa, outlet 35 mg/Sm3). Two units fail treatment n-1 for WDR-HIGH; the 10 MPa DEHY120 is not pressure-rated for the 12 MPa source pressure.
- Grid metering: two MTR120 in series-free parallel paths - one for injection (GRID-TIE -> station) because a meter is one-way and a second for withdrawal - so that all exchanged gas passes through active meter capacity of 120 kg/s = the largest scenario flow, satisfying the 1.0 capacity fraction requirement.
- Pressure control: one REG120 (120 kg/s, 16 MPa) on the withdrawal path, letting the withdrawal trains deliver at a controlled grid pressure irrespective of well pressure (WDR-HIGH 12 MPa, WDR-MID 8 MPa, WDR-LOW 4.5 MPa). The published sink pressure is a lower limit, so the valve is not needed for feasibility; it is kept as a deliberate, costed design choice (0.34 MBCU capital + 0.018 MBCU/y = 0.52 MBCU lifecycle) because delivering uncontrolled 11.8 MPa well gas into a 6 MPa grid tie is not an acceptable operating philosophy.
- Headers: four HDR120 manifolds (suction, discharge, station/trunk, well manifold) provide the physical branching that the published semantics require. HDR120 has the same 6 x 3 m footprint and 16 MPa rating as the larger HDR180, ten branch ports (the largest demand is the suction header with eight) and a 120 kg/s rating equal to the largest header through-flow in any case; it is the lowest-LCC manifold that meets the branch-count and flow requirements (HDR180 would cut header pressure drop by 0.006 MPa but costs 0.11 MBCU capital and 0.004 MBCU/y more per header).
- Closed drains: three DRN-S (0.8 kg/s each) - one per separator as required by the semantics; the maximum liquid side stream is 0.60 kg/s (60 kg/s gas at 0.01 loading in the separator n-1 case), within capacity. Chaining drains would not reduce instances because each drain has a single inlet, so three discharge lines run to the outfall (3 of the 8 permitted connections, 1.2 kg/s of the 10 kg/s limit).

---

## 3. System architecture and process connections

```
                                wells WG-01..WG-06
                                     |   (6 branches, DN250/300/350)
                                 [H-WELL header]
                                     |   trunk DN600
                                 [H-SITE header] ---------- cooler return (DN600)
                                     |                                 |
          +--------------------------+--------------+            [COOL120]
          |                          |              |                  |
      [SEP-A]                    [SEP-B]        [SEP-C]           [H-DIS header]
          |                          |              |                  |
      [DEH-A]                    [DEH-B]        [DEH-C]       +---+---+---+
          |                          |              |          |   |   |   |
          +-----------+--------------+--------------+----------+   |   |   |
                      |                                            |   |   |
                 [H-SUC header] -------- bypass (DN350) -----------+   |   |
                      |                                                |   |
          +-----------+-----------+                         +----------+   |
          |           |           |                         |   |   |      |
      [CMP-A]     [CMP-B]     [CMP-C]  ------------------- +   |   |      |
                                                               |   |      |
                                              [REG120] --------+   |      |
                                                  |                |      |
                            (withdrawal) [MTR-B] --+                |      |
                                                  |                |      |
                                              GRID-TIE <-----------+------+
                                                  ^
                                                  |  (injection)
                                              [MTR-A] -- [H-SUC header]
```

### 3.1 Physical connections

| Pipeline | From (node.port) | To (node.port) | Service | Function |
|---|---|---|---|---|
| P01 | GRID-TIE.gas | MTR-A.gas_in | gas | injection feed from grid tie |
| P02 | MTR-A.gas_out | H-SUC.branch_05 | gas | metered injection gas to station |
| P33 | MTR-B.gas_out | GRID-TIE.gas | gas | withdrawal gas to grid tie |
| P03 | H-SUC.branch_10 | CMP-A.suction | gas | train A suction |
| P04 | H-SUC.branch_06 | CMP-B.suction | gas | train B suction |
| P05 | H-SUC.branch_02 | CMP-C.suction | gas | train C suction |
| P06 | CMP-A.discharge | H-DIS.branch_10 | gas | train A discharge |
| P07 | CMP-B.discharge | H-DIS.branch_06 | gas | train B discharge |
| P08 | CMP-C.discharge | H-DIS.branch_02 | gas | train C discharge |
| P09 | H-SUC.branch_07 | H-DIS.branch_07 | gas | compressor bank bypass |
| P10 | H-DIS.branch_09 | COOL.gas_in | gas | hot discharge gas to aftercooler |
| P11 | COOL.gas_out | H-SITE.branch_05 | gas | cooled injection gas to station header |
| P12 | H-SITE.branch_04 | H-WELL.branch_06 | gas | main trunk header to well manifold |
| P13 | H-WELL.branch_03 | WG-01.gas | gas | well group 01 branch |
| P14 | H-WELL.branch_07 | WG-02.gas | gas | well group 02 branch |
| P15 | H-WELL.branch_01 | WG-03.gas | gas | well group 03 branch |
| P16 | H-WELL.branch_05 | WG-04.gas | gas | well group 04 branch |
| P17 | H-WELL.branch_09 | WG-05.gas | gas | well group 05 branch |
| P18 | H-WELL.branch_04 | WG-06.gas | gas | well group 06 branch |
| P19 | H-SITE.branch_10 | SEP-A.gas_in | gas | train A feed |
| P20 | H-SITE.branch_06 | SEP-B.gas_in | gas | train B feed |
| P21 | H-SITE.branch_02 | SEP-C.gas_in | gas | train C feed |
| P22 | SEP-A.gas_out | DEH-A.gas_in | gas | train A separated gas to dehydrator |
| P23 | SEP-B.gas_out | DEH-B.gas_in | gas | train B separated gas to dehydrator |
| P24 | SEP-C.gas_out | DEH-C.gas_in | gas | train C separated gas to dehydrator |
| P28 | DEH-A.gas_out | H-SUC.branch_04 | gas | train A dry gas |
| P29 | DEH-B.gas_out | H-SUC.branch_08 | gas | train B dry gas |
| P30 | DEH-C.gas_out | H-SUC.branch_09 | gas | train C dry gas |
| P31 | H-DIS.branch_05 | REG.gas_in | gas | to grid pressure control |
| P32 | REG.gas_out | MTR-B.gas_in | gas | controlled gas to grid meter |
| P34 | SEP-A.liquid_out | DRN-A.drain_in | liquid | train A drain |
| P35 | SEP-B.liquid_out | DRN-B.drain_in | liquid | train B drain |
| P36 | SEP-C.liquid_out | DRN-C.drain_in | liquid | train C drain |
| P37 | DRN-A.drain_out | LIQUID-DRAIN-OUTFALL.drain | liquid | drain discharge line A |
| P38 | DRN-B.drain_out | LIQUID-DRAIN-OUTFALL.drain | liquid | drain discharge line B |
| P39 | DRN-C.drain_out | LIQUID-DRAIN-OUTFALL.drain | liquid | drain discharge line C |

Every equipment port carries at most one physical connection, the external interfaces use only their published connection allowance (GRID-TIE 2 of 2, LIQUID-DRAIN-OUTFALL 3 of 8, well groups 1 each), and all process branching or merging is performed by catalogued header ports. Each separator liquid outlet is connected to its own closed drain, and the drains discharge to the public liquid-drain outfall.

Flow directions: the injection path uses `gas_in`/`gas_out` ports of MTR-A and the compressors; the withdrawal path uses MTR-B, the pressure-control valve and the same compressor bank (or the parallel bypass). `gas_out` ports are never reversed; reverse service uses the dedicated withdrawal path.

---

## 4. Operating philosophy and scenario results

Normal operation (all six scenarios) uses:

- injection: GRID-TIE -> injection meter -> suction header -> 3 compressors (equal flow split) -> discharge header -> aftercooler -> station header -> trunk -> well manifold -> 6 well-group branches;
- withdrawal: well groups -> well manifold -> trunk -> station header -> 3 separator/dehydrator trains -> suction header -> compressors (only when the well pressure is below the grid requirement, i.e. WDR-LOW) or the compressor bypass -> discharge header -> pressure-control valve -> withdrawal meter -> GRID-TIE.

| Scenario | Compressor discharge (MPa) | Suction P (MPa) | Ratio | Discharge T (degC) | Sink P (MPa) | Sink T (degC) | Sink water | Sink free liquid | Energy (MWh/y) |
|---|---|---|---|---|---|---|---|---|---|
| INJ-LOW | 8.654 | 6.450 | 1.342 | 51.15 | 8.550 | 40.00 | 40.00 | 0.00e+00 | 7307.6 |
| INJ-MID | 11.127 | 6.459 | 1.723 | 74.84 | 11.050 | 40.00 | 40.00 | 0.00e+00 | 16920.2 |
| INJ-HIGH | 13.607 | 6.468 | 2.104 | 94.77 | 13.550 | 40.00 | 40.00 | 0.00e+00 | 8223.9 |
| WDR-HIGH | n/a (bypass) | n/a | n/a | n/a | 6.090 | 13.36 | 35.00 | 5.00e-06 | 1080.0 |
| WDR-MID | n/a (bypass) | n/a | n/a | n/a | 6.117 | 18.15 | 35.00 | 5.00e-06 | 1620.0 |
| WDR-LOW | 6.300 | 4.350 | 1.448 | 52.71 | 6.145 | 52.61 | 35.00 | 5.00e-06 | 5681.0 |

Setpoints: aftercooler outlet 40 degC (all injection scenarios, >= the catalogue minimum of 35 degC); grid pressure-control setpoint 6.20 MPa (all withdrawal scenarios); compressor discharge pressure per scenario as tabulated. Injection discharge pressures are set to give 0.05 MPa margin above the required well-group pressure; with a 0.05 MPa margin the worst-delivered well group is exactly at the required pressure +0.05 MPa.

### 4.1 Per-scenario pressure profile (selected)

**INJ-LOW** (flow 120 kg/s):

| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |
|---|---|---|---|---|---|
| P01 | 120 | 6.500 | 6.496 | 25 | 0.0039 |
| P02 | 120 | 6.476 | 6.464 | 25 | 0.0118 |
| P03 | 40.00 | 6.454 | 6.450 | 25 | 0.0039 |
| P06 | 40.00 | 8.654 | 8.644 | 51.15 | 0.0095 |
| P04 | 40.00 | 6.454 | 6.453 | 25 | 0.0014 |
| P07 | 40.00 | 8.654 | 8.646 | 51.12 | 0.0080 |
| P05 | 40.00 | 6.454 | 6.450 | 25 | 0.0039 |
| P08 | 40.00 | 8.654 | 8.648 | 51.15 | 0.0060 |
| P10 | 120 | 8.634 | 8.633 | 51.14 | 0.0018 |
| P11 | 120 | 8.598 | 8.586 | 40.00 | 0.0116 |
| P12 | 120 | 8.576 | 8.569 | 40.00 | 0.0073 |
| P13 | 20.00 | 8.559 | 8.551 | 40.00 | 0.0081 |
| P14 | 20.00 | 8.559 | 8.554 | 40.00 | 0.0053 |
| P15 | 20.00 | 8.559 | 8.551 | 40.00 | 0.0082 |
| P16 | 20.00 | 8.559 | 8.553 | 40.00 | 0.0060 |
| P17 | 20.00 | 8.559 | 8.550 | 40.00 | 0.0088 |
| P18 | 20.00 | 8.559 | 8.554 | 40.00 | 0.0052 |
| MTR-A | 120 | 6.496 | 6.476 | 25 | 0.0200 |
| H-SUC | 120 | 6.464 | 6.454 | 25 | 0.0100 |
| CMP-A | 40.00 | 6.450 | 8.654 | 25 | - |
| CMP-B | 40.00 | 6.453 | 8.654 | 25 | - |
| CMP-C | 40.00 | 6.450 | 8.654 | 25 | - |
| H-DIS | 120 | 8.644 | 8.634 | 51.14 | 0.0100 |
| COOL | 120 | 8.633 | 8.598 | 51.14 | 0.0350 |
| H-SITE | 120 | 8.586 | 8.576 | 40.00 | 0.0100 |
| H-WELL | 120 | 8.569 | 8.559 | 40.00 | 0.0100 |

**INJ-MID** (flow 100 kg/s):

| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |
|---|---|---|---|---|---|
| P01 | 100 | 6.500 | 6.497 | 25 | 0.0027 |
| P02 | 100 | 6.477 | 6.469 | 25 | 0.0082 |
| P03 | 33.33 | 6.462 | 6.459 | 25 | 0.0027 |
| P06 | 33.33 | 11.127 | 11.122 | 74.84 | 0.0056 |
| P04 | 33.33 | 6.462 | 6.461 | 25 | 0.0010 |
| P07 | 33.33 | 11.127 | 11.123 | 74.81 | 0.0047 |
| P05 | 33.33 | 6.462 | 6.459 | 25 | 0.0027 |
| P08 | 33.33 | 11.127 | 11.124 | 74.84 | 0.0035 |
| P10 | 100 | 11.115 | 11.114 | 74.83 | 0.0010 |
| P11 | 100 | 11.079 | 11.073 | 40.00 | 0.0063 |
| P12 | 100 | 11.066 | 11.062 | 40.00 | 0.0039 |
| P13 | 16.67 | 11.055 | 11.050 | 40.00 | 0.0044 |
| P14 | 16.67 | 11.055 | 11.052 | 40.00 | 0.0028 |
| P15 | 16.67 | 11.055 | 11.050 | 40.00 | 0.0044 |
| P16 | 16.67 | 11.055 | 11.052 | 40.00 | 0.0032 |
| P17 | 16.67 | 11.055 | 11.050 | 40.00 | 0.0048 |
| P18 | 16.67 | 11.055 | 11.052 | 40.00 | 0.0028 |
| MTR-A | 100 | 6.497 | 6.477 | 25 | 0.0200 |
| H-SUC | 100 | 6.469 | 6.462 | 25 | 0.0069 |
| CMP-A | 33.33 | 6.459 | 11.127 | 25 | - |
| CMP-B | 33.33 | 6.461 | 11.127 | 25 | - |
| CMP-C | 33.33 | 6.459 | 11.127 | 25 | - |
| H-DIS | 100 | 11.122 | 11.115 | 74.83 | 0.0069 |
| COOL | 100 | 11.114 | 11.079 | 74.83 | 0.0350 |
| H-SITE | 100 | 11.073 | 11.066 | 40.00 | 0.0069 |
| H-WELL | 100 | 11.062 | 11.055 | 40.00 | 0.0069 |

**INJ-HIGH** (flow 75 kg/s):

| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |
|---|---|---|---|---|---|
| P01 | 75 | 6.500 | 6.498 | 25 | 0.0016 |
| P02 | 75 | 6.478 | 6.474 | 25 | 0.0046 |
| P03 | 25.00 | 6.470 | 6.468 | 25 | 0.0015 |
| P06 | 25.00 | 13.607 | 13.604 | 94.77 | 0.0028 |
| P04 | 25.00 | 6.470 | 6.469 | 25 | 0.0006 |
| P07 | 25.00 | 13.607 | 13.605 | 94.76 | 0.0023 |
| P05 | 25.00 | 6.470 | 6.468 | 25 | 0.0015 |
| P08 | 25.00 | 13.607 | 13.605 | 94.77 | 0.0017 |
| P10 | 75 | 13.600 | 13.600 | 94.77 | 0.0005 |
| P11 | 75 | 13.565 | 13.562 | 40.00 | 0.0029 |
| P12 | 75 | 13.558 | 13.556 | 40.00 | 0.0018 |
| P13 | 12.50 | 13.552 | 13.550 | 40.00 | 0.0020 |
| P14 | 12.50 | 13.552 | 13.551 | 40.00 | 0.0013 |
| P15 | 12.50 | 13.552 | 13.550 | 40.00 | 0.0020 |
| P16 | 12.50 | 13.552 | 13.551 | 40.00 | 0.0015 |
| P17 | 12.50 | 13.552 | 13.550 | 40.00 | 0.0022 |
| P18 | 12.50 | 13.552 | 13.551 | 40.00 | 0.0013 |
| MTR-A | 75 | 6.498 | 6.478 | 25 | 0.0200 |
| H-SUC | 75 | 6.474 | 6.470 | 25 | 0.0039 |
| CMP-A | 25.00 | 6.468 | 13.607 | 25 | - |
| CMP-B | 25.00 | 6.469 | 13.607 | 25 | - |
| CMP-C | 25.00 | 6.468 | 13.607 | 25 | - |
| H-DIS | 75 | 13.604 | 13.600 | 94.77 | 0.0039 |
| COOL | 75 | 13.600 | 13.565 | 94.77 | 0.0350 |
| H-SITE | 75 | 13.562 | 13.558 | 40.00 | 0.0039 |
| H-WELL | 75 | 13.556 | 13.552 | 40.00 | 0.0039 |

**WDR-HIGH** (flow 120 kg/s):

| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |
|---|---|---|---|---|---|
| P13 | 20.00 | 12.000 | 11.995 | 20 | 0.0054 |
| P14 | 20.00 | 12.000 | 11.996 | 20 | 0.0035 |
| P15 | 20.00 | 12.000 | 11.995 | 20 | 0.0055 |
| P16 | 20.00 | 12.000 | 11.996 | 20 | 0.0040 |
| P17 | 20.00 | 12.000 | 11.994 | 20 | 0.0059 |
| P18 | 20.00 | 12.000 | 11.997 | 20 | 0.0035 |
| P12 | 120 | 11.984 | 11.979 | 20.00 | 0.0049 |
| P19 | 40.00 | 11.969 | 11.959 | 20.00 | 0.0104 |
| P22 | 40.00 | 11.929 | 11.923 | 20.00 | 0.0060 |
| P28 | 40.00 | 11.843 | 11.839 | 20.00 | 0.0043 |
| P20 | 40.00 | 11.969 | 11.961 | 20.00 | 0.0086 |
| P23 | 40.00 | 11.931 | 11.922 | 20.00 | 0.0083 |
| P29 | 40.00 | 11.842 | 11.839 | 20.00 | 0.0036 |
| P21 | 40.00 | 11.969 | 11.959 | 20.00 | 0.0104 |
| P24 | 40.00 | 11.929 | 11.925 | 20.00 | 0.0037 |
| P30 | 40.00 | 11.845 | 11.841 | 20.00 | 0.0044 |
| P09 | 120 | 11.829 | 11.776 | 20.00 | 0.0530 |
| P31 | 120 | 11.766 | 11.733 | 20.00 | 0.0328 |
| P32 | 120 | 6.200 | 6.168 | 13.36 | 0.0315 |
| P33 | 120 | 6.148 | 6.090 | 13.36 | 0.0580 |
| H-WELL | 120 | 11.994 | 11.984 | 20.00 | 0.0100 |
| H-SITE | 120 | 11.979 | 11.969 | 20.00 | 0.0100 |
| SEP-A | 40.00 | 11.959 | 11.929 | 20.00 | 0.0300 |
| DEH-A | 40.00 | 11.923 | 11.843 | 20.00 | 0.0800 |
| SEP-B | 40.00 | 11.961 | 11.931 | 20.00 | 0.0300 |
| DEH-B | 40.00 | 11.922 | 11.842 | 20.00 | 0.0800 |
| SEP-C | 40.00 | 11.959 | 11.929 | 20.00 | 0.0300 |
| DEH-C | 40.00 | 11.925 | 11.845 | 20.00 | 0.0800 |
| H-SUC | 120 | 11.839 | 11.829 | 20.00 | 0.0100 |
| H-DIS | 120 | 11.776 | 11.766 | 20.00 | 0.0100 |
| REG | 120 | 11.733 | 6.200 | 20.00 | - |
| MTR-B | 120 | 6.168 | 6.148 | 13.36 | 0.0200 |

**WDR-MID** (flow 100 kg/s):

| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |
|---|---|---|---|---|---|
| P13 | 16.67 | 8.000 | 7.994 | 20 | 0.0056 |
| P14 | 16.67 | 8.000 | 7.996 | 20 | 0.0036 |
| P15 | 16.67 | 8.000 | 7.994 | 20 | 0.0057 |
| P16 | 16.67 | 8.000 | 7.996 | 20 | 0.0042 |
| P17 | 16.67 | 8.000 | 7.994 | 20 | 0.0061 |
| P18 | 16.67 | 8.000 | 7.996 | 20 | 0.0036 |
| P12 | 100 | 7.987 | 7.982 | 20.00 | 0.0050 |
| P19 | 33.33 | 7.975 | 7.964 | 20.00 | 0.0107 |
| P22 | 33.33 | 7.934 | 7.928 | 20.00 | 0.0062 |
| P28 | 33.33 | 7.848 | 7.844 | 20.00 | 0.0044 |
| P20 | 33.33 | 7.975 | 7.966 | 20.00 | 0.0089 |
| P23 | 33.33 | 7.936 | 7.927 | 20.00 | 0.0086 |
| P29 | 33.33 | 7.847 | 7.844 | 20.00 | 0.0038 |
| P21 | 33.33 | 7.975 | 7.964 | 20.00 | 0.0107 |
| P24 | 33.33 | 7.934 | 7.930 | 20.00 | 0.0039 |
| P30 | 33.33 | 7.850 | 7.846 | 20.00 | 0.0046 |
| P09 | 100 | 7.837 | 7.781 | 20.00 | 0.0553 |
| P31 | 100 | 7.774 | 7.740 | 20.00 | 0.0342 |
| P32 | 100 | 6.200 | 6.178 | 18.15 | 0.0223 |
| P33 | 100 | 6.158 | 6.117 | 18.15 | 0.0410 |
| H-WELL | 100 | 7.994 | 7.987 | 20.00 | 0.0069 |
| H-SITE | 100 | 7.982 | 7.975 | 20.00 | 0.0069 |
| SEP-A | 33.33 | 7.964 | 7.934 | 20.00 | 0.0300 |
| DEH-A | 33.33 | 7.928 | 7.848 | 20.00 | 0.0800 |
| SEP-B | 33.33 | 7.966 | 7.936 | 20.00 | 0.0300 |
| DEH-B | 33.33 | 7.927 | 7.847 | 20.00 | 0.0800 |
| SEP-C | 33.33 | 7.964 | 7.934 | 20.00 | 0.0300 |
| DEH-C | 33.33 | 7.930 | 7.850 | 20.00 | 0.0800 |
| H-SUC | 100 | 7.844 | 7.837 | 20.00 | 0.0069 |
| H-DIS | 100 | 7.781 | 7.774 | 20.00 | 0.0069 |
| REG | 100 | 7.740 | 6.200 | 20.00 | - |
| MTR-B | 100 | 6.178 | 6.158 | 18.15 | 0.0200 |

**WDR-LOW** (flow 70 kg/s):

| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |
|---|---|---|---|---|---|
| P13 | 11.67 | 4.500 | 4.495 | 20 | 0.0049 |
| P14 | 11.67 | 4.500 | 4.497 | 20 | 0.0032 |
| P15 | 11.67 | 4.500 | 4.495 | 20 | 0.0049 |
| P16 | 11.67 | 4.500 | 4.496 | 20 | 0.0036 |
| P17 | 11.67 | 4.500 | 4.495 | 20 | 0.0053 |
| P18 | 11.67 | 4.500 | 4.497 | 20 | 0.0031 |
| P12 | 70 | 4.491 | 4.487 | 20.00 | 0.0044 |
| P19 | 23.33 | 4.484 | 4.474 | 20.00 | 0.0093 |
| P22 | 23.33 | 4.444 | 4.439 | 20.00 | 0.0054 |
| P28 | 23.33 | 4.359 | 4.355 | 20.00 | 0.0039 |
| P20 | 23.33 | 4.484 | 4.476 | 20.00 | 0.0077 |
| P23 | 23.33 | 4.446 | 4.438 | 20.00 | 0.0074 |
| P29 | 23.33 | 4.358 | 4.355 | 20.00 | 0.0033 |
| P21 | 23.33 | 4.484 | 4.474 | 20.00 | 0.0093 |
| P24 | 23.33 | 4.444 | 4.441 | 20.00 | 0.0033 |
| P30 | 23.33 | 4.361 | 4.357 | 20.00 | 0.0041 |
| P03 | 23.33 | 4.352 | 4.350 | 20.00 | 0.0019 |
| P06 | 23.33 | 6.300 | 6.296 | 52.71 | 0.0045 |
| P04 | 23.33 | 4.352 | 4.351 | 20.00 | 0.0007 |
| P07 | 23.33 | 6.300 | 6.296 | 52.68 | 0.0038 |
| P05 | 23.33 | 4.352 | 4.350 | 20.00 | 0.0019 |
| P08 | 23.33 | 6.300 | 6.297 | 52.71 | 0.0028 |
| P31 | 70 | 6.292 | 6.269 | 52.70 | 0.0232 |
| P32 | 70 | 6.200 | 6.188 | 52.61 | 0.0124 |
| P33 | 70 | 6.168 | 6.145 | 52.61 | 0.0227 |
| H-WELL | 70 | 4.495 | 4.491 | 20.00 | 0.0034 |
| H-SITE | 70 | 4.487 | 4.484 | 20.00 | 0.0034 |
| SEP-A | 23.33 | 4.474 | 4.444 | 20.00 | 0.0300 |
| DEH-A | 23.33 | 4.439 | 4.359 | 20.00 | 0.0800 |
| SEP-B | 23.33 | 4.476 | 4.446 | 20.00 | 0.0300 |
| DEH-B | 23.33 | 4.438 | 4.358 | 20.00 | 0.0800 |
| SEP-C | 23.33 | 4.474 | 4.444 | 20.00 | 0.0300 |
| DEH-C | 23.33 | 4.441 | 4.361 | 20.00 | 0.0800 |
| H-SUC | 70 | 4.355 | 4.352 | 20.00 | 0.0034 |
| CMP-A | 23.33 | 4.350 | 6.300 | 20.00 | - |
| CMP-B | 23.33 | 4.351 | 6.300 | 20.00 | - |
| CMP-C | 23.33 | 4.350 | 6.300 | 20.00 | - |
| H-DIS | 70 | 6.296 | 6.292 | 52.70 | 0.0034 |
| REG | 70 | 6.269 | 6.200 | 52.70 | - |
| MTR-B | 70 | 6.188 | 6.168 | 52.61 | 0.0200 |

### 4.2 Contingency (n-1) cases

| Case | Outage | Delivered flow kg/s | Retained fraction | Required | Feasible | Violations |
|---|---|---|---|---|---|---|
| INJ-LOW-N1-CMP-A | compressor #0 | 120 | 1.000 | 0.7 | yes | 0 |
| INJ-LOW-N1-CMP-B | compressor #1 | 120 | 1.000 | 0.7 | yes | 0 |
| INJ-LOW-N1-CMP-C | compressor #2 | 120 | 1.000 | 0.7 | yes | 0 |
| INJ-MID-N1-CMP-A | compressor #0 | 100 | 1.000 | 0.7 | yes | 0 |
| INJ-MID-N1-CMP-B | compressor #1 | 100 | 1.000 | 0.7 | yes | 0 |
| INJ-MID-N1-CMP-C | compressor #2 | 100 | 1.000 | 0.7 | yes | 0 |
| INJ-HIGH-N1-CMP-A | compressor #0 | 75 | 1.000 | 0.7 | yes | 0 |
| INJ-HIGH-N1-CMP-B | compressor #1 | 75 | 1.000 | 0.7 | yes | 0 |
| INJ-HIGH-N1-CMP-C | compressor #2 | 75 | 1.000 | 0.7 | yes | 0 |
| WDR-HIGH-N1-SEP-A | separator #0 | 120 | 1.000 | 0.7 | yes | 0 |
| WDR-HIGH-N1-SEP-B | separator #1 | 120 | 1.000 | 0.7 | yes | 0 |
| WDR-HIGH-N1-SEP-C | separator #2 | 120 | 1.000 | 0.7 | yes | 0 |
| WDR-HIGH-N1-DEH-A | dehydration #0 | 120 | 1.000 | 0.7 | yes | 0 |
| WDR-HIGH-N1-DEH-B | dehydration #1 | 120 | 1.000 | 0.7 | yes | 0 |
| WDR-HIGH-N1-DEH-C | dehydration #2 | 120 | 1.000 | 0.7 | yes | 0 |
| WDR-MID-N1-SEP-A | separator #0 | 100 | 1.000 | 0.7 | yes | 0 |
| WDR-MID-N1-SEP-B | separator #1 | 100 | 1.000 | 0.7 | yes | 0 |
| WDR-MID-N1-SEP-C | separator #2 | 100 | 1.000 | 0.7 | yes | 0 |
| WDR-MID-N1-DEH-A | dehydration #0 | 100 | 1.000 | 0.7 | yes | 0 |
| WDR-MID-N1-DEH-B | dehydration #1 | 100 | 1.000 | 0.7 | yes | 0 |
| WDR-MID-N1-DEH-C | dehydration #2 | 100 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-CMP-A | compressor #0 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-CMP-B | compressor #1 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-CMP-C | compressor #2 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-SEP-A | separator #0 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-SEP-B | separator #1 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-SEP-C | separator #2 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-DEH-A | dehydration #0 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-DEH-B | dehydration #1 | 70 | 1.000 | 0.7 | yes | 0 |
| WDR-LOW-N1-DEH-C | dehydration #2 | 70 | 1.000 | 0.7 | yes | 0 |

All contingency cases are feasible with zero rule violations, and in every case the full scenario flow (100 %) can be retained, which exceeds the 70 % requirement. Each contingency case is recorded with its full operating path, setpoints and per-element states in `operating_plan.json`.

Liquid side streams and drain velocities (the benchmark publishes no liquid density, so the band below spans water to a deliberately pessimistic gas-density-like fluid at the closed-drain pressure):


| Pipeline | DN | Design liquid flow (kg/s) | v at 1000 | v at 800 | v at 500 | v at 100 | v at 8.2 kg/m3 | Limit |
|---|---|---|---|---|---|---|---|---|
| P34 | DN200 | 0.5997 | 0.0216 | 0.027 | 0.0432 | 0.216 | 2.6346 | 3.0 m/s |
| P35 | DN200 | 0.5997 | 0.0216 | 0.027 | 0.0432 | 0.216 | 2.6346 | 3.0 m/s |
| P36 | DN200 | 0.5997 | 0.0216 | 0.027 | 0.0432 | 0.216 | 2.6346 | 3.0 m/s |
| P37 | DN200 | 0.5997 | 0.0216 | 0.027 | 0.0432 | 0.216 | 2.6346 | 3.0 m/s |
| P38 | DN200 | 0.5997 | 0.0216 | 0.027 | 0.0432 | 0.216 | 2.6346 | 3.0 m/s |
| P39 | DN200 | 0.5997 | 0.0216 | 0.027 | 0.0432 | 0.216 | 2.6346 | 3.0 m/s |

The maximum separator liquid side stream is 0.60 kg/s (separator n-1 case); each drain is rated 0.8 kg/s and the combined flow to the outfall is 1.20 kg/s of the 10 kg/s limit, using 3 of the 8 permitted outfall connections.

---

## 5. Site layout, safety and maintenance access

### 5.1 Arrangement

- The site is used west to east: well manifold and trunk in the west, the three separator/dehydrator trains in three horizontal lanes at y = 70, 140 and 210 m, the compressor bank east of the trains, the aftercooler in the north band, and metering and grid tie on the east boundary.
- The well manifold sits close to the well-group interface line (x = 90 m), keeping the six well branches short and their pressure losses balanced.
- The main access road runs from the ROAD-ENTRANCE (0, 225) east to x = 560 m; a crane-access spur at x = 505 m serves the compressor removal envelopes (2.5 m clearance, limit 4.5 m) and a second spur at x = 302 m serves the separator maintenance envelopes (3 m clearance, limit 7 m).
- Equipment is kept out of the FUTURE-EXPANSION, DRAINAGE-CHANNEL and GRID-FACILITY no-build zones; pipelines avoid the two pipeline-exclusion zones; roads avoid all road-exclusion zones.
- The compressor bank is arranged as a north-south column with all heavy-maintenance removal envelopes facing the crane road, so lifting equipment out never crosses another footprint.
- The liquid-drain outfall is approached by the three drain discharge lines from three different directions (from the west, from the north and from the south), which keeps them free of same-level overlaps.

### 5.2 Safety separation

Minimum separation distances are taken from `safety_requirements.json` and are measured boundary-to-boundary between rotated footprints. The design satisfies every pair (worst achieved vs required):


| Pair | Achieved (m) | Required (m) |
|---|---|---|
| DRN-A - SEP-A | 13.00 | 8 |
| DRN-B - SEP-B | 13.00 | 8 |
| DRN-C - SEP-C | 13.00 | 8 |
| COOL - REG | 16.32 | 6 |
| DRN-B - H-SITE | 28.85 | 8 |
| H-SITE - SEP-B | 33.00 | 5 |
| CMP-B - H-SUC | 39.50 | 10 |

### 5.3 Maintenance envelopes, roads and access

Routine clearance envelopes (catalogue `clearance_m`) plus the heavy-maintenance removal envelopes of the three compressors (12.0 m x 6.4 m, east side) are kept inside the site, outside equipment-exclusion zones and clear of all other equipment footprints. Road access and crane access distances:


| Instance | Road access required | Crane access required | Distance to paved road (m) | Road limit (m) | Crane limit (m) |
|---|---|---|---|---|---|
| CMP-A | yes | yes | 2.50 | 7.0 | 4.5 |
| CMP-B | yes | yes | 2.50 | 7.0 | 4.5 |
| CMP-C | yes | yes | 2.50 | 7.0 | 4.5 |
| SEP-A | yes | no | 3.00 | 7.0 | - |
| SEP-B | yes | no | 3.00 | 7.0 | - |
| SEP-C | yes | no | 3.00 | 7.0 | - |

| Road | Width (m) | Centreline length (m) |
|---|---|---|
| RD-CRANE | 6.0 | 175.0 |
| RD-MAIN | 8.0 | 556.0 |
| RD-SEP | 6.0 | 175.0 |

The road network is connected and contains the ROAD-ENTRANCE point; its paved geometry stays inside the site, out of road-exclusion zone interiors and clear of all equipment footprints.

---

## 6. Piping and network definition

| Pipeline | DN | ID (m) | Class | Level | Length (m) | Max velocity (m/s) | Installed capex (MBCU) |
|---|---|---|---|---|---|---|---|
| P01 | DN600 | 0.564 | CS-DRY-160 | ground | 101.0 | 9.39 | 0.0633 |
| P02 | DN600 | 0.564 | CS-DRY-160 | ground | 301.5 | 9.43 | 0.1902 |
| P03 | DN400 | 0.376 | CS-DRY-160 | ground | 108.5 | 10.64 | 0.0393 |
| P04 | DN400 | 0.376 | CS-DRY-160 | ground | 39.5 | 10.63 | 0.0143 |
| P05 | DN400 | 0.376 | CS-DRY-160 | ground | 108.5 | 10.64 | 0.0393 |
| P06 | DN350 | 0.329 | CS-DRY-160 | ground | 163.5 | 11.40 | 0.0493 |
| P07 | DN350 | 0.329 | CS-DRY-160 | ground | 138.5 | 11.39 | 0.0419 |
| P08 | DN400 | 0.376 | CS-DRY-160 | ground | 203.5 | 8.72 | 0.0743 |
| P09 | DN350 | 0.329 | CS-DRY-160 | ground | 156.0 | 18.99 | 0.0471 |
| P10 | DN600 | 0.564 | CS-DRY-160 | ground | 55.5 | 7.77 | 0.0348 |
| P11 | DN600 | 0.564 | CS-DRY-160 | ground | 372.5 | 7.52 | 0.2353 |
| P12 | DN600 | 0.564 | CS-WET-160 | ground | 194.8 | 7.73 | 0.1252 |
| P13 | DN300 | 0.282 | CS-WET-160 | ground | 213.0 | 5.15 | 0.0528 |
| P14 | DN300 | 0.282 | CS-WET-160 | ground | 138.0 | 5.14 | 0.0342 |
| P15 | DN250 | 0.235 | CS-WET-160 | ground | 83.5 | 7.41 | 0.0163 |
| P16 | DN300 | 0.282 | CS-WET-160 | ground | 157.5 | 5.15 | 0.0395 |
| P17 | DN300 | 0.282 | CS-WET-160 | ground | 231.5 | 5.15 | 0.0579 |
| P18 | DN350 | 0.329 | CS-WET-160 | ground | 300.8 | 3.78 | 0.0929 |
| P19 | DN300 | 0.282 | CS-WET-160 | ground | 102.0 | 15.55 | 0.0253 |
| P20 | DN250 | 0.235 | CS-WET-160 | ground | 33.0 | 22.37 | 0.0064 |
| P21 | DN300 | 0.282 | CS-WET-160 | ground | 102.0 | 15.55 | 0.0253 |
| P22 | DN350 | 0.329 | CS-WET-160 | ground | 131.0 | 11.53 | 0.0407 |
| P23 | DN300 | 0.282 | CS-WET-160 | ground | 81.0 | 15.70 | 0.0204 |
| P24 | DN350 | 0.329 | CS-WET-160 | ground | 81.0 | 11.52 | 0.0253 |
| P28 | DN350 | 0.329 | CS-DRY-160 | ground | 111.2 | 11.76 | 0.0333 |
| P29 | DN300 | 0.282 | CS-DRY-160 | ground | 42.8 | 16.01 | 0.0103 |
| P30 | DN350 | 0.329 | CS-DRY-160 | ground | 115.5 | 11.75 | 0.0345 |
| P31 | DN350 | 0.329 | CS-DRY-160 | ground | 96.0 | 19.09 | 0.0287 |
| P32 | DN400 | 0.376 | CS-DRY-160 | ground | 100.5 | 21.32 | 0.0364 |
| P33 | DN400 | 0.376 | CS-DRY-160 | ground | 183.0 | 21.59 | 0.0663 |
| P34 | DN200 | 0.188 | CS-WET-100 | buried | 32.0 | 0.00 | 0.0050 |
| P35 | DN200 | 0.188 | CS-WET-100 | buried | 32.0 | 0.00 | 0.0050 |
| P36 | DN200 | 0.188 | CS-WET-100 | buried | 32.0 | 0.00 | 0.0050 |
| P37 | DN200 | 0.188 | CS-WET-100 | buried | 464.0 | 0.00 | 0.0725 |
| P38 | DN200 | 0.188 | CS-WET-100 | buried | 484.0 | 0.00 | 0.0756 |
| P39 | DN200 | 0.188 | CS-WET-100 | buried | 554.0 | 0.00 | 0.0866 |

Class selection: all gas services use CS-WET-160 where the stream can be wet (well branches, trunk, station header, separator/dehydrator trains up to the dehydration outlet) and CS-DRY-160 on the dry sections (grid tie, metering, compressor bank, aftercooler, dehydrator outlet, pressure control); all gas classes are both wet- and dry-compatible, so no scenario can violate compatibility. Drain services use CS-WET-100 (liquid-drain compatible, 10 MPa) well above the 1 MPa closed-drain domain. Velocity limits (25 m/s gas, 3 m/s liquid) are met in every operating and contingency case, including the highest-flow cases (the worst gas velocity in the whole case set is 22.4 m/s).

Installation levels: process and metering piping is at grade (`ground`, 4160.5 m); drain pipelines and the lengths that cross paved roads are `buried` (1684.0 m, 54 segments). No two segments of the same installation level overlap for a positive length anywhere in the design (verified), and no segment enters a pipeline-exclusion zone, crosses an equipment footprint interior or leaves the site.

---

## 7. Quantities and lifecycle cost

### 7.1 Quantities

| Item | Value |
|---|---|
| Equipment instances | C60 x3, COOL120 x1, DEHY70 x3, DRN-S x3, HDR120 x4, MTR120 x2, REG120 x1, SEP70 x3 |
| Total pipeline length | 5844.5 m |
| Road centreline length | 906.0 m |
| Equipment foundation area | 793.0 m2 |
| Required maintenance area | 1602.4 m2 |
| Annual energy | 40832.6 MWh/y |
| Annual maintenance | 1.0750 MBCU/y |

### 7.2 Lifecycle cost

Present-value factor: PVF = (1-(1+i)^-N)/i with i = 0.08 and N = 20 years = 9.818147. Energy tariff 0.00012 MBCU/MWh.

| Component | MBCU |
|---|---|
| Equipment CAPEX | 30.4900 |
| Piping CAPEX | 1.8505 |
| Civil / access CAPEX | 0.1710 |
| Energy present value | 48.1081 |
| Maintenance present value | 10.5545 |
| **LCC total** | **91.1741** |

Civil / access breakdown: roads 0.1359, foundations 0.0032, maintenance areas 0.0016, pipeline civil 0.0303 MBCU.

Energy by scenario (MWh/y): INJ-LOW 7308, INJ-MID 16920, INJ-HIGH 8224, WDR-HIGH 1080, WDR-MID 1620, WDR-LOW 5681.

---

## 8. Verification

Automated checks were run over 6 mandatory scenarios and 30 contingency cases; the geometry/topology rule set was evaluated over 20 equipment instances, 3 roads and 36 pipelines (157 routed segments, including 54 buried segments and road crossings).

Total individual checks performed: 12158; total failures: 0. Per-rule records with the number of checks performed and the failure count are in `verification.json`:


| Rule | Checks | Failures | Result |
|---|---|---|---|
| Equipment footprints inside the site boundary | 20 | 0 | PASS |
| Equipment footprints clear of equipment-exclusion zones | 60 | 0 | PASS |
| No positive-area overlap between equipment footprints | 190 | 0 | PASS |
| Safety separation matrix for every category pair | 190 | 0 | PASS |
| Maintenance envelopes inside site / zones / clear of footprints | 23 | 0 | PASS |
| Road definition (width >= 4 m), paved geometry and connectivity | 6 | 0 | PASS |
| Road-access and crane-access distances | 6 | 0 | PASS |
| Pipeline segments: site, pipeline-exclusion zones, footprint interiors | 157 | 0 | PASS |
| No positive-length same-level pipeline overlap | 6684 | 0 | PASS |
| Port cardinality, interface limits and port-type compatibility | 105 | 0 | PASS |
| Separator/filter liquid outlets connected to closed drains | 3 | 0 | PASS |
| Equipment capacity limits (flow <= capacity) | 378 | 0 | PASS |
| Equipment pressure limits | 378 | 0 | PASS |
| Compressor ratio / discharge pressure / suction limits | 54 | 0 | PASS |
| Compressor temperature and minimum stable flow | 54 | 0 | PASS |
| Compressor driver power limits | 54 | 0 | PASS |
| Cooler duty and outlet temperature limits | 12 | 0 | PASS |
| Separator/filter liquid rate and feed loading limits | 54 | 0 | PASS |
| Dehydrator feed loading limits | 54 | 0 | PASS |
| Pipe class pressure rating in each operating case | 656 | 0 | PASS |
| Pipe class temperature limits in each operating case | 656 | 0 | PASS |
| Pipe class wet/dry eligibility in each operating case | 656 | 0 | PASS |
| Gas velocity limit (25 m/s) | 656 | 0 | PASS |
| Pressure-loss convergence (8 updates) | 656 | 0 | PASS |
| Delivery quality limits (water, free liquid) at every sink | 96 | 0 | PASS |
| Delivery temperature limits at every sink | 96 | 0 | PASS |
| Required sink pressure at every sink | 96 | 0 | PASS |
| Well-group boundary flow limits | 72 | 0 | PASS |
| GRID-TIE metering capacity at full scenario flow | 36 | 0 | PASS |

Liquid-drain class and velocity checks are reported in section 4.2 (the benchmark publishes no liquid density, so the velocity is bounded by an assumed density band rather than a single value). Total reported violations: 0. Machine-readable evidence is in `verification.json`, `case_summary.json` and the per-case element states in `operating_plan.json`.

---

## 9. Known limitations

- Steady-state only: no transient, surge, blowdown or start-up case is modelled; the benchmark does not publish transient criteria.
- The benchmark's simplified gas-property and equipment models are used as published; no detailed thermodynamics, hydrate or phase-envelope analysis is included, and the case explicitly excludes condensation and vaporisation.
- Dehydration water removal, regeneration, and water disposal are outside the modelled process, as stated in the published semantics.
- The closed-drain pressure letdown is treated as integral to the separator liquid outlet per the published semantics; no letdown valve, flashing or control valve sizing is presented.
- Metering is represented by catalogue capacity and pressure-drop models only: no uncertainty, proving, calibration or fiscal-metering standard is addressed.
- Electrical, instrument-air and firewater distribution are excluded; the equivalent utility ties are abstract boundaries and only catalogued equipment energy enters the lifecycle cost.
- Pipelines are modelled as zero-width plan-view centrelines with four discrete installation levels; support spacing, flexibility, stress analysis, corrosion allowance and sleeving at road crossings are not designed.
- Where two same-level pipelines cross at a single point in plan view (permitted by the published rules) a local elevation change would be required in detailed design; this is recorded as an assumption and not costed.
- Structural, civil, buildings, fire-water synthesis, full process-safety study and regulatory/code compliance are excluded by the project scope; the synthetic safety separations are not code criteria.
- The pipe-diameter optimisation is a coordinate descent over the complete published DN ladder (DN150-DN700 per line, continued while the LCC improves, up to six sweeps), so it terminates at a local rather than a proven global optimum; equipment model selection is by explicit comparison of the catalogue options rather than by a formal search. Cost rates are used as published, with no escalation, currency or financing assumptions beyond the published discount rate.
- Setpoint margins (0.05 MPa on injection pressure, 40 degC aftercooling) are design choices; they add a small energy penalty and increase robustness to modelling tolerance.
