# UGS-SYNTH-D01 v1.1 - Underground Gas Storage Facility Design Report

Case `UGS-SYNTH-D01`, benchmark family `UGS-SYNTH`. All results are computed from the
published synthetic assumptions in `brief/`; they are not production engineering
criteria. SI units throughout: metres, MPa, degrees Celsius, kg/s, MW, MWh, MBCU.

## 1. Design basis and assumptions

* Primary objective: minimise benchmark lifecycle cost (LCC) among feasible designs.
* Six mandatory operating scenarios (three injection, three withdrawal); full stated
  flow is required in normal operation; `annual_hours` weight the annual energy.
* Velocity limits: 25 m/s (gas), 3 m/s (liquid drain). Delivery limits at every sink:
  water <= 50 mg/Sm3, free liquid <= 1e-4 kg/kg, temperature in [-10, 60] degC.
* `required_sink_pressure_mpa` is treated as a minimum required delivery pressure.
  Delivery pressure is actively controlled to the required value (compressors raise it,
  the withdrawal regulator trims it).
* Reliability: with any one compressor unavailable, >=70% of scenario flow remains
  deliverable for every scenario needing compression; with any one separator or
  dehydration unit unavailable, >=70% of every withdrawal scenario remains deliverable.
* Liquid density is assumed 1000 kg/m3 for the drain-velocity check (not published);
  the resulting drain velocities are far below the 3 m/s limit.
* Electric power, instrument air and firewater are abstract, unlimited utilities.

## 2. System architecture and process connections

A single physical facility serves both injection and withdrawal. Gas moves between the
grid tie (east), the six well groups (west) and the liquid outfall.

**Injection** (`INJ-*`): GRID-TIE -> MTR-INJ (metering) -> X (suction header) ->
two parallel C60 compressors -> DH (discharge header) -> CLR1 (cooler to <=60 degC) ->
WP -> WH (well manifold) -> the six well-group laterals.

**Withdrawal** (`WDR-*`): the six well laterals -> WH -> WP -> three parallel
separator trains (SEP1..3, each followed by DHY1..3) -> X. For `WDR-MID`/`WDR-HIGH`
the surplus well pressure is trimmed directly (`X -> Y`) and regulated to the grid
setpoint by REG1. For `WDR-LOW` the gas is boosted by the two C60 compressors, cooled
by CLR2 and passed through Y and REG1. All delivery gas passes MTR-WDR before GRID-TIE.

Two physical paths connect to GRID-TIE (its connection limit is 2): the injection feed
(through MTR-INJ) and the withdrawal delivery (through MTR-WDR). Every separator
`liquid_out` is routed to a dedicated closed drain (DRN1..3) and thence to
LIQUID-DRAIN-OUTFALL; the outfall connection limit (8) and flow limit (10 kg/s) hold.

The compressors are reused between injection (grid->wells) and low-load withdrawal
(wells->grid) through the bidirectional headers X and DH; a parallel `X -> Y` bypass
(`PX-Y`) carries the high/mid withdrawal streams that need no boost. This intentional
parallel path (a physical loop) is permitted by the network rules; the active branch is
stated for every scenario in `scenarios_operating.json`.

## 3. Equipment selection and capacities

| id | model | category | footprint (m) | position (m) | orientation | capex (MBCU) |
|---|---|---|---|---|---|---|
| WH | HDR180 | header | 6x3 | 180.0, 225.0 | 0.0 | 0.36 |
| WP | HDR180 | header | 6x3 | 320.0, 225.0 | 0.0 | 0.36 |
| X | HDR180 | header | 6x3 | 440.0, 225.0 | 0.0 | 0.36 |
| DH | HDR180 | header | 6x3 | 560.0, 225.0 | 0.0 | 0.36 |
| CMP1 | C60 | compressor | 15x8 | 300.0, 345.0 | 0.0 | 6.5 |
| CMP2 | C60 | compressor | 15x8 | 385.0, 345.0 | 0.0 | 6.5 |
| CMP3 | C40 | compressor | 12x7 | 458.0, 345.0 | 0.0 | 4.6 |
| CLR1 | COOL120 | cooler | 12x6 | 620.0, 300.0 | 0.0 | 0.92 |
| CLR2 | COOL70 | cooler | 9x5 | 600.0, 120.0 | 0.0 | 0.66 |
| Y | HDR180 | header | 6x3 | 600.0, 190.0 | 0.0 | 0.36 |
| SEP1 | SEP70 | separator | 8x4 | 430.0, 110.0 | 0.0 | 0.78 |
| SEP2 | SEP70 | separator | 8x4 | 430.0, 135.0 | 0.0 | 0.78 |
| SEP3 | SEP70 | separator | 8x4 | 430.0, 160.0 | 0.0 | 0.78 |
| DHY1 | DEHY70 | dehydration | 10x5 | 550.0, 110.0 | 0.0 | 1.85 |
| DHY2 | DEHY70 | dehydration | 10x5 | 550.0, 135.0 | 0.0 | 1.85 |
| DHY3 | DEHY70 | dehydration | 10x5 | 550.0, 160.0 | 0.0 | 1.85 |
| REG1 | REG120 | regulator | 5x3 | 650.0, 165.0 | 0.0 | 0.34 |
| MTR-INJ | MTR120 | meter | 4x2 | 650.0, 292.0 | 0.0 | 0.3 |
| MTR-WDR | MTR120 | meter | 4x2 | 668.0, 170.0 | 0.0 | 0.3 |
| DRN1 | DRN-S | closed_drain | 2x2 | 430.0, 62.0 | 0.0 | 0.08 |
| DRN2 | DRN-S | closed_drain | 2x2 | 462.0, 62.0 | 0.0 | 0.08 |
| DRN3 | DRN-S | closed_drain | 2x2 | 494.0, 62.0 | 0.0 | 0.08 |

