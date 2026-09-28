"""Quantities and lifecycle cost according to the published LCC basis."""
import math
import catalog as C
import design as D
import geometry as G
import process as PR
import scenarios as S
import checks as CHK
import scenarios as S


def maintenance_areas(eq):
    out = {}
    for e in eq.values():
        polys = CHK.maintenance_envelope(e)
        if not polys:
            out[e["id"]] = 0.0
            continue
        area = CHK.envelope_area(e)
        foot = G.polygon_area(e["poly"])
        out[e["id"]] = max(0.0, area - foot)
    return out


def road_lengths(roads):
    out = {}
    for rid, r in roads.items():
        pts = r["centerline"]
        out[rid] = sum(G.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return out


def pipe_quantities(segs):
    """Returns per-pipe capex and civil cost plus totals by DN/class/level."""
    capex = {}
    civil = {}
    lengths = {}
    for s in segs:
        pid = s["pipe"]
        L = G.dist(s["a"], s["b"])
        cur = S.PIPES[s["pipe"]]
        lvl = s["level"]                      # per-segment level (road crossings differ)
        rate = C.DIAMS[cur["dn"]]["installed_cost_mbcu_per_m"]
        cmul = C.CLASSES[cur["class"]]["installed_cost_multiplier"]
        lmul = C.PIPING["routing_levels"][lvl]["installed_cost_multiplier"]
        ccost = C.PIPING["routing_levels"][lvl]["civil_cost_mbcu_per_m"]
        capex[pid] = capex.get(pid, 0.0) + L * rate * cmul * lmul
        civil[pid] = civil.get(pid, 0.0) + L * ccost
        lengths[pid] = lengths.get(pid, 0.0) + L
    return capex, civil, lengths


def equipment_capex(eq):
    return {e["id"]: C.MODELS[e["model"]]["capex_mbcu"] for e in eq.values()}


def annual_maintenance(eq):
    return {e["id"]: C.MODELS[e["model"]]["annual_maintenance_mbcu"] for e in eq.values()}


def lifecycle_cost(eq, roads, segs, scenario_energy_mwh):
    pvf = PR.pvf(C.ECON["discount_rate"], C.ECON["project_life_years"])
    ceq = equipment_capex(eq)
    pcapex, pcivil, plen = pipe_quantities(segs)
    m_area = maintenance_areas(eq)
    r_len = road_lengths(roads)
    civil = dict(C.ECON["civil"])
    eq_capex = sum(ceq.values())
    pipe_capex = sum(pcapex.values())
    road_civil = sum(r_len.values()) * civil["road_mbcu_per_m"]
    found_civil = sum(G.polygon_area(e["poly"]) for e in eq.values()) * civil["foundation_mbcu_per_m2"]
    maint_civil = sum(m_area.values()) * civil["maintenance_area_mbcu_per_m2"]
    pipe_civil = sum(pcivil.values())
    civil_total = road_civil + found_civil + maint_civil + pipe_civil
    annual_energy = sum(scenario_energy_mwh.values())      # MWh/year
    energy_pv = annual_energy * C.ECON["energy_tariff_mbcu_per_mwh"] * pvf
    annual_maint = sum(annual_maintenance(eq).values())
    maint_pv = annual_maint * pvf
    total = eq_capex + pipe_capex + civil_total + energy_pv + maint_pv
    return {
        "pvf": pvf,
        "equipment_capex_mbcu": eq_capex,
        "piping_capex_mbcu": pipe_capex,
        "civil_capex_mbcu": civil_total,
        "energy_pv_mbcu": energy_pv,
        "maintenance_pv_mbcu": maint_pv,
        "annual_energy_mwh": annual_energy,
        "annual_maintenance_mbcu": annual_maint,
        "lcc_mbcu": total,
        "detail": {
            "equipment": ceq, "piping": pcapex, "pipe_civil": pcivil,
            "pipe_lengths": plen, "road_lengths": r_len,
            "maintenance_area_m2": m_area,
            "road_civil": road_civil, "foundation_civil": found_civil,
            "maintenance_civil": maint_civil, "pipe_civil_total": pipe_civil,
            "scenario_energy_mwh": scenario_energy_mwh,
        },
    }


def scenario_energy(res):
    """Annual energy (MWh) for one scenario result."""
    mw = 0.0
    for r in res["rep"]["equipment"]:
        mw += r.get("power_mw", 0.0)
        mw += r.get("energy_mw", 0.0)
        mw += r.get("electric_mw", 0.0)
    return mw * res["scenario"]["annual_hours"]
