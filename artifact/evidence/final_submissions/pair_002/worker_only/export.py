"""Export the complete, reconstructable design to design.json."""
import json, math, os
from collections import Counter
import lib_geom as G
import ugscat as U
import design as D
import solve as S
import sim as SIM

OUT = os.path.dirname(os.path.abspath(__file__))

eqmap, ifaces, pipes = S.build()
scens = {s["scenario_id"]: s for s in U.SCEN["scenarios"]}
env_by_eq = {eid: S.envelopes(eqmap[eid]) for eid in eqmap}

sims = {}
for sid, sc in scens.items():
    sims[sid] = SIM.sim_injection(sc, eqmap, pipes) if sc["service"] == "injection" \
        else SIM.sim_withdrawal(sc, eqmap, pipes)

doc = {
    "case": "UGS-SYNTH-D01 v1.1",
    "units": {"length": "m", "pressure": "MPa", "temperature": "degC", "flow": "kg/s",
              "power": "MW", "energy": "MWh", "cost": "MBCU", "velocity": "m/s"},
    "coordinate_system": "site plan metres, x east, y north, all routes at level 'ground'",
    "assumptions": [
        "Synthetic benchmark data only; not production criteria.",
        "Drain/liquid line hydraulic velocity uses an assumed liquid density of 700 kg/m3.",
        "Inactive branches of the shared compressor headers are isolated by valves (not modelled).",
        "Water removed by dehydration and its regeneration/disposal are outside the process model.",
        "Metering is single-string per flow direction (no n-1 required by the brief).",
    ],
    "interfaces": {iid: dict(id=it["id"], pos=list(it["pos"]), port_type=it["port_type"],
                             maximum_connections=it["maximum_connections"],
                             maximum_flow_kg_s=it["maximum_flow_kg_s"])
                   for iid, it in ifaces.items()},
    "equipment": {},
    "pipes": {},
    "roads": {},
    "scenarios": {},
}

for eid, eq in eqmap.items():
    m = eq["m"]
    doc["equipment"][eid] = dict(
        model_id=eq["model"], category=m["category"], safety_category=m["safety_category"],
        x=eq["x"], y=eq["y"], orientation_deg=eq["orient"],
        footprint_m=m["footprint_m"], footprint_polygon_m=[[round(a, 4), round(b, 4)] for a, b in eq["poly"]],
        capacity_kg_s=m["capacity_kg_s"], capex_mbcu=m["capex_mbcu"],
        annual_maintenance_mbcu=m["annual_maintenance_mbcu"],
        ports={pid: dict(type=pp["type"], offset_m=list(pp["offset"]), pos=[round(v, 4) for v in pp["pos"]])
               for pid, pp in eq["ports"].items()},
        maintenance=m["maintenance"],
        maintenance_envelopes_m={k: [[round(a, 4), round(b, 4)] for a, b in poly] for k, poly in env_by_eq[eid]},
        limits={k: v for k, v in m.items()
                if k in ("maximum_pressure_mpa", "pressure_drop_mpa", "maximum_pressure_ratio",
                         "minimum_stable_flow_kg_s", "maximum_suction_pressure_mpa",
                         "maximum_discharge_pressure_mpa", "maximum_suction_temperature_c",
                         "maximum_discharge_temperature_c", "maximum_power_mw",
                         "efficiency_proxy", "driver_efficiency", "liquid_removal_efficiency",
                         "maximum_feed_free_liquid_fraction", "maximum_liquid_rate_kg_s",
                         "normal_outlet_water_mg_sm3", "energy_mw_per_kg_s",
                         "minimum_outlet_temperature_c", "maximum_duty_mw",
                         "electric_power_fraction_of_duty", "maximum_outlet_temperature_c",
                         "jt_temperature_coefficient_k_per_mpa", "maximum_branch_connections",
                         "pressure_drop_at_capacity_mpa")},
    )

# port type lookup for pipes
def port_type(ref):
    eid, pname = ref.split(".")
    if eid in eqmap:
        return eqmap[eid]["ports"][pname]["type"]
    return ifaces[eid]["port_type"]

for pid, p in pipes.items():
    sp = p["spec"]
    d = U.DIAM[sp["dia"]]
    cl = U.CLS[sp["cls"]]
    doc["pipes"][pid] = dict(
        a=sp["a"], b=sp["b"], a_port_type=port_type(sp["a"]), b_port_type=port_type(sp["b"]),
        medium=sp.get("medium", "gas"), nominal_diameter=sp["dia"],
        internal_diameter_m=d["internal_diameter_m"], pipe_class=sp["cls"],
        class_max_pressure_mpa=cl["maximum_allowable_pressure_mpa"],
        class_temperature_limits_c=cl["temperature_limits_c"], roughness_m=cl["roughness_m"],
        routing_level=sp["level"], corridor=sp.get("corridor"),
        route_m=[[round(a, 4), round(b, 4)] for a, b in p["pts"]],
        length_m=round(p["length"], 4),
        segments=[dict(a=[round(s["a"][0], 4), round(s["a"][1], 4)],
                       b=[round(s["b"][0], 4), round(s["b"][1], 4)],
                       length_m=round(math.dist(s["a"], s["b"]), 4), level=s["level"]) for s in p["segs"]],
    )

