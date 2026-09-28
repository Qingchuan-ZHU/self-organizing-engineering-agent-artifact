# UGS-SYNTH-D01 v1.1 - Underground gas storage surface facilities design report

Case `UGS-SYNTH-D01`, case version `1.1.0-development`.
Every published input is a synthetic benchmark assumption taken from `brief/`; the data are
not vendor data, production engineering criteria or code-compliance guidance.

## 1. Purpose and scope

This report defines one complete, self-consistent surface facilities design for the six
published operating scenarios of the case: process architecture, equipment selection and
count, operating philosophy, site layout, safety provisions, maintenance access, roads,
the pipeline network, quantities and lifecycle cost. In-scope work is the `scope` list of
`project_requirements.json`; the `excluded_scope` items are not addressed.

## 2. Deliverable index

| File | Content |
|---|---|
| `design_report.md` | this report |
| `equipment_register.csv` / `equipment_register.json` | every equipment instance: catalogue model, safety category, position, orientation, capacity, cost, maintenance flags, port coordinates |
| `process_topology.json` | external interfaces and every pipeline with endpoint ports, diameter, class, levels and route coordinates |
| `scenario_operations.json` | per scenario: active equipment and stages, setpoints, pipeline flows and hydraulics, equipment operating points, delivered conditions, energy |
| `well_group_allocations.csv` | per-scenario well-group flow allocation |
| `reliability_cases.json` | every N-1 case with its evaluated results |
| `pipeline_schedule.csv` | pipeline schedule with route segments |
| `quantities.json` | quantities take-off |
| `lcc.json` | lifecycle-cost basis, components and result |
| `validation_report.md`, `validation_results.json` | every check performed and its outcome |
| `layout.svg` | plan view of layout, roads, exclusion zones and pipeline routes |

## 3. Design basis

* Units: m, MPa, degC, kg/s, MW, MWh, MBCU; dimensionless quantities as published.
* Gas properties, pipe pressure loss and every equipment model are implemented exactly as
  published in `engineering_calculation_basis.md`, including the fixed-point pressure-loss
  convention (trial `P_out = P_in`, at most eight updates, 1e-5 MPa convergence) and the
  published numerical tolerances.
* Geometry follows `engineering_geometry_basis.md`: rectangular footprints, mitered
  clearance envelopes, removal envelopes on the published heavy-maintenance side,
  boundary-to-boundary separation distances, corridor and same-level overlap rules.
* Network semantics follow `network_semantics.md`: one physical connection per ordinary
  port, published interface connection limits, branching only through catalogued headers,
  one-way equipment ports, and the closed-drain liquid domain (declared at the published
  maximum of 1.0 MPa, with idealised letdown at separator `liquid_out`).
* Economic basis: discount rate 0.08, project life 20 years, PVF = 9.81815,
  energy tariff 0.00012 MBCU/MWh, road 0.00015 MBCU/m, foundations 4e-06 MBCU/m2,
  maintenance area 1e-06 MBCU/m2.

### 3.1 Operating scenarios

| Scenario | Service | Source | Sink | Flow (kg/s) | Sink pressure (MPa) | Source pressure (MPa) | Source T (degC) | Water (mg/Sm3) | Free liquid (kg/kg) | h/yr |
|---|---|---|---|---|---|---|---|---|---|---|
| INJ-LOW | injection | GRID-TIE | WG-01, WG-02, WG-03, WG-04, WG-05, WG-06 | 120.0 | 8.50 | 6.50 | 25.0 | 40 | 0.000 | 900 |
| INJ-MID | injection | GRID-TIE | WG-01, WG-02, WG-03, WG-04, WG-05, WG-06 | 100.0 | 11.00 | 6.50 | 25.0 | 40 | 0.000 | 1300 |
| INJ-HIGH | injection | GRID-TIE | WG-01, WG-02, WG-03, WG-04, WG-05, WG-06 | 75.0 | 13.50 | 6.50 | 25.0 | 40 | 0.000 | 600 |
| WDR-HIGH | withdrawal | well_groups | GRID-TIE | 120.0 | 6.00 | 12.00 | 20.0 | 220 | 0.010 | 500 |
| WDR-MID | withdrawal | well_groups | GRID-TIE | 100.0 | 6.00 | 8.00 | 20.0 | 220 | 0.010 | 900 |
| WDR-LOW | withdrawal | well_groups | GRID-TIE | 70.0 | 6.00 | 4.50 | 20.0 | 220 | 0.010 | 800 |

The six annual weights sum to the published 5000 h/yr, and the full stated flow is required
in normal operation.

### 3.2 Delivery requirements

Free-liquid loading <= 0.0001 kg/kg, water content <= 50 mg/Sm3 and gas temperature within
[-10, 60] degC, evaluated at the scenario sink interfaces. `required_sink_pressure_mpa` is
treated as the minimum pressure that must be reached at each sink interface; for withdrawal
this is the pressure the receiving grid must see, and the design regulates the GRID-TIE
pressure to exactly 6.000 MPa rather than delivering the well pressure. The design in fact
delivers exactly the required pressure at every sink in every scenario, so it satisfies an
equality reading as well.

## 4. Process architecture

### 4.1 Services and flow paths

* **Injection** (GRID-TIE -> six well groups): inlet metering line P01 -> suction manifold
  HDR-A -> the compressor bank -> discharge manifold HDR-B -> aftercooler COOL -> well
  manifold HDR-C -> six well flowlines P11..P16.
* **Withdrawal** (six well groups -> GRID-TIE): the same six well flowlines -> well
  manifold HDR-C -> withdrawal inlet line L1 -> suction manifold HDR-A -> the same
  compressor bank (boosting only in WDR-LOW) -> discharge manifold HDR-B -> feed manifold
  HDR-E -> three parallel separation + dehydration trains -> product manifold HDR-F ->
  delivery regulator REG-WDR -> outlet metering line -> GRID-TIE.
* **Liquid**: each separator `liquid_out` has its own closed drain DRN-1..3; the drains
  discharge to LIQUID-DRAIN-OUTFALL through three independent drain pipelines.
* **Metering**: GRID-TIE permits two connections, so the station has one inlet metering
  line (MTR-INJ, 160 kg/s) and one outlet metering line (MTR-WDR, 160 kg/s). Every molecule
  exchanged in either direction passes catalogued active metering capacity larger than the
  largest scenario flow (120 kg/s).

The same compressor bank serves both services. The bank's own ports are never reversed -
gas always enters at `suction` and leaves at `discharge` - and the change of service is made
in the header-to-header connections around it (P02 into HDR-A on the injection side, L1 into
HDR-A and L2 out of HDR-B on the withdrawal side), all of which join ports of type
`gas_bidirectional`. This is the "reverse station service may use a different physical path"
arrangement of `network_semantics.md`, implemented with the station line-up of section 5.3.
Using one bank rather than two is also what the primary objective (minimise lifecycle cost)
requires: a second bank of two C60 units would add 13.0 MBCU of CAPEX, 3.1 MBCU of
maintenance present value and about 0.1 MBCU of piping while carrying no duty that the
three-unit bank cannot carry.

### 4.2 Equipment selection and count

