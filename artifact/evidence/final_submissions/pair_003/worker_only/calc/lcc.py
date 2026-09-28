"""
Lifecycle-cost model and quantity take-off (brief/engineering_calculation_basis.md).
"""
from __future__ import annotations

import ugslib as U
import design as D
import checks as C
from ugslib import CATALOG, DIAMETERS, CLASSES, LEVELS, PVF, ENERGY_TARIFF, ECON

CF = ECON["civil"]


def equipment_capex():
    detail = {}
    for eid, e in D.EQUIPMENT.items():
        detail[eid] = e["model"]["capex_mbcu"]
    return detail


def piping_capex():
    detail = {}
    for pid, p in D.PIPELINES.items():
        L = D.pipe_length(pid)
        dn = DIAMETERS[p["dn"]]
        cls = CLASSES[p["cls"]]
        lvl = LEVELS[p["level"]]
        cost = L * dn["installed_cost_mbcu_per_m"] * cls["installed_cost_multiplier"] \
            * lvl["installed_cost_multiplier"]
        detail[pid] = cost
    return detail


def civil_capex():
    roads = sum(sum(_len(road["centreline"]) for _ in [0]) for road in [])
    road_len = 0.0
    for road in D.ROADS:
        cl = road["centreline"]
        road_len += sum(_d(cl[i], cl[i + 1]) for i in range(len(cl) - 1))
    footprints = 0.0
    maint_area = 0.0
    for eid in D.EQUIPMENT:
        fp = C.equip_rect(eid)
        a = (fp[2] - fp[0]) * (fp[3] - fp[1])
        footprints += a
        maint_area += max(0.0, C.envelope_area(eid) - a)
    pipe_civil = 0.0
    for pid, p in D.PIPELINES.items():
        pipe_civil += D.pipe_length(pid) * LEVELS[p["level"]]["civil_cost_mbcu_per_m"]
    return {
        "road_m": road_len,
        "road_capex": road_len * CF["road_mbcu_per_m"],
        "foundation_m2": footprints,
        "foundation_capex": footprints * CF["foundation_mbcu_per_m2"],
        "maintenance_area_m2": maint_area,
        "maintenance_capex": maint_area * CF["maintenance_area_mbcu_per_m2"],
        "pipeline_civil": pipe_civil,
    }


def _d(a, b):
    import math
    return math.dist(a, b)


def _len(cl):
    return sum(_d(cl[i], cl[i + 1]) for i in range(len(cl) - 1))


def annual_maintenance():
    return sum(e["model"]["annual_maintenance_mbcu"] for e in D.EQUIPMENT.values())


def scenario_energy(result):
    """Annual-weighted electrical/thermal energy of one scenario, MWh/year."""
    hours = U.SCENARIOS["scenarios"]
    sc = next(s for s in hours if s["scenario_id"] == result["scenario"])
    p = result["compressor_power_mw"] + result["aux_power_mw"] + result.get("dehyd_power_mw", 0.0)
    return p * sc["annual_hours"], sc["annual_hours"], p


def lifecycle_cost(results):
    ecap = equipment_capex()
    pcap = piping_capex()
    civ = civil_capex()
    equip_total = sum(ecap.values())
    pipe_total = sum(pcap.values())
    civil_total = (civ["road_capex"] + civ["foundation_capex"]
                   + civ["maintenance_capex"] + civ["pipeline_civil"])
    energy_rows = []
    annual_energy = 0.0
    for r in results:
        e, h, p = scenario_energy(r)
        annual_energy += e
        energy_rows.append({"scenario": r["scenario"], "hours": h,
                            "power_mw": p, "energy_mwh_per_year": e})
    annual_energy_cost = annual_energy * ENERGY_TARIFF
    energy_pv = annual_energy_cost * PVF
    maint = annual_maintenance()
    maint_pv = maint * PVF
    lcc = equip_total + pipe_total + civil_total + energy_pv + maint_pv
    return {
        "equipment_capex": equip_total,
        "equipment_detail": ecap,
        "piping_capex": pipe_total,
        "piping_detail": pcap,
        "civil": civ,
        "civil_capex_total": civil_total,
        "annual_energy_mwh": annual_energy,
        "annual_energy_cost_mbcu": annual_energy_cost,
        "energy_pv": energy_pv,
        "energy_rows": energy_rows,
        "annual_maintenance_mbcu": maint,
        "maintenance_pv": maint_pv,
        "pvf": PVF,
        "lcc": lcc,
    }


def quantities():
    q = {}
    # piping by diameter / class / level
    rows = {}
    for pid, p in D.PIPELINES.items():
        key = (p["dn"], p["cls"], p["level"], p["service"])
        rows.setdefault(key, {"length_m": 0.0, "count": 0})
        rows[key]["length_m"] += D.pipe_length(pid)
        rows[key]["count"] += 1
    q["piping"] = [{"dn": k[0], "class": k[1], "level": k[2], "service": k[3],
                    "count": v["count"], "length_m": v["length_m"]}
                   for k, v in sorted(rows.items())]
    q["total_pipe_length_m"] = sum(D.pipe_length(pid) for pid in D.PIPELINES)
    q["equipment"] = {}
    for eid, e in D.EQUIPMENT.items():
        q["equipment"][e["model_id"]] = q["equipment"].get(e["model_id"], 0) + 1
    q["road_length_m"] = sum(_len(road["centreline"]) for road in D.ROADS)
    q["site_area_m2"] = 700.0 * 450.0
    q["footprint_area_m2"] = sum(
        (C.equip_rect(eid)[2] - C.equip_rect(eid)[0]) * (C.equip_rect(eid)[3] - C.equip_rect(eid)[1])
        for eid in D.EQUIPMENT)
    q["maintenance_area_m2"] = sum(
        max(0.0, C.envelope_area(eid) -
            (C.equip_rect(eid)[2] - C.equip_rect(eid)[0]) * (C.equip_rect(eid)[3] - C.equip_rect(eid)[1]))
        for eid in D.EQUIPMENT)
    return q