for rid, r in D.ROADS.items():
    hw = r["width"] / 2
    doc["roads"][rid] = dict(width_m=r["width"], centreline_m=r["pts"],
                             length_m=round(sum(math.dist(r["pts"][i], r["pts"][i + 1])
                                                for i in range(len(r["pts"]) - 1)), 3))

for sid, sc in scens.items():
    r = sims[sid]
    entry = dict(scenario_id=sid, service=sc["service"], annual_hours=sc["annual_hours"],
                 required_total_flow_kg_s=sc["required_total_flow_kg_s"],
                 source_interface=sc["source_interface"], sink_interfaces=sc["sink_interfaces"],
                 source_pressure_mpa=sc["source_pressure_mpa"],
                 source_temperature_c=sc["source_temperature_c"],
                 source_water_mg_sm3=sc["source_water_mg_sm3"],
                 source_free_liquid_mass_fraction=sc["source_free_liquid_mass_fraction"],
                 required_sink_pressure_mpa=sc["required_sink_pressure_mpa"],
                 pipe_operating_points={}, equipment_operating_points={})
    for pid, o in r["rec"].items():
        e = dict(P_out_mpa=round(o.get("P", 0), 4), T_c=round(o.get("T", 0), 3))
        if "v" in o:
            e.update(flow_kg_s=o.get("m"), velocity_m_s=round(o["v"], 4),
                     Re=round(o["Re"], 1), loss_mpa=round(o.get("dP", 0), 4) if "dP" in o else None)
        if "dP" in o:
            e.update(kind="header", dP_mpa=round(o["dP"], 5), flow_kg_s=o.get("m"))
        e["kind"] = "header" if "dP" in o else ("pipe" if "v" in o else "equipment")
        entry["pipe_operating_points"][pid] = e
    if r["service"] == "injection":
        entry["well_group_flows_kg_s"] = {w: r["Q"] / 6 for w in D.WELL_IDS}
        entry["compressor_bank"] = dict(units=r["units"], total_power_mw=round(r["comp_power_total"], 4))
        entry["cooler"] = dict(outlet_T_c=round(r["cooler_outlet_T"], 3), duty_mw=round(r["cooler_duty"], 4),
                               electric_power_mw=round(r["cooler_power"], 4))
        entry["delivered"] = dict(min_well_pressure_mpa=round(r["Pwell"], 4),
                                  temperature_c=round(r["Twell"], 3),
                                  water_mg_sm3=sc["source_water_mg_sm3"],
                                  free_liquid_mass_fraction=sc["source_free_liquid_mass_fraction"])
    else:
        entry["well_group_flows_kg_s"] = {w: r["Q"] / 6 for w in D.WELL_IDS}
        entry["dehydration_energy_mw"] = round(r["dehy_energy"], 4)
        entry["separator_liquid"] = {k: dict(removed_kg_s=round(v["m_removed"], 5),
                                             outlet_free_liquid=v["f_out"]) for k, v in r["liquid"].items()}
        if r["boost"]:
            entry["compressor_bank"] = dict(units=[r["comp"]], total_power_mw=round(r["comp_power_total"], 4))
        entry["delivered"] = dict(grid_tie_pressure_mpa=round(r["delivered"], 4),
                                  temperature_c=round(r["rec"]["MTR-O"]["T"], 3),
                                  water_mg_sm3=35.0, free_liquid_mass_fraction=5.0e-6)
    # explicit active operating path (ordered) and isolated branches
    if r["service"] == "injection":
        path = ["GRID-TIE", "G-TIE-IN", "MTR-I", "G-IN-1", "HDR-CS",
                "G-C1S", "C-1", "G-C1D", "G-C2S", "C-2", "G-C2D",
                "HDR-CD", "G-CD-CL", "COOL", "G-CL-W", "HDR-W"]
        for wp, wid in zip(D.WELL_PIPES, D.WELL_IDS):
            path += [wp, wid]
    else:
        path = []
        for wp, wid in zip(D.WELL_PIPES, D.WELL_IDS):
            path += [wid, wp]
        path += ["HDR-W", "G-W-REG", "REG-W", "G-REG-R", "HDR-R"]
        for rs, sep, sd, deh, dt in [("G-R-S1", "SEP-1", "G-S1-D1", "DEH-1", "G-D1-T"),
                                     ("G-R-S2", "SEP-2", "G-S2-D2", "DEH-2", "G-D2-T")]:
            path += [rs, sep, sd, deh, dt]
        if r["boost"]:
            path += ["HDR-T", "G-T-CS", "HDR-CS", "G-C1S", "C-1", "G-C1D", "G-C2S", "C-2",
                     "G-C2D", "HDR-CD", "G-CD-M", "HDR-M", "G-M-TO", "MTR-O", "G-TO-TIE", "GRID-TIE"]
        else:
            path += ["HDR-T", "G-T-M", "HDR-M", "G-M-TO", "MTR-O", "G-TO-TIE", "GRID-TIE"]
    entry["operating_path"] = path
    active = set(k for k in r["rec"].keys() if k in pipes)
    entry["active_pipes"] = sorted(active)
    entry["pipes_with_zero_flow"] = sorted(set(pipes.keys()) - active)
    doc["scenarios"][sid] = entry

