"""
Export the complete design to ../data/design.json (machine readable,
sufficient for independent reconstruction and recalculation).
"""
from __future__ import annotations

import json
import os

import ugslib as U
import design as D
import checks as C
import model as M
import lcc as LC
import validate as V
from ugslib import CATALOG, DIAMETERS, CLASSES, LEVELS

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "design.json")


def equipment_export():
    out = []
    for eid, e in D.EQUIPMENT.items():
        rect = C.equip_rect(eid)
        ports = []
        for p in e["model"]["ports"]:
            xy = D.port_xy(eid, p["id"])
            uses = [pid for pid, pl in D.PIPELINES.items()
                    if (pl["src"][0] == "E" and pl["src"][1] == eid and pl["src"][2] == p["id"])
                    or (pl["dst"][0] == "E" and pl["dst"][1] == eid and pl["dst"][2] == p["id"])]
            ports.append({"id": p["id"], "type": p["type"], "xy_m": list(xy),
                          "connected_by": uses})
        out.append({
            "instance_id": eid, "model_id": e["model_id"], "category": e["category"],
            "safety_category": e["safety_category"], "description": e["description"],
            "centre_m": [e["cx"], e["cy"]], "orientation_deg": e["orientation_deg"],
            "footprint_m": e["model"]["footprint_m"],
            "footprint_bbox_m": list(rect),
            "capex_mbcu": e["model"]["capex_mbcu"],
            "annual_maintenance_mbcu": e["model"]["annual_maintenance_mbcu"],
            "ports": ports,
            "key_catalog_values": _key_values(e["model"]),
        })
    return out


KEY_KEYS = ["capacity_kg_s", "pressure_drop_mpa", "pressure_drop_at_capacity_mpa",
            "maximum_pressure_mpa", "maximum_branch_connections",
            "minimum_stable_flow_kg_s", "maximum_pressure_ratio", "efficiency_proxy",
            "driver_efficiency", "maximum_suction_pressure_mpa",
            "maximum_discharge_pressure_mpa", "maximum_suction_temperature_c",
            "maximum_discharge_temperature_c", "maximum_power_mw",
            "liquid_removal_efficiency", "maximum_feed_free_liquid_fraction",
            "maximum_liquid_rate_kg_s", "normal_outlet_water_mg_sm3",
            "energy_mw_per_kg_s", "minimum_outlet_temperature_c", "maximum_duty_mw",
            "electric_power_fraction_of_duty", "maximum_outlet_temperature_c",
            "jt_temperature_coefficient_k_per_mpa"]


def _key_values(mod):
    return {k: mod[k] for k in KEY_KEYS if k in mod}


def pipeline_export():
    out = []
    for pid, p in D.PIPELINES.items():
        cls = CLASSES[p["cls"]]
        dn = DIAMETERS[p["dn"]]
        cost = (D.pipe_length(pid) * dn["installed_cost_mbcu_per_m"]
                * cls["installed_cost_multiplier"]
                * LEVELS[p["level"]]["installed_cost_multiplier"])
        out.append({
            "pipeline_id": pid,
            "source": {"kind": p["src"][0], "id": p["src"][1], "port": p["src"][2]},
            "destination": {"kind": p["dst"][0], "id": p["dst"][1], "port": p["dst"][2]},
            "service": p["service"],
            "route_m": [list(pt) for pt in p["route"]],
            "length_m": D.pipe_length(pid),
            "nominal_diameter": p["dn"],
            "internal_diameter_m": dn["internal_diameter_m"],
            "pipe_class": p["cls"],
            "roughness_m": cls["roughness_m"],
            "level": p["level"],
            "corridor": p["corridor"],
            "installed_capex_mbcu": cost,
        })
    return out


