"""Case driver: runs every required operating case, checks limits, costs the design."""
import math
import catalog as C
import design as D
import process as PR
import scenarios as S

SCEN_BY_ID = {s["scenario_id"]: s for s in C.SCEN["scenarios"]}
PVF = PR.pvf(C.ECON["discount_rate"], C.ECON["project_life_years"])
DELIV = C.REQS["gas_delivery_requirements"]
WET_WATER = DELIV["maximum_water_content_mg_sm3"]
WET_LIQ = DELIV["maximum_free_liquid_mass_fraction"]
WELL_IDS = S.WELL_IDS


def is_wet(water, liquid):
    return water > WET_WATER + 1e-5 or liquid > WET_LIQ + 1e-9


def needs_compression(scen):
    return scen["required_sink_pressure_mpa"] > scen["source_pressure_mpa"]


def build_plan(scen, flow, outage=None):
    keep = {0, 1, 2}
    if outage:
        keep = {i for i in (0, 1, 2) if i != outage[1]}
    act = tuple(sorted(keep))
    if scen["service"] == "injection":
        return S.injection_plan(flow, active_cmp=act)
    kw = {}
    if outage and outage[0] == "separator":
        kw["active_sep"] = act
    if outage and outage[0] in ("separator", "dehydration"):
        # no separator or dehydrator bypass exists: an outage of either unit
        # isolates the whole treatment train (all gas must be dehydrated).
        kw["active_sep"] = act
        kw["active_deh"] = act
    if outage and outage[0] == "compressor":
        kw["active_cmp"] = act
    return S.withdrawal_plan(flow, compress=needs_compression(scen), **kw)


def run_case(scen_id, flow=None, outage=None, label=None):
    scen = SCEN_BY_ID[scen_id]
    flow = scen["required_total_flow_kg_s"] if flow is None else flow
    plan = build_plan(scen, flow, outage)
    ctx = {}
    t_in = scen["source_temperature_c"]
    water = scen["source_water_mg_sm3"]
    liquid = scen["source_free_liquid_mass_fraction"]
    inj = scen["service"] == "injection"
    if inj:
        target = scen["required_sink_pressure_mpa"] + S.SINK_MARGIN
        lo, hi = 1e-3, 20.0
        for _ in range(28):
            mid = 0.5 * (lo + hi)
            ctx["comp_discharge_mpa"] = mid
            rep = {"pipes": [], "equipment": []}
            _, sinks = S.run_plan(plan, S.state(flow, scen["source_pressure_mpa"], t_in,
                                                water, liquid), ctx, rep)
            worst = min(s["p"] for s in sinks)
            if worst < target:
                lo = mid
            else:
                hi = mid
            if abs(worst - target) < 1e-7:
                break
        ctx["comp_discharge_mpa"] = hi
    elif needs_compression(scen):
        ctx["comp_discharge_mpa"] = 6.30
    rep = {"pipes": [], "equipment": []}
    st, sinks = S.run_plan(plan, S.state(flow, scen["source_pressure_mpa"], t_in, water, liquid),
                           ctx, rep)
    if inj:
        sank = list(zip(WELL_IDS, sinks))
    else:
        sank = [("GRID-TIE", st)]
    return {"scenario": scen, "case": label or scen_id, "flow": flow, "outage": outage,
            "plan": plan, "ctx": ctx, "rep": rep, "sinks": sank, "final": st,
            "needs_compression": needs_compression(scen)}


