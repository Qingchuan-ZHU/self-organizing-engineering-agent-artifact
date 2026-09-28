"""Generate the design report (markdown) from the verified model."""
import math, json, os
import lib_geom as G
import ugscat as U
import design as D
import solve as S
import sim as SIM

OUT = os.path.dirname(os.path.abspath(__file__))
eqmap, ifaces, pipes = S.build()
scens = {s["scenario_id"]: s for s in U.SCEN["scenarios"]}
sims = {sid: (SIM.sim_injection(sc, eqmap, pipes) if sc["service"] == "injection"
              else SIM.sim_withdrawal(sc, eqmap, pipes)) for sid, sc in scens.items()}

PVF = (1 - (1 + U.ECON["discount_rate"]) ** (-U.ECON["project_life_years"])) / U.ECON["discount_rate"]
eq_capex = sum(eqmap[e]["m"]["capex_mbcu"] for e in eqmap)
maint = sum(eqmap[e]["m"]["annual_maintenance_mbcu"] for e in eqmap)
pipe_capex = sum(p["length"] * U.DIAM[p["spec"]["dia"]]["installed_cost_mbcu_per_m"]
                 * U.CLS[p["spec"]["cls"]]["installed_cost_multiplier"]
                 * U.LEVELS[p["spec"]["level"]]["installed_cost_multiplier"] for p in pipes.values())
road_len = sum(math.dist(r["pts"][i], r["pts"][i + 1]) for r in D.ROADS.values() for i in range(len(r["pts"]) - 1))
found_area = sum(eq["m"]["footprint_m"]["length"] * eq["m"]["footprint_m"]["width"] for eq in eqmap.values())
env_by_eq = {eid: S.envelopes(eqmap[eid]) for eid in eqmap}
maint_area = 0.0
for eid, eq in eqmap.items():
    fa = eq["m"]["footprint_m"]["length"] * eq["m"]["footprint_m"]["width"]
    clr = [poly for k, poly in env_by_eq[eid] if k == "clearance"][0]
    rm = [poly for k, poly in env_by_eq[eid] if k == "removal"]
    env_area = G.poly_area(clr)
    if rm:
        env_area += G.poly_area(rm[0]) - G.convex_overlap_area(rm[0], clr)
    maint_area += max(0.0, env_area - fa)
road_capex = road_len * U.ECON["civil"]["road_mbcu_per_m"]
found_capex = found_area * U.ECON["civil"]["foundation_mbcu_per_m2"]
maint_area_capex = maint_area * U.ECON["civil"]["maintenance_area_mbcu_per_m2"]
civil_capex = road_capex + found_capex + maint_area_capex
energy = 0.0
for sid, sc in scens.items():
    r = sims[sid]
    e = (r["comp_power_total"] + r["cooler_power"]) if r["service"] == "injection" else (r["comp_power_total"] + r["dehy_energy"])
    energy += e * sc["annual_hours"]
energy_pv = energy * U.ECON["energy_tariff_mbcu_per_mwh"] * PVF
maint_pv = maint * PVF
LCC = eq_capex + pipe_capex + civil_capex + energy_pv + maint_pv

ver = json.load(open(os.path.join(OUT, "verification.json")))
nchecks = len(ver["checks"])
nfail = sum(1 for c in ver["checks"] if not c["ok"])

L = []
A = L.append

A("# UGS-SYNTH-D01 v1.1 - Underground Gas Storage Surface Facility")
A("")
A("## Design report")
A("")
A("Synthetic benchmark deliverable (case `UGS-SYNTH-D01`, version `1.1.0-development`). "
  "All data are deterministic benchmark assumptions, not vendor data or production engineering "
  "criteria. SI units are used throughout: metres, MPa, degC, kg/s, MW, MWh and MBCU; angles in "
  "degrees counter-clockwise. The site coordinate system is the plan frame defined in "
  "`site.json` (x east, y north, flat terrain at elevation 0).")
A("")
A("---")
A("")
A("## 1. Purpose, scope and objectives")
A("")
A("The facility connects a single grid tie point (`GRID-TIE`) to six public well-group "
  "interfaces (`WG-01`..`WG-06`). It must:")