| Instance | Model | Category | Safety category | Centre (x, y) m | Orient (deg) | Rated capacity (kg/s) | CAPEX (MBCU) | Maint. (MBCU/yr) |
|---|---|---|---|---|---|---|---|---|
| COOL | COOL120 | cooler | hydrocarbon_treatment | (530.0, 380.0) | 0 | 120.0 | 0.92 | 0.050 |
| DEHY-1 | DEHY70 | dehydration | hydrocarbon_treatment | (555.0, 250.0) | 0 | 70.0 | 1.85 | 0.095 |
| DEHY-2 | DEHY70 | dehydration | hydrocarbon_treatment | (555.0, 195.0) | 0 | 70.0 | 1.85 | 0.095 |
| DEHY-3 | DEHY70 | dehydration | hydrocarbon_treatment | (555.0, 140.0) | 0 | 70.0 | 1.85 | 0.095 |
| DRN-1 | DRN-S | closed_drain | drain | (540.0, 115.0) | 0 | 0.8 | 0.08 | 0.004 |
| DRN-2 | DRN-S | closed_drain | drain | (540.0, 105.0) | 0 | 0.8 | 0.08 | 0.004 |
| DRN-3 | DRN-S | closed_drain | drain | (540.0, 95.0) | 0 | 0.8 | 0.08 | 0.004 |
| HDR-A | HDR120 | header | hydrocarbon_treatment | (345.0, 380.0) | 0 | 120.0 | 0.25 | 0.012 |
| HDR-B | HDR120 | header | hydrocarbon_treatment | (470.0, 380.0) | 0 | 120.0 | 0.25 | 0.012 |
| HDR-C | HDR120 | header | hydrocarbon_treatment | (340.0, 245.0) | 0 | 120.0 | 0.25 | 0.012 |
| HDR-E | HDR120 | header | hydrocarbon_treatment | (470.0, 178.0) | 0 | 120.0 | 0.25 | 0.012 |
| HDR-F | HDR120 | header | hydrocarbon_treatment | (605.0, 190.0) | 0 | 120.0 | 0.25 | 0.012 |
| INJ-C1 | C60 | compressor | compressor | (398.0, 400.0) | 0 | 60.0 | 6.50 | 0.160 |
| INJ-C2 | C60 | compressor | compressor | (398.0, 355.0) | 0 | 60.0 | 6.50 | 0.160 |
| INJ-C3 | C40 | compressor | compressor | (400.0, 315.0) | 0 | 40.0 | 4.60 | 0.120 |
| MTR-INJ | MTR120 | meter | metering | (640.0, 300.0) | 90 | 120.0 | 0.30 | 0.016 |
| MTR-WDR | MTR120 | meter | metering | (640.0, 245.0) | 90 | 120.0 | 0.30 | 0.016 |
| REG-WDR | REG120 | regulator | pressure_control | (640.0, 190.0) | 90 | 120.0 | 0.34 | 0.018 |
| SEP-1 | SEP70 | separator | hydrocarbon_treatment | (490.0, 250.0) | 0 | 70.0 | 0.78 | 0.050 |
| SEP-2 | SEP70 | separator | hydrocarbon_treatment | (490.0, 195.0) | 0 | 70.0 | 0.78 | 0.050 |
| SEP-3 | SEP70 | separator | hydrocarbon_treatment | (490.0, 140.0) | 0 | 70.0 | 0.78 | 0.050 |

Selection logic, and why the counts cannot be reduced:

**Compression - three units, one bank.** The compressor N-1 requirement applies to every
scenario with `required_sink_pressure_mpa > source_pressure_mpa`, i.e. all three injection
scenarios and WDR-LOW. The largest flow to be covered is the 120 kg/s of INJ-LOW, for which
at least 84 kg/s must remain deliverable after any one unit is unavailable; WDR-LOW needs
70 kg/s with at least 49 kg/s retained. No catalogue model reaches 84 kg/s, so at least
three units are needed. The cheapest set with capacity >= 120 kg/s and retained capacity
>= 84 kg/s is two C60 units plus one C40: catalogue CAPEX 17.60 MBCU, installed capacity
160 kg/s, retained capacity 100 kg/s. The same set satisfies the withdrawal requirement with
the same margin, so one bank serves both directions. In normal operation the two C60 units
(higher efficiency) share the duty equally and the C40 is isolated by its unit valves; the
C40 is started only in the reliability cases where a C60 is unavailable, and duty sharing is
a control setpoint (compressor loading is set by the unit control system, as in any
station). Running the C40 at its minimum stable flow instead would cost about
0.13 MBCU of present value, so it is left isolated.

**Withdrawal inlet path - piping only.** In WDR-HIGH the well groups deliver at 12 MPa while
the C40 unit's published maximum suction pressure is 12 MPa, so the C40 is isolated in the
two high-pressure withdrawal scenarios (which need no pressure lift and therefore carry no
published compressor N-1 requirement anyway); it runs in withdrawal service only in WDR-LOW,
where the inlet is 4.46 MPa. The withdrawal inlet line is DN350 and the compressor bus is
therefore protected by the inlet path losses: in the informative contingency in which the
C40 has to run in WDR-HIGH with one C60 unavailable, its suction is 11.976 MPa, just
inside the limit. No pressure-reducing regulator is fitted: one was evaluated and rejected
because it would cost about 0.52 MBCU of lifecycle cost and add a single series element to
all withdrawal service without being required for compliance. The small margin in that
non-required contingency is a known limitation (section 12).

**Treatment - three parallel trains.** Withdrawal gas carries 220 mg/Sm3 water and 0.01
free-liquid loading, so separation (to 5e-6 kg/kg) and dehydration (to 35 mg/Sm3) are both
mandatory. The separator/dehydration N-1 requirement retains 84 kg/s in WDR-HIGH, so the
surviving trains must have at least 84 kg/s capacity each. Three SEP70/DEHY70 trains
(CAPEX 7.89 MBCU, retained capacity 140 kg/s) satisfy that and are chosen as three
*identical* trains: equal model pressure drops and equal-sized pipework make the parallel
paths hydraulically equivalent, so the flow split over the trains is the passive
equilibrium of the network and needs no flow-control device. A mixed-size set
(SEP40 + 2 x SEP70, DEHY40 + 2 x DEHY70) is about 0.7 MBCU cheaper on equipment, but the
small models are rated to 10 MPa while WDR-HIGH reaches the treatment feed at about
11.9 MPa, so that set needs a pre-treatment regulator whose fixed pressure drop (about
1.4 MPa) far exceeds the head available between the feed and product manifolds (about
0.13 MPa); the small train could then not run in parallel with 16 MPa-rated trains, and
forcing the split would drive the larger trains past their 70 kg/s rating. The identical
three-train set is therefore used. Two SEP120/DEHY120 trains would be cheaper on equipment
alone but are rated to 10 MPa, so WDR-HIGH would need pre-treatment pressure reduction, and
their total lifecycle cost is higher.

**Cooler - one COOL120.** Only the injection service needs cooling: the compressor discharge
temperature is below the 60 degC delivery limit in INJ-LOW, but 74 degC in INJ-MID and
96 degC in INJ-HIGH, which would breach the delivery temperature limit. One COOL120 covers
120 kg/s with 32 MW of duty against 7.0 MW required, including the compressor N-1 cases.
Cooler outage is not part of the published reliability requirement (see limitations).

**Headers - five HDR120.** Branching and merging may only pass through catalogued
header/manifold components, so five manifolds are needed (compressor suction, compressor
discharge, well manifold, treatment feed, product). The largest flow through any of them is
the 120 kg/s scenario flow, so the smallest header whose rated capacity covers the
scenarios (HDR120, 120 kg/s, 14 -> 10 branch ports, 16 MPa) is used for all five; its
pressure drop at the design flow is 0.01 MPa. No header carries more than eight branch
connections, inside the published limit of ten.

**Drains - three DRN-S.** Each closed drain has one `drain_in`, and every separator
`liquid_out` must be connected to a closed drain in every scenario, so three drains are
required. The largest liquid stream is 0.47 kg/s against the 0.8 kg/s rating.

### 4.3 Liquid handling

Each separator removes m x 0.01 x 0.9995 of liquid: at most 0.47 kg/s per train in
WDR-HIGH and 0.42 kg/s in the treatment N-1 cases, inside the 0.8 kg/s rating of the DRN-S.
The total outfall flow (1.2 kg/s at the maximum) is far inside the 10 kg/s limit, and the
three outfall connections are inside the published limit of eight. Drain lines are DN200 in
the liquid-drain compatible CS-WET-100 class, sized so that the liquid-drain velocity limit
is met under the conservative reading of the published velocity rule (see assumption 6).

## 5. Operating philosophy

### 5.1 Per-scenario operating points