**Compression.** Three units: 2 x C60 (60 kg/s, eff 0.80) plus 1 x C40 (40 kg/s,
eff 0.76). Normal operation runs the two C60 units; the C40 is the N-1 standby. The set
is the minimum-capex combination that satisfies the compression N-1 rule for the 120
kg/s scenario: with one unit out, 100 kg/s of capacity remains (>= 0.7 x 120 = 84 kg/s).

**Withdrawal treatment.** 3 x SEP70 (70 kg/s, P16) and 3 x DEHY70 (70 kg/s, P16). The
P16 rating is required because WDR-HIGH supplies the trains at ~11.8 MPa; three parallel
units of each are needed so that one unit may be lost while >=84 kg/s (0.7 x 120) remains
treatable. Each train is one separator feeding one dehydrator; dehydration sets outlet
water to 35 mg/Sm3 (< 50 limit).

**Other.** CLR1 = COOL120 (injection cooler, up to 120 kg/s); CLR2 = COOL70 (WDR-LOW
cooler, 70 kg/s); REG1 = REG120 (grid delivery); MTR-INJ and MTR-WDR = MTR120 (120 kg/s,
P16); drains DRN1..3 = DRN-S. Five HDR180 headers (WH, WP, X, DH, Y), each P16 and rated
180 kg/s with up to 14 branch connections.

## 4. Operating philosophy and scenario results

Well allocations are even across the six groups and sum to the required flow. The six
annual weights sum to 5000 h/year, equal to `operating_hours_per_year`. Both GRID-TIE
connection slots are used (injection feed and withdrawal delivery).

| scenario | service | flow kg/s | hours | sink (MPa) | comp units | delivered P (MPa) | T (degC) | water | free liquid |
|---|---|---|---|---|---|---|---|---|---|
| INJ-LOW | inj | 120.0 | 900 | 8.5 | CMP1,CMP2 | 8.5 | 50.97 | 40.0 | 0.0 |
| INJ-MID | inj | 100.0 | 1300 | 11.0 | CMP1,CMP2 | 11.0 | 55.0 | 40.0 | 0.0 |
| INJ-HIGH | inj | 75.0 | 600 | 13.5 | CMP1,CMP2 | 13.5 | 55.0 | 40.0 | 0.0 |
| WDR-HIGH | wdr | 120.0 | 500 | 6.0 | - | 6.0 | 13.3 | 35.0 | 5e-06 |
| WDR-MID | wdr | 100.0 | 900 | 6.0 | - | 6.0 | 18.1 | 35.0 | 5e-06 |
| WDR-LOW | wdr | 70.0 | 800 | 6.0 | CMP1,CMP2 | 6.0 | 52.45 | 35.0 | 5e-06 |

**INJ-LOW compressor setpoints:**

| unit | flow kg/s | suction MPa | discharge MPa | ratio | T_out degC | power MW |
|---|---|---|---|---|---|---|
| CMP1 | 60.0 | 6.463704 | 8.657263 | 1.3394 | 50.996911 | 3.9808 |
| CMP2 | 60.0 | 6.465108 | 8.654406 | 1.3386 | 50.946562 | 3.9731 |

**INJ-MID compressor setpoints:**

| unit | flow kg/s | suction MPa | discharge MPa | ratio | T_out degC | power MW |
|---|---|---|---|---|---|---|
| CMP1 | 50.0 | 6.468655 | 11.103399 | 1.7165 | 74.487945 | 6.3149 |
| CMP2 | 50.0 | 6.469635 | 11.101835 | 1.716 | 74.459464 | 6.3112 |

**INJ-HIGH compressor setpoints:**

