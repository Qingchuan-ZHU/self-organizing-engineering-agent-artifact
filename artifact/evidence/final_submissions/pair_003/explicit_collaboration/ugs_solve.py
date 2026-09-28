"""Process solver for the UGS-SYNTH-D01 proposed design.

Element chain language
----------------------
state        = (P_MPa, T_degC, water_mg_sm3, free_liquid_kg_per_kg)
element      = ("pipe", pipeline_id, flow_fraction)
             | ("equip", instance_id, flow_fraction, setpoint_dict)
             | ("par", [branch, ...])                      parallel block, merge
             | ("split", [branch, ...])                    split to sink boundaries
             | ("source_par", [branch, ...])               several source boundaries
`flow_fraction` is the fraction of the scenario's total gas mass flow carried by the
element; the branch flow of a parallel branch is the fraction declared on its first
element.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ugs_lib import load_brief, pipe_outlet_state, pvf, poly_len
import ugs_design as D

B = load_brief()
MODELS = B["models"]
CLASSES = B["classes"]
DN = B["dn"]
LEVELS = B["routing_levels"]
GAS = B["gas"]
CP = GAS["heat_capacity_cp_j_kg_k"]
KRATIO = GAS["specific_heat_ratio"]
A_EXP = (KRATIO - 1.0) / KRATIO
SITE = B["site"]
IFACES = {i["interface_id"]: i for i in SITE["external_interfaces"]}
SCEN = {s["scenario_id"]: s for s in B["scenarios"]}
PIPES = {p["id"]: p for p in D.PIPELINES}
EQUIP = {e[0]: e for e in D.EQUIPMENT}
ROADS = {r["id"]: r for r in D.ROADS}
AREA_INFO = {}


class Blocker(Exception):
    pass


def inst_model(eid):
    return MODELS[EQUIP[eid][1]]


def inst_pose(eid):
    e = EQUIP[eid]
    return dict(id=e[0], model_id=e[1], x=e[2], y=e[3], orientation_deg=e[4], description=e[5])


def pipe_state(pid, m_dot, P_in, T_c):
    pipe = PIPES[pid]
    dn = DN[pipe["dn"]]
    cls = CLASSES[pipe["cls"]]
    L = poly_len([tuple(p) for p in pipe["route"]])
    return pipe_outlet_state(dn["internal_diameter_m"], cls["roughness_m"], L, m_dot, P_in, T_c, GAS)


def branch_frac(branch):
    for el in branch:
        if el[0] in ("pipe", "equip"):
            return el[2]
    return 0.0


def active_branch(branch):
    return branch_frac(branch) > 0.0


def apply_equip(eid, m_dot, P, T, water, fl, sp, comp_set, reg_set, energy, trace):
    mdl = inst_model(eid)
    cat = mdl["category"]
    if cat == "header":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity (%.3f > %.3f kg/s)" % (eid, m_dot, mdl["capacity_kg_s"]))
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s process pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_pressure_mpa"]))
        P -= mdl["pressure_drop_at_capacity_mpa"] * (m_dot / mdl["capacity_kg_s"]) ** 2
    elif cat in ("separator", "filter"):
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity (%.3f > %.3f kg/s)" % (eid, m_dot, mdl["capacity_kg_s"]))
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s process pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_pressure_mpa"]))
        if fl > mdl["maximum_feed_free_liquid_fraction"] + 1e-12:
            raise Blocker("%s feed free-liquid loading %.3e exceeds %.3e" % (eid, fl, mdl["maximum_feed_free_liquid_fraction"]))
        liq = m_dot * fl * mdl["liquid_removal_efficiency"]
        if liq > mdl["maximum_liquid_rate_kg_s"] + 1e-12:
            raise Blocker("%s liquid rate %.4f exceeds %.3f kg/s" % (eid, liq, mdl["maximum_liquid_rate_kg_s"]))
        fl = fl * (1.0 - mdl["liquid_removal_efficiency"])
        P -= mdl["pressure_drop_mpa"]
        energy["liq_" + eid] = energy.get("liq_" + eid, 0.0) + liq
    elif cat == "dehydration":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity (%.3f > %.3f kg/s)" % (eid, m_dot, mdl["capacity_kg_s"]))
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s process pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_pressure_mpa"]))
        if fl > mdl["maximum_feed_free_liquid_fraction"] + 1e-12:
            raise Blocker("%s feed free-liquid loading %.3e exceeds limit" % (eid, fl))
        water = mdl["normal_outlet_water_mg_sm3"]
        P -= mdl["pressure_drop_mpa"]
        energy["duty"] = energy.get("duty", 0.0) + m_dot * mdl["energy_mw_per_kg_s"]
    elif cat == "compressor":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity (%.3f > %.3f kg/s)" % (eid, m_dot, mdl["capacity_kg_s"]))
        if m_dot < mdl["minimum_stable_flow_kg_s"] - 1e-6:
            raise Blocker("%s below minimum stable flow (%.3f < %.3f kg/s)" % (eid, m_dot, mdl["minimum_stable_flow_kg_s"]))
        if P > mdl["maximum_suction_pressure_mpa"] + 1e-6:
            raise Blocker("%s suction pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_suction_pressure_mpa"]))
        if T > mdl["maximum_suction_temperature_c"] + 1e-4:
            raise Blocker("%s suction temperature %.2f exceeds %.2f C" % (eid, T, mdl["maximum_suction_temperature_c"]))
        P_out = comp_set[eid]
        r = P_out / P
        if r > mdl["maximum_pressure_ratio"] + 1e-9:
            raise Blocker("%s pressure ratio %.4f exceeds %.2f" % (eid, r, mdl["maximum_pressure_ratio"]))
        if P_out > mdl["maximum_discharge_pressure_mpa"] + 1e-6:
            raise Blocker("%s discharge pressure %.3f exceeds %.3f MPa" % (eid, P_out, mdl["maximum_discharge_pressure_mpa"]))
        Tk = T + 273.15
        Tout = Tk * (1.0 + (r ** A_EXP - 1.0) / mdl["efficiency_proxy"]) - 273.15
        if Tout > mdl["maximum_discharge_temperature_c"] + 1e-4:
            raise Blocker("%s discharge temperature %.2f exceeds %.2f C" % (eid, Tout, mdl["maximum_discharge_temperature_c"]))
        W = m_dot * CP * Tk * (r ** A_EXP - 1.0) / (mdl["efficiency_proxy"] * mdl["driver_efficiency"]) / 1e6
        if W > mdl["maximum_power_mw"] + 1e-6:
            raise Blocker("%s driver power %.3f exceeds %.2f MW" % (eid, W, mdl["maximum_power_mw"]))
        energy["comp_" + eid] = energy.get("comp_" + eid, 0.0) + W
        T, P = Tout, P_out
    elif cat == "cooler":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity (%.3f > %.3f kg/s)" % (eid, m_dot, mdl["capacity_kg_s"]))
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s process pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_pressure_mpa"]))
        t_out = sp["t_out_c"]
        if t_out < mdl["minimum_outlet_temperature_c"] - 1e-4:
            raise Blocker("%s outlet temperature below catalog minimum" % eid)
        duty = m_dot * CP * abs(t_out - T) / 1e6
        if duty > mdl["maximum_duty_mw"] + 1e-9:
            raise Blocker("%s duty %.3f exceeds %.2f MW" % (eid, duty, mdl["maximum_duty_mw"]))
        energy["cool_" + eid] = energy.get("cool_" + eid, 0.0) + duty * mdl["electric_power_fraction_of_duty"]
        T = t_out
        P -= mdl["pressure_drop_mpa"]
    elif cat == "heater":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity (%.3f > %.3f kg/s)" % (eid, m_dot, mdl["capacity_kg_s"]))
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s process pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_pressure_mpa"]))
        t_out = sp["t_out_c"]
        if t_out > mdl["maximum_outlet_temperature_c"] + 1e-4:
            raise Blocker("%s outlet temperature above catalog maximum" % eid)
        duty = m_dot * CP * abs(t_out - T) / 1e6
        if duty > mdl["maximum_duty_mw"] + 1e-9:
            raise Blocker("%s duty %.3f exceeds %.2f MW" % (eid, duty, mdl["maximum_duty_mw"]))
        energy["heat_" + eid] = energy.get("heat_" + eid, 0.0) + duty
        T = t_out
        P -= mdl["pressure_drop_mpa"]
    elif cat == "regulator":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity" % eid)
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s inlet pressure %.3f exceeds %.3f MPa" % (eid, P, mdl["maximum_pressure_mpa"]))
        P_out = reg_set[eid]
        if P_out > P + 1e-12:
            raise Blocker("%s cannot raise pressure" % eid)
        T = T - mdl["jt_temperature_coefficient_k_per_mpa"] * (P - P_out)
        P = P_out
    elif cat == "meter":
        if m_dot > mdl["capacity_kg_s"] + 1e-6:
            raise Blocker("%s over capacity" % eid)
        if P > mdl["maximum_pressure_mpa"] + 1e-6:
            raise Blocker("%s pressure limit" % eid)
        P -= mdl["pressure_drop_mpa"]
    elif cat == "closed_drain":
        if m_dot > mdl["capacity_kg_s"] + 1e-12:
            raise Blocker("%s over capacity" % eid)
        if P > mdl["maximum_pressure_mpa"] + 1e-12:
            raise Blocker("%s pressure limit" % eid)
    else:
        raise Blocker("unhandled category %s" % cat)
    if trace is not None:
        trace.append(dict(kind="equip", id=eid, model=mdl["model_id"], flow=m_dot, P=P, T=T,
                          water=water, fl=fl, setpoint=sp))
    return P, T, water, fl


def run_chain(total, chain, state, comp_set, reg_set, energy, trace, depth=0):
    """state = (P, T, water, fl).  Returns (state, sink_states or None)."""
    P, T, water, fl = state
    sinks = None
    for el in chain:
        k = el[0]
        if k == "pipe":
            pid, frac = el[1], el[2]
            m = total * frac
            if m > 0:
                P_in_before = P
                r = pipe_state(pid, m, P, T)
                if not r["converged"]:
                    raise Blocker("pressure loss did not converge on %s" % pid)
                cls = CLASSES[PIPES[pid]["cls"]]
                if P > cls["maximum_allowable_pressure_mpa"] + 1e-6:
                    raise Blocker("class %s under-rated on %s at %.3f MPa" % (cls["class_id"], pid, P))
                lo, hi = cls["temperature_limits_c"]
                if not (lo - 1e-6 <= T <= hi + 1e-6):
                    raise Blocker("class %s temperature out of range on %s (%.2f C)" % (cls["class_id"], pid, T))
                if r["v"] > B["max_gas_v"] + 1e-6:
                    raise Blocker("gas velocity %.3f m/s on %s exceeds %.1f m/s" % (r["v"], pid, B["max_gas_v"]))
                P = r["P_out"]
                if trace is not None:
                    trace.append(dict(kind="pipe", id=pid, flow=m, P_in=P_in_before, P_out=P, T=T,
                                          v=r["v"], dP=r["dP"], dn=PIPES[pid]["dn"], cls=PIPES[pid]["cls"]))
        elif k == "equip":
            eid, frac, sp = el[1], el[2], el[3]
            m = total * frac
            if m > 0:
                P, T, water, fl = apply_equip(eid, m, P, T, water, fl, sp, comp_set, reg_set, energy, trace)
        elif k == "par":
            outs = []
            for br in el[1]:
                if not active_branch(br):
                    continue
                st, _ = run_chain(total, br, (P, T, water, fl), comp_set, reg_set, energy, trace, depth + 1)
                outs.append((st, total * branch_frac(br)))
            if outs:
                tot = sum(f for _, f in outs)
                P = min(s[0] for s, _ in outs)
                T = sum(s[1] * f for s, f in outs) / tot
                water = sum(s[2] * f for s, f in outs) / tot
                fl = sum(s[3] * f for s, f in outs) / tot
        elif k in ("split", "source_par"):
            outs = []
            for br in el[1]:
                if not active_branch(br) and k == "par":
                    continue
                st, _ = run_chain(total, br, (P, T, water, fl), comp_set, reg_set, energy, trace, depth + 1)
                outs.append((st, total * branch_frac(br)))
            if k == "split":
                sinks = [s for s, _ in outs]
            else:
                tot = sum(f for _, f in outs)
                P = min(s[0] for s, _ in outs)
                T = sum(s[1] * f for s, f in outs) / tot
                water = sum(s[2] * f for s, f in outs) / tot
                fl = sum(s[3] * f for s, f in outs) / tot
        else:
            raise Blocker("unknown element %s" % k)
    return (P, T, water, fl), sinks


def boundary_state(scn, node):
    """State at a scenario source boundary."""
    return (scn["source_pressure_mpa"], scn["source_temperature_c"],
            scn["source_water_mg_sm3"], scn["source_free_liquid_mass_fraction"])


def evaluate(sid, flow=None, comp_set=None, reg_set=None, energy=None, trace=None):
    scn = SCEN[sid]
    if flow is None:
        flow = scn["required_total_flow_kg_s"]
    chain = D.SCENARIO_PATHS[sid]["chain"]
    st0 = boundary_state(scn, None)
    return run_chain(flow, chain, st0, comp_set or {}, reg_set or {}, energy if energy is not None else {}, trace)


def solve_scenario(sid, margin=0.05, flow=None, max_iter=80):
    """Find the pressure-control setpoint that meets the sink pressure requirement."""
    scn = SCEN[sid]
    req = scn["required_sink_pressure_mpa"]
    key = "comp" if sid in COMPRESSOR_SETPOINTS else "reg"
    ids = COMPRESSOR_SETPOINTS.get(sid) or REGULATOR_SETPOINTS.get(sid)
    guess = req + 1.0
    energy, trace = {}, []
    st = sinks = None
    delivered = None
    hist = []
    for _ in range(max_iter):
        comp = {i: guess for i in ids} if key == "comp" else {}
        reg = {i: guess for i in ids} if key == "reg" else {}
        energy, trace = {}, []
        st, sinks = evaluate(sid, flow=flow, comp_set=comp, reg_set=reg, energy=energy, trace=trace)
        sink_list = sinks if sinks else [st]
        delivered = min(s[0] for s in sink_list)
        hist.append(delivered)
        delta = (req + margin) - delivered
        if abs(delta) < 1e-6:
            break
        guess += delta
    return dict(scenario=sid, delivered=delivered, required=req,
                setpoints=(comp if key == "comp" else reg), kind=key,
                state=st, sinks=sinks, energy=energy, trace=trace, flow=flow or scn["required_total_flow_kg_s"])


COMPRESSOR_SETPOINTS = {
    "INJ-LOW": ["ICOMP-1", "ICOMP-2", "ICOMP-3"],
    "INJ-MID": ["ICOMP-1", "ICOMP-2", "ICOMP-3"],
    "INJ-HIGH": ["ICOMP-1", "ICOMP-2", "ICOMP-3"],
    "WDR-LOW": ["WCOMP-1", "WCOMP-2"],
}
REGULATOR_SETPOINTS = {"WDR-HIGH": ["REG-1"], "WDR-MID": ["REG-1"]}


def solve_all(margin=0.05):
    return {sid: solve_scenario(sid, margin) for sid in SCEN}


# --------------------------------------------------------------------------------------
# n-1 (single equipment outage) operating cases
# --------------------------------------------------------------------------------------
def distribute(total, units, need):
    """Return per-unit flows for `need` kg/s over `units` (capacities/min stable honoured)."""
    caps = [MODELS[EQUIP[u][1]]["capacity_kg_s"] for u in units]
    mins = [MODELS[EQUIP[u][1]]["minimum_stable_flow_kg_s"] for u in units]
    if need > sum(caps) + 1e-9:
        return None
    flows = [min(c, need / len(units)) for c in caps]
    for _ in range(200):
        deficit = need - sum(flows)
        if deficit <= 1e-12:
            break
        slack = sum(caps[i] - flows[i] for i in range(len(units)) if flows[i] < caps[i] - 1e-12)
        if slack <= 1e-12:
            break
        for i in range(len(units)):
            if flows[i] < caps[i] - 1e-12:
                flows[i] += deficit * (caps[i] - flows[i]) / slack
    if abs(sum(flows) - need) > 1e-6:
        return None
    # put the required retained flow through the fewest units with stable flow
    for i in range(len(units)):
        if 1e-9 < flows[i] < mins[i] - 1e-9:
            return None
    return flows


def _par_index(chain, probe):
    for i, el in enumerate(chain):
        if el[0] == "par":
            for br in el[1]:
                if any(x[0] == "equip" and x[1] == probe for x in br):
                    return i
    raise KeyError(probe)


def n1_compressor_case(sid, failed, margin=0.05):
    """Scenario re-run at 70 % flow with `failed` compressor out of service."""
    scn = SCEN[sid]
    need = 0.7 * scn["required_total_flow_kg_s"]
    if sid.startswith("INJ"):
        all_units = ["ICOMP-1", "ICOMP-2", "ICOMP-3"]
        pipe_map = {"ICOMP-1": ("PL-IS-1", "PL-ID-1"), "ICOMP-2": ("PL-IS-2", "PL-ID-2"),
                    "ICOMP-3": ("PL-IS-3", "PL-ID-3")}
        base = D.SCENARIO_PATHS[sid]["chain"]
        par_index = _par_index(base, "ICOMP-1")
    else:
        all_units = ["WCOMP-1", "WCOMP-2"]
        pipe_map = {"WCOMP-1": ("PL-PC-C1", "PL-PC-C1o"), "WCOMP-2": ("PL-PC-C2", "PL-PC-C2o")}
        base = D.SCENARIO_PATHS[sid]["chain"]
        par_index = _par_index(base, "WCOMP-1")
    units = [u for u in all_units if u != failed]
    flows = distribute(scn["required_total_flow_kg_s"], units, need)
    if flows is None:
        return dict(ok=False, msg="insufficient retained compressor capacity")
    branches = []
    for u, f in zip(units, flows):
        pi, po = pipe_map[u]
        fr = f / need
        branches.append([("pipe", pi, fr), ("equip", u, fr, {"mode": "compress"}), ("pipe", po, fr)])
    chain = list(base)
    chain[par_index] = ("par", branches)
    return run_n1(sid, need, chain, margin)


def n1_treatment_case(sid, category, failed_train, margin=0.05):
    """Scenario re-run at 70 % flow with one separator or dehydration unit out."""
    scn = SCEN[sid]
    need = 0.7 * scn["required_total_flow_kg_s"]
    keep = [t for t in ("A", "B", "C") if t != failed_train]
    chains = []
    for t in keep:
        fr = 1.0 / len(keep)
        ch = [("pipe", "PL-T%s-1" % t, fr), ("equip", "SEP-%s" % t, fr, {}),
              ("pipe", "PL-T%s-2" % t, fr), ("equip", "DEH-%s" % t, fr, {}),
              ("pipe", "PL-T%s-3" % t, fr)]
        chains.append(ch)
    base = list(D.SCENARIO_PATHS[sid]["chain"])
    chain = base[:]
    chain[_par_index(base, "SEP-A")] = ("par", chains)
    return run_n1(sid, need, chain, margin)


def run_n1(sid, need, chain, margin=0.05):
    scn = SCEN[sid]
    req = scn["required_sink_pressure_mpa"]
    key = "comp" if sid in COMPRESSOR_SETPOINTS else "reg"
    ids = COMPRESSOR_SETPOINTS.get(sid) or REGULATOR_SETPOINTS.get(sid)
    guess = req + 1.0
    for _ in range(80):
        comp = {i: guess for i in ids} if key == "comp" else {}
        reg = {i: guess for i in ids} if key == "reg" else {}
        energy = {}
        try:
            st, sinks = run_chain(need, chain, boundary_state(scn, None), comp, reg, energy, None)
        except Blocker as ex:
            return dict(ok=False, msg=str(ex), flow=need)
        sink_list = sinks if sinks else [st]
        delivered = min(s[0] for s in sink_list)
        delta = (req + margin) - delivered
        if abs(delta) < 1e-6:
            break
        guess += delta
    ok = delivered >= req - 1e-6
    msgs = []
    for s in sink_list:
        P, T, water, fl = s
        d = B["req"]["gas_delivery_requirements"]
        if fl > d["maximum_free_liquid_mass_fraction"] + 1e-12:
            ok = False
            msgs.append("free liquid %.3e" % fl)
        if water > d["maximum_water_content_mg_sm3"] + 1e-9:
            ok = False
            msgs.append("water %.2f" % water)
        lo, hi = d["temperature_limits_c"]
        if not (lo - 1e-6 <= T <= hi + 1e-6):
            ok = False
            msgs.append("temperature %.2f" % T)
    return dict(ok=ok, flow=need, delivered=delivered, required=req,
                msg="retained %.1f kg/s delivered %.4f MPa %s" % (need, delivered, ";".join(msgs)))