| Scenario | Compressor discharge setpoint (MPa) | Compressor duty split (kg/s) | Regulator setpoint (MPa) | Sink pressure (MPa) | Sink temperature (degC) |
|---|---|---|---|---|---|
| INJ-LOW | 8.5809 | INJ-C1=60.000, INJ-C2=60.000, INJ-C3=isolated | not applicable | 8.500000, 8.500000, 8.500000, 8.500000, 8.500000, 8.500000 | 50.25 |
| INJ-MID | 11.0634 | INJ-C1=50.000, INJ-C2=50.000, INJ-C3=isolated | not applicable | 11.000000, 11.000000, 11.000000, 11.000000, 11.000000, 11.000000 | 58.00 |
| INJ-HIGH | 13.5496 | INJ-C1=37.500, INJ-C2=37.500, INJ-C3=isolated | not applicable | 13.500000, 13.500000, 13.500000, 13.500000, 13.500000, 13.500000 | 58.00 |
| WDR-HIGH | unloaded pass-through | INJ-C1=60.000, INJ-C2=60.000, INJ-C3=isolated | 6.0363 | 6.000000 | 13.10 |
| WDR-MID | unloaded pass-through | INJ-C1=50.000, INJ-C2=50.000, INJ-C3=isolated | 6.0315 | 6.000000 | 17.88 |
| WDR-LOW | 6.3709 | INJ-C1=35.000, INJ-C2=35.000, INJ-C3=isolated | 6.0264 | 6.000000 | 50.90 |

### 5.2 Setpoint derivation and passive balances

* **Well-group allocation.** The six well flowlines are solved as a passive, balanced
  distribution: the common well-manifold pressure is set so the required wellhead pressure
  is reached at every well group, and each branch then carries the flow that makes its
  pressure loss equal to that of every other branch. The allocation is therefore solved
  rather than assumed, it sums to the scenario flow, every well group stays inside its
  25 kg/s boundary limit, and every well group receives exactly its required pressure
  (within 1e-9 MPa) instead of some wells being over-pressured.
* **Treatment train allocation** is solved the same way - a common head loss over the three
  identical trains, so it is the network's passive equilibrium (typical splits
  1 34.5 kg/s, 2 47.2 kg/s, 3 38.3 kg/s). The same applies to the two C60 unit paths when they carry gas unloaded;
  the small difference between those two pipe paths is taken up by the unit bypass valves
  (assumption 3).
* **Compressor discharge pressure** is solved per scenario as the minimum value that
  satisfies every delivery point: 8.5809 MPa (INJ-LOW), 11.0634 MPa (INJ-MID) and
  13.5496 MPa (INJ-HIGH). Discharge pressure is held as low as the requirement permits
  because compressor power is the dominant lifecycle component.
* **Aftercooler outlet** is controlled to 58.0 degC, 2 K inside the 60 degC delivery limit.
  When the compressor discharge is already below the setpoint (INJ-LOW), the cooler passes
  the gas with zero duty.
* **Withdrawal compressor discharge pressure** is held just above the delivery regulator's
  inlet requirement (6.3709 MPa in WDR-LOW) so the regulator always has positive
  letdown. In WDR-MID and WDR-HIGH no lift is required and the units pass the gas at equal
  inlet and outlet pressure with zero driver power.
* **Delivery regulator setpoint** is solved so the GRID-TIE boundary pressure is exactly
  6.000 MPa, including the outlet metering-line loss (6.0264 MPa in WDR-LOW).
* **Metering lines** are in service in the active direction only.

### 5.3 Isolation (line-up) schedule

The published model contains no valve components, so isolation is stated as an operating
requirement. Each scenario uses one of the two station sections; the other is isolated at
both ends, so no unaccounted flow path exists in any scenario, and each compressor has unit
isolation and discharge check valves so a failed unit can be taken out of service.

| Valve | Location | Injection scenarios | Withdrawal scenarios |
|---|---|---|---|
| V-01 | P01, inlet metering line at GRID-TIE | open | closed |
| V-02 | P02, inlet metering line at HDR-A | open (injection feed) | closed (injection feed isolated) |
| V-03 | L1, withdrawal inlet path at HDR-A and HDR-C | closed (withdrawal feed isolated) | open |
| V-05 | L2, withdrawal discharge path at HDR-B | closed (treatment feed isolated) | open |
| V-06 | P09, injection discharge at HDR-B | open (cooler feed) | closed (cooler feed isolated) |
| V-07 | P10, aftercooler discharge at HDR-C | open (injection delivery) | closed |
| V-08 | P32, outlet metering line at GRID-TIE | closed | open |
| unit valves | each compressor suction and discharge | open when the unit runs | open when the unit runs |

### 5.4 Unit states

| Scenario | Compressor bank | Inlet pressure control | Cooler | Treatment trains | Meters |
|---|---|---|---|---|---|
| INJ-LOW, INJ-MID, INJ-HIGH | running (2 x C60; C40 isolated) | not fitted | in service | isolated | MTR-INJ active |
| WDR-HIGH, WDR-MID | unloaded pass-through (2 x C60; C40 isolated) | not fitted | isolated | 3 trains in service | MTR-WDR active |
| WDR-LOW | running (2 x C60; C40 isolated) | not fitted | isolated | 3 trains in service | MTR-WDR active |

In the reliability cases the C40 is started: it carries the duty alongside a surviving C60
when a C60 is unavailable, or the whole retained flow with the other C60 when the failed
unit is a C40.

The compressor units are modelled as passive pass-through elements in WDR-HIGH and WDR-MID
(equal inlet and outlet pressure, no temperature change, zero driver power): those scenarios
need no pressure lift, and the fixed physical network offers no alternative path around the
units. This convention is stated explicitly; in a detailed design those units would
additionally have a bypass line with isolation valves.

### 5.5 GRID-TIE metering

In every scenario the active meter rated capacity (160 kg/s) is at least the scenario flow
(70-120 kg/s), so `minimum_active_meter_capacity_fraction_of_scenario_flow = 1.0` is met in
both directions.

## 6. Layout, safety provisions and maintenance access

### 6.1 Positions and orientations

Equipment instances, catalogue models, footprint centres and rotations are listed in the
table above and in `equipment_register.csv` / `equipment_register.json`, which also give
every local port offset and its resulting site coordinate. The layout is drawn in
`layout.svg`.

### 6.2 Separation distances

The published matrix is applied boundary-to-boundary between the rotated footprint
polygons. The closest relationships in the design are:

| Equipment pair | Categories | Achieved separation (m) | Required (m) |
|---|---|---|---|
| DRN-1 / DRN-2 | drain / drain | 8.00 | 4.0 |
| DRN-2 / DRN-3 | drain / drain | 8.00 | 4.0 |
| HDR-E / SEP-2 | hydrocarbon_treatment / hydrocarbon_treatment | 18.74 | 5.0 |
| DRN-1 / DRN-3 | drain / drain | 18.00 | 4.0 |
| DEHY-3 / DRN-1 | hydrocarbon_treatment / drain | 23.31 | 8.0 |
| REG-WDR / HDR-F | pressure_control / hydrocarbon_treatment | 30.50 | 6.0 |
| DEHY-3 / DRN-2 | hydrocarbon_treatment / drain | 32.76 | 8.0 |
| INJ-C2 / INJ-C3 | compressor / compressor | 32.50 | 6.0 |
| INJ-C1 / INJ-C2 | compressor / compressor | 37.00 | 6.0 |
| HDR-E / SEP-3 | hydrocarbon_treatment / hydrocarbon_treatment | 36.87 | 5.0 |
| DEHY-3 / DRN-3 | hydrocarbon_treatment / drain | 42.46 | 8.0 |
| INJ-C1 / HDR-A | compressor / hydrocarbon_treatment | 44.91 | 10.0 |

### 6.3 Maintenance envelopes and access

Clearance envelopes are mitered expansions of the footprints. The five compressor units
carry heavy-maintenance removal envelopes on their local east side, all facing the
north-south road at x = 421 m; the largest distance from a required envelope boundary to the
paved road boundary is 2.40 m against the 4.5 m crane-access buffer. The
separator clearance envelopes are 3.00 m from the paved road at x = 478 m against
the 7 m road-access buffer. No other model declares a road or crane access requirement.
Every required envelope lies inside the site, outside the equipment-exclusion zones and
clear of other footprints; total required maintenance area (envelope minus footprint) is
1589.9 m2. All access distances are measured to the full-width paved boundary.

