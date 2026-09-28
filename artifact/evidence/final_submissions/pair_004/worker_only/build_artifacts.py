"""Build all final artifacts: design_output.json + quantities + LCC + checks."""
import sys, json, math, os
sys.path.insert(0, "/workspace/project")
import ugs_core as C
import ugs_analysis as A
import ugs_lcc as L
from ugs_design import load, load_catalog, INSTANCES, ROADS, footprint, envelope_rects, port_world

# ---- design options (fixed for the delivered design) ----
HIGH = set(["N-TS-REG", "N-TS-CW1", "N-TS-CW2", "N-DEH1-TS", "N-DEH2-TS", "N-DEH3-TS",
            "N-SEP1-DEH1", "N-SEP2-DEH2", "N-SEP3-DEH3", "N-WS-SEP1", "N-WS-SEP2", "N-WS-SEP3",
            "N-CI1-CH", "N-CI2-CH", "N-CI3-CH", "N-CH-COOL", "N-COOL-WS"] + [f"N-WS-WG{i}" for i in range(1, 7)])
WET = set(["N-WS-SEP1", "N-WS-SEP2", "N-WS-SEP3", "N-SEP1-DEH1", "N-SEP2-DEH2", "N-SEP3-DEH3"] + [f"N-WS-WG{i}" for i in range(1, 7)])


def class_for(nid, tbl):
    if (nid.startswith("N-SEP") and "-DRN" in nid) or nid.startswith("N-DRN"):
        return "CS-WET-100"
    if nid in HIGH:
        return "CS-WET-160" if nid in WET else "CS-DRY-160"
    return "CS-WET-100"


A.class_for = class_for
A.T_COOL = 58.0

# ---- convergence tracking on pipe loss ----
_orig_pout = A.pout
CONV = {"n": 0, "bad": 0}


def pout_track(P_in, m, D, L, eps, T):
    r = C.pipe_pressure_loss_mpa(P_in, m, D, L, eps, T, A.GP)
    CONV["n"] += 1
    if not r["converged"]:
        CONV["bad"] += 1
    return r["P_out"], r


A.pout = pout_track

diam = json.load(open("/workspace/project/diam_opt.json"))
dg = A.make_design()
dg["diam"] = diam
dg["Dyn"] = {nid: A.DIAM_MAP[dn]["internal_diameter_m"] for nid, dn in diam.items()}
dg["cls"] = {nid: class_for(nid, dg["tbl"]) for nid in A.LEN}
dg["epsn"] = {nid: A.CLASSES[dg["cls"][nid]]["roughness_m"] for nid in A.LEN}

del L.CHECKS[:]
res = L.solve_all(dg)
energy = L.check_scenarios(dg, res)
import nminus1
n1 = nminus1.run_all(dg)
lcc = L.compute_lcc(dg, energy)

print("pipe-loss evaluations:", CONV["n"], "non-converged:", CONV["bad"])
bad = [c for c in L.CHECKS if not c["ok"]]
print("checks:", len(L.CHECKS), "failed:", len(bad))
for b in bad:
    print("   FAIL", b["scenario"], b["tag"], b["message"])
print("LCC", round(lcc["lcc_mbcu"], 4))
print("breakdown", {k: round(v, 3) for k, v in lcc["breakdown"].items()})

# ---------------- assemble output document ----------------
CAT = A.CAT
out = {}
out["case"] = load("case.json")
out["design_basis"] = dict(
    T_aftercooler_c=A.T_COOL,
    operation=dict(
        injection="grid tie -> active meter -> grid-side header -> 2 x C60 (parallel, balanced) -> discharge header -> aftercooler -> well-side header -> 6 well lines",
        withdrawal_high_mid="6 well lines -> well-side header -> 3 x SEP70 -> 3 x DEHY70 -> treated header -> REG120 -> active meter -> grid tie",
        withdrawal_low="6 well lines -> well-side header -> 3 x SEP70 -> 3 x DEHY70 -> treated header -> 2 x C60 boosters -> active meter -> grid tie",
    ),
    velocities=dict(max_gas_m_s=A.GAS_VMAX, max_liquid_drain_m_s=A.LIQ_VMAX),
    liquid_density_assumption_kg_m3=A.CP_LIQ,
)

