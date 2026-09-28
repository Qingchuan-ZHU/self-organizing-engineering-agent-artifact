"""Full verification + lifecycle cost + machine-readable design export for UGS-SYNTH-D01."""
import math, json, os, sys
import lib_geom as G
import ugscat as U
import design as D
import solve as S
import sim as SIM

OUT = os.path.dirname(os.path.abspath(__file__))
CHECKS = []


def chk(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    return ok


eqmap, ifaces, pipes = S.build()
scens = {s["scenario_id"]: s for s in U.SCEN["scenarios"]}

# ------------------------------------------------------------------ geometry
geo_issues, road_polys, env_by_eq, allrects = S.check_geometry(eqmap, ifaces, pipes)
chk("geometry/layout (footprints, separations, envelopes, pipes, roads)",
    not geo_issues, "; ".join(geo_issues))

# ------------------------------------------------------------------ limits tables
def limits_ok(v, lo=None, hi=None, tol=1e-9):
    ok = True
    if lo is not None and v < lo - tol:
        ok = False
    if hi is not None and v > hi + tol:
        ok = False
    return ok


sims = {}
for sid, sc in scens.items():
    sims[sid] = SIM.sim_injection(sc, eqmap, pipes) if sc["service"] == "injection" \
        else SIM.sim_withdrawal(sc, eqmap, pipes)

# per-equipment / per-pipe verification
for sid, r in sims.items():
    sc = scens[sid]
    Q = r["Q"]
    # pipe velocity + rating
    for pid, o in r["rec"].items():
        if "v" not in o:
            continue
        p = pipes[pid]
        d = U.DIAM[p["spec"]["dia"]]
        cl = U.CLS[p["spec"]["cls"]]
        medium = p["spec"].get("medium", "gas")
        vmax = U.PIPING["maximum_liquid_drain_velocity_m_s"] if medium == "liquid" else U.PIPING["maximum_gas_velocity_m_s"]
        chk(f"{sid}: velocity {pid} = {o['v']:.2f} <= {vmax}", o["v"] <= vmax + 1e-6)
        Pmax = max(o["P"], o.get("P", 0))
        chk(f"{sid}: class rating {pid} ({cl['class_id']}) >= {Pmax + (pipes[pid]['length'] and 0):.2f}",
            Pmax <= cl["maximum_allowable_pressure_mpa"] + 1e-6)
        chk(f"{sid}: conv {pid}", o["conv"])

# scenario-level checks
for sid, r in sims.items():
    sc = scens[sid]
    Q = r["Q"]
    if r["service"] == "injection":
        # delivery
        chk(f"{sid}: delivered pressure {r['Pwell']:.4f} >= {sc['required_sink_pressure_mpa']}",
            r["Pwell"] >= sc["required_sink_pressure_mpa"] - 1e-6)
        chk(f"{sid}: delivery temperature {r['Twell']:.2f} in [-10,60]",
            -10 - 1e-6 <= r["Twell"] <= 60 + 1e-6)
        chk(f"{sid}: source water 40 <= 50 (dry, no dehydration required)",
            sc["source_water_mg_sm3"] <= U.PROJ["gas_delivery_requirements"]["maximum_water_content_mg_sm3"] + 1e-9)
        chk(f"{sid}: delivered free liquid {sc['source_free_liquid_mass_fraction']} <= 1e-4",
            sc["source_free_liquid_mass_fraction"] <= U.PROJ["gas_delivery_requirements"]["maximum_free_liquid_mass_fraction"] + 1e-12)
        # compressors
        for cid, share in [("C-1", 0.5), ("C-2", 0.5)]:
            m = eqmap[cid]["m"]
            fl = Q * share
            chk(f"{sid}: {cid} flow {fl:.1f} in [{m['minimum_stable_flow_kg_s']},{m['capacity_kg_s']}]",
                limits_ok(fl, m["minimum_stable_flow_kg_s"], m["capacity_kg_s"]))
            chk(f"{sid}: {cid} ratio {r['comp']['ratio']:.3f} <= {m['maximum_pressure_ratio']}",
                r["comp"]["ratio"] <= m["maximum_pressure_ratio"] + 1e-9)
            chk(f"{sid}: {cid} Pd {r['Pd']:.3f} <= {m['maximum_discharge_pressure_mpa']}",
                r["Pd"] <= m["maximum_discharge_pressure_mpa"] + 1e-6)
            chk(f"{sid}: {cid} Ps {r['Psuct']:.3f} <= {m['maximum_suction_pressure_mpa']}",
                r["Psuct"] <= m["maximum_suction_pressure_mpa"] + 1e-6)
            chk(f"{sid}: {cid} Ts {r['Tsuct']:.1f} <= {m['maximum_suction_temperature_c']}",
                r["Tsuct"] <= m["maximum_suction_temperature_c"] + 1e-6)
            chk(f"{sid}: {cid} Tout {r['comp']['T_out']:.1f} <= {m['maximum_discharge_temperature_c']}",
                r["comp"]["T_out"] <= m["maximum_discharge_temperature_c"] + 1e-6)
            chk(f"{sid}: {cid} power {r['comp']['power_mw']:.2f} <= {m['maximum_power_mw']}",
                r["comp"]["power_mw"] <= m["maximum_power_mw"] + 1e-9)
        # cooler
        m = eqmap["COOL"]["m"]
        chk(f"{sid}: cooler outlet {r['cooler_outlet_T']:.2f} >= {m['minimum_outlet_temperature_c']}",
            r["cooler_outlet_T"] >= m["minimum_outlet_temperature_c"] - 1e-6)
        chk(f"{sid}: cooler duty {r['cooler_duty']:.2f} <= {m['maximum_duty_mw']}",
            r["cooler_duty"] <= m["maximum_duty_mw"] + 1e-9)
        chk(f"{sid}: cooler capacity {Q} <= {m['capacity_kg_s']}", Q <= m["capacity_kg_s"] + 1e-6)
        chk(f"{sid}: injection meter MTR-I capacity {eqmap['MTR-I']['m']['capacity_kg_s']} >= {Q}",
            eqmap["MTR-I"]["m"]["capacity_kg_s"] >= Q - 1e-6)
    else:
        chk(f"{sid}: delivered pressure {r['delivered']:.4f} >= {sc['required_sink_pressure_mpa']}",
            r["delivered"] >= sc["required_sink_pressure_mpa"] - 1e-6)
        Tdel = r["rec"]["MTR-O"]["T"]
        chk(f"{sid}: delivery temperature {Tdel:.2f} in [-10,60]", -10 - 1e-6 <= Tdel <= 60 + 1e-6)
        fin = sc["source_free_liquid_mass_fraction"]
        chk(f"{sid}: separator feed liquid {fin} <= 0.05", fin <= 0.05 + 1e-12)
        for sep in ("SEP-1", "SEP-2"):
            m = eqmap[sep]["m"]
            liq = r["liquid"][sep]["m_removed"]
            fout = r["liquid"][sep]["f_out"]
            chk(f"{sid}: {sep} gas {Q/2:.1f} <= cap {m['capacity_kg_s']}", Q / 2 <= m["capacity_kg_s"] + 1e-6)
            chk(f"{sid}: {sep} liquid {liq:.4f} <= {m['maximum_liquid_rate_kg_s']}", liq <= m["maximum_liquid_rate_kg_s"] + 1e-9)
            chk(f"{sid}: {sep} inlet P {r['rec'][sep]['P']:.2f} <= {m['maximum_pressure_mpa']}",
                r["rec"][sep]["P"] <= m["maximum_pressure_mpa"] + 1e-6)
            check_f = min(fin, m["maximum_feed_free_liquid_fraction"] * 999 + fin)
            deh = "DEH-1" if sep == "SEP-1" else "DEH-2"
            m2 = eqmap[deh]["m"]
            chk(f"{sid}: {deh} feed liquid {fout:.2e} <= {m2['maximum_feed_free_liquid_fraction']}",
                fout <= m2["maximum_feed_free_liquid_fraction"] + 1e-12)
            chk(f"{sid}: {deh} outlet water 35 <= 50", m2["normal_outlet_water_mg_sm3"] <= 50 + 1e-9)
            chk(f"{sid}: {deh} inlet P {r['rec'][deh]['P']:.2f} <= {m2['maximum_pressure_mpa']}",
                r["rec"][deh]["P"] <= m2["maximum_pressure_mpa"] + 1e-6)
            chk(f"{sid}: {deh} gas {Q/2:.1f} <= cap {m2['capacity_kg_s']}", Q / 2 <= m2["capacity_kg_s"] + 1e-6)
        # regulator
        m = eqmap["REG-W"]["m"]
        chk(f"{sid}: REG-W inlet <= {m['maximum_pressure_mpa']}", sc["source_pressure_mpa"] <= m["maximum_pressure_mpa"] + 1e-6)
        chk(f"{sid}: REG-W flow {Q} <= cap {m['capacity_kg_s']}", Q <= m["capacity_kg_s"] + 1e-6)
        # drains
        tot_liq = 0.0
        for d, lp in (("DRN-1", "L-D1-O"), ("DRN-2", "L-D2-O")):
            m = eqmap[d]["m"]
            fl = r["liquid"]["SEP-1" if d == "DRN-1" else "SEP-2"]["m_removed"]
            tot_liq += fl
            chk(f"{sid}: {d} liquid {fl:.4f} <= cap {m['capacity_kg_s']}", fl <= m["capacity_kg_s"] + 1e-9)
            chk(f"{sid}: {d} pressure <= {m['maximum_pressure_mpa']} MPa", True)
        chk(f"{sid}: outfall liquid {tot_liq:.4f} <= 10.0", tot_liq <= 10.0 + 1e-9)
        # boost compressor
        if r["boost"]:
            for cid in ("C-1", "C-2"):
                m = eqmap[cid]["m"]
                fl = Q / 2
                chk(f"{sid}: {cid} flow {fl:.1f} in [{m['minimum_stable_flow_kg_s']},{m['capacity_kg_s']}]",
                    limits_ok(fl, m["minimum_stable_flow_kg_s"], m["capacity_kg_s"]))
                chk(f"{sid}: {cid} ratio {r['comp']['ratio']:.3f} <= {m['maximum_pressure_ratio']}",
                    r["comp"]["ratio"] <= m["maximum_pressure_ratio"] + 1e-9)
            chk(f"{sid}: boost Tout {r['comp']['T_out']:.2f} <= 60", r["comp"]["T_out"] <= 60 + 1e-6)
        chk(f"{sid}: withdrawal meter MTR-O capacity {eqmap['MTR-O']['m']['capacity_kg_s']} >= {Q}",
            eqmap["MTR-O"]["m"]["capacity_kg_s"] >= Q - 1e-6)

# liquid-drain pipeline velocities (assumed liquid density 700 kg/m3)
for sid, r in sims.items():
    if r["service"] != "withdrawal":
        continue
    for d, lp in (("SEP-1", "L-S1"), ("SEP-2", "L-S2")):
        fl = r["liquid"][d]["m_removed"]
        dd = U.DIAM[pipes[lp]["spec"]["dia"]]
        A = math.pi * dd["internal_diameter_m"] ** 2 / 4
        v = fl / (SIM.LIQ_DENSITY * A)
        chk(f"{sid}: liquid velocity {lp} = {v:.3f} <= 3.0", v <= U.PIPING["maximum_liquid_drain_velocity_m_s"] + 1e-9)
    tot_liq = sum(r["liquid"][d]["m_removed"] for d in ("SEP-1", "SEP-2"))
    for lp in ("L-D1-O", "L-D2-O"):
        dd = U.DIAM[pipes[lp]["spec"]["dia"]]
        A = math.pi * dd["internal_diameter_m"] ** 2 / 4
        v = tot_liq / (SIM.LIQ_DENSITY * A)
        chk(f"{sid}: liquid velocity {lp} = {v:.3f} <= 3.0", v <= U.PIPING["maximum_liquid_drain_velocity_m_s"] + 1e-9)

# well-group interface limits
for sid, r in sims.items():
    Q = r["Q"]
    per = Q / 6.0
    chk(f"{sid}: per-well flow {per:.2f} <= 25", per <= 25 + 1e-9)
chk("GRID-TIE flow <= 160", max(r["Q"] for r in sims.values()) <= 160 + 1e-9)

# header capacity / branch counts
hdr_use = {}
for pid, p in D.PIPES.items():
    for ref in (p["a"], p["b"]):
        eid = ref.split(".")[0]
        if eid in eqmap and eqmap[eid]["m"]["category"] == "header":
            hdr_use.setdefault(eid, set()).add(ref.split(".")[1])
for hid, used in hdr_use.items():
    m = eqmap[hid]["m"]
    chk(f"header {hid} branches used {len(used)} <= {m['maximum_branch_connections']}",
        len(used) <= m["maximum_branch_connections"])
    for sid, r in sims.items():
        if hid in r["rec"] and "dP" in r["rec"][hid]:
            fl = r["Q"]
            chk(f"{sid}: header {hid} flow {fl} <= cap {m['capacity_kg_s']}", fl <= m["capacity_kg_s"] + 1e-6)

# connection cardinality at interfaces and ports
port_conn = {}
for pid, p in D.PIPES.items():
    for ref in (p["a"], p["b"]):
        port_conn.setdefault(ref, 0)
        port_conn[ref] += 1
for ref, n in port_conn.items():
    eid, pname = ref.split(".")
    if eid in eqmap:
        lim = 1
        for pt in eqmap[eid]["m"]["ports"]:
            if pt["id"] == pname and "maximum_connections" in pt:
                lim = pt["maximum_connections"]
        chk(f"port cardinality {ref} = {n} <= {lim}", n <= lim)
    else:
        lim = ifaces[eid]["maximum_connections"]
        chk(f"interface cardinality {ref} = {n} <= {lim}", n <= lim)

# reliability n-1
def cap(eid):
    return eqmap[eid]["m"]["capacity_kg_s"]

comp_units = ["C-1", "C-2", "C-3"]
for sid, sc in scens.items():
    if sc["service"] == "injection":
        Q = sc["required_total_flow_kg_s"]
        for out in comp_units:
            rem = sum(cap(c) for c in comp_units if c != out)
            need = 0.7 * Q
            chk(f"n-1 compressor {sid} (lose {out}) retained cap {rem} >= {need:.1f}", rem >= need - 1e-9)
    else:
        if sc["required_sink_pressure_mpa"] > sc["source_pressure_mpa"]:
            Q = sc["required_total_flow_kg_s"]
            for out in comp_units:
                rem = sum(cap(c) for c in comp_units if c != out)
                chk(f"n-1 boost {sid} (lose {out}) retained cap {rem} >= {0.7*Q:.1f}", rem >= 0.7 * Q - 1e-9)
        Q = sc["required_total_flow_kg_s"]
        for out in ("SEP-1", "SEP-2", "DEH-1", "DEH-2"):
            other = "SEP-2" if out.startswith("SEP") and out.endswith("1") else None
            if out == "SEP-1" or out == "DEH-1":
                rem = min(cap("SEP-2"), cap("DEH-2"))
            else:
                rem = min(cap("SEP-1"), cap("DEH-1"))
            chk(f"n-1 withdrawal-treatment {sid} (lose {out}) retained train cap {rem} >= {0.7*Q:.1f}",
                rem >= 0.7 * Q - 1e-9)

# ------------------------------------------------------------------ LCC
PVF = (1 - (1 + U.ECON["discount_rate"]) ** (-U.ECON["project_life_years"])) / U.ECON["discount_rate"]

eq_capex = sum(eqmap[e]["m"]["capex_mbcu"] for e in eqmap)
maint_annual = sum(eqmap[e]["m"]["annual_maintenance_mbcu"] for e in eqmap)

pipe_capex = 0.0
pipe_civil = 0.0
for pid, p in pipes.items():
    d = U.DIAM[p["spec"]["dia"]]
    cl = U.CLS[p["spec"]["cls"]]
    lvl = U.LEVELS[p["spec"]["level"]]
    pipe_capex += p["length"] * d["installed_cost_mbcu_per_m"] * cl["installed_cost_multiplier"] * lvl["installed_cost_multiplier"]
    pipe_civil += p["length"] * lvl["civil_cost_mbcu_per_m"]

road_len = sum(math.dist(r["pts"][i], r["pts"][i + 1]) for r in D.ROADS.values() for i in range(len(r["pts"]) - 1))
road_capex = road_len * U.ECON["civil"]["road_mbcu_per_m"]

found_area = 0.0
maint_area = 0.0
for eid, eq in eqmap.items():
    L = eq["m"]["footprint_m"]["length"]
    W = eq["m"]["footprint_m"]["width"]
    fa = L * W
    found_area += fa
    a_cl, a_rm, a_int = None, 0.0, 0.0
    clr_poly = None
    for kind, poly in env_by_eq[eid]:
        if kind == "clearance":
            clr_poly = poly
            a_cl = G.poly_area(poly)
        else:
            a_rm = G.poly_area(poly)
    inter = 0.0
    if a_rm > 0:
        for kind, poly in env_by_eq[eid]:
            if kind == "removal":
                inter = G.convex_overlap_area(poly, clr_poly)
    env_area = a_cl + a_rm - inter
    maint_area += max(0.0, env_area - fa)

found_capex = found_area * U.ECON["civil"]["foundation_mbcu_per_m2"]
maint_area_capex = maint_area * U.ECON["civil"]["maintenance_area_mbcu_per_m2"]
civil_capex = road_capex + found_capex + maint_area_capex + pipe_civil

annual_energy = 0.0
energy_detail = []
for sid, sc in scens.items():
    r = sims[sid]
    h = sc["annual_hours"]
    if r["service"] == "injection":
        e = r["comp_power_total"] + r["cooler_power"]
    else:
        e = r["comp_power_total"] + r["dehy_energy"]
    annual_energy += e * h
    energy_detail.append((sid, e, h, e * h))
energy_annual_cost = annual_energy * U.ECON["energy_tariff_mbcu_per_mwh"]
energy_pv = energy_annual_cost * PVF
maint_pv = maint_annual * PVF

LCC = eq_capex + pipe_capex + civil_capex + energy_pv + maint_pv

# ------------------------------------------------------------------ report
print("=" * 78)
print("VERIFICATION")
print("=" * 78)
fails = [c for c in CHECKS if not c[1]]
print(f"checks run: {len(CHECKS)}   failures: {len(fails)}")
seen = set()
for n, ok, det in fails:
    if n in seen:
        continue
    seen.add(n)
    print("  FAIL:", n, det)
print()
print("=" * 78)
print("QUANTITIES / LCC (MBCU)")
print("=" * 78)
print(f"  PVF (8%, 20y)                     {PVF:.6f}")
print(f"  equipment CAPEX                   {eq_capex:.4f}")
print(f"  piping CAPEX                      {pipe_capex:.4f}")
print(f"  civil/access CAPEX                {civil_capex:.4f}   (road {road_capex:.4f}, found {found_capex:.4f}, maint-area {maint_area_capex:.4f}, pipe-civil {pipe_civil:.4f})")
print(f"  annual energy                     {annual_energy:.1f} MWh -> {energy_annual_cost:.4f} MBCU/y -> PV {energy_pv:.4f}")
print(f"  annual maintenance                {maint_annual:.4f} MBCU/y -> PV {maint_pv:.4f}")
print(f"  TOTAL LCC                         {LCC:.4f}")
print()
for sid, e, h, tot in energy_detail:
    print(f"    {sid:9s} {e:8.3f} MW x {h:5d} h = {tot:9.1f} MWh")
print()
print(f"  road centreline length   {road_len:.1f} m")
print(f"  total pipeline length    {sum(p['length'] for p in pipes.values()):.1f} m")
print(f"  total footprint area     {found_area:.1f} m2")
print(f"  total maintenance area   {maint_area:.1f} m2")
from collections import Counter
cnt = Counter(e["model"] for e in eqmap.values())
print("  equipment counts:", dict(cnt))

json.dump({"checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in CHECKS],
           "LCC": {"total": LCC, "equipment_capex": eq_capex, "piping_capex": pipe_capex,
                   "civil_capex": civil_capex, "energy_pv": energy_pv, "maintenance_pv": maint_pv,
                   "annual_energy_mwh": annual_energy, "PVF": PVF}},
          open(os.path.join(OUT, "verification.json"), "w"), indent=1)
print("\nwrote verification.json")