### 6.4 Road network

Four 6 m wide roads (minimum permitted width 4 m) form one connected network containing the
ROAD-ENTRANCE point: the main east-west road (x = 0 to 660 m at y = 225 m), a north-south
road at x = 421 m serving both compressor areas, an east-west road at y = 120 m serving the
treatment area and drain outfall, and a north-south road at x = 478 m giving the treatment
trains their road access. Total road centreline length is 1406 m; road CAPEX uses
centreline length at 0.00015 MBCU/m and does not vary with width.

### 6.5 Safety provisions

The published separation matrix is the only quantitative safety requirement, and it is met
for every equipment pair (section 6.2). Firewater, instrument air and electric power are
externally available abstract services with assumed sufficient availability and capacity;
their distribution networks are outside scope. Hazardous-area classification, relief and
blowdown, and fire protection detail are excluded scope.

## 7. Piping and other network definition

### 7.1 Classes, diameters and routing levels

| Pipeline group | DN | Class | Level | Rationale |
|---|---|---|---|---|
| P01, P02 grid-tie inlet lines | DN700 | CS-DRY-160 | ground | dry injection gas; suction-side loss is multiplied by the compressor power price, so the line is generously sized |
| P03-P08 compressor suction/discharge | DN300, DN400 | CS-WET-160 | ground | carry dry injection gas and wet withdrawal gas, so a wet-compatible class is required; sized by loss on the compression path subject to the 25 m/s velocity limit |
| P09, P10 injection main line | DN600 | CS-DRY-160 | ground | 120 kg/s at low loss, injection service only |
| P11-P16 well flowlines | DN300 | CS-WET-160 | ground | shared between dry injection and wet withdrawal service |
| L1 withdrawal inlet path | DN350 | CS-WET-160 | ground | 120 kg/s wet service; sized to keep the C40 suction inside its 12 MPa limit in WDR-HIGH |
| L2 withdrawal discharge path | DN500 | CS-WET-160 | ground | 120 kg/s; its loss is paid for by the WDR-LOW booster duty |
| P21-P29 treatment trains | DN300 | CS-WET-160 | ground | up to 48 kg/s per train |
| P30 product manifold line | DN500 | CS-WET-160 | ground | 120 kg/s into the regulator |
| P31, P32 outlet metering lines | DN500 | CS-WET-160 | ground | 120 kg/s at grid pressure; the meter is the smallest model whose rated capacity covers the largest scenario flow |
| P36-P41 drain lines | DN200 | CS-WET-100 | ground | liquid-drain compatible class, sized on the conservative drain-velocity reading |

CS-WET-160 is both wet- and dry-gas compatible, rated 16 MPa over -20 to 120 degC, so it
covers every line that carries either service; CS-DRY-160 is used only where the service is
always dry injection gas. Each pipeline is checked in every scenario against its pressure
rating, temperature range, dry/wet compatibility and, for drains, liquid-drain compatibility
and the liquid-drain velocity limit.

### 7.2 Pipeline schedule

| Pipeline | From -> To | DN | Class | Routing level | Length (m) | Service |
|---|---|---|---|---|---|---|
| L1 | HDR-C.branch_09 -> HDR-A.branch_04 | DN500 | CS-WET-160 | ground | 176.50 | gas |
| L2 | HDR-B.branch_03 -> HDR-E.branch_05 | DN500 | CS-WET-160 | ground | 200.50 | gas |
| P01 | GRID-TIE.gas -> MTR-INJ.gas_in | DN700 | CS-DRY-160 | ground | 133.00 | gas |
| P02 | MTR-INJ.gas_out -> HDR-A.branch_03 | DN700 | CS-DRY-160 | ground | 370.00 | gas |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | 62.00 | gas |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | 70.50 | gas |
| P05 | HDR-A.branch_10 -> INJ-C3.suction | DN300 | CS-WET-160 | ground | 110.00 | gas |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | 80.75 | gas |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | 85.75 | gas |
| P08 | INJ-C3.discharge -> HDR-B.branch_07 | DN300 | CS-WET-160 | ground | 126.00 | gas |
| P09 | HDR-B.branch_06 -> COOL.gas_in | DN600 | CS-DRY-160 | ground | 51.00 | gas |
| P10 | COOL.gas_out -> HDR-C.branch_10 | DN600 | CS-DRY-160 | ground | 258.01 | gas |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | 382.11 | gas |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | 352.95 | gas |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | 329.66 | gas |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | 325.36 | gas |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | 339.21 | gas |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | 362.49 | gas |
| P21 | HDR-E.branch_02 -> SEP-1.gas_in | DN300 | CS-WET-160 | ground | 72.18 | gas |
| P22 | HDR-E.branch_06 -> SEP-2.gas_in | DN300 | CS-WET-160 | ground | 21.40 | gas |
| P23 | HDR-E.branch_10 -> SEP-3.gas_in | DN300 | CS-WET-160 | ground | 39.22 | gas |
| P24 | SEP-1.gas_out -> DEHY-1.gas_in | DN300 | CS-WET-160 | ground | 56.00 | gas |
| P25 | SEP-2.gas_out -> DEHY-2.gas_in | DN300 | CS-WET-160 | ground | 56.00 | gas |
| P26 | SEP-3.gas_out -> DEHY-3.gas_in | DN300 | CS-WET-160 | ground | 56.00 | gas |
| P27 | DEHY-1.gas_out -> HDR-F.branch_07 | DN300 | CS-WET-160 | ground | 105.00 | gas |
| P28 | DEHY-2.gas_out -> HDR-F.branch_04 | DN300 | CS-WET-160 | ground | 47.75 | gas |
| P29 | DEHY-3.gas_out -> HDR-F.branch_01 | DN300 | CS-WET-160 | ground | 94.50 | gas |
| P30 | HDR-F.branch_06 -> REG-WDR.gas_in | DN500 | CS-WET-160 | ground | 34.50 | gas |
| P31 | REG-WDR.gas_out -> MTR-WDR.gas_in | DN500 | CS-WET-160 | ground | 50.50 | gas |
| P32 | MTR-WDR.gas_out -> GRID-TIE.gas | DN500 | CS-WET-160 | ground | 82.00 | gas |
| P36 | SEP-1.liquid_out -> DRN-1.drain_in | DN200 | CS-WET-100 | ground | 182.00 | liquid_drain |
| P37 | SEP-2.liquid_out -> DRN-2.drain_in | DN200 | CS-WET-100 | ground | 137.00 | liquid_drain |
| P38 | SEP-3.liquid_out -> DRN-3.drain_in | DN200 | CS-WET-100 | ground | 92.00 | liquid_drain |
| P39 | DRN-1.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | 144.00 | liquid_drain |
| P40 | DRN-2.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | 154.00 | liquid_drain |
| P41 | DRN-3.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | 184.00 | liquid_drain |

Full route coordinates and installation levels are in `pipeline_schedule.csv`,
`process_topology.json` and `scenario_operations.json`.

### 7.3 Scenario hydraulics

<details><summary>INJ-LOW pipeline operating table</summary>

| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |
|---|---|---|---|---|---|---|---|---|---|---|
| P01 | GRID-TIE.gas -> MTR-INJ.gas_in | DN700 | CS-DRY-160 | ground | +120.0000 | 6.5000 | 6.4977 | 0.0023 | 6.896 | 25.00 |
| P02 | MTR-INJ.gas_out -> HDR-A.branch_03 | DN700 | CS-DRY-160 | ground | +120.0000 | 6.4777 | 6.4711 | 0.0066 | 6.924 | 25.00 |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | +60.0000 | 6.4611 | 6.4592 | 0.0019 | 6.798 | 25.00 |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | +60.0000 | 6.4611 | 6.4590 | 0.0021 | 6.798 | 25.00 |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | +60.0000 | 8.5809 | 8.5789 | 0.0020 | 5.607 | 50.25 |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | +60.0000 | 8.5809 | 8.5788 | 0.0021 | 5.607 | 50.25 |
| P09 | HDR-B.branch_06 -> COOL.gas_in | DN600 | CS-DRY-160 | ground | +120.0000 | 8.5688 | 8.5671 | 0.0016 | 7.798 | 50.25 |
| P10 | COOL.gas_out -> HDR-C.branch_10 | DN600 | CS-DRY-160 | ground | +120.0000 | 8.5321 | 8.5238 | 0.0084 | 7.837 | 50.25 |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | +19.0751 | 8.5138 | 8.5000 | 0.0138 | 4.997 | 50.25 |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | +19.8529 | 8.5138 | 8.5000 | 0.0138 | 5.200 | 50.25 |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | +20.5469 | 8.5138 | 8.5000 | 0.0138 | 5.382 | 50.25 |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | +20.6833 | 8.5138 | 8.5000 | 0.0138 | 5.418 | 50.25 |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | +20.2536 | 8.5138 | 8.5000 | 0.0138 | 5.305 | 50.25 |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | +19.5881 | 8.5138 | 8.5000 | 0.0138 | 5.131 | 50.25 |

