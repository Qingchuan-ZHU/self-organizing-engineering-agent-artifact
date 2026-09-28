"""
Scenario hydraulic / quality solver, reliability checks and lifecycle cost.

Implements brief/engineering_calculation_basis.md.
"""
from __future__ import annotations

import math

import ugslib as U
import design as D
import checks as C
from ugslib import CATALOG, CP, K_RATIO, CLASSES, DIAMETERS, density, viscosity


# ---------------------------------------------------------------------------
def _find_pipe(src, dst):
    for pid, p in D.PIPELINES.items():
        if p["src"] == src and p["dst"] == dst:
            return pid
        if p["src"] == dst and p["dst"] == src:
            return pid
    raise KeyError((src, dst))


# ---------------------------------------------------------------------------
class State:
    __slots__ = ("P", "T", "m", "water", "fl", "trace")

    def __init__(self, P, T, m, water, fl, trace=None):
        self.P, self.T, self.m = P, T, m
        self.water, self.fl = water, fl
        self.trace = trace if trace is not None else []


def pipedata(pid):
    cls = CLASSES[D.PIPELINES[pid]["cls"]]
    dn = DIAMETERS[D.PIPELINES[pid]["dn"]]
    return D.pipe_length(pid), dn["internal_diameter_m"], cls["roughness_m"]


def flow_pipe(st, pid, m=None):
    m = st.m if m is None else m
    L, diam, eps = pipedata(pid)
    res = U.solve_pipe(m, diam, L, st.P, st.T, eps)
    st.trace.append({"kind": "pipe", "id": pid, "L": L, "dn": D.PIPELINES[pid]["dn"],
                     "class": D.PIPELINES[pid]["cls"], "level": D.PIPELINES[pid]["level"],
                     "m": m, "P_in": st.P, "P_out": res["P_out"], "dP": res["dp"],
                     "v": res["v"], "Re": res["Re"], "rho": res["rho"],
                     "converged": res["converged"]})
    st.P = res["P_out"]
    return res


def flow_header(st, eid, m=None):
    m = st.m if m is None else m
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    dp = mod["pressure_drop_at_capacity_mpa"] * (m / mod["capacity_kg_s"]) ** 2
    st.trace.append({"kind": "header", "id": eid, "m": m, "P_in": st.P,
                     "P_out": st.P - dp, "dP": dp})
    st.P -= dp
    return dp


def flow_meter(st, eid, m=None):
    m = st.m if m is None else m
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    dp = mod["pressure_drop_mpa"]
    st.trace.append({"kind": "meter", "id": eid, "model": mod["model_id"], "m": m,
                     "P_in": st.P, "P_out": st.P - dp, "dP": dp})
    st.P -= dp
    return dp


def flow_compressor(st, eid, m, ratio):
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    P_in, T_in = st.P, st.T
    perf = U.compressor_performance(m, ratio, T_in, mod["efficiency_proxy"],
                                    mod["driver_efficiency"])
    st.P = P_in * ratio
    st.T = perf["T_out_c"]
    st.trace.append({"kind": "compressor", "id": eid, "model": mod["model_id"],
                     "m": m, "P_in": P_in, "P_out": st.P, "ratio": ratio,
                     "T_in": T_in, "T_out": st.T, "power_mw": perf["power_mw"]})
    return perf


def flow_cooler(st, eid, m, T_set):
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    T_in = st.T
    T_out = min(T_in, T_set)
    duty = m * CP * abs(T_out - T_in) / 1e6
    elec = duty * mod["electric_power_fraction_of_duty"]
    P_in = st.P
    st.P -= mod["pressure_drop_mpa"]
    st.T = T_out
    st.trace.append({"kind": "cooler", "id": eid, "model": mod["model_id"], "m": m,
                     "T_in": T_in, "T_out": T_out, "duty_mw": duty, "elec_mw": elec,
                     "P_in": P_in, "P_out": st.P})
    return duty, elec


def flow_regulator(st, eid, m, P_out):
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    P_in, T_in = st.P, st.T
    drop = max(0.0, P_in - P_out)
    T_out = T_in - mod["jt_temperature_coefficient_k_per_mpa"] * drop
    st.P, st.T = P_out, T_out
    st.trace.append({"kind": "regulator", "id": eid, "model": mod["model_id"], "m": m,
                     "P_in": P_in, "P_out": P_out, "T_in": T_in, "T_out": T_out})
    return T_out