A("")
A("* inject grid gas into the wells at three pressure levels;")
A("* withdraw well gas to the grid, conditioned to the project gas-delivery limits;")
A("* meter all gas exchanged at `GRID-TIE`;")
A("* remain serviceable after the loss of any one compressor (injection) or any one separator / "
  "dehydration unit (withdrawal), retaining at least 70 % of the affected scenario flow;")
A("* minimise the benchmark lifecycle cost (LCC) among feasible designs.")
A("")
A("Excluded scope (per `project_requirements.json`): reservoir model, well completion, full "
  "electrical/control systems, firewater synthesis, structural/civil/building detailed design, "
  "full process-safety study, code compliance and vendor procurement. Electric power, instrument "
  "air and firewater are externally available abstract services at the `POWER-TIE`, "
  "`INSTRUMENT-AIR-TIE` and `FIREWATER-TIE` boundaries; their distribution networks are out of "
  "scope and their capacity is assumed sufficient.")
A("")
A("### Operating scenarios (published)")
A("")
A("| Scenario | Service | h/y | Q (kg/s) | Source | P_source (MPa) | T_source (degC) | Water (mg/Sm3) | Free liquid | P_sink req. (MPa) | Sink |")
A("|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|")
for sid, sc in scens.items():
    A(f"| {sid} | {sc['service']} | {sc['annual_hours']} | {sc['required_total_flow_kg_s']} | "
      f"{sc['source_interface']} | {sc['source_pressure_mpa']} | {sc['source_temperature_c']} | "
      f"{sc['source_water_mg_sm3']} | {sc['source_free_liquid_mass_fraction']} | "
      f"{sc['required_sink_pressure_mpa']} | {', '.join(sc['sink_interfaces'])} |")
A("")
A(f"Total operating hours: {sum(s['annual_hours'] for s in scens.values())} h/y.")
A("")
A("Project delivery limits: free-liquid loading <= 1.0e-4 kg liquid/kg gas, water content "
  "<= 50 mg/Sm3, temperature within -10..60 degC.")
A("")
A("---")
A("")
A("## 2. Design basis and assumptions")
A("")
A("The calculation rules of `engineering_calculation_basis.md` (v1.1) and the geometry rules of "
  "`engineering_geometry_basis.md` (v1.1) are applied exactly. Key modelling conventions:")
A("")
A("* Gas properties: Z and viscosity from the published proxy correlations (with catalogue "
  "clamping); density from the real-gas expression; constant cp = 2450 J/(kg K) and k = 1.3.")
A("* Pipe pressure loss: Darcy-Weisbach with Swamee-Jain friction for Re >= 2300 and 64/Re "
  "otherwise, evaluated by the published fixed-point procedure at the representative mean "
  "pressure (max 8 updates, 1e-5 MPa convergence). No minor losses or elevation correction.")
A("* Compressor: `T_out = T_in (1 + (r^((k-1)/k)-1)/eta)`, "
  "`W = m cp T_in (r^((k-1)/k)-1)/(eta eta_driver)` with T_in in kelvin.")
A("* Regulator: `T_out = T_in - JT (P_in - P_out)` with JT = 1.2 K/MPa.")
A("* Header: `dP = pressure_drop_at_capacity (m/capacity)^2`.")
A("* Mixing: equal-pressure-weighted lowest-pressure rule; split conserves gas flow.")
A("")
A("Engineering assumptions adopted for this design (in addition to the brief):")
A("")
A("1. **Liquid line hydraulics:** the brief does not publish a liquid density. A condensate "
  "density of 700 kg/m3 is assumed for drain-line velocity checks (flow rates are ~0.6 kg/s, so "
  "velocities are ~0.05 m/s, far below the 3 m/s limit - the design is insensitive to this value).")
A("2. **Shared compressor bank:** the three reciprocating compressors serve both injection "
  "compression and the withdrawal boost through shared suction (`HDR-CS`) and discharge "
  "(`HDR-CD`) headers. Paths not used by a scenario are isolated by valves; valving itself is "
  "outside the modelled equipment scope.")
A("3. **Metering:** one metering string per flow direction satisfies the published metering rule "
  "(active capacity 160 kg/s >= 120 kg/s peak scenario flow). No metering n-1 is required by the "
  "brief and none is provided.")