</details>

<details><summary>INJ-MID pipeline operating table</summary>

| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |
|---|---|---|---|---|---|---|---|---|---|---|
| P01 | GRID-TIE.gas -> MTR-INJ.gas_in | DN700 | CS-DRY-160 | ground | +100.0000 | 6.5000 | 6.4984 | 0.0016 | 5.746 | 25.00 |
| P02 | MTR-INJ.gas_out -> HDR-A.branch_03 | DN700 | CS-DRY-160 | ground | +100.0000 | 6.4784 | 6.4738 | 0.0046 | 5.768 | 25.00 |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | +50.0000 | 6.4668 | 6.4655 | 0.0013 | 5.659 | 25.00 |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | +50.0000 | 6.4668 | 6.4654 | 0.0015 | 5.660 | 25.00 |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | +50.0000 | 11.0634 | 11.0622 | 0.0012 | 3.928 | 74.18 |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | +50.0000 | 11.0634 | 11.0622 | 0.0012 | 3.928 | 74.19 |
| P09 | HDR-B.branch_06 -> COOL.gas_in | DN600 | CS-DRY-160 | ground | +100.0000 | 11.0552 | 11.0543 | 0.0010 | 5.459 | 74.18 |
| P10 | COOL.gas_out -> HDR-C.branch_10 | DN600 | CS-DRY-160 | ground | +100.0000 | 11.0193 | 11.0146 | 0.0047 | 5.210 | 58.00 |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | +15.8949 | 11.0076 | 11.0000 | 0.0076 | 3.317 | 58.00 |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | +16.5439 | 11.0076 | 11.0000 | 0.0076 | 3.452 | 58.00 |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | +17.1230 | 11.0076 | 11.0000 | 0.0076 | 3.573 | 58.00 |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | +17.2369 | 11.0076 | 11.0000 | 0.0076 | 3.597 | 58.00 |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | +16.8783 | 11.0076 | 11.0000 | 0.0076 | 3.522 | 58.00 |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | +16.3230 | 11.0076 | 11.0000 | 0.0076 | 3.406 | 58.00 |

</details>

<details><summary>INJ-HIGH pipeline operating table</summary>

| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |
|---|---|---|---|---|---|---|---|---|---|---|
| P01 | GRID-TIE.gas -> MTR-INJ.gas_in | DN700 | CS-DRY-160 | ground | +75.0000 | 6.5000 | 6.4991 | 0.0009 | 4.309 | 25.00 |
| P02 | MTR-INJ.gas_out -> HDR-A.branch_03 | DN700 | CS-DRY-160 | ground | +75.0000 | 6.4791 | 6.4765 | 0.0026 | 4.324 | 25.00 |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | +37.5000 | 6.4726 | 6.4718 | 0.0007 | 4.240 | 25.00 |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | +37.5000 | 6.4726 | 6.4717 | 0.0008 | 4.241 | 25.00 |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | +37.5000 | 13.5496 | 13.5490 | 0.0006 | 2.563 | 94.29 |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | +37.5000 | 13.5496 | 13.5490 | 0.0006 | 2.563 | 94.29 |
| P09 | HDR-B.branch_06 -> COOL.gas_in | DN600 | CS-DRY-160 | ground | +75.0000 | 13.5451 | 13.5446 | 0.0005 | 3.561 | 94.29 |
| P10 | COOL.gas_out -> HDR-C.branch_10 | DN600 | CS-DRY-160 | ground | +75.0000 | 13.5096 | 13.5074 | 0.0022 | 3.200 | 58.00 |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | +11.9199 | 13.5035 | 13.5000 | 0.0035 | 2.035 | 58.00 |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | +12.4078 | 13.5035 | 13.5000 | 0.0035 | 2.119 | 58.00 |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | +12.8430 | 13.5035 | 13.5000 | 0.0035 | 2.193 | 58.00 |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | +12.9286 | 13.5035 | 13.5000 | 0.0035 | 2.207 | 58.00 |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | +12.6591 | 13.5035 | 13.5000 | 0.0035 | 2.161 | 58.00 |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | +12.2417 | 13.5035 | 13.5000 | 0.0035 | 2.090 | 58.00 |

</details>

<details><summary>WDR-HIGH pipeline operating table</summary>

| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | HDR-C.branch_09 -> HDR-A.branch_04 | DN500 | CS-WET-160 | ground | +120.0000 | 11.9811 | 11.9698 | 0.0113 | 7.302 | 20.00 |
| L2 | HDR-B.branch_03 -> HDR-E.branch_05 | DN500 | CS-WET-160 | ground | +120.0000 | 11.9472 | 11.9343 | 0.0129 | 7.323 | 20.00 |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | +60.0000 | 11.9598 | 11.9588 | 0.0010 | 3.654 | 20.00 |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | +60.0000 | 11.9598 | 11.9586 | 0.0011 | 3.654 | 20.00 |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | +60.0000 | 11.9588 | 11.9575 | 0.0013 | 3.655 | 20.00 |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | +60.0000 | 11.9586 | 11.9572 | 0.0014 | 3.655 | 20.00 |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | -19.0754 | 12.0000 | 11.9911 | 0.0089 | 3.219 | 20.00 |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | -19.8530 | 12.0000 | 11.9911 | 0.0089 | 3.350 | 20.00 |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | -20.5467 | 12.0000 | 11.9911 | 0.0089 | 3.467 | 20.00 |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | -20.6831 | 12.0000 | 11.9911 | 0.0089 | 3.490 | 20.00 |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | -20.2535 | 12.0000 | 11.9911 | 0.0089 | 3.417 | 20.00 |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | -19.5882 | 12.0000 | 11.9911 | 0.0089 | 3.305 | 20.00 |
| P21 | HDR-E.branch_02 -> SEP-1.gas_in | DN300 | CS-WET-160 | ground | +34.5263 | 11.9243 | 11.9188 | 0.0055 | 5.860 | 20.00 |
| P22 | HDR-E.branch_06 -> SEP-2.gas_in | DN300 | CS-WET-160 | ground | +47.1808 | 11.9243 | 11.9213 | 0.0030 | 8.007 | 20.00 |
| P23 | HDR-E.branch_10 -> SEP-3.gas_in | DN300 | CS-WET-160 | ground | +38.2929 | 11.9243 | 11.9207 | 0.0037 | 6.499 | 20.00 |
| P24 | SEP-1.gas_out -> DEHY-1.gas_in | DN300 | CS-WET-160 | ground | +34.5263 | 11.8888 | 11.8846 | 0.0043 | 5.877 | 20.00 |
| P25 | SEP-2.gas_out -> DEHY-2.gas_in | DN300 | CS-WET-160 | ground | +47.1808 | 11.8913 | 11.8833 | 0.0080 | 8.032 | 20.00 |
| P26 | SEP-3.gas_out -> DEHY-3.gas_in | DN300 | CS-WET-160 | ground | +38.2929 | 11.8907 | 11.8854 | 0.0052 | 6.518 | 20.00 |
| P27 | DEHY-1.gas_out -> HDR-F.branch_07 | DN300 | CS-WET-160 | ground | +34.5263 | 11.8046 | 11.7965 | 0.0081 | 5.920 | 20.00 |
| P28 | DEHY-2.gas_out -> HDR-F.branch_04 | DN300 | CS-WET-160 | ground | +47.1808 | 11.8033 | 11.7965 | 0.0068 | 8.090 | 20.00 |
| P29 | DEHY-3.gas_out -> HDR-F.branch_01 | DN300 | CS-WET-160 | ground | +38.2929 | 11.8054 | 11.7965 | 0.0089 | 6.566 | 20.00 |
| P30 | HDR-F.branch_06 -> REG-WDR.gas_in | DN500 | CS-WET-160 | ground | +120.0000 | 11.7865 | 11.7842 | 0.0023 | 7.415 | 20.00 |
| P31 | REG-WDR.gas_out -> MTR-WDR.gas_in | DN500 | CS-WET-160 | ground | +120.0000 | 6.0363 | 6.0301 | 0.0062 | 13.936 | 13.10 |
| P32 | MTR-WDR.gas_out -> GRID-TIE.gas | DN500 | CS-WET-160 | ground | +120.0000 | 6.0101 | 6.0000 | 0.0101 | 14.004 | 13.10 |
| P36 | SEP-1.liquid_out -> DRN-1.drain_in | DN200 | CS-WET-100 | ground | +0.3451 | 1.00 (closed-drain domain) | 1.00 | - | 1.5105 | 20.0 |
| P37 | SEP-2.liquid_out -> DRN-2.drain_in | DN200 | CS-WET-100 | ground | +0.4716 | 1.00 (closed-drain domain) | 1.00 | - | 2.0641 | 20.0 |
| P38 | SEP-3.liquid_out -> DRN-3.drain_in | DN200 | CS-WET-100 | ground | +0.3827 | 1.00 (closed-drain domain) | 1.00 | - | 1.6753 | 20.0 |
| P39 | DRN-1.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.3451 | 1.00 (closed-drain domain) | 1.00 | - | 1.5105 | 20.0 |
| P40 | DRN-2.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.4716 | 1.00 (closed-drain domain) | 1.00 | - | 2.0641 | 20.0 |
| P41 | DRN-3.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.3827 | 1.00 (closed-drain domain) | 1.00 | - | 1.6753 | 20.0 |