# ---- quantities + LCC -------------------------------------------------
PVF = (1 - (1 + U.ECON["discount_rate"]) ** (-U.ECON["project_life_years"])) / U.ECON["discount_rate"]
eq_capex = sum(eqmap[e]["m"]["capex_mbcu"] for e in eqmap)
maint = sum(eqmap[e]["m"]["annual_maintenance_mbcu"] for e in eqmap)
pipe_capex = sum(p["length"] * U.DIAM[p["spec"]["dia"]]["installed_cost_mbcu_per_m"]
                 * U.CLS[p["spec"]["cls"]]["installed_cost_multiplier"]
                 * U.LEVELS[p["spec"]["level"]]["installed_cost_multiplier"] for p in pipes.values())
road_len = sum(math.dist(r["pts"][i], r["pts"][i + 1]) for r in D.ROADS.values() for i in range(len(r["pts"]) - 1))
found_area = sum(eq["m"]["footprint_m"]["length"] * eq["m"]["footprint_m"]["width"] for eq in eqmap.values())
maint_area = 0.0
for eid, eq in eqmap.items():
    fa = eq["m"]["footprint_m"]["length"] * eq["m"]["footprint_m"]["width"]
    clr = [q for k, q in env_by_eq[eid] if k == "clearance"][0]
    rm = [q for k, q in env_by_eq[eid] if k == "removal"]
    a = G.poly_area(clr)
    if rm:
        a += G.poly_area(rm[0]) - G.convex_overlap_area(rm[0], clr)
    maint_area += max(0.0, a - fa)
civil = (road_len * U.ECON["civil"]["road_mbcu_per_m"]
         + found_area * U.ECON["civil"]["foundation_mbcu_per_m2"]
         + maint_area * U.ECON["civil"]["maintenance_area_mbcu_per_m2"])
energy = sum(((sims[s]["comp_power_total"] + sims[s]["cooler_power"]) if scens[s]["service"] == "injection"
              else (sims[s]["comp_power_total"] + sims[s]["dehy_energy"])) * scens[s]["annual_hours"] for s in scens)
energy_pv = energy * U.ECON["energy_tariff_mbcu_per_mwh"] * PVF
maint_pv = maint * PVF
doc["quantities"] = dict(
    equipment_count=len(eqmap),
    model_counts=dict(Counter(eq["model"] for eq in eqmap.values())),
    pipe_count=len(pipes), pipeline_length_m=round(sum(p["length"] for p in pipes.values()), 3),
    road_length_m=round(road_len, 3), footprint_area_m2=round(found_area, 3),
    maintenance_area_m2=round(maint_area, 3), annual_energy_mwh=round(energy, 3),
    pipe_length_by_class=dict(Counter({p["spec"]["cls"]: 0 for p in pipes.values()})),
)
plc = {}
for p in pipes.values():
    plc[p["spec"]["cls"]] = plc.get(p["spec"]["cls"], 0) + p["length"]
doc["quantities"]["pipe_length_by_class"] = {k: round(v, 2) for k, v in plc.items()}
doc["lcc_mbcu"] = dict(pvf=PVF, equipment_capex=round(eq_capex, 4), piping_capex=round(pipe_capex, 4),
                       civil_capex=round(civil, 4), energy_present_value=round(energy_pv, 4),
                       maintenance_present_value=round(maint_pv, 4),
                       total=round(eq_capex + pipe_capex + civil + energy_pv + maint_pv, 4),
                       annual_energy_mwh=round(energy, 3),
                       annual_maintenance_mbcu=round(maint, 4))

with open(os.path.join(OUT, "design.json"), "w") as f:
    json.dump(doc, f, indent=1)
print("wrote design.json", os.path.getsize(os.path.join(OUT, "design.json")), "bytes")