A("4. **Regulation philosophy:** the withdrawal pressure regulator `REG-W` upstream of the "
  "treatment trains limits the treatment pressure to 6.5 MPa and sets the grid-tie delivery "
  "pressure; for WDR-LOW (source 4.5 MPa) the regulator passes through and the compressor bank "
  "provides the boost, delivering 6.20 MPa.")
A("5. **Dehydration regeneration / water disposal** are outside the process model, as stated in "
  "the brief.")
A("6. All process piping is at the `ground` routing level; no catalogue corridor is used.")
A("7. **Road ends:** road centrelines use butted (square) ends so that the paved geometry of the "
  "`ROAD-ENTRANCE` link terminates exactly on the site boundary rather than projecting outside "
  "it; interior road ends are also butted.")
A("8. **Access distances:** the published `road_access_buffer_m` (7 m) and `crane_access_buffer_m` "
  "(4.5 m) are applied to the shortest boundary-to-boundary distance between the required "
  "maintenance envelope and the nearest paved road, as defined in `engineering_geometry_basis.md`. "
  "Roads are nevertheless placed 0.5-2.7 m from the relevant envelopes.")
A("")
A("---")
A("")
A("## 3. Process architecture")
A("")
A("### 3.1 Functional decomposition")
A("")
A("```")
A("                          +-------------------------- INJECTION --------------------------+")
A("  GRID-TIE -- MTR-I -- HDR-CS -- [ C-1 C-2 (C-3 stby) ] -- HDR-CD -- COOL -- HDR-W -- 6 x WG")
A("                          +--------------------------- BOOST ----------------------------+")
A("")
A("  6 x WG -- HDR-W -- REG-W -- HDR-R -- ( SEP-1 -> DEH-1 ), ( SEP-2 -> DEH-2 ) -- HDR-T")
A("                                                                                   |")
A("                                            HDR-T -- HDR-M -- MTR-O -- GRID-TIE <----+")
A("                                            HDR-T -- HDR-CS -- compressors -- HDR-CD -- HDR-M   (boost)")
A("")
A("  liquid:  SEP-1.liquid_out -> DRN-1 -> LIQUID-DRAIN-OUTFALL")
A("           SEP-2.liquid_out -> DRN-2 -> LIQUID-DRAIN-OUTFALL")
A("```")
A("")
A("The design uses two service paths that share the well-side manifold `HDR-W` and the grid-side "
  "meters, consistent with the rule that only `gas_bidirectional` ports carry gas in either "
  "direction:")
A("")
A("* **Injection path** (grid -> wells): `GRID-TIE -> MTR-I -> HDR-CS -> compressors -> "
  "HDR-CD -> COOL -> HDR-W -> 6 well pipelines`.")
A("* **Withdrawal path** (wells -> grid): `6 well pipelines -> HDR-W -> REG-W -> HDR-R -> "
  "two parallel treatment trains (SEP + DEH) -> HDR-T -> HDR-M -> MTR-O -> GRID-TIE`. The "
  "WDR-LOW scenario is boosted: `HDR-T -> HDR-CS -> compressors -> HDR-CD -> HDR-M -> MTR-O -> "
  "GRID-TIE`.")
A("")
A("### 3.2 Shared compression")
A("")
A("A single 3-unit compressor bank (2 x C60 duty + 1 x C40) is manifolded between `HDR-CS` "
  "(suction) and `HDR-CD` (discharge). This topology avoids duplicating a second compression "
  "bank, since the WDR-LOW scenario (source 4.5 MPa) requires a boost to reach the 6.0 MPa grid "
  "tie, and saves ~13 MBCU of installed capital and maintenance relative to separate banks.")
A("")
A("### 3.3 Headers and branches used")
A("")
A("| Header | Model | Service | Branches used |")
A("|---|---|---|---|")
hdr_use = {}
for pid, p in D.PIPES.items():
    for ref in (p["a"], p["b"]):
        eid = ref.split(".")[0]
        if eid in eqmap and eqmap[eid]["m"]["category"] == "header":
            hdr_use.setdefault(eid, []).append(ref.split(".")[1])