| unit | flow kg/s | suction MPa | discharge MPa | ratio | T_out degC | power MW |
|---|---|---|---|---|---|---|
| CMP1 | 37.5 | 6.473587 | 13.5676 | 2.0958 | 94.396073 | 6.6414 |
| CMP2 | 37.5 | 6.474144 | 13.56687 | 2.0955 | 94.381805 | 6.6401 |

**WDR-LOW compressor setpoints:**

| unit | flow kg/s | suction MPa | discharge MPa | ratio | T_out degC | power MW |
|---|---|---|---|---|---|---|
| CMP1 | 35.0 | 4.211238 | 6.084084 | 1.4447 | 52.471166 | 2.9004 |
| CMP2 | 35.0 | 4.211966 | 6.083006 | 1.4442 | 52.438945 | 2.8975 |

The cooler outlet target is 55 degC so that every well receives gas at <=60 degC; the
cooler only removes heat, so scenarios whose compressor discharge is already below
55 degC incur no cooling duty.

## 5. Site layout, safety and maintenance access

The site is the 700 x 450 m rectangle from `site.json`. Equipment footprints are inside
the boundary, outside every `equipment_exclusion` interior and non-overlapping. The
published minimum separations are met for every category pair (verified in
`check_summary.json`). Routine-clearance envelopes and heavy-maintenance removal
envelopes stay inside the site and clear of other footprints. A road network from
ROAD-ENTRANCE serves both the compressor row (crane access within 4.5 m of the removal
envelopes) and the separator row (road access within 7.0 m).

## 6. Piping and network definition

All pipelines are in `pipelines.json`. Gas lines are rated CS-DRY-160 (post-treatment,
dry) or CS-WET-160 (wet/dry capable). Liquid drains are CS-WET-100 (liquid compatible).
Diameters were selected by a greedy LCC minimiser: the reduced pressure loss lowers the
compressor pressure ratio, and the saved energy present value exceeds the extra pipe
capital cost. Sizes are recorded per line; the highest gas velocity in any
scenario is 23.8 m/s, below the 25 m/s limit.

### 6.1 Pipeline schedule