def scenario_export(res, n1):
    req = {s["scenario_id"]: s for s in U.SCENARIOS["scenarios"]}
    out = []
    for r in res:
        sc = req[r["scenario"]]
        out.append({
            "scenario_id": r["scenario"],
            "service": r["service"],
            "annual_hours": sc["annual_hours"],
            "required_total_flow_kg_s": sc["required_total_flow_kg_s"],
            "required_sink_pressure_mpa": sc["required_sink_pressure_mpa"],
            "source_interface": sc["source_interface"],
            "sink_interfaces": sc["sink_interfaces"],
            "source_conditions": {
                "P_mpa": sc["source_pressure_mpa"], "T_c": sc["source_temperature_c"],
                "water_mg_sm3": sc["source_water_mg_sm3"],
                "free_liquid_kg_kg": sc["source_free_liquid_mass_fraction"]},
            "operating": {
                "compressor_lineup": r["compressor_split"],
                "compressor_suction_P_mpa": r.get("suction_P"),
                "compressor_suction_T_c": r.get("suction_T"),
                "compressor_total_discharge_P_mpa": r.get("discharge_P"),
                "compressor_discharge_T_c": r.get("discharge_T"),
                "compressor_pressure_ratio": r["ratio"],
                "compressor_power_mw": r["compressor_power_mw"],
                "cooler_outlet_T_c": (58.0 if r["service"] == "injection" else None),
                "cooler_electric_MW": r["aux_power_mw"],
                "regulator_outlet_P_mpa": r.get("regulator_out_P"),
                "dehydration_power_mw": r["dehyd_power_mw"],
                "compressor_station_bypassed": bool(r.get("use_bypass")),
            },
            "flow_allocation_kg_s": r["well_flows"],
            "delivery": r["delivery"],
            "total_equipment_power_mw": (r["compressor_power_mw"] + r["aux_power_mw"]
                                         + r["dehyd_power_mw"]),
            "path": _path_from_trace(r["trace"]),
        })
    return out


def _path_from_trace(trace):
    path = []
    for t in trace:
        if t["kind"] == "pipe":
            path.append({"element": "pipeline", "id": t["id"], "flow_kg_s": t["m"],
                         "P_in_mpa": t["P_in"], "P_out_mpa": t["P_out"],
                         "velocity_m_s": t["v"], "deltaP_mpa": t["dP"]})
        elif t["kind"] == "header":
            path.append({"element": "header", "id": t["id"], "flow_kg_s": t["m"],
                         "P_out_mpa": t["P_out"], "deltaP_mpa": t["dP"]})
        elif t["kind"] in ("compressor", "cooler", "regulator", "meter",
                           "dehydration", "separator"):
            path.append({"element": t["kind"], "id": t["id"], "flow_kg_s": t["m"],
                         "P_in_mpa": t.get("P_in"), "P_out_mpa": t.get("P_out"),
                         "T_in_c": t.get("T_in"), "T_out_c": t.get("T_out"),
                         "power_mw": t.get("power_mw"), "duty_mw": t.get("duty_mw")})
    return path


def main():
    rep, L, Q, res, n1 = V.main()
    design = {
        "case": U.CASE,
        "units": "SI: m, kg/s, MPa, degC, MW, MWh, MBCU",
        "boundaries": [{"interface_id": i["interface_id"], "type": i["interface_type"],
                        "port_type": i["port_type"], "point_m": i["point_m"],
                        "maximum_connections": i.get("maximum_connections"),
                        "maximum_flow_kg_s": i.get("maximum_flow_kg_s")}
                       for i in U.SITE["external_interfaces"]],
        "equipment": equipment_export(),
        "pipelines": pipeline_export(),
        "roads": D.ROADS,
        "scenarios": scenario_export(res, n1),
        "n1_outages": [{"case": lbl, "total_flow_kg_s": r["total_flow"],
                        "delivery": r["delivery"],
                        "compressor_power_mw": r["compressor_power_mw"]}
                       for lbl, r in n1],
        "lifecycle_cost": {k: v for k, v in L.items() if k != "energy_rows"},
        "energy_by_scenario": L["energy_rows"],
        "quantities": Q,
        "validation_issues": {k: v for k, v in rep.items() if not k.startswith("_")},
        "validation_issue_count": rep["_total"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(design, fh, indent=1)
    print("wrote", OUT, os.path.getsize(OUT), "bytes; issues:", rep["_total"])
    return design


if __name__ == "__main__":
    main()
