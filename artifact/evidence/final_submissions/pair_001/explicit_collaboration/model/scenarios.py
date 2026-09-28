"""Scenario operating plans and the steady-state network solver."""
import math
import catalog as C
import design as D
import geometry as G
import process as PR


# --------------------------------------------------------------- pipe data
def pipe_table():
    out = {}
    for pid, src, dst, wp, dn, cls, level, service, note in D.PIPELINES:
        pts = G.simplify([tuple(p) for p in wp])
        length = G.polyline_length(pts)
        out[pid] = {"id": pid, "src": src, "dst": dst, "pts": pts,
                    "length_m": length, "dn": dn,
                    "id_m": C.DIAMS[dn]["internal_diameter_m"],
                    "cost_rate": C.DIAMS[dn]["installed_cost_mbcu_per_m"],
                    "class": cls, "level": level, "service": service,
                    "note": note, "nseg": len(pts) - 1}
    return out


PIPES = pipe_table()

# --------------------------------------------------------------- constants
SINK_MARGIN = 0.05          # MPa delivery margin used for setpoint sizing
COOLER_SETPOINT_C = 40.0    # injection aftercooler outlet setpoint (>=35 C)
REG_SETPOINT_MPA = 6.20     # grid pressure-control setpoint (withdrawal)

WELL_IDS = ["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"]
WELL_BRANCH = {"WG-01": "P13", "WG-02": "P14", "WG-03": "P15",
               "WG-04": "P16", "WG-05": "P17", "WG-06": "P18"}

E_MODEL = {eid: model for eid, model, _c, _o in D.EQUIPMENT}


def state(flow, p, t, water, liquid):
    return {"flow": flow, "p": p, "t": t, "water": water, "liquid": liquid}


def mix(states):
    flow = sum(s["flow"] for s in states)
    if flow <= 0:
        return dict(states[0])
    return state(flow,
                 min(s["p"] for s in states),
                 sum(s["t"] * s["flow"] for s in states) / flow,
                 sum(s["water"] * s["flow"] for s in states) / flow,
                 sum(s["liquid"] * s["flow"] for s in states) / flow)


# ------------------------------------------------------- element evaluators
def eval_pipe(pid, st, rep):
    p = PIPES[pid]
    d = p["id_m"]
    eps = C.CLASSES[p["class"]]["roughness_m"]
    v_in = PR.pipe_velocity(st["flow"], st["p"], st["t"], d)
    p_out, conv, n = PR.pipe_outlet_pressure(st["flow"], st["p"], st["t"], p["length_m"], d, eps)
    v_out = PR.pipe_velocity(st["flow"], max(p_out, 1e-6), st["t"], d)
    rep["pipes"].append({
        "pipe": pid, "note": p["note"], "flow_kg_s": st["flow"],
        "p_in_mpa": st["p"], "p_out_mpa": p_out, "dp_mpa": st["p"] - p_out,
        "t_c": st["t"], "velocity_m_s": max(v_in, v_out),
        "water_mg_sm3": st["water"], "liquid_loading": st["liquid"],
        "length_m": p["length_m"], "dn": p["dn"], "class": p["class"],
        "level": p["level"], "converged": conv, "updates": n})
    return state(st["flow"], p_out, st["t"], st["water"], st["liquid"])