hdr_desc = {"HDR-W": "well manifold / injection supply / withdrawal take-off",
            "HDR-R": "regulator outlet, split to 2 treatment trains",
            "HDR-T": "combine 2 treatment trains, feed grid or boost",
            "HDR-M": "select grid feed (direct or boosted)",
            "HDR-CS": "compressor suction manifold (injection feed / boost feed)",
            "HDR-CD": "compressor discharge manifold (cooler / boost discharge)"}
for hid in ["HDR-W", "HDR-R", "HDR-T", "HDR-M", "HDR-CS", "HDR-CD"]:
    A(f"| {hid} | {eqmap[hid]['model']} | {hdr_desc[hid]} | {len(hdr_use[hid])} |")
A("")
A("---")
A("")
A("## 4. Equipment selection and capacities")
A("")
A("| Tag | Model | Category | Safety category | x (m) | y (m) | Orient. (deg) | Capacity | Capex (MBCU) | Maint. (MBCU/y) |")
A("|---|---|---|---|---:|---:|---:|---:|---:|---:|")
for eid, eq in eqmap.items():
    m = eq["m"]
    cap = f"{m['capacity_kg_s']} kg/s"
    if m["category"] == "compressor":
        cap = f"{m['capacity_kg_s']} kg/s gas ({m['minimum_stable_flow_kg_s']}-{m['capacity_kg_s']})"
    A(f"| {eid} | {eq['model']} | {m['category']} | {m['safety_category']} | {eq['x']:.0f} | "
      f"{eq['y']:.0f} | {eq['orient']} | {cap} | {m['capex_mbcu']} | {m['annual_maintenance_mbcu']} |")
A("")
from collections import Counter
cnt = Counter(e["model"] for e in eqmap.values())
A("Model counts: " + ", ".join(f"{k} x {v}" for k, v in sorted(cnt.items())) + ".")
A("")
A("### 4.1 Compressor operating envelopes")
A("")
A("| Model | Capacity (kg/s) | Min stable (kg/s) | Max ratio | Max suction (MPa) | Max discharge (MPa) | Max T_disch (degC) | Max power (MW) | eta |")
A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for mid in ["C40", "C60"]:
    m = U.CAT[mid]
    A(f"| {mid} | {m['capacity_kg_s']} | {m['minimum_stable_flow_kg_s']} | {m['maximum_pressure_ratio']} | "
      f"{m['maximum_suction_pressure_mpa']} | {m['maximum_discharge_pressure_mpa']} | "
      f"{m['maximum_discharge_temperature_c']} | {m['maximum_power_mw']} | {m['efficiency_proxy']} |")
A("")
A("### 4.2 Why these models")
A("")
A("* **Compressors** - the compression n-1 rule requires, for INJ-LOW (120 kg/s), that 84 kg/s "
  "remains deliverable after the loss of any one unit. A 3-unit bank is therefore required, and "
  "{C60, C60, C40} is the minimum-capex combination meeting it (removing either C60 leaves "
  "100 kg/s; removing the C40 leaves 120 kg/s). The C80 was rejected: its higher capital cost "
  "outweighs the small efficiency gain at the modelled duty.")
A("* **Separators** - SEP120 is used because, with the upstream regulator holding pressure at "
  "6.5 MPa, its 10 MPa rating is adequate and its 120 kg/s capacity gives the required n-1 "
  "margin from a 2-train arrangement (one train = 120 kg/s >= 84 kg/s). A single stage at the "
  "published 0.9995 removal efficiency reduces the free-liquid loading from 1.0e-2 to 5.0e-6, "
  "already below the 1.0e-4 delivery limit, so no filter is required.")
A("* **Dehydration** - DEHY120 sets outlet water to 35 mg/Sm3 (<= 50). Two trains give the "
  "required n-1 margin; the upstream regulator keeps the unit pressure (10 MPa rating) in range.")
A("* **Cooler** - COOL120 is required to bring the compressor discharge (up to 95 degC at "
  "INJ-HIGH) below the 60 degC delivery limit; the outlet is controlled to 45 degC.")
A("* **Regulator** - REG180 (180 kg/s) covers the 120 kg/s peak in one unit; no regulator n-1 is "
  "required by the brief.")
A("* **Meters** - MTR160 provides 160 kg/s of active metering capacity per direction, exceeding "
  "the 1.0 x scenario-flow requirement.")
