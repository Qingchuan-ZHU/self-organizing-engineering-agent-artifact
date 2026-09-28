"""Greedy coordinate-descent optimiser for pipeline diameters (minimise LCC).

Enforces n-1 constraints: the three compressor-branch pipes share one diameter per
side, and the withdrawal treatment-train pipes are checked at 70 % flow.
"""
import math, json, os
import ugscat as U
import design as D
import solve as S
import sim as SIM

DIAMS = [d["nominal_diameter"] for d in U.PIPING["diameters"]]
SUCT = ["G-C1S", "G-C2S", "G-C3S"]
DISCH = ["G-C1D", "G-C2D", "G-C3D"]
TRAIN1 = ["G-R-S1", "G-S1-D1", "G-D1-T"]
TRAIN2 = ["G-R-S2", "G-S2-D2", "G-D2-T"]


def normalise(dia):
    return dict(dia)


BRANCH_UNIT = {"G-C1S": "C-1", "G-C2S": "C-2", "G-C3S": "C-3",
               "G-C1D": "C-1", "G-C2D": "C-2", "G-C3D": "C-3"}


def _n1_branch_ok(eqmap, pipes, scens, sims):
    """Velocity check on the compressor branch pipes at the n-1 (70 %) flow."""
    for sid, sc in scens.items():
        if sc["service"] != "injection":
            continue
        Q = sc["required_total_flow_kg_s"]
        Qn = 0.7 * Q
        r = sims[sid]
        for pid, cid in BRANCH_UNIT.items():
            cap = eqmap[cid]["m"]["capacity_kg_s"]
            flo = min(cap, Qn)
            if pid.endswith("S"):
                P = r["rec"]["HDR-CS"]["P"]; T = r["Tsuct"]
            else:
                P = r["comp"]["Pd"]; T = r["comp"]["T_out"]
            o = SIM.p_pipe(eqmap, pipes, pid, P, T, flo)
            if o["v"] > U.PIPING["maximum_gas_velocity_m_s"] + 1e-6:
                return False
    return True


def _n1_train_ok(eqmap, pipes, scens, sims):
    """Single-train 70 % withdrawal check for the two treatment trains."""
    for sid, sc in scens.items():
        if sc["service"] != "withdrawal":
            continue
        Q = sc["required_total_flow_kg_s"]
        Qn = 0.7 * Q
        for tr, (rs, sd, dt) in enumerate([TRAIN1, TRAIN2]):
            P = sims[sid]["rec"]["HDR-R"]["P"]
            T = sims[sid]["rec"][rs]["T"]
            o = SIM.p_pipe(eqmap, pipes, rs, P, T, Qn)
            if o["v"] > U.PIPING["maximum_gas_velocity_m_s"] + 1e-6:
                return False
            Pt, Tt = o["P"], o["T"]
            sep = "SEP-1" if tr == 0 else "SEP-2"
            deh = "DEH-1" if tr == 0 else "DEH-2"
            o = SIM.p_equip(eqmap, sep, Pt, Tt, Qn); Pt, Tt = o["P"], o["T"]
            o = SIM.p_pipe(eqmap, pipes, sd, Pt, Tt, Qn)
            if o["v"] > U.PIPING["maximum_gas_velocity_m_s"] + 1e-6:
                return False
            Pt, Tt = o["P"], o["T"]
            o = SIM.p_equip(eqmap, deh, Pt, Tt, Qn); Pt, Tt = o["P"], o["T"]
            o = SIM.p_pipe(eqmap, pipes, dt, Pt, Tt, Qn)
            if o["v"] > U.PIPING["maximum_gas_velocity_m_s"] + 1e-6:
                return False
    return True