def flow_dehyd(st, eid, m):
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    st.P -= mod["pressure_drop_mpa"]
    st.water = mod["normal_outlet_water_mg_sm3"]
    power = m * mod["energy_mw_per_kg_s"]
    st.trace.append({"kind": "dehydration", "id": eid, "model": mod["model_id"], "m": m,
                     "P_out": st.P, "water_out": st.water, "power_mw": power})
    return power


def flow_separator(st, eid, m, eta_L):
    mod = CATALOG[D.EQUIPMENT[eid]["model_id"]]
    fl_in = st.fl
    removed = m * fl_in * eta_L
    st.fl = fl_in * (1.0 - eta_L)
    st.P -= mod["pressure_drop_mpa"]
    st.trace.append({"kind": "separator", "id": eid, "model": mod["model_id"], "m": m,
                     "P_out": st.P, "fl_in": fl_in, "fl_out": st.fl,
                     "liquid_removed_kg_s": removed})
    return removed


# ---------------------------------------------------------------------------
SCEN = {s["scenario_id"]: s for s in U.SCENARIOS["scenarios"]}
WELL_IDS = ["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"]
WELL_PORT = {"WG-01": "branch_11", "WG-02": "branch_07", "WG-03": "branch_03",
             "WG-04": "branch_04", "WG-05": "branch_08", "WG-06": "branch_12"}
WELL_PIPE = {w: _find_pipe(("E", "HM", WELL_PORT[w]), ("B", w, "gas")) for w in WELL_IDS}

SEP_LIST = ["SEP1", "SEP2", "SEP3"]
DH_LIST = ["DH1", "DH2", "DH3"]
COMP_LIST = ["C1", "C2", "C3"]

SEP_FEED = {s: _find_pipe(("E", "HSI", pp), ("E", s, "gas_in"))
            for s, pp in (("SEP1", "branch_04"), ("SEP2", "branch_08"), ("SEP3", "branch_07"))}
SEP_OUT = {s: _find_pipe(("E", s, "gas_out"), ("E", "HSD", pp))
           for s, pp in (("SEP1", "branch_04"), ("SEP2", "branch_08"), ("SEP3", "branch_03"))}
SEP_LIQ = {s: _find_pipe(("E", s, "liquid_out"), ("E", d, "drain_in"))
           for s, d in (("SEP1", "D1"), ("SEP2", "D2"), ("SEP3", "D3"))}
DRN_OUT = {d: _find_pipe(("E", d, "drain_out"), ("B", "LIQUID-DRAIN-OUTFALL", "drain"))
           for d in ("D1", "D2", "D3")}
DH_IN = {s: _find_pipe(("E", "HSD", pp), ("E", s, "gas_in"))
         for s, pp in (("DH1", "branch_02"), ("DH2", "branch_06"), ("DH3", "branch_10"))}
DH_OUT = {s: _find_pipe(("E", s, "gas_out"), ("E", "HCS", pp))
          for s, pp in (("DH1", "branch_04"), ("DH2", "branch_08"), ("DH3", "branch_07"))}
C_SUCT = {c: _find_pipe(("E", "HCS", pp), ("E", c, "suction"))
          for c, pp in (("C1", "branch_01"), ("C2", "branch_05"), ("C3", "branch_09"))}
C_DISC = {c: _find_pipe(("E", c, "discharge"), ("E", "HCD", pp))
          for c, pp in (("C1", "branch_04"), ("C2", "branch_07"), ("C3", "branch_08"))}

PL_HM_HSI = _find_pipe(("E", "HM", "branch_05"), ("E", "HSI", "branch_05"))
PL_BYPASS = _find_pipe(("E", "HCS", "branch_10"), ("E", "HCD", "branch_03"))
PL_HCD_COOL = _find_pipe(("E", "HCD", "branch_01"), ("E", "COOL", "gas_in"))
PL_COOL_HM = _find_pipe(("E", "COOL", "gas_out"), ("E", "HM", "branch_01"))
PL_HCD_REG = _find_pipe(("E", "HCD", "branch_02"), ("E", "REG", "gas_in"))
PL_REG_MW = _find_pipe(("E", "REG", "gas_out"), ("E", "MW", "gas_in"))
PL_MW_GRID = _find_pipe(("E", "MW", "gas_out"), ("B", "GRID-TIE", "gas"))
PL_GRID_MI = _find_pipe(("B", "GRID-TIE", "gas"), ("E", "MI", "gas_in"))
PL_MI_HCS = _find_pipe(("E", "MI", "gas_out"), ("E", "HCS", "branch_06"))