A("* **Drains** - DRN-L (2.0 kg/s) is sized so a single drain can carry the n-1 liquid rate "
  "(0.84 kg/s) as well as the normal 0.60 kg/s.")
A("")
A("---")
A("")
A("## 5. Physical process topology and pipelines")
A("")
A(f"{len(pipes)} pipelines are installed, total length {sum(p['length'] for p in pipes.values()):.1f} m. "
  "All are at the `ground` routing level.")
A("")
A("| Pipe | From (port) | To (port) | Medium | DN | Class | Level | Length (m) |")
A("|---|---|---|---|---|---|---|---:|")
for pid, p in pipes.items():
    sp = p["spec"]
    A(f"| {pid} | {sp['a']} | {sp['b']} | {sp.get('medium','gas')} | {sp['dia']} | {sp['cls']} | "
      f"{sp['level']} | {p['length']:.1f} |")
A("")
A("Port-type compatibility: every connection uses one of the permitted pairs "
  "(gas_out->gas_in/gas_bidirectional, gas_bidirectional->gas_in/gas_bidirectional, "
  "liquid_out->drain_in, drain_out->drain_in). Closed-drain outlets discharge directly to the "
  "`LIQUID-DRAIN-OUTFALL` boundary (2 of the 8 permitted connections, 1.2 kg/s of the 10 kg/s limit).")
A("")
A("---")
A("")
A("## 6. Operating philosophy and scenario plans")
A("")
A("### 6.1 Setpoints")
A("")
A(f"* Injection cooler outlet: 45 degC (cooler `COOL`).")
A(f"* Withdrawal grid pressure control (`REG-W`): 6.5 MPa (bypassed by pressure when the source "
  f"is lower, as in WDR-LOW).")
A(f"* Withdrawal boost (`WDR-LOW`): compressor discharge controlled to deliver 6.20 MPa at "
  f"`GRID-TIE`.")
A(f"* Injection: compressor discharge controlled to hold the lowest well-group pressure at the "
  f"scenario requirement + 0.1 MPa.")
A("")
A("### 6.2 Compressor dispatch and paths")
A("")
A("| Scenario | Active compressors | Flow per unit (kg/s) | Ratio | T_out (degC) | Bank power (MW) |")
A("|---|---|---:|---:|---:|---:|")
for sid in ["INJ-LOW", "INJ-MID", "INJ-HIGH", "WDR-HIGH", "WDR-MID", "WDR-LOW"]:
    r = sims[sid]
    if r.get("units"):
        units = ", ".join(u["id"] for u in r["units"])
        per = ", ".join(f"{u['flow']:.1f}" for u in r["units"])
        rr = max(u["ratio"] for u in r["units"])
        tt = max(u["T_out"] for u in r["units"])
        pw = r["comp_power_total"]
    elif r["comp"]:
        units, per = "C-1, C-2", f"{r['Q']/2:.1f}, {r['Q']/2:.1f}"
        rr, tt, pw = r["comp"]["ratio"], r["comp"]["T_out"], r["comp_power_total"]
    else:
        units, per, rr, tt, pw = "- (pressure let-down)", "-", "-", "-", "-"
    A(f"| {sid} | {units} | {per} | {rr if rr=='-' else format(rr,'.3f')} | "
      f"{tt if tt=='-' else format(tt,'.2f')} | {pw if pw=='-' else format(pw,'.3f')} |")
A("")
A("### 6.3 Per-scenario operating summary")
A("")
A("| Scenario | Delivered pressure (MPa) | Delivered T (degC) | Delivered water (mg/Sm3) | Delivered free liquid | Energy (MW) |")
A("|---|---:|---:|---:|---:|---:|")
for sid, sc in scens.items():
    r = sims[sid]
    if r["service"] == "injection":
        e = r["comp_power_total"] + r["cooler_power"]
        A(f"| {sid} | {r['Pwell']:.3f} (min well) | {r['Twell']:.1f} | {sc['source_water_mg_sm3']} | "
          f"{sc['source_free_liquid_mass_fraction']:.1e} | {e:.3f} |")
    else:
        e = r["comp_power_total"] + r["dehy_energy"]
        A(f"| {sid} | {r['delivered']:.3f} | {r['rec']['MTR-O']['T']:.1f} | 35 | 5.0e-06 | {e:.3f} |")