def evaluate(dia_map):
    dia_map = normalise(dia_map)
    saved = {pid: D.PIPES[pid]["dia"] for pid in D.PIPES}
    for pid, dname in dia_map.items():
        D.PIPES[pid]["dia"] = dname
    try:
        eqmap, ifaces, pipes = S.build()
        scens = {s["scenario_id"]: s for s in U.SCEN["scenarios"]}
        sims = {}
        for sid, sc in scens.items():
            sims[sid] = SIM.sim_injection(sc, eqmap, pipes) if sc["service"] == "injection" \
                else SIM.sim_withdrawal(sc, eqmap, pipes)
        for sid, r in sims.items():
            sc = scens[sid]
            Q = r["Q"]
            if r["service"] == "injection":
                if r["Pwell"] < sc["required_sink_pressure_mpa"] - 1e-6:
                    return None, None
                if not (-10 <= r["Twell"] <= 60):
                    return None, None
                for u in r["units"]:
                    m = eqmap[u["id"]]["m"]
                    if u["ratio"] > m["maximum_pressure_ratio"] + 1e-9:
                        return None, None
                    if u["Pd"] > m["maximum_discharge_pressure_mpa"] + 1e-6:
                        return None, None
                    if u["Ps"] > m["maximum_suction_pressure_mpa"] + 1e-6:
                        return None, None
                    if u["power_mw"] > m["maximum_power_mw"] + 1e-9:
                        return None, None
                    if u["T_out"] > m["maximum_discharge_temperature_c"] + 1e-6:
                        return None, None
            else:
                if r["delivered"] < sc["required_sink_pressure_mpa"] - 1e-6:
                    return None, None
                if not (-10 <= r["rec"]["MTR-O"]["T"] <= 60):
                    return None, None
                if r["boost"] and r["comp"]["T_out"] > 60 + 1e-6:
                    return None, None
            for pid, o in r["rec"].items():
                if "v" not in o:
                    continue
                p = pipes[pid]
                med = p["spec"].get("medium", "gas")
                vmax = U.PIPING["maximum_liquid_drain_velocity_m_s"] if med == "liquid" else U.PIPING["maximum_gas_velocity_m_s"]
                if o["v"] > vmax + 1e-6 or not o["conv"]:
                    return None, None
                cl = U.CLS[p["spec"]["cls"]]
                if max(o["P"], 0) > cl["maximum_allowable_pressure_mpa"] + 1e-6:
                    return None, None
        if not _n1_train_ok(eqmap, pipes, scens, sims):
            return None, None
        if not _n1_branch_ok(eqmap, pipes, scens, sims):
            return None, None
        return lcc_of(eqmap, pipes, sims, scens), (eqmap, pipes, sims, scens)
    finally:
        for pid, d in saved.items():
            D.PIPES[pid]["dia"] = d


def lcc_of(eqmap, pipes, sims, scens):
    PVF = (1 - (1 + U.ECON["discount_rate"]) ** (-U.ECON["project_life_years"])) / U.ECON["discount_rate"]
    eq_capex = sum(eqmap[e]["m"]["capex_mbcu"] for e in eqmap)
    maint = sum(eqmap[e]["m"]["annual_maintenance_mbcu"] for e in eqmap)
    pipe_capex = 0.0
    for pid, p in pipes.items():
        d = U.DIAM[p["spec"]["dia"]]
        cl = U.CLS[p["spec"]["cls"]]
        lvl = U.LEVELS[p["spec"]["level"]]
        pipe_capex += p["length"] * d["installed_cost_mbcu_per_m"] * cl["installed_cost_multiplier"] * lvl["installed_cost_multiplier"]
    road_len = sum(math.dist(r["pts"][i], r["pts"][i + 1]) for r in D.ROADS.values() for i in range(len(r["pts"]) - 1))
    civil = road_len * U.ECON["civil"]["road_mbcu_per_m"]
    found_area = sum(eq["m"]["footprint_m"]["length"] * eq["m"]["footprint_m"]["width"] for eq in eqmap.values())
    civil += found_area * U.ECON["civil"]["foundation_mbcu_per_m2"]
    energy = 0.0
    for sid, sc in scens.items():
        r = sims[sid]
        e = (r["comp_power_total"] + r["cooler_power"]) if r["service"] == "injection" else (r["comp_power_total"] + r["dehy_energy"])
        energy += e * sc["annual_hours"]
    return eq_capex + pipe_capex + civil + energy * U.ECON["energy_tariff_mbcu_per_mwh"] * PVF + maint * PVF


if __name__ == "__main__":
    dia = {pid: D.PIPES[pid]["dia"] for pid in D.PIPES}
    best, _ = evaluate(dia)
    print("start LCC", round(best, 4))
    rounds = 0
    improved = True
    while improved and rounds < 10:
        improved = False
        rounds += 1
        for pid in list(D.PIPES.keys()):
            cur = dia[pid]
            curi = DIAMS.index(cur)
            bestv, bestd = best, cur
            for shift in (-1, 1, 2, 3):
                i = curi + shift
                if i < 0 or i >= len(DIAMS):
                    continue
                trial = normalise({**dia, pid: DIAMS[i]})
                v, _ = evaluate(trial)
                if v is not None and v < bestv - 1e-9:
                    bestv, bestd = v, DIAMS[i]
            if bestd != cur:
                dia = normalise({**dia, pid: bestd})
                best = bestv
                improved = True
        print(f"round {rounds}: LCC {best:.4f}")
    print(json.dumps(dia, indent=1))
    json.dump(dia, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "opt_diameters.json"), "w"), indent=1)