</details>

<details><summary>WDR-MID pipeline operating table</summary>

| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | HDR-C.branch_09 -> HDR-A.branch_04 | DN500 | CS-WET-160 | ground | +100.0000 | 7.9839 | 7.9721 | 0.0117 | 9.058 | 20.00 |
| L2 | HDR-B.branch_03 -> HDR-E.branch_05 | DN500 | CS-WET-160 | ground | +100.0000 | 7.9556 | 7.9422 | 0.0134 | 9.091 | 20.00 |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | +50.0000 | 7.9652 | 7.9641 | 0.0010 | 4.533 | 20.00 |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | +50.0000 | 7.9652 | 7.9640 | 0.0012 | 4.534 | 20.00 |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | +50.0000 | 7.9641 | 7.9628 | 0.0014 | 4.534 | 20.00 |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | +50.0000 | 7.9640 | 7.9626 | 0.0014 | 4.534 | 20.00 |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | -15.8954 | 8.0000 | 7.9908 | 0.0092 | 3.990 | 20.00 |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | -16.5440 | 8.0000 | 7.9908 | 0.0092 | 4.153 | 20.00 |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | -17.1228 | 8.0000 | 7.9908 | 0.0092 | 4.298 | 20.00 |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | -17.2365 | 8.0000 | 7.9908 | 0.0092 | 4.327 | 20.00 |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | -16.8782 | 8.0000 | 7.9908 | 0.0092 | 4.237 | 20.00 |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | -16.3232 | 8.0000 | 7.9908 | 0.0092 | 4.098 | 20.00 |
| P21 | HDR-E.branch_02 -> SEP-1.gas_in | DN300 | CS-WET-160 | ground | +28.7692 | 7.9353 | 7.9296 | 0.0057 | 7.277 | 20.00 |
| P22 | HDR-E.branch_06 -> SEP-2.gas_in | DN300 | CS-WET-160 | ground | +39.3209 | 7.9353 | 7.9321 | 0.0031 | 9.942 | 20.00 |
| P23 | HDR-E.branch_10 -> SEP-3.gas_in | DN300 | CS-WET-160 | ground | +31.9099 | 7.9353 | 7.9315 | 0.0038 | 8.069 | 20.00 |
| P24 | SEP-1.gas_out -> DEHY-1.gas_in | DN300 | CS-WET-160 | ground | +28.7692 | 7.8996 | 7.8952 | 0.0044 | 7.308 | 20.00 |
| P25 | SEP-2.gas_out -> DEHY-2.gas_in | DN300 | CS-WET-160 | ground | +39.3209 | 7.9021 | 7.8939 | 0.0083 | 9.990 | 20.00 |
| P26 | SEP-3.gas_out -> DEHY-3.gas_in | DN300 | CS-WET-160 | ground | +31.9099 | 7.9015 | 7.8960 | 0.0054 | 8.105 | 20.00 |
| P27 | DEHY-1.gas_out -> HDR-F.branch_07 | DN300 | CS-WET-160 | ground | +28.7692 | 7.8152 | 7.8068 | 0.0084 | 7.389 | 20.00 |
| P28 | DEHY-2.gas_out -> HDR-F.branch_04 | DN300 | CS-WET-160 | ground | +39.3209 | 7.8139 | 7.8068 | 0.0071 | 10.099 | 20.00 |
| P29 | DEHY-3.gas_out -> HDR-F.branch_01 | DN300 | CS-WET-160 | ground | +31.9099 | 7.8160 | 7.8067 | 0.0093 | 8.195 | 20.00 |
| P30 | HDR-F.branch_06 -> REG-WDR.gas_in | DN500 | CS-WET-160 | ground | +100.0000 | 7.7998 | 7.7975 | 0.0023 | 9.257 | 20.00 |
| P31 | REG-WDR.gas_out -> MTR-WDR.gas_in | DN500 | CS-WET-160 | ground | +100.0000 | 6.0315 | 6.0272 | 0.0044 | 11.822 | 17.88 |
| P32 | MTR-WDR.gas_out -> GRID-TIE.gas | DN500 | CS-WET-160 | ground | +100.0000 | 6.0072 | 6.0000 | 0.0072 | 11.874 | 17.88 |
| P36 | SEP-1.liquid_out -> DRN-1.drain_in | DN200 | CS-WET-100 | ground | +0.2875 | 1.00 (closed-drain domain) | 1.00 | - | 1.2586 | 20.0 |
| P37 | SEP-2.liquid_out -> DRN-2.drain_in | DN200 | CS-WET-100 | ground | +0.3930 | 1.00 (closed-drain domain) | 1.00 | - | 1.7202 | 20.0 |
| P38 | SEP-3.liquid_out -> DRN-3.drain_in | DN200 | CS-WET-100 | ground | +0.3189 | 1.00 (closed-drain domain) | 1.00 | - | 1.3960 | 20.0 |
| P39 | DRN-1.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.2875 | 1.00 (closed-drain domain) | 1.00 | - | 1.2586 | 20.0 |
| P40 | DRN-2.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.3930 | 1.00 (closed-drain domain) | 1.00 | - | 1.7202 | 20.0 |
| P41 | DRN-3.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.3189 | 1.00 (closed-drain domain) | 1.00 | - | 1.3960 | 20.0 |

</details>

<details><summary>WDR-LOW pipeline operating table</summary>

| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | HDR-C.branch_09 -> HDR-A.branch_04 | DN500 | CS-WET-160 | ground | +70.0000 | 4.4886 | 4.4785 | 0.0102 | 11.157 | 20.00 |
| L2 | HDR-B.branch_03 -> HDR-E.branch_05 | DN500 | CS-WET-160 | ground | +70.0000 | 6.3665 | 6.3574 | 0.0091 | 8.798 | 51.14 |
| P03 | HDR-A.branch_09 -> INJ-C1.suction | DN500 | CS-WET-160 | ground | +35.0000 | 4.4751 | 4.4742 | 0.0009 | 5.584 | 20.00 |
| P04 | HDR-A.branch_07 -> INJ-C2.suction | DN500 | CS-WET-160 | ground | +35.0000 | 4.4751 | 4.4741 | 0.0010 | 5.584 | 20.00 |
| P06 | INJ-C1.discharge -> HDR-B.branch_08 | DN500 | CS-WET-160 | ground | +35.0000 | 6.3709 | 6.3700 | 0.0009 | 4.391 | 51.14 |
| P07 | INJ-C2.discharge -> HDR-B.branch_04 | DN500 | CS-WET-160 | ground | +35.0000 | 6.3709 | 6.3699 | 0.0010 | 4.391 | 51.14 |
| P11 | HDR-C.branch_07 -> WG-01.gas | DN300 | CS-WET-160 | ground | -11.1254 | 4.5000 | 4.4920 | 0.0080 | 4.911 | 20.00 |
| P12 | HDR-C.branch_03 -> WG-02.gas | DN300 | CS-WET-160 | ground | -11.5806 | 4.5000 | 4.4920 | 0.0080 | 5.112 | 20.00 |
| P13 | HDR-C.branch_04 -> WG-03.gas | DN300 | CS-WET-160 | ground | -11.9867 | 4.5000 | 4.4920 | 0.0080 | 5.291 | 20.00 |
| P14 | HDR-C.branch_08 -> WG-04.gas | DN300 | CS-WET-160 | ground | -12.0666 | 4.5000 | 4.4920 | 0.0080 | 5.327 | 20.00 |
| P15 | HDR-C.branch_05 -> WG-05.gas | DN300 | CS-WET-160 | ground | -11.8151 | 4.5000 | 4.4920 | 0.0080 | 5.216 | 20.00 |
| P16 | HDR-C.branch_01 -> WG-06.gas | DN300 | CS-WET-160 | ground | -11.4256 | 4.5000 | 4.4920 | 0.0080 | 5.044 | 20.00 |
| P21 | HDR-E.branch_02 -> SEP-1.gas_in | DN300 | CS-WET-160 | ground | +20.1326 | 6.3540 | 6.3501 | 0.0039 | 7.037 | 51.14 |
| P22 | HDR-E.branch_06 -> SEP-2.gas_in | DN300 | CS-WET-160 | ground | +27.5324 | 6.3540 | 6.3519 | 0.0021 | 9.621 | 51.14 |
| P23 | HDR-E.branch_10 -> SEP-3.gas_in | DN300 | CS-WET-160 | ground | +22.3350 | 6.3540 | 6.3514 | 0.0026 | 7.805 | 51.14 |
| P24 | SEP-1.gas_out -> DEHY-1.gas_in | DN300 | CS-WET-160 | ground | +20.1326 | 6.3201 | 6.3171 | 0.0030 | 7.073 | 51.14 |
| P25 | SEP-2.gas_out -> DEHY-2.gas_in | DN300 | CS-WET-160 | ground | +27.5324 | 6.3219 | 6.3162 | 0.0056 | 9.674 | 51.14 |
| P26 | SEP-3.gas_out -> DEHY-3.gas_in | DN300 | CS-WET-160 | ground | +22.3350 | 6.3214 | 6.3177 | 0.0037 | 7.846 | 51.14 |
| P27 | DEHY-1.gas_out -> HDR-F.branch_07 | DN300 | CS-WET-160 | ground | +20.1326 | 6.2371 | 6.2314 | 0.0057 | 7.168 | 51.14 |
| P28 | DEHY-2.gas_out -> HDR-F.branch_04 | DN300 | CS-WET-160 | ground | +27.5324 | 6.2362 | 6.2314 | 0.0049 | 9.803 | 51.14 |
| P29 | DEHY-3.gas_out -> HDR-F.branch_01 | DN300 | CS-WET-160 | ground | +22.3350 | 6.2377 | 6.2314 | 0.0063 | 7.952 | 51.14 |
| P30 | HDR-F.branch_06 -> REG-WDR.gas_in | DN500 | CS-WET-160 | ground | +70.0000 | 6.2280 | 6.2264 | 0.0016 | 8.980 | 51.14 |
| P31 | REG-WDR.gas_out -> MTR-WDR.gas_in | DN500 | CS-WET-160 | ground | +70.0000 | 6.0264 | 6.0239 | 0.0024 | 9.268 | 50.90 |
| P32 | MTR-WDR.gas_out -> GRID-TIE.gas | DN500 | CS-WET-160 | ground | +70.0000 | 6.0039 | 6.0000 | 0.0039 | 9.304 | 50.90 |
| P36 | SEP-1.liquid_out -> DRN-1.drain_in | DN200 | CS-WET-100 | ground | +0.2012 | 1.00 (closed-drain domain) | 1.00 | - | 0.9794 | 51.1 |
| P37 | SEP-2.liquid_out -> DRN-2.drain_in | DN200 | CS-WET-100 | ground | +0.2752 | 1.00 (closed-drain domain) | 1.00 | - | 1.3393 | 51.1 |
| P38 | SEP-3.liquid_out -> DRN-3.drain_in | DN200 | CS-WET-100 | ground | +0.2232 | 1.00 (closed-drain domain) | 1.00 | - | 1.0865 | 51.1 |
| P39 | DRN-1.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.2012 | 1.00 (closed-drain domain) | 1.00 | - | 0.9794 | 51.1 |
| P40 | DRN-2.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.2752 | 1.00 (closed-drain domain) | 1.00 | - | 1.3393 | 51.1 |
| P41 | DRN-3.drain_out -> LIQUID-DRAIN-OUTFALL.gas | DN200 | CS-WET-100 | ground | +0.2232 | 1.00 (closed-drain domain) | 1.00 | - | 1.0865 | 51.1 |

</details>

## 8. Results

### 8.1 Delivery compliance

| Scenario | Sink | Delivered pressure (MPa) | Required (MPa) | Delivered temperature (degC) | Water (mg/Sm3) | Free liquid (kg/kg) |
|---|---|---|---|---|---|---|
| INJ-LOW | WG-01..WG-06 | 8.500000 (identical at all six well groups) | 8.500 | 50.25 | 40.00 | 0.000 |
| INJ-MID | WG-01..WG-06 | 11.000000 (identical at all six well groups) | 11.000 | 58.00 | 40.00 | 0.000 |
| INJ-HIGH | WG-01..WG-06 | 13.500000 (identical at all six well groups) | 13.500 | 58.00 | 40.00 | 0.000 |
| WDR-HIGH | GRID-TIE | 6.000000 | 6.000 | 13.10 | 35.00 | 5.0e-06 |
| WDR-MID | GRID-TIE | 6.000000 | 6.000 | 17.88 | 35.00 | 5.0e-06 |
| WDR-LOW | GRID-TIE | 6.000000 | 6.000 | 50.90 | 35.00 | 5.0e-06 |

Every delivery point is at or above the required pressure and inside the water,
free-liquid and temperature limits. The six well-group pressures equal the requirement to
within 1e-9 MPa because the well flowlines are hydraulically balanced.

### 8.2 Energy

| Scenario | Compressor power (MW) | Cooler electric (MW) | Dehydration (MW) | Total (MW) | Hours (h/yr) | Annual energy (MWh/yr) | Energy cost (MBCU/yr) |
|---|---|---|---|---|---|---|---|
| INJ-LOW | 7.732 | 0.000 | 0.000 | 7.732 | 900 | 6959.0 | 0.8351 |
| INJ-MID | 12.552 | 0.139 | 0.000 | 12.691 | 1300 | 16498.5 | 1.9798 |
| INJ-HIGH | 13.262 | 0.233 | 0.000 | 13.496 | 600 | 8097.5 | 0.9717 |
| WDR-HIGH | 0.000 | 0.000 | 2.160 | 2.160 | 500 | 1080.0 | 0.1296 |
| WDR-MID | 0.000 | 0.000 | 1.800 | 1.800 | 900 | 1620.0 | 0.1944 |
| WDR-LOW | 5.563 | 0.000 | 1.260 | 6.823 | 800 | 5458.4 | 0.6550 |
| **All scenarios** | | | | | **5000** | **39713.4** | **4.7656** |