A("")
A("Notes:")
A("")
A("* Injection gas is delivered dry and liquid-free (source 40 mg/Sm3, no free liquid), so no "
  "treatment is required; only cooling is applied.")
A("* Withdrawal gas is separated (0.9995 efficiency) and dehydrated (35 mg/Sm3) before metering.")
A("* Well-group allocations are equal shares of the scenario flow (Q/6 per well); the peak "
  "allocation is 20 kg/s against the 25 kg/s per-interface limit.")
A("")
A("### 6.4 Reliability (n-1) provisions")
A("")
A("* **Compression n-1** (applies to all three injection scenarios and to WDR-LOW): after any "
  "one compressor is unavailable, the remaining two units provide at least 100 kg/s, exceeding "
  "the 70 % requirement (84 / 70 / 52.5 / 49 kg/s for INJ-LOW / INJ-MID / INJ-HIGH / WDR-LOW).")
A("* **Withdrawal treatment n-1**: each train is rated 120 kg/s; if one separator or one "
  "dehydration unit is unavailable, the surviving train alone provides 120 kg/s >= 84 kg/s.")
A("* **Delivery limits remain applicable after any outage** - the surviving equipment preserves "
  "the water, free-liquid and temperature limits.")
A("")
A("---")
A("")
A("## 7. Site layout, safety and maintenance access")
A("")
A("The plant is laid out on a 700 m x 450 m flat site. All footprints avoid the "
  "`FUTURE-EXPANSION`, `DRAINAGE-CHANNEL` and `GRID-FACILITY` no-build zones. A plan view is "
  "rendered in `layout.svg`.")
A("")
A("### 7.1 Footprint separation")
A("")
A("Boundary-to-boundary separations are verified against `safety_requirements.json` for every "
  "equipment pair (compressor/compressor 6 m, compressor/hydrocarbon-treatment 10 m, "
  "compressor/metering 6 m, compressor/pressure-control 8 m, compressor/drain 12 m, "
  "hydrocarbon-treatment/hydrocarbon-treatment 5 m, and so on). The layout is organised in a "
  "well-side header row (y = 225 m), two treatment trains (y = 170 m and y = 280 m) and an "
  "injection row (y ~ 320-445 m) with generous clearances.")
A("")
A("### 7.2 Maintenance envelopes")
A("")
A("* Every required routine-clearance envelope lies inside the site, avoids equipment-exclusion "
  "interiors and does not touch any other footprint.")
A("* Heavy-maintenance removal envelopes (compressors only) are also clear of all other "
  "footprints and of the exclusion zones.")
A(f"* Total required maintenance area: {maint_area:.1f} m2; total equipment footprint area: "
  f"{found_area:.1f} m2.")
A("")
A("### 7.3 Roads and access")
A("")
A(f"A {road_len:.0f} m single connected road network (6 m wide) links `ROAD-ENTRANCE` "
  "to the process area and provides access to every model that declares "
  "`road_access_required` (separators) and `crane_access_required` (compressors).")
A("")
A("| Road | Centreline | Width (m) | Length (m) |")
A("|---|---|---:|---:|")
for rid, r in D.ROADS.items():
    ln = sum(math.dist(r["pts"][i], r["pts"][i + 1]) for i in range(len(r["pts"]) - 1))
    A(f"| {rid} | {r['pts'][0]} -> {r['pts'][-1]} | {r['width']:.0f} | {ln:.0f} |")
A("")
A("---")
A("")
A("## 8. Piping classes and installation levels")
A("")
A("| Class | Max pressure (MPa) | T limits (degC) | Roughness (m) | Wet | Dry | Liquid drain | Multiplier |")
A("|---|---:|---|---:|---|---|---|---:|")
for c in U.PIPING["classes"]:
    A(f"| {c['class_id']} | {c['maximum_allowable_pressure_mpa']} | {c['temperature_limits_c']} | "
      f"{c['roughness_m']} | {c['wet_gas_compatible']} | {c['dry_gas_compatible']} | "
      f"{c['liquid_drain_compatible']} | {c['installed_cost_multiplier']} |")