DELIV_MAX_FL = U.PROJECT["gas_delivery_requirements"]["maximum_free_liquid_mass_fraction"]
DELIV_MAX_W = U.PROJECT["gas_delivery_requirements"]["maximum_water_content_mg_sm3"]
DELIV_T = U.PROJECT["gas_delivery_requirements"]["temperature_limits_c"]


# ---------------------------------------------------------------------------
def _mix(states, flows):
    """Gas-flow-weighted temperature/water/free-liquid mixing; pressure = min."""
    tot = sum(flows)
    if tot <= 0:
        return states[0]
    T = sum(s.T * f for s, f in zip(states, flows)) / tot
    w = sum(s.water * f for s, f in zip(states, flows)) / tot
    fl = sum(s.fl * f for s, f in zip(states, flows)) / tot
    out = State(min(s.P for s in states), T, tot, w, fl)
    out.trace = [x for s in states for x in s.trace]
    return out


def solve_injection(sid, comp_lineup, T_cool=40.0, flow=None):
    """comp_lineup: {comp_id: flow_kg_s}; units with flow<=0 are offline."""
    sc = SCEN[sid]
    m = sc["required_total_flow_kg_s"] if flow is None else flow
    treq = sc["required_sink_pressure_mpa"]
    well_flows = {w: m / 6.0 for w in WELL_IDS}
    online = [(c, f) for c, f in comp_lineup.items() if f > 0]

    st = State(sc["source_pressure_mpa"], sc["source_temperature_c"], m,
               sc["source_water_mg_sm3"], sc["source_free_liquid_mass_fraction"])
    flow_pipe(st, PL_GRID_MI)
    flow_meter(st, "MI")
    flow_pipe(st, PL_MI_HCS)
    flow_header(st, "HCS")
    P_suct, T_suct = st.P, st.T
    up_trace = st.trace

    def evaluate(P_cd):
        outs, flows, powers, ratios = [], [], [], []
        for c, f in online:
            s2 = State(P_suct, T_suct, f, st.water, st.fl, [])
            flow_pipe(s2, C_SUCT[c], f)
            r = P_cd / s2.P
            perf = flow_compressor(s2, c, f, r)
            ratios.append(r)
            flow_pipe(s2, C_DISC[c], f)
            outs.append(s2)
            flows.append(f)
            powers.append(perf["power_mw"])
        comp = _mix(outs, flows)
        comp.m = m
        comp.trace = [x for s2 in outs for x in s2.trace]
        flow_header(comp, "HCD")
        flow_pipe(comp, PL_HCD_COOL)
        flow_cooler(comp, "COOL", m, T_cool)
        flow_pipe(comp, PL_COOL_HM)
        flow_header(comp, "HM")
        dels = {}
        for w, f in well_flows.items():
            s3 = State(comp.P, comp.T, f, comp.water, comp.fl, [])
            flow_pipe(s3, WELL_PIPE[w], f)
            dels[w] = s3
        return comp, outs, flows, powers, dels, ratios

    lo, hi = P_suct * 1.0001, P_suct * 2.5
    for _ in range(42):
        mid = (lo + hi) / 2.0
        comp, outs, flows, powers, dels, ratios = evaluate(mid)
        worst = min(d.P for d in dels.values())
        if worst > treq:
            hi = mid
        else:
            lo = mid
    P_cd = (lo + hi) / 2.0
    comp, outs, flows, powers, dels, ratios = evaluate(P_cd)
    # mixing temperature for reporting
    T_disc = sum(o.T * f for o, f in zip(outs, flows)) / sum(flows)
    return {
        "scenario": sid, "service": "injection", "total_flow": m,
        "well_flows": well_flows, "ratio": max(ratios), "ratios": ratios,
        "suction_P": P_suct, "suction_T": T_suct,
        "discharge_P": P_cd, "discharge_T": T_disc, "header_HM_P": comp.P,
        "compressor_power_mw": sum(powers), "compressor_split": dict(online),
        "compressor_flows": {c: f for c, f in online},
        "delivery": {w: {"P": d.P, "T": d.T, "water": d.water, "fl": d.fl}
                     for w, d in dels.items()},
        "trace": up_trace + comp.trace + [x for d in dels.values() for x in d.trace],
        "aux_power_mw": sum(x["elec_mw"] for x in comp.trace if x["kind"] == "cooler"),
        "dehyd_power_mw": 0.0,
    }