def eval_equip(eid, st, rep, ctx, **kw):
    m = C.MODELS[E_MODEL[eid]]
    cat = m["category"]
    flow, p, t = st["flow"], st["p"], st["t"]
    out = dict(st)
    rec = {"equipment": eid, "model": m["model_id"], "category": cat,
           "flow_kg_s": flow, "p_in_mpa": p, "t_in_c": t}
    if cat == "header":
        dp = m["pressure_drop_at_capacity_mpa"] * (flow / m["capacity_kg_s"]) ** 2
        out["p"] = max(1e-6, p - dp)
        rec.update({"dp_mpa": dp, "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    elif cat == "meter":
        dp = m["pressure_drop_mpa"]
        out["p"] = max(1e-6, p - dp)
        rec.update({"dp_mpa": dp, "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    elif cat == "regulator":
        p_out = ctx.get("reg_setpoint_mpa", REG_SETPOINT_MPA)
        if p_out > p + 1e-9:
            raise ValueError(f"{eid}: inlet {p:.4f} below regulator setpoint {p_out}")
        dT = m["jt_temperature_coefficient_k_per_mpa"] * (p - p_out)
        out["p"] = p_out
        out["t"] = t - dT
        rec.update({"p_out_mpa": p_out, "t_out_c": out["t"], "jt_drop_k": dT,
                    "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    elif cat == "cooler":
        sp = ctx.get("cooler_setpoint_c", COOLER_SETPOINT_C)
        t_out = max(sp, m["minimum_outlet_temperature_c"]) if t > sp else t
        duty = flow * PR.CP * abs(t_out - t) / 1e6
        dp = m["pressure_drop_mpa"]
        out["t"] = t_out
        out["p"] = max(1e-6, p - dp)
        rec.update({"t_out_c": t_out, "duty_mw": duty, "dp_mpa": dp,
                    "electric_mw": duty * m["electric_power_fraction_of_duty"],
                    "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    elif cat == "compressor":
        p_out = ctx["comp_discharge_mpa"]
        ratio = p_out / p
        eta = m["efficiency_proxy"]
        t_out = PR.compressor_outlet_temperature(t, ratio, eta)
        power = PR.compressor_power_mw(flow, t, ratio, eta, m["driver_efficiency"])
        out["p"], out["t"] = p_out, t_out
        rec.update({"p_out_mpa": p_out, "ratio": ratio, "t_out_c": t_out,
                    "power_mw": power, "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"],
                    "minimum_stable_flow_kg_s": m["minimum_stable_flow_kg_s"]})
    elif cat in ("separator", "filter"):
        dp = m["pressure_drop_mpa"]
        out["p"] = max(1e-6, p - dp)
        eta_l = m["liquid_removal_efficiency"]
        removed = flow * st["liquid"] * eta_l
        out["liquid"] = st["liquid"] * (1.0 - eta_l)
        rec.update({"dp_mpa": dp, "liquid_removed_kg_s": removed,
                    "feed_free_liquid": st["liquid"],
                    "liquid_out_loading": out["liquid"],
                    "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    elif cat == "dehydration":
        dp = m["pressure_drop_mpa"]
        out["p"] = max(1e-6, p - dp)
        out["water"] = m["normal_outlet_water_mg_sm3"]
        rec.update({"dp_mpa": dp, "feed_free_liquid": st["liquid"],
                    "energy_mw": flow * m["energy_mw_per_kg_s"],
                    "capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    elif cat == "closed_drain":
        rec.update({"capacity_kg_s": m["capacity_kg_s"],
                    "utilisation": flow / m["capacity_kg_s"]})
    else:
        raise ValueError(f"unhandled category {cat}")
    rec["p_out_mpa"] = out["p"]
    rec.update(kw)
    rep["equipment"].append(rec)
    return out


def step_eval(step, st, rep, ctx):
    kind = step[0]
    if kind in ("pipe", "equip"):
        s = dict(st)
        if len(step) > 2:
            s["flow"] = step[2]
        if kind == "pipe":
            return eval_pipe(step[1], s, rep)
        kw = step[3] if len(step) > 3 else {}
        return eval_equip(step[1], s, rep, ctx, **kw)
    raise ValueError(kind)


def run_plan(plan, st0, ctx, rep):
    """Walk a plan; return (final mixed state, last-stage states)."""
    st = st0
    sink_states = [st]
    for i, step in enumerate(plan):
        if step[0] == "parallel":
            outs = []
            for sub in step[1]:
                s = dict(st)
                for s2 in sub:
                    if isinstance(s2, tuple):
                        s = step_eval(s2, s, rep, ctx)
                    else:                      # nested step list
                        s = run_plan(s2, s, ctx, rep)[0]
                outs.append(s)
            st = mix(outs)
            if i == len(plan) - 1:
                sink_states = outs
        else:
            st = step_eval(step, st, rep, ctx)
            if i == len(plan) - 1:
                sink_states = [st]
    return st, sink_states


# ------------------------------------------------------------ path builders
# lane = (separator, dehydrator, compressor, feed pipe, sep->dehy pipe,
#         dehy->suction pipe, compressor suction pipe, compressor discharge pipe)
LANES = [("SEP-A", "DEH-A", "CMP-A", "P19", "P22", "P28", "P03", "P06"),
         ("SEP-B", "DEH-B", "CMP-B", "P20", "P23", "P29", "P04", "P07"),
         ("SEP-C", "DEH-C", "CMP-C", "P21", "P24", "P30", "P05", "P08")]


def lanecols(i):
    sep, deh, cmp_, feed, sep2deh, deh2suc, suc, dis = LANES[i]
    return {"sep": sep, "deh": deh, "cmp": cmp_, "feed": feed, "sep2deh": sep2deh,
            "deh2suc": deh2suc, "suc": suc, "dis": dis}


def injection_plan(flow, active_cmp=(0, 1, 2)):
    per = flow / float(len(active_cmp))
    lanes = [[("pipe", lanecols(i)["suc"], per), ("equip", lanecols(i)["cmp"], per),
              ("pipe", lanecols(i)["dis"], per)] for i in active_cmp]
    wells = [[("pipe", WELL_BRANCH[w], flow / 6.0)] for w in WELL_IDS]
    return [
        ("pipe", "P01", flow),
        ("equip", "MTR-A", flow),
        ("pipe", "P02", flow),
        ("equip", "H-SUC", flow),
        ("parallel", lanes),
        ("equip", "H-DIS", flow),
        ("pipe", "P10", flow),
        ("equip", "COOL", flow),
        ("pipe", "P11", flow),
        ("equip", "H-SITE", flow),
        ("pipe", "P12", flow),
        ("equip", "H-WELL", flow),
        ("parallel", wells),
    ]


def withdrawal_plan(flow, compress=True, active_sep=(0, 1, 2), active_deh=(0, 1, 2),
                    active_cmp=(0, 1, 2)):
    per_sep = flow / float(len(active_sep))
    per_deh = flow / float(len(active_deh))
    per_cmp = flow / float(len(active_cmp))
    pre = [[("pipe", lanecols(i)["feed"], per_sep), ("equip", lanecols(i)["sep"], per_sep),
            ("pipe", lanecols(i)["sep2deh"], per_sep),
            ("equip", lanecols(i)["deh"], per_sep),
            ("pipe", lanecols(i)["deh2suc"], per_sep)] for i in active_sep]
    post = []
    if compress:
        mid = [[("pipe", lanecols(i)["suc"], per_cmp), ("equip", lanecols(i)["cmp"], per_cmp),
                ("pipe", lanecols(i)["dis"], per_cmp)] for i in active_cmp]
        comp = ("parallel", mid)
    else:
        comp = ("pipe", "P09", flow)
    wells = [[("pipe", WELL_BRANCH[w], flow / 6.0)] for w in WELL_IDS]
    return [
        ("parallel", wells),
        ("equip", "H-WELL", flow),
        ("pipe", "P12", flow),
        ("equip", "H-SITE", flow),
        ("parallel", pre),
        ("equip", "H-SUC", flow),
        comp,
        ("equip", "H-DIS", flow),
        ("pipe", "P31", flow),
        ("equip", "REG", flow),
        ("pipe", "P32", flow),
        ("equip", "MTR-B", flow),
        ("pipe", "P33", flow),
    ]