A("")
A("All gas lines conveying the high-pressure injection/withdrawal gas use CS-WET-160 (16 MPa); "
  "post-regulation and suction-side lines use CS-WET-100 (10 MPa), which is compatible with both "
  "wet and dry gas. Liquid drain lines use CS-WET-100 (liquid-drain compatible).")
A("")
A("Peak gas velocities remain well below the 25 m/s limit (highest ~21 m/s at G-T-M during "
  "WDR-HIGH). Pipe diameters were selected by a lifecycle-cost optimisation: the additional "
  "capital of the larger sizes is outweighed by the reduction in compression energy.")
A("")
A("---")
A("")
A("## 9. Quantities and lifecycle cost")
A("")
A("### 9.1 Quantities")
A("")
A(f"* Equipment instances: {len(eqmap)} ({', '.join(f'{k} x {v}' for k, v in sorted(cnt.items()))})")
A(f"* Total installed pipeline length: {sum(p['length'] for p in pipes.values()):.1f} m")
A(f"* Road centreline length: {road_len:.1f} m")
A(f"* Equipment footprint area: {found_area:.1f} m2")
A(f"* Required maintenance area: {maint_area:.1f} m2")
A(f"* Annual energy consumption: {energy:.1f} MWh/y")
A("")
A("### 9.2 Lifecycle-cost basis")
A("")
A(f"* Present-value factor: PVF = (1 - 1.08^-20)/0.08 = {PVF:.6f}")
A(f"* Energy tariff: {U.ECON['energy_tariff_mbcu_per_mwh']} MBCU/MWh; "
  f"road: {U.ECON['civil']['road_mbcu_per_m']} MBCU/m; "
  f"foundation: {U.ECON['civil']['foundation_mbcu_per_m2']} MBCU/m2; "
  f"maintenance area: {U.ECON['civil']['maintenance_area_mbcu_per_m2']} MBCU/m2.")
A("")
A("### 9.3 LCC result")
A("")
A("| Component | Value (MBCU) |")
A("|---|---:|")
A(f"| Equipment CAPEX | {eq_capex:.4f} |")
A(f"| Piping CAPEX | {pipe_capex:.4f} |")
A(f"| Civil / access CAPEX | {civil_capex:.4f} |")
A(f"| Energy present value | {energy_pv:.4f} |")
A(f"| Maintenance present value | {maint_pv:.4f} |")
A(f"| **Total LCC** | **{LCC:.4f}** |")
A("")
A("Annual energy by scenario (MW x h):")
A("")
for sid, sc in scens.items():
    r = sims[sid]
    e = (r["comp_power_total"] + r["cooler_power"]) if r["service"] == "injection" else (r["comp_power_total"] + r["dehy_energy"])
    A(f"* {sid}: {e:.3f} MW x {sc['annual_hours']} h = {e*sc['annual_hours']:.1f} MWh")
A("")
A("---")
A("")
A("## 10. Verification")
A("")
A(f"An independent check script (`verify.py`) evaluates {nchecks} assertions covering geometry, "
  f"separation, maintenance envelopes, road access, port cardinality, pipe velocity and rating, "
  f"equipment capacities and pressure/temperature limits, compressor envelopes, delivery quality "
  f"limits, metering and the two n-1 rules. **{nchecks - nfail} of {nchecks} pass, {nfail} fail.** "
  "Full results are in `verification.json`.")
A("")
A("---")
A("")
A("## 11. Known limitations")
A("")
A("* Synthetic benchmark data only; no vendor quotations, no code compliance, no detailed "
  "mechanical, electrical, control, structural or civil design.")
A("* Valve-level isolation of inactive shared-header branches is stated but not modelled as "
  "equipment; dynamic/transient behaviour, surge, hydrate formation and liquid flashing are out "
  "of scope per the brief.")
A("* Water removed by dehydration, its regeneration stream and disposal are excluded.")
A("* The stated grid-tie delivery requirement is a minimum pressure; the design controls the "
  "grid pressure to 6.2-6.5 MPa. No maximum grid pressure is imposed by the brief.")
A("")
open(os.path.join(OUT, "design_report.md"), "w").write("\n".join(L) + "\n")
print("wrote design_report.md", len("\n".join(L)), "chars")