| id | from -> to | DN | class | level | length m | max v m/s |
|---|---|---|---|---|---|---|
| PGRID-INJ | GRID-TIE.gas -> MTR-INJ.gas_in | DN700 | CS-WET-160 | ground | 109.742158 | 6.8951 |
| PINJ-X | MTR-INJ.gas_out -> X.branch_01 | DN700 | CS-WET-160 | ground | 224.038641 | 6.9196 |
| PWH-WP | WH.branch_07 -> WP.branch_01 | DN700 | CS-WET-160 | ground | 137.782664 | 5.8106 |
| PWP-CLR | WP.branch_02 -> CLR1.gas_out | DN600 | CS-DRY-160 | ground | 311.875802 | 7.8991 |
| PWG1 | WG-01.gas -> WH.branch_01 | DN200 | CS-WET-160 | ground | 245.795265 | 11.9258 |
| PWG2 | WG-02.gas -> WH.branch_02 | DN200 | CS-WET-160 | ground | 202.852818 | 11.9161 |
| PWG3 | WG-03.gas -> WH.branch_03 | DN200 | CS-WET-160 | ground | 173.465414 | 11.9095 |
| PWG4 | WG-04.gas -> WH.branch_04 | DN200 | CS-WET-160 | ground | 169.097605 | 11.9085 |
| PWG5 | WG-05.gas -> WH.branch_05 | DN200 | CS-WET-160 | ground | 198.279632 | 11.9151 |
| PWG6 | WG-06.gas -> WH.branch_06 | DN200 | CS-WET-160 | ground | 248.004316 | 11.9263 |
| PWP-SEP1 | WP.branch_03 -> SEP1.gas_in | DN350 | CS-WET-160 | ground | 153.942359 | 7.6445 |
| PSEP-DHY1 | SEP1.gas_out -> DHY1.gas_in | DN200 | CS-WET-160 | ground | 111.0 | 23.8083 |
| PDHY-X1 | DHY1.gas_out -> X.branch_02 | DN250 | CS-DRY-160 | ground | 161.335104 | 15.7277 |
| PWP-SEP2 | WP.branch_04 -> SEP2.gas_in | DN350 | CS-WET-160 | ground | 140.719579 | 7.644 |
| PSEP-DHY2 | SEP2.gas_out -> DHY2.gas_in | DN200 | CS-WET-160 | ground | 111.0 | 23.8054 |
| PDHY-X2 | DHY2.gas_out -> X.branch_03 | DN250 | CS-DRY-160 | ground | 143.531355 | 15.719 |
| PWP-SEP3 | WP.branch_05 -> SEP3.gas_in | DN300 | CS-WET-160 | ground | 125.768885 | 10.4109 |
| PSEP-DHY3 | SEP3.gas_out -> DHY3.gas_in | DN200 | CS-WET-160 | ground | 111.0 | 23.8363 |
| PDHY-X3 | DHY3.gas_out -> X.branch_04 | DN250 | CS-DRY-160 | ground | 134.238594 | 15.7369 |
| PX-CMP1 | X.branch_06 -> CMP1.suction | DN500 | CS-DRY-160 | ground | 192.250853 | 6.7907 |
| PCMP-DH1 | CMP1.discharge -> DH.branch_01 | DN450 | CS-DRY-160 | ground | 276.888628 | 7.9849 |
| PX-CMP2 | X.branch_07 -> CMP2.suction | DN500 | CS-DRY-160 | ground | 136.632719 | 6.7899 |
| PCMP-DH2 | CMP2.discharge -> DH.branch_02 | DN450 | CS-DRY-160 | ground | 207.849743 | 7.9861 |
| PX-CMP3 | X.branch_08 -> CMP3.suction | DN250 | CS-DRY-160 | ground | 120.933866 | 0.0 |
| PCMP-DH3 | CMP3.discharge -> DH.branch_03 | DN200 | CS-DRY-160 | ground | 156.096925 | 0.0 |
| PX-Y | X.branch_05 -> Y.branch_02 | DN350 | CS-DRY-160 | ground | 167.52747 | 19.2381 |
| PDH-CLR | DH.branch_04 -> CLR1.gas_in | DN600 | CS-DRY-160 | ground | 95.0 | 9.0037 |
| PDH-CLR2 | DH.branch_05 -> CLR2.gas_in | DN450 | CS-DRY-160 | ground | 112.500278 | 11.6898 |
| PCLR2-Y | CLR2.gas_out -> Y.branch_01 | DN450 | CS-DRY-160 | ground | 71.817912 | 11.4855 |
| PY-REG | Y.branch_03 -> REG1.gas_in | DN450 | CS-DRY-160 | ground | 51.210351 | 11.6992 |
| PREG-MTR | REG1.gas_out -> MTR-WDR.gas_in | DN450 | CS-DRY-160 | ground | 14.39618 | 17.6343 |
| PMTR-GRID | MTR-WDR.gas_out -> GRID-TIE.gas | DN450 | CS-DRY-160 | ground | 62.64982 | 17.7119 |
| PSEP-DRN1 | SEP1.liquid_out -> DRN1.drain_in | DN150 | CS-WET-100 | buried | 46.010868 | 0.0256 |
| PDRN-OUT1 | DRN1.drain_out -> LIQUID-DRAIN-OUTFALL.drain | DN150 | CS-WET-100 | buried | 255.665797 | 0.0256 |
| PSEP-DRN2 | SEP2.liquid_out -> DRN2.drain_in | DN150 | CS-WET-100 | buried | 77.472576 | 0.0256 |
| PDRN-OUT2 | DRN2.drain_out -> LIQUID-DRAIN-OUTFALL.drain | DN150 | CS-WET-100 | buried | 224.617453 | 0.0256 |
| PSEP-DRN3 | SEP3.liquid_out -> DRN3.drain_in | DN150 | CS-WET-100 | buried | 114.825955 | 0.0256 |
| PDRN-OUT3 | DRN3.drain_out -> LIQUID-DRAIN-OUTFALL.drain | DN150 | CS-WET-100 | buried | 193.878828 | 0.0256 |

Full waypoint coordinates are in `pipelines.json`.

## 7. Quantities and lifecycle cost

PVF = (1-(1+i)^-N)/i with i = 0.08, N = 20 -> 9.8181.

| component | value |
|---|---|
| Equipment CAPEX | 30.050 MBCU |
| Piping CAPEX | 1.767 MBCU |
| Civil / access CAPEX | 0.217 MBCU |
| Annual energy | 40256.7 MWh/year |
| Energy present value | 47.430 MBCU |
| Annual maintenance | 1.102 MBCU/year |
| Maintenance present value | 10.820 MBCU |
| **LCC** | **90.284 MBCU** |

Energy dominates the LCC; the compressor pressure ratios are close to the scenario
source/sink ratios after pipe upsizing, so little further energy can be removed without
multi-stage compression, which the extra capital cost does not justify.

## 8. Assumptions and known limitations

* Liquid density for drain-velocity estimation is assumed 1000 kg/m3 (unpublished).
* The parallel `X -> Y` bypass creates a physical loop; it is permitted by the network
  rules and the active branch is stated per scenario.
* No elevation, minor losses, condensation or vaporisation are modelled, per the basis.
* Detailed electrical, control, structural, civil and safety studies are out of scope.

## 9. Reproduction

`python project/run.py` rebuilds the network, re-runs every check and regenerates the
artefacts in `design/` and this report in `report/`.