### 8.3 Reliability

All 30 N-1 cases were evaluated with the retained flow fixed at 0.7 x scenario flow,
the failed unit isolated and the setpoints re-solved; 0 exceptions were found. The
delivery limits remain satisfied at every sink the scenario serves, and the retained flow
stays inside the capacity of the surviving equipment.

## 9. Quantities

```json
{
  "equipment_count": 21,
  "equipment_by_category": {
    "compressor": 3,
    "header": 5,
    "cooler": 1,
    "meter": 2,
    "regulator": 1,
    "separator": 3,
    "dehydration": 3,
    "closed_drain": 3
  },
  "pipe_length_total_m": 5423.837362334221,
  "pipe_length_by_dn": {
    "DN700": 503.0,
    "DN500": 843.0014204086917,
    "DN300": 2875.82577953381,
    "DN600": 309.01016239171906,
    "DN200": 893.0
  },
  "pipe_length_by_class": {
    "CS-DRY-160": 812.0101623917191,
    "CS-WET-160": 3718.827199942502,
    "CS-WET-100": 893.0
  },
  "pipe_length_by_level": {
    "ground": 5423.837362334221
  },
  "pipe_count": 36,
  "road_length_m": 1406.0,
  "footprint_area_m2": 775,
  "maintenance_area_m2": 1589.88
}
```

## 10. Lifecycle cost

### 10.1 Basis

`PVF = (1 - (1+i)^-N)/i` with i = 0.08 and N = 20 years = 9.81815. Equipment CAPEX is
the sum of catalogue capex over every installed instance. Piping CAPEX is summed over every
installed segment as length x diameter installed cost per metre x pipe-class multiplier x
routing-level multiplier. Civil/access CAPEX is road centreline length x road rate, plus
equipment footprint area x foundation rate, plus required maintenance-envelope area x
maintenance-area rate, plus pipeline length x the routing-level civil rate (charged for
every co-routed pipeline). Annual energy is the sum over scenarios of catalogued equipment
power or duty (compressors, aftercooler electric power, dehydration energy) times scenario
hours, and its present value is annual energy cost x PVF. Annual maintenance is the sum of
the installed models' annual maintenance values, present-valued with the same PVF.

### 10.2 Result

| LCC component | Value | Basis |
|---|---|---|
| Equipment CAPEX | 28.8400 MBCU | sum of installed catalogue capex_mbcu |
| Piping CAPEX | 1.8374 MBCU | sum over segments of length x DN rate x class multiplier x level multiplier |
| Civil / access CAPEX | 0.2156 MBCU | roads 0.2109 + foundations 0.0031 + maintenance areas 0.0016 + pipeline civil 0.0000 |
| Energy present value | 46.7894 MBCU | 39713.4 MWh/yr x 0.00012 MBCU/MWh x PVF 9.81815 |
| Maintenance present value | 10.2796 MBCU | 1.0470 MBCU/yr x PVF 9.81815 |
| **Lifecycle cost (objective)** | **87.9620 MBCU** | equipment + piping + civil + energy PV + maintenance PV |

### 10.3 Design choices driven by the cost basis

* Energy is the largest single component (46.79 MBCU of 87.96 MBCU). The design
  therefore minimises pressure ratio: discharge pressures are solved to the minimum that
  meets every delivery point, the common compression-path mains are DN600 to DN700, and the
  parallel well flowlines and treatment trains are balanced so that no delivery point is
  over-pressured.
* The measured marginal value of pressure loss on the compressor discharge path in this
  design is 0.81 MBCU of present value per 0.1 MPa, which is why the injection
  mains, the grid-tie inlet lines and the compressor suction/discharge lines were upsized
  beyond the velocity-limited size, while the well flowlines, treatment pipework and drain
  lines were kept at their cost-optimal size.
* Maintenance is the largest non-capital recurring term, which is why the compressor,
  header, meter, regulator and treatment items are all held at the smallest catalogue
  models whose rated capacity covers the largest scenario flow (the published rule treats
  a value at its limit as compliant), and why one compressor bank serves both directions
  instead of two.

## 11. Assumptions

1. `required_sink_pressure_mpa` is a minimum delivery pressure. The design nevertheless
   delivers exactly the required pressure at every sink (regulated at GRID-TIE, passively
   balanced at the well groups), so it also satisfies an equality interpretation.
2. Isolation and check valves are not catalogue components and are not modelled as physical
   items; the operating philosophy states the required line-up (section 5.3). Every
   scenario's declared flow set contains exactly one active path from its source to each
   sink, with zero declared flow on all other pipelines.
3. The compressor units run unloaded as passive pass-through elements in WDR-MID and
   WDR-HIGH (no lift required, zero driver power). The flow is shared between the units by
   their bypass line-up rather than by pipework resistance, because the two C60 suction and
   discharge paths differ by about 9 % in loss; the declared split is the bypass setting,
   and the C40 is isolated in those cases (section 5.4).
4. The delivery regulator is modelled as a pressure-reducing device that holds its setpoint
   when the inlet pressure is above it and passes freely below it; its setpoint is solved so
   that the GRID-TIE boundary pressure is exactly the required 6.000 MPa. No other pressure
   control device is fitted (see section 4.2).
5. The aftercooler is modelled with an outlet temperature setpoint; when the inlet is
   already below the setpoint the duty is zero.
6. Liquid-drain lines are checked with the only published density formulation - the gas
   property proxy - evaluated in the declared closed-drain domain, which is taken at the
   published maximum of 1.0 MPa. That is the conservative reading of the published velocity
   rule and it governs the drain size: the largest drain velocity is 2.06 m/s against
   the 3 m/s limit, while a condensate density of 1000 kg/m3 would give about 0.02 m/s.
   The drain lines are sized on the conservative case.
7. Compressor duty sharing between running units is a control setpoint (unit loading), not a
   passive split; the well flowlines and the treatment trains are solved as passive
   hydraulic balances, and the flow through unloaded units follows their bypass line-up
   (assumption 3).
8. Dehydration energy and cooler electric power are catalogued energy demands; electric
   power, instrument air and firewater are externally available abstract services whose
   availability and capacity are assumed sufficient, as published.
9. Gas properties use the published deterministic proxies only. No condensation,
   vaporisation, elevation or minor-loss effects are modelled, as published.
10. Routes are plan-view only (flat terrain, zero elevation). Road crossings are at grade in
    the model; in a detailed design they would be buried or sleeved.
11. `orientation_options_deg` limits each footprint rotation to 0 or 90 degrees; the design
    uses 0 degrees for the flow-through items and 90 degrees for the two grid-tie meters and
    the delivery regulator so that their one-way ports line up with the flow path.

## 12. Known limitations

* The design provides exactly the published N-1 redundancy: one compressor out of the bank
  and one treatment train. It does not provide maintenance spares beyond that.
* The aftercooler and the two regulators are not covered by the published N-1 requirement;
  their loss of service would require curtailment or an operating bypass.
* Two physically separate grid-tie lines are used (one per direction); the inactive line is
  isolated per scenario rather than being a bidirectional metering station.
* Withdrawal service passes through the compressor casings unloaded in WDR-MID and WDR-HIGH
  (assumption 3); a detailed design would add a valved bypass around the bank.
* Withdrawal gas is treated as dry of condensed liquid after separation - the published
  model induces no condensation - so low-point drainage, hydrate prevention and water dew
  point analysis are not included.
* No compressor suction pressure-control valve is fitted: the C40 suction limit is not
  binding in any required operating or reliability case. In the non-required contingency in
  which the C40 runs in WDR-HIGH it sits at 11.976 MPa against its 12 MPa limit, a
  margin of about 0.05 MPa; a design with less appetite for that margin would add a
  regulator (about 0.52 MBCU).
* The compressor units run at their rated capacity in the largest scenarios (60 kg/s each
  on the two C60 units at 120 kg/s station flow) because the published rule treats a value
  at its limit as compliant; a design preferring more headroom would use larger models.
* Relief, blowdown, flare, instrumentation, electrical, control, structural, civil drainage
  and firewater design are excluded scope, as are regulatory and code compliance and vendor
  procurement.