def solve_withdrawal(sid, comp_lineup=None, use_bypass=True, sep_list=None,
                     dh_list=None, flow=None):
    sc = SCEN[sid]
    sep_list = SEP_LIST if sep_list is None else sep_list
    dh_list = DH_LIST if dh_list is None else dh_list
    m = sc["required_total_flow_kg_s"] if flow is None else flow
    treq = sc["required_sink_pressure_mpa"]
    well_flows = {w: m / 6.0 for w in WELL_IDS}

    # --- 6 well branches into HM; mixed pressure = lowest incoming --------
    branches = []
    for w in WELL_IDS:
        f = well_flows[w]
        s2 = State(sc["source_pressure_mpa"], sc["source_temperature_c"], f,
                   sc["source_water_mg_sm3"], sc["source_free_liquid_mass_fraction"])
        flow_pipe(s2, WELL_PIPE[w], f)
        branches.append(s2)
    st = _mix(branches, [well_flows[w] for w in WELL_IDS])
    st.m = m
    flow_header(st, "HM")
    flow_pipe(st, PL_HM_HSI)
    flow_header(st, "HSI")

    # --- separator bank ---------------------------------------------------
    nsep = len(sep_list)
    sepin = []
    for s in sep_list:
        f = m / nsep
        s2 = State(st.P, st.T, f, st.water, st.fl, [])
        flow_pipe(s2, SEP_FEED[s], f)
        sepin.append(s2)
    sepA = _mix(sepin, [m / nsep] * nsep)
    sepA.m = m
    removed = 0.0
    sepouts = []
    for s in sep_list:
        f = m / nsep
        s3 = State(sepA.P, sepA.T, f, sepA.water, sepA.fl, [])
        mod = CATALOG[D.EQUIPMENT[s]["model_id"]]
        removed += flow_separator(s3, s, f, mod["liquid_removal_efficiency"])
        flow_pipe(s3, SEP_OUT[s], f)
        sepouts.append(s3)
    sepB = _mix(sepouts, [m / nsep] * nsep)
    sepB.m = m
    flow_header(sepB, "HSD")

    # liquid side streams: each separator -> its closed drain -> outfall
    liq_trace = []
    m_liq = removed / nsep
    for i, sep in enumerate(sep_list):
        drn = ("D1", "D2", "D3")[i]
        liq_trace.append({"kind": "closed_drain", "id": drn,
                          "model": CATALOG[D.EQUIPMENT[drn]["model_id"]]["model_id"],
                          "m": m_liq, "P_in": 1.0, "P_out": 1.0, "dp": 0.0})
        for pid in (SEP_LIQ[sep], DRN_OUT[drn]):
            d = DIAMETERS[D.PIPELINES[pid]["dn"]]["internal_diameter_m"]
            a = 3.141592653589793 * d * d / 4.0
            liq_trace.append({"kind": "pipe", "id": pid, "L": D.pipe_length(pid),
                              "dn": D.PIPELINES[pid]["dn"], "class": D.PIPELINES[pid]["cls"],
                              "level": D.PIPELINES[pid]["level"], "m": m_liq,
                              "P_in": 1.0, "P_out": 1.0, "dP": 0.0,
                              "v": m_liq / (U.LIQUID_DENSITY * a), "Re": 0.0,
                              "rho": U.LIQUID_DENSITY, "converged": True})

    # --- dehydration bank -------------------------------------------------
    ndh = len(dh_list)
    dhin = []
    for s in dh_list:
        f = m / ndh
        s2 = State(sepB.P, sepB.T, f, sepB.water, sepB.fl, [])
        flow_pipe(s2, DH_IN[s], f)
        dhin.append(s2)
    dhA = _mix(dhin, [m / ndh] * ndh)
    dhA.m = m
    dh_energy = 0.0
    dhouts = []
    for s in dh_list:
        f = m / ndh
        s3 = State(dhA.P, dhA.T, f, dhA.water, dhA.fl, [])
        dh_energy += flow_dehyd(s3, s, f)
        flow_pipe(s3, DH_OUT[s], f)
        dhouts.append(s3)
    dhB = _mix(dhouts, [m / ndh] * ndh)
    dhB.m = m
    flow_header(dhB, "HCS")
    P_suct, T_suct = dhB.P, dhB.T
    REG_JT = CATALOG[D.EQUIPMENT["REG"]["model_id"]]["jt_temperature_coefficient_k_per_mpa"]

    def downstream(Q, T_at_REG_out, trace):
        s = State(Q, T_at_REG_out, m, dhB.water, dhB.fl, trace)
        flow_pipe(s, PL_REG_MW)
        flow_meter(s, "MW")
        flow_pipe(s, PL_MW_GRID)
        return s

    def reg_out_for(P_in, T_in):
        """Regulator outlet pressure that puts GRID-TIE exactly on the limit."""
        Q = P_in
        for _ in range(200):
            s = downstream(Q, T_in - REG_JT * (P_in - Q), [])
            err = s.P - treq
            if abs(err) < 1e-13:
                break
            Q -= err
        return Q

    def delivery_at(P_reg_in, T_reg_in):
        """Regulate and deliver; returns (state, regulator outlet pressure)."""
        Q = P_reg_in
        for _ in range(90):
            T_rego = T_reg_in - REG_JT * max(0.0, P_reg_in - Q)
            s = downstream(Q, T_rego, [])
            err = s.P - treq
            if abs(err) < 1e-13:
                break
            Q -= err
        Q = min(Q, P_reg_in)          # a regulator can only reduce pressure
        T_rego = T_reg_in - REG_JT * max(0.0, P_reg_in - Q)
        s = downstream(Q, T_rego, [])
        return s, Q

    if use_bypass:
        s = State(P_suct, T_suct, m, dhB.water, dhB.fl, [])
        flow_pipe(s, PL_BYPASS, m)
        flow_header(s, "HCD")
        flow_pipe(s, PL_HCD_REG)
        delivery, Q = delivery_at(s.P, s.T)
        flow_regulator(s, "REG", m, Q)
        delivery.trace = s.trace + delivery.trace
        comp_power, r, T_hot, P_hcd_in = 0.0, None, None, None
    else:
        if comp_lineup is None:
            comp_lineup = {"C1": m / 2.0, "C2": m / 2.0}
        online = [(c, f) for c, f in comp_lineup.items() if f > 0]

        def eval_comp(P_cd):
            ss, fs, powers = [], [], []
            for c, f in online:
                s2 = State(P_suct, T_suct, f, dhB.water, dhB.fl, [])
                flow_pipe(s2, C_SUCT[c], f)
                r = P_cd / s2.P
                perf = flow_compressor(s2, c, f, r)
                flow_pipe(s2, C_DISC[c], f)
                ss.append(s2)
                fs.append(f)
                powers.append(perf["power_mw"])
            cm = _mix(ss, fs)
            cm.m = m
            flow_header(cm, "HCD")
            flow_pipe(cm, PL_HCD_REG)
            return cm, r, powers

        lo, hi = P_suct * 1.0000001, P_suct * 2.0
        while True:
            cm, _, _ = eval_comp(hi)
            d, _ = delivery_at(cm.P, cm.T)
            if d.P >= treq - 1e-9:
                break
            hi = P_suct + (hi - P_suct) * 2.0
            if hi > P_suct * 2.4:
                break
        for _ in range(45):
            mid = (lo + hi) / 2.0
            cm, _, _ = eval_comp(mid)
            d, _ = delivery_at(cm.P, cm.T)
            if d.P >= treq - 1e-9:
                hi = mid
            else:
                lo = mid
        P_hcd_in = hi
        cm, r, powers = eval_comp(P_hcd_in)
        d, Q = delivery_at(cm.P, cm.T)
        flow_regulator(cm, "REG", m, Q)
        delivery = d
        delivery.trace = cm.trace + d.trace
        comp_power = sum(powers)
        T_hot = cm.T

    return {
        "scenario": sid, "service": "withdrawal", "total_flow": m,
        "well_flows": well_flows, "use_bypass": use_bypass, "ratio": r,
        "suction_P": P_suct, "suction_T": T_suct,
        "compressor_power_mw": comp_power, "compressor_split": comp_lineup,
        "regulator_out_P": Q,
        "liquid_total_kg_s": removed,
        "liquid_per_separator_kg_s": removed / nsep,
        "delivery": {"GRID-TIE": {"P": delivery.P, "T": delivery.T,
                                  "water": delivery.water, "fl": delivery.fl}},
        "trace": (st.trace + sepA.trace + sepB.trace + dhA.trace + dhB.trace
                  + liq_trace + delivery.trace),
        "aux_power_mw": 0.0, "dehyd_power_mw": dh_energy,
        "sep_out_P": sepB.P, "dehyd_out_P": dhB.P,
    }
