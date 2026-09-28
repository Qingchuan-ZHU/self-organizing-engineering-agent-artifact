TEMPLATE = r"""# UGS-SYNTH-D01 v1.1 - Underground gas storage surface facilities design report

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
* Economic basis: discount rate {rate}, project life {life} years, PVF = {pvf},
  energy tariff 0.00012 MBCU/MWh, road {road_rate} MBCU/m, foundations {found_rate} MBCU/m2,
  maintenance area {maint_rate} MBCU/m2.

### 3.1 Operating scenarios

{scenario_table}

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

{equipment}

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
{c40_idle_delta} MBCU of present value, so it is left isolated.

**Withdrawal inlet path - piping only.** In WDR-HIGH the well groups deliver at 12 MPa while
the C40 unit's published maximum suction pressure is 12 MPa, so the C40 is isolated in the
two high-pressure withdrawal scenarios (which need no pressure lift and therefore carry no
published compressor N-1 requirement anyway); it runs in withdrawal service only in WDR-LOW,
where the inlet is 4.46 MPa. The withdrawal inlet line is DN350 and the compressor bus is
therefore protected by the inlet path losses: in the informative contingency in which the
C40 has to run in WDR-HIGH with one C60 unavailable, its suction is {c40_suction} MPa, just
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

{operating_table}

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
  {train_split}). The same applies to the two C60 unit paths when they carry gas unloaded;
  the small difference between those two pipe paths is taken up by the unit bypass valves
  (assumption 3).
* **Compressor discharge pressure** is solved per scenario as the minimum value that
  satisfies every delivery point: {inj_low} MPa (INJ-LOW), {inj_mid} MPa (INJ-MID) and
  {inj_high} MPa (INJ-HIGH). Discharge pressure is held as low as the requirement permits
  because compressor power is the dominant lifecycle component.
* **Aftercooler outlet** is controlled to 58.0 degC, 2 K inside the 60 degC delivery limit.
  When the compressor discharge is already below the setpoint (INJ-LOW), the cooler passes
  the gas with zero duty.
* **Withdrawal compressor discharge pressure** is held just above the delivery regulator's
  inlet requirement ({wdr_discharge} MPa in WDR-LOW) so the regulator always has positive
  letdown. In WDR-MID and WDR-HIGH no lift is required and the units pass the gas at equal
  inlet and outlet pressure with zero driver power.
* **Delivery regulator setpoint** is solved so the GRID-TIE boundary pressure is exactly
  6.000 MPa, including the outlet metering-line loss ({reg_setpoint} MPa in WDR-LOW).
* **Metering lines** are in service in the active direction only.

### 5.3 Isolation (line-up) schedule

The published model contains no valve components, so isolation is stated as an operating
requirement. Each scenario uses one of the two station sections; the other is isolated at
both ends, so no unaccounted flow path exists in any scenario, and each compressor has unit
isolation and discharge check valves so a failed unit can be taken out of service.

{valve_schedule}

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

{sep}

### 6.3 Maintenance envelopes and access

Clearance envelopes are mitered expansions of the footprints. The five compressor units
carry heavy-maintenance removal envelopes on their local east side, all facing the
north-south road at x = 421 m; the largest distance from a required envelope boundary to the
paved road boundary is {crane_max:.2f} m against the 4.5 m crane-access buffer. The
separator clearance envelopes are {sep_max:.2f} m from the paved road at x = 478 m against
the 7 m road-access buffer. No other model declares a road or crane access requirement.
Every required envelope lies inside the site, outside the equipment-exclusion zones and
clear of other footprints; total required maintenance area (envelope minus footprint) is
{maint_area:.1f} m2. All access distances are measured to the full-width paved boundary.

### 6.4 Road network

Four 6 m wide roads (minimum permitted width 4 m) form one connected network containing the
ROAD-ENTRANCE point: the main east-west road (x = 0 to 660 m at y = 225 m), a north-south
road at x = 421 m serving both compressor areas, an east-west road at y = 120 m serving the
treatment area and drain outfall, and a north-south road at x = 478 m giving the treatment
trains their road access. Total road centreline length is {road_len:.0f} m; road CAPEX uses
centreline length at {road_rate} MBCU/m and does not vary with width.

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

{pipelines}

Full route coordinates and installation levels are in `pipeline_schedule.csv`,
`process_topology.json` and `scenario_operations.json`.

### 7.3 Scenario hydraulics

{hydraulics}

## 8. Results

### 8.1 Delivery compliance

| Scenario | Sink | Delivered pressure (MPa) | Required (MPa) | Delivered temperature (degC) | Water (mg/Sm3) | Free liquid (kg/kg) |
|---|---|---|---|---|---|---|
| INJ-LOW | WG-01..WG-06 | {p01} | 8.500 | {p01t} | 40.00 | 0.000 |
| INJ-MID | WG-01..WG-06 | {p02} | 11.000 | {p02t} | 40.00 | 0.000 |
| INJ-HIGH | WG-01..WG-06 | {p03} | 13.500 | {p03t} | 40.00 | 0.000 |
| WDR-HIGH | GRID-TIE | {p04} | 6.000 | {p04t} | 35.00 | 5.0e-06 |
| WDR-MID | GRID-TIE | {p05} | 6.000 | {p05t} | 35.00 | 5.0e-06 |
| WDR-LOW | GRID-TIE | {p06} | 6.000 | {p06t} | 35.00 | 5.0e-06 |

Every delivery point is at or above the required pressure and inside the water,
free-liquid and temperature limits. The six well-group pressures equal the requirement to
within 1e-9 MPa because the well flowlines are hydraulically balanced.

### 8.2 Energy

{energy_table}

### 8.3 Reliability

All {n_cases} N-1 cases were evaluated with the retained flow fixed at 0.7 x scenario flow,
the failed unit isolated and the setpoints re-solved; {rel_fail} exceptions were found. The
delivery limits remain satisfied at every sink the scenario serves, and the retained flow
stays inside the capacity of the surviving equipment.

## 9. Quantities

```json
{quantities}
```

## 10. Lifecycle cost

### 10.1 Basis

`PVF = (1 - (1+i)^-N)/i` with i = {rate} and N = {life} years = {pvf}. Equipment CAPEX is
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

{lcc_table}

### 10.3 Design choices driven by the cost basis

* Energy is the largest single component ({energy_pv} MBCU of {lcc} MBCU). The design
  therefore minimises pressure ratio: discharge pressures are solved to the minimum that
  meets every delivery point, the common compression-path mains are DN600 to DN700, and the
  parallel well flowlines and treatment trains are balanced so that no delivery point is
  over-pressured.
* The measured marginal value of pressure loss on the compressor discharge path in this
  design is {loss_sensitivity} MBCU of present value per 0.1 MPa, which is why the injection
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
   rule and it governs the drain size: the largest drain velocity is {drain_v} m/s against
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
  which the C40 runs in WDR-HIGH it sits at {c40_suction} MPa against its 12 MPa limit, a
  margin of about 0.05 MPa; a design with less appetite for that margin would add a
  regulator (about 0.52 MBCU).
* The compressor units run at their rated capacity in the largest scenarios (60 kg/s each
  on the two C60 units at 120 kg/s station flow) because the published rule treats a value
  at its limit as compliant; a design preferring more headroom would use larger models.
* Relief, blowdown, flare, instrumentation, electrical, control, structural, civil drainage
  and firewater design are excluded scope, as are regulatory and code compliance and vendor
  procurement.
"""