# equipment instances + ports
insts = []
for inst in INSTANCES:
    m = CAT[inst["model_id"]]
    ports = {}
    for p in m["ports"]:
        wx, wy = port_world(inst, CAT, p["id"])
        ports[p["id"]] = dict(type=p["type"], x=wx, y=wy)
    fr = footprint(inst, CAT)
    insts.append(dict(id=inst["id"], model_id=inst["model_id"], category=m["category"],
                      safety_category=m["safety_category"], x=inst["x"], y=inst["y"],
                      orientation_deg=inst["o"], footprint_m=dict(length=m["footprint_m"]["length"],
                                                                  width=m["footprint_m"]["width"]),
                      footprint_extent=[fr[0], fr[1], fr[2], fr[3]],
                      capacity_kg_s=m["capacity_kg_s"], capex_mbcu=m["capex_mbcu"],
                      annual_maintenance_mbcu=m["annual_maintenance_mbcu"], ports=ports,
                      heavy_maintenance=bool(m["maintenance"].get("heavy_maintenance"))))
out["equipment_instances"] = insts

out["external_interfaces"] = load("site.json")["external_interfaces"]
out["roads"] = [dict(id=r["id"], centreline=r["pts"], width_m=r["width"]) for r in ROADS]

# header port -> connection mapping
hdr_conn = {}
import nets as NETMOD
for n in NETMOD.NETS:
    pass
PORTASSIGN = {
    "H-GS": {"branch_02": "N-MTRINJ-GS", "branch_10": "N-GS-MTRWDR", "branch_06": "N-REG-GS",
             "branch_04": "N-GS-CI1", "branch_07": "N-GS-CI2", "branch_08": "N-GS-CI3",
             "branch_05": "N-CW1-GS", "branch_09": "N-CW2-GS"},
    "H-CH": {"branch_04": "N-CI1-CH", "branch_08": "N-CI2-CH", "branch_01": "N-CI3-CH",
             "branch_02": "N-CH-COOL"},
    "H-WS": {"branch_06": "N-COOL-WS", "branch_04": "N-WS-WG1", "branch_01": "N-WS-WG2",
             "branch_05": "N-WS-WG3", "branch_08": "N-WS-WG4", "branch_07": "N-WS-WG5",
             "branch_09": "N-WS-WG6", "branch_02": "N-WS-SEP1", "branch_10": "N-WS-SEP2",
             "branch_03": "N-WS-SEP3"},
    "H-TS": {"branch_04": "N-DEH1-TS", "branch_01": "N-DEH2-TS", "branch_02": "N-DEH3-TS",
             "branch_06": "N-TS-REG", "branch_03": "N-TS-CW1", "branch_10": "N-TS-CW2"},
}
out["header_port_assignments"] = PORTASSIGN

# pipelines
pipes = []
for n in NETMOD.NETS:
    nid = n["id"]
    pipes.append(dict(id=nid, service=n["service"], a=list(n["start"]), b=list(n["end"]),
                      nominal_diameter=diam[nid], class_id=dg["cls"][nid], level=A.LEVEL[nid],
                      length_m=round(A.LEN[nid], 3), segments=json.load(open("/workspace/project/routes.json"))[nid]["pts"]))
out["pipelines"] = pipes