# ------------------------------------------------------------ limit checking
def check_case(res):
    errs = []
    scen = res["scenario"]
    flow = res["flow"]
    sid = res["case"]
    for r in res["rep"]["equipment"]:
        m = C.MODELS[r["model"]]
        cat = r["category"]
        cap = r.get("capacity_kg_s")
        if cap is not None and r["flow_kg_s"] > cap + 1e-5:
            errs.append(f"{sid}: {r['equipment']} flow {r['flow_kg_s']:.4f} > capacity {cap}")
        p_max = m.get("maximum_pressure_mpa")
        if p_max is not None and r["p_in_mpa"] > p_max + 1e-5:
            errs.append(f"{sid}: {r['equipment']} pressure {r['p_in_mpa']:.4f} > max {p_max}")
        if cat == "compressor":
            if r["ratio"] > m["maximum_pressure_ratio"] + 1e-9:
                errs.append(f"{sid}: {r['equipment']} pressure ratio {r['ratio']:.4f} > "
                            f"{m['maximum_pressure_ratio']}")
            if r["p_out_mpa"] > m["maximum_discharge_pressure_mpa"] + 1e-5:
                errs.append(f"{sid}: {r['equipment']} discharge pressure above limit")
            if r["p_in_mpa"] > m["maximum_suction_pressure_mpa"] + 1e-5:
                errs.append(f"{sid}: {r['equipment']} suction pressure above limit")
            if r["t_in_c"] > m["maximum_suction_temperature_c"] + 1e-6:
                errs.append(f"{sid}: {r['equipment']} suction temperature above limit")
            if r["t_out_c"] > m["maximum_discharge_temperature_c"] + 1e-6:
                errs.append(f"{sid}: {r['equipment']} discharge temperature above limit")
            if r["power_mw"] > m["maximum_power_mw"] + 1e-9:
                errs.append(f"{sid}: {r['equipment']} driver power above limit")
            if r["flow_kg_s"] < m["minimum_stable_flow_kg_s"] - 1e-9:
                errs.append(f"{sid}: {r['equipment']} flow below minimum stable flow")
        if cat == "cooler":
            if r.get("duty_mw", 0) > m["maximum_duty_mw"] + 1e-9:
                errs.append(f"{sid}: {r['equipment']} duty above limit")
            if r["t_out_c"] < m["minimum_outlet_temperature_c"] - 1e-6:
                errs.append(f"{sid}: {r['equipment']} outlet temperature below limit")
        if cat in ("separator", "filter"):
            if r["liquid_removed_kg_s"] > m["maximum_liquid_rate_kg_s"] + 1e-9:
                errs.append(f"{sid}: {r['equipment']} liquid rate "
                            f"{r['liquid_removed_kg_s']:.4f} > {m['maximum_liquid_rate_kg_s']}")
        if cat in ("separator", "filter", "dehydration"):
            if r.get("feed_free_liquid") is not None and \
                    r["feed_free_liquid"] > m["maximum_feed_free_liquid_fraction"] + 1e-9:
                errs.append(f"{sid}: {r['equipment']} feed free liquid "
                            f"{r['feed_free_liquid']:.3e} > "
                            f"{m['maximum_feed_free_liquid_fraction']}")
    for r in res["rep"]["pipes"]:
        pid = r["pipe"]
        pdef = S.PIPES[pid]
        cls = C.CLASSES[r["class"]]
        limit = (C.PIPING["maximum_liquid_drain_velocity_m_s"]
                 if pdef["service"] == "liquid" else C.PIPING["maximum_gas_velocity_m_s"])
        if r["velocity_m_s"] > limit + 1e-6:
            errs.append(f"{sid}: {pid} velocity {r['velocity_m_s']:.3f} > {limit} m/s")
        p_hi = max(r["p_in_mpa"], r["p_out_mpa"])
        if p_hi > cls["maximum_allowable_pressure_mpa"] + 1e-5:
            errs.append(f"{sid}: {pid} pressure {p_hi:.4f} > class rating "
                        f"{cls['maximum_allowable_pressure_mpa']}")
        lo, hi = cls["temperature_limits_c"]
        if r["t_c"] > hi + 1e-4 or r["t_c"] < lo - 1e-4:
            errs.append(f"{sid}: {pid} temperature {r['t_c']:.2f} outside class range")
        if pdef["service"] == "liquid":
            if not cls["liquid_drain_compatible"]:
                errs.append(f"{sid}: {pid} class is not liquid-drain compatible")
        else:
            wet = is_wet(r["water_mg_sm3"], r["liquid_loading"])
            if wet and not cls["wet_gas_compatible"]:
                errs.append(f"{sid}: {pid} carries wet gas but class is not wet compatible")
            if (not wet) and not cls["dry_gas_compatible"]:
                errs.append(f"{sid}: {pid} carries dry gas but class is not dry compatible")
        if not r["converged"]:
            errs.append(f"{sid}: {pid} pressure loss did not converge within 8 updates")
    for wid, st in res["sinks"]:
        if st["liquid"] > WET_LIQ + 1e-9:
            errs.append(f"{sid}: {wid} free-liquid loading {st['liquid']:.3e} > {WET_LIQ}")
        if st["water"] > WET_WATER + 1e-5:
            errs.append(f"{sid}: {wid} water content {st['water']:.3f} > {WET_WATER}")
        lo, hi = DELIV["temperature_limits_c"]
        if st["t"] > hi + 1e-4 or st["t"] < lo - 1e-4:
            errs.append(f"{sid}: {wid} temperature {st['t']:.3f} outside {lo}..{hi}")
        if st["p"] < scen["required_sink_pressure_mpa"] - 1e-5:
            errs.append(f"{sid}: {wid} pressure {st['p']:.4f} < required "
                        f"{scen['required_sink_pressure_mpa']}")
        if wid.startswith("WG"):
            if st["flow"] > C.REQS["well_group_limits"]["maximum_flow_per_interface_kg_s"] + 1e-5:
                errs.append(f"{sid}: {wid} flow {st['flow']:.3f} > well-group limit")
            if st["flow"] < C.REQS["well_group_limits"]["minimum_flow_kg_s"] - 1e-9:
                errs.append(f"{sid}: {wid} flow below well-group minimum")
    # grid-tie metering
    active_cap = 0.0
    for r in res["rep"]["equipment"]:
        if r["category"] == "meter" and r["flow_kg_s"] > 1e-12:
            active_cap += C.MODELS[r["model"]]["capacity_kg_s"]
    frac = C.REQS["grid_tie_metering_requirement"]["minimum_active_meter_capacity_fraction_of_scenario_flow"]
    if active_cap + 1e-6 < frac * flow:
        errs.append(f"{sid}: active grid-tie meter capacity {active_cap} < {frac} x {flow}")
    return errs