# scenarios
scen_out = []
for s in A.SCEN:
    r = res[s["id"]]
    e = dict(id=s["id"], service=s["service"], required_total_flow_kg_s=s["m"],
             source_interface=("GRID-TIE" if s["service"] == "injection" else "well_groups"),
             sink_interfaces=(["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"]
                              if s["service"] == "injection" else ["GRID-TIE"]),
             source_pressure_mpa=s["Psrc"], source_temperature_c=s["Tsrc"],
             required_sink_pressure_mpa=s["Psink"], annual_hours=s["hours"],
             equipment_power_mw=round(energy[s["id"]], 4))
    if s["service"] == "injection":
        e["well_group_allocation_kg_s"] = {f"WG-0{i}": round(s["m"] / 6, 4) for i in range(1, 7)}
        e["compressor_state"] = {k: dict(suction_mpa=round(v["Ps"], 3), discharge_mpa=round(v["Pd"], 3),
                                         ratio=round(v["r"], 4), outlet_c=round(v["To"], 2),
                                         flow_kg_s=v["q"]) for k, v in r["comp"].items()}
        e["P_GS_mpa"] = round(r["P_GS"], 3)
        e["P_CH_mpa"] = round(r["P_CH"], 3)
        e["cooler_outlet_c"] = round(r["Tcool"], 2)
        e["well_pressures_mpa"] = {f"WG-0{i}": round(r["wells"][i - 1][0], 3) for i in range(1, 7)}
    else:
        e["well_group_allocation_kg_s"] = {f"WG-0{i}": round(s["m"] / 6, 4) for i in range(1, 7)}
        e["P_WS_mpa"] = round(r["P_WS"], 3)
        e["P_TS_mpa"] = round(r["P_TS"], 3)
        if s["id"] in ("WDR-HIGH", "WDR-MID"):
            e["regulator"] = dict(inlet_mpa=round(r["P_reg_in"], 3), outlet_mpa=round(r["Preg_out"], 3),
                                  outlet_c=round(r["Tdel"], 2))
        else:
            e["boosters"] = [dict(id=c["id"], suction_mpa=round(c["Ps"], 3), discharge_mpa=round(c["Pd"], 3),
                                  ratio=round(c["r"], 4), power_mw=round(c["W"], 3), flow_kg_s=c["q"])
                             for c in r["comp"]]
            e["booster_outlet_c"] = round(r["Tdel"], 2)
        e["delivered_water_mg_sm3"] = CAT["DEHY70"]["normal_outlet_water_mg_sm3"]
        e["delivered_free_liquid_fraction"] = round(s["fl"] * (1 - CAT["SEP70"]["liquid_removal_efficiency"]), 8)
        e["P_grid_tie_mpa"] = round(r["Pgrid"], 3)
    scen_out.append(e)
out["scenario_results"] = scen_out

out["n_minus_one"] = n1
out["checks"] = L.CHECKS
out["quantities"] = dict(
    equipment_count={},
    total_pipe_length_m=round(sum(A.LEN.values()), 3),
    pipe_length_by_dn={},
    road_length_m=round(lcc["civil"]["road_length_m"], 3),
    footprint_area_m2=round(lcc["civil"]["footprint_area_m2"], 3),
    maintenance_area_m2=round(lcc["civil"]["maintenance_area_m2"], 3),
)
from collections import Counter
cnt = Counter(i["model_id"] for i in INSTANCES)
out["quantities"]["equipment_count"] = dict(cnt)
bydn = Counter()
for nid, d in diam.items():
    bydn[d] += A.LEN[nid]
out["quantities"]["pipe_length_by_dn"] = {k: round(v, 2) for k, v in sorted(bydn.items())}
out["lcc"] = lcc

out["assumptions_and_limitations"] = [
    "All values follow the synthetic v1.1 deterministic basis; they are not vendor or production data.",
    "Liquid-drain velocity uses an assumed liquid density of 1000 kg/m3 (the basis provides only a gas density law).",
    "Inactive branches are treated as isolated by valves per the published operating philosophy; a scenario only carries flow on its active path.",
    "Compressor bank: 2 x C60 in normal service with one C40 spare provides compression N-1 for injection; 2 x C60 boosters provide N-1 for WDR-LOW.",
    "Pipe bores were selected to minimise lifecycle cost subject to the 25 m/s (gas) and 3 m/s (liquid) velocity limits.",
    "No elevation, minor losses, or heat transfer between equipment are modelled (per basis).",
]

with open("/workspace/project/design_output.json", "w") as f:
    json.dump(out, f, indent=1)
print("wrote design_output.json")
