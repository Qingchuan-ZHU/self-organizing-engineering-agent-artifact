"""Writes all deliverable data files (JSON) and the design report (Markdown)."""
import json
import os
import catalog as C
import design as D
import geometry as G
import process as PR
import scenarios as S
import checks as CHK
import quantities as Q
import analysis as A
import run_case as RC

OUT = RC.OUT
SCEN_IDS = RC.SCEN_IDS


def rnd(x, n=6):
    return round(x, n) if isinstance(x, float) else x


def jdump(name, obj):
    with open(os.path.join(OUT, name), "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


# ------------------------------------------------------------------ writers
def equipment_json(eq):
    out = []
    for e in sorted(eq.values(), key=lambda x: x["id"]):
        m = e["model_data"]
        ports = []
        for pid, p in sorted(e["ports"].items()):
            ports.append({"port_id": pid, "port_type": p["type"],
                          "position_m": [rnd(p["pt"][0], 4), rnd(p["pt"][1], 4)],
                          "outward_normal": [rnd(p["normal"][0], 4), rnd(p["normal"][1], 4)],
                          "maximum_connections": p["max_connections"],
                          "connected": sorted(_connected(eq, e["id"], pid))})
        maint = m.get("maintenance", {})
        envs = CHK.maintenance_envelope(e)
        out.append({
            "instance_id": e["id"], "model_id": m["model_id"],
            "category": m["category"], "safety_category": m["safety_category"],
            "centre_m": [e["centre"][0], e["centre"][1]],
            "orientation_deg": e["orientation"],
            "footprint_m": {"length": m["footprint_m"]["length"],
                            "width": m["footprint_m"]["width"],
                            "corners_m": [[rnd(p[0], 4), rnd(p[1], 4)] for p in e["poly"]]},
            "footprint_area_m2": rnd(G.polygon_area(e["poly"]), 3),
            "maintenance": {
                "clearance_m": maint.get("clearance_m"),
                "heavy_maintenance": bool(maint.get("heavy_maintenance")),
                "side": maint.get("side"),
                "removal_envelope_m": maint.get("removal_envelope_m"),
                "road_access_required": bool(maint.get("road_access_required")),
                "crane_access_required": bool(maint.get("crane_access_required")),
                "envelope_polygons_m": [[[rnd(p[0], 4), rnd(p[1], 4)] for p in poly]
                                        for poly in envs],
                "required_maintenance_area_m2": rnd(
                    max(0.0, CHK.envelope_area(e) - G.polygon_area(e["poly"])), 3),
            },
            "catalogue": {
                "capacity_kg_s": m.get("capacity_kg_s"),
                "capex_mbcu": m["capex_mbcu"],
                "annual_maintenance_mbcu": m["annual_maintenance_mbcu"],
            },
            "ports": ports})
    return out


def _connected(eq, eid, port):
    conns = []
    for pid, src, dst, *_ in D.PIPELINES:
        if src == (eid, port):
            conns.append(f"{pid}->{dst[0]}.{dst[1]}")
        if dst == (eid, port):
            conns.append(f"{pid}<-{src[0]}.{src[1]}")
    return conns


def _segments(pid, p, segs):
    out = []
    for s in segs:
        if s["pipe"] != pid:
            continue
        out.append({"from_m": [rnd(s["a"][0], 6), rnd(s["a"][1], 6)],
                    "to_m": [rnd(s["b"][0], 6), rnd(s["b"][1], 6)],
                    "length_m": rnd(G.dist(s["a"], s["b"]), 6),
                    "installation_level": s["level"]})
    return out


def pipelines_json(eq, segs):
    lengths = {pid: 0.0 for pid in S.PIPES}
    for s in segs:
        lengths[s["pipe"]] += G.dist(s["a"], s["b"])
    out = []
    for pid, p in sorted(S.PIPES.items()):
        out.append({
            "pipeline_id": pid,
            "service": p["service"],
            "from": {"node": p["src"][0], "port": p["src"][1],
                     "point_m": [rnd(S.PIPES[pid]["pts"][0][0], 4),
                                 rnd(S.PIPES[pid]["pts"][0][1], 4)]},
            "to": {"node": p["dst"][0], "port": p["dst"][1],
                   "point_m": [rnd(p["pts"][-1][0], 4), rnd(p["pts"][-1][1], 4)]},
            "route_m": [[rnd(x, 6), rnd(y, 6)] for x, y in p["pts"]],
            "route_length_m": rnd(lengths[pid], 6),
            "segments": _segments(pid, p, segs),
            "nominal_diameter": p["dn"],
            "internal_diameter_m": C.DIAMS[p["dn"]]["internal_diameter_m"],
            "pipe_class": p["class"],
            "roughness_m": C.CLASSES[p["class"]]["roughness_m"],
            "class_rating_mpa": C.CLASSES[p["class"]]["maximum_allowable_pressure_mpa"],
            "class_temperature_limits_c": C.CLASSES[p["class"]]["temperature_limits_c"],
            "wet_gas_compatible": C.CLASSES[p["class"]]["wet_gas_compatible"],
            "dry_gas_compatible": C.CLASSES[p["class"]]["dry_gas_compatible"],
            "liquid_drain_compatible": C.CLASSES[p["class"]]["liquid_drain_compatible"],
            "description": p["note"],
        })
    return out


def topology_json(eq):
    conns = []
    for pid, src, dst, wp, dn, cls, level, service, note in D.PIPELINES:
        conns.append({"pipeline_id": pid, "source": {"node": src[0], "port": src[1]},
                      "destination": {"node": dst[0], "port": dst[1]},
                      "service": service, "description": note})
    ifaces = []
    for iid, iface in sorted(C.INTERFACES.items()):
        used = [c["pipeline_id"] for c in conns
                if c["source"]["node"] == iid or c["destination"]["node"] == iid]
        ifaces.append({"interface_id": iid, "interface_type": iface["interface_type"],
                       "point_m": iface["point_m"], "port_id": iface["port_id"],
                       "port_type": iface["port_type"],
                       "maximum_connections": iface.get("maximum_connections"),
                       "maximum_flow_kg_s": iface.get("maximum_flow_kg_s"),
                       "connected_pipelines": used})
    return {"connections": conns, "interfaces": ifaces}


def site_json(eq, roads):
    out = {"site_boundary_polygon_m": C.SITE["boundary_polygon_m"],
           "no_build_zones": C.SITE["no_build_zones"],
           "routing_corridors": C.SITE["routing_corridors"],
           "terrain": C.SITE["terrain"],
           "roads": []}
    for rid, r in sorted(roads.items()):
        pts = r["centerline"]
        out["roads"].append({
            "road_id": rid, "width_m": r["width"],
            "centreline_m": [[p[0], p[1]] for p in pts],
            "centreline_length_m": rnd(sum(G.dist(pts[i], pts[i + 1])
                                           for i in range(len(pts) - 1)), 6),
            "paved_polygons_m": [[[rnd(p[0], 4), rnd(p[1], 4)] for p in poly]
                                 for poly in r["pieces"]]})
    return out


def _serialise_plan(plan):
    out = []
    for step in plan:
        if step[0] == "parallel":
            out.append(["parallel", [_serialise_plan(sub) for sub in step[1]]])
        elif step[0] == "pipe":
            out.append(["pipe", step[1], step[2]])
        elif step[0] == "equip":
            out.append(["equipment", step[1], step[2]])
    return out


DRAIN_OF_SEP = {"SEP-A": "DRN-A", "SEP-B": "DRN-B", "SEP-C": "DRN-C"}
OUTFALL_LINE = {"DRN-A": "P37", "DRN-B": "P38", "DRN-C": "P39"}


def _liquid_streams(res):
    rows = []
    total = 0.0
    for r in res["rep"]["equipment"]:
        if r["category"] in ("separator", "filter"):
            rem = r.get("liquid_removed_kg_s", 0.0)
            total += rem
            drain = DRAIN_OF_SEP.get(r["equipment"])
            rows.append({"separator": r["equipment"],
                         "gas_flow_kg_s": r["flow_kg_s"],
                         "liquid_removed_kg_s": rnd(rem, 6),
                         "outlet_free_liquid_loading": r.get("liquid_out_loading"),
                         "connected_drain": drain,
                         "drain_pipe": "P34" if drain == "DRN-A" else ("P35" if drain == "DRN-B" else "P36"),
                         "outfall_pipeline": OUTFALL_LINE.get(drain),
                         "drain_capacity_kg_s": 0.8,
                         "drain_utilisation": rnd(rem / 0.8, 4) if drain else None})
    return {"streams": rows, "total_liquid_to_outfall_kg_s": rnd(total, 6),
            "outfall_flow_limit_kg_s": 10.0,
            "outfall_connections_used": 3, "outfall_connection_limit": 8}


LIQUID_DENSITIES = [1000.0, 800.0, 500.0, 100.0, 8.2]


def liquid_velocity_table(max_flow_kg_s):
    """Liquid-drain velocities for the drain pipelines at assumed densities.

    The benchmark publishes no liquid density, so the band below spans water
    (1000 kg/m3) to the pessimistic case of a gas-density-like fluid at the
    closed-drain pressure (8.2 kg/m3), which bounds the velocity from above.
    """
    rows = []
    for pid in ("P34", "P35", "P36", "P37", "P38", "P39"):
        d = C.DIAMS[S.PIPES[pid]["dn"]]["internal_diameter_m"]
        area = 3.141592653589793 * d * d / 4.0
        v = {str(int(rho)) if rho >= 10 else "8.2": rnd(max_flow_kg_s / (rho * area), 4)
             for rho in LIQUID_DENSITIES}
        rows.append({"pipeline_id": pid, "dn": S.PIPES[pid]["dn"],
                     "internal_diameter_m": d, "design_liquid_flow_kg_s": rnd(max_flow_kg_s, 4),
                     "velocity_m_s_vs_assumed_density": v,
                     "limit_m_s": C.PIPING["maximum_liquid_drain_velocity_m_s"],
                     "class": S.PIPES[pid]["class"],
                     "liquid_drain_compatible": C.CLASSES[S.PIPES[pid]["class"]]["liquid_drain_compatible"]})
    return rows


def operating_json(normal, n1):
    out = {"scenarios": [], "contingency_cases": []}
    for sid in SCEN_IDS:
        res = normal[sid]
        scen = res["scenario"]
        sinks = [{"interface_id": wid,
                  "flow_kg_s": rnd(st["flow"], 4),
                  "pressure_mpa": rnd(st["p"], 4),
                  "temperature_c": rnd(st["t"], 3),
                  "water_content_mg_sm3": rnd(st["water"], 3),
                  "free_liquid_mass_fraction": st["liquid"]}
                 for wid, st in res["sinks"]]
        out["scenarios"].append({
            "scenario_id": sid, "service": scen["service"],
            "annual_hours": scen["annual_hours"],
            "required_total_flow_kg_s": scen["required_total_flow_kg_s"],
            "required_sink_pressure_mpa": scen["required_sink_pressure_mpa"],
            "source": {"interface": scen["source_interface"],
                       "pressure_mpa": scen["source_pressure_mpa"],
                       "temperature_c": scen["source_temperature_c"],
                       "water_content_mg_sm3": scen["source_water_mg_sm3"],
                       "free_liquid_mass_fraction": scen["source_free_liquid_mass_fraction"]},
            "sinks": sinks,
            "setpoints": {
                "compressor_discharge_pressure_mpa": rnd(res["ctx"].get("comp_discharge_mpa", 0), 4)
                if res["ctx"].get("comp_discharge_mpa") else None,
                "aftercooler_outlet_temperature_c": S.COOLER_SETPOINT_C if scen["service"] == "injection" else None,
                "grid_pressure_control_setpoint_mpa": S.REG_SETPOINT_MPA if scen["service"] == "withdrawal" else None,
            },
            "operating_path": _serialise_plan(res["plan"]),
            "element_states": {"pipes": res["rep"]["pipes"],
                               "equipment": res["rep"]["equipment"]},
            "energy_mwh": rnd(Q.scenario_energy(res), 3),
            "liquid_side_streams": _liquid_streams(res),
        })
    all_liq = []
    for sid in SCEN_IDS:
        for st in normal[sid]["rep"]["equipment"]:
            if st["category"] in ("separator", "filter"):
                all_liq.append(st.get("liquid_removed_kg_s", 0.0))
    for c in n1:
        for st in c["result"]["rep"]["equipment"]:
            if st["category"] in ("separator", "filter"):
                all_liq.append(st.get("liquid_removed_kg_s", 0.0))
    out["liquid_drain_velocity_check"] = {
        "note": "drain velocity = liquid mass flow / (assumed liquid density x pipe area); "
                "the benchmark publishes no liquid density, so a density band from water "
                "(1000 kg/m3) to a gas-density-like fluid (8.2 kg/m3) is reported",
        "design_liquid_flow_kg_s": rnd(max(all_liq) if all_liq else 0.0, 4),
        "rows": liquid_velocity_table(max(all_liq) if all_liq else 0.0),
    }
    for c in n1:
        res = c["result"]
        out["contingency_cases"].append({
            "case_id": c["case"], "scenario_id": c["scenario"],
            "outage": {"category": c["outage"][0], "instance_index": c["outage"][1]},
            "delivered_flow_kg_s": c["flow_kg_s"],
            "retained_flow_fraction": c["retained_fraction"],
            "required_retained_flow_fraction": c["required_fraction"],
            "sinks": [{"interface_id": wid, "flow_kg_s": rnd(st["flow"], 4),
                       "pressure_mpa": rnd(st["p"], 4), "temperature_c": rnd(st["t"], 3),
                       "water_content_mg_sm3": rnd(st["water"], 3),
                       "free_liquid_mass_fraction": st["liquid"]}
                      for wid, st in res["sinks"]],
            "violations": c["violations"],
            "operating_path": _serialise_plan(res["plan"]),
            "setpoints": {"compressor_discharge_pressure_mpa":
                          rnd(res["ctx"].get("comp_discharge_mpa", 0), 4)
                          if res["ctx"].get("comp_discharge_mpa") else None},
            "element_states": {"pipes": res["rep"]["pipes"],
                               "equipment": res["rep"]["equipment"]},
            "liquid_side_streams": _liquid_streams(res),
        })
    return out


def quantities_json(eq, roads, segs, energy):
    capex, civil, lengths = Q.pipe_quantities(segs)
    by_dn = {}
    for pid, L in lengths.items():
        by_dn.setdefault(S.PIPES[pid]["dn"], 0.0)
        by_dn[S.PIPES[pid]["dn"]] += L
    by_class = {}
    for pid, L in lengths.items():
        by_class.setdefault(S.PIPES[pid]["class"], 0.0)
        by_class[S.PIPES[pid]["class"]] += L
    by_level = {}
    for s in segs:
        by_level.setdefault(s["level"], 0.0)
        by_level[s["level"]] += G.dist(s["a"], s["b"])
    equip_counts = {}
    for e in eq.values():
        equip_counts.setdefault(e["model"], 0)
        equip_counts[e["model"]] += 1
    return {
        "equipment_counts": equip_counts,
        "equipment_capex_mbcu": Q.equipment_capex(eq),
        "equipment_annual_maintenance_mbcu": Q.annual_maintenance(eq),
        "pipeline_length_m": lengths,
        "pipeline_length_by_dn_m": by_dn,
        "pipeline_length_by_class_m": by_class,
        "pipeline_length_by_level_m": by_level,
        "pipeline_capex_mbcu": capex,
        "pipeline_civil_mbcu": civil,
        "road_length_m": Q.road_lengths(roads),
        "foundation_area_m2": {e["id"]: rnd(G.polygon_area(e["poly"]), 3)
                               for e in sorted(eq.values(), key=lambda x: x["id"])},
        "maintenance_area_m2": Q.maintenance_areas(eq),
        "annual_energy_mwh": energy,
        "total_pipeline_length_m": rnd(sum(lengths.values()), 3),
    }


RULE_MAP = [
    ("Equipment footprints inside the site boundary",
     ["footprint_inside_site"], ["SITE"]),
    ("Equipment footprints clear of equipment-exclusion zones",
     ["footprint_vs_equipment_exclusion_zones"], ["ZONE"]),
    ("No positive-area overlap between equipment footprints",
     ["footprint_pair_overlap_test"], ["OVERLAP"]),
    ("Safety separation matrix for every category pair",
     ["safety_separation_pair_test"], ["SEPARATION"]),
    ("Maintenance envelopes inside site / zones / clear of footprints",
     ["maintenance_envelope_test"], ["MAINT", "SITE", "ZONE"]),
    ("Road definition (width >= 4 m), paved geometry and connectivity",
     ["road_definition_test", "road_paved_geometry_test"], ["ROAD"]),
    ("Road-access and crane-access distances",
     ["road_crane_access_test"], ["ACCESS"]),
    ("Pipeline segments: site, pipeline-exclusion zones, footprint interiors",
     ["pipeline_segment_test"], ["PIPE"]),
    ("No positive-length same-level pipeline overlap",
     ["same_level_overlap_pair_test"], ["OVERLAP", "CORRIDOR"]),
    ("Port cardinality, interface limits and port-type compatibility",
     ["port_connection_test", "port_compatibility_test"], ["CARD", "PORTTYPE"]),
    ("Separator/filter liquid outlets connected to closed drains",
     ["separator_liquid_connection_test"], ["LIQUID"]),
]


def verification(chk, normal, n1, errors):
    """Per-rule verification record with check counts and failure counts."""
    rule_records = []
    total_checks = 0
    for title, counters, codes in RULE_MAP:
        n = sum(chk.counts.get(c, 0) for c in counters)
        total_checks += n
        fails = [e for e in chk.errors if e[0] in codes]
        rule_records.append({"rule": title, "checks_performed": n,
                             "failures": len(fails),
                             "result": "PASS" if not fails else "FAIL",
                             "failure_detail": [f"{c}: {m}" for c, m in fails]})
    # operating rule records
    op_rules = []
    checks = {
        "Equipment capacity limits (flow <= capacity)": 0,
        "Equipment pressure limits": 0,
        "Compressor ratio / discharge pressure / suction limits": 0,
        "Compressor temperature and minimum stable flow": 0,
        "Compressor driver power limits": 0,
        "Cooler duty and outlet temperature limits": 0,
        "Separator/filter liquid rate and feed loading limits": 0,
        "Dehydrator feed loading limits": 0,
        "Pipe class pressure rating in each operating case": 0,
        "Pipe class temperature limits in each operating case": 0,
        "Pipe class wet/dry eligibility in each operating case": 0,
        "Gas velocity limit (25 m/s)": 0,
        "Pressure-loss convergence (8 updates)": 0,
        "Delivery quality limits (water, free liquid) at every sink": 0,
        "Delivery temperature limits at every sink": 0,
        "Required sink pressure at every sink": 0,
        "Well-group boundary flow limits": 0,
        "GRID-TIE metering capacity at full scenario flow": 0,
    }
    all_cases = [(sid, normal[sid]) for sid in SCEN_IDS] + \
                [(c["case"], c["result"]) for c in n1]
    for name, res in all_cases:
        for r in res["rep"]["equipment"]:
            checks["Equipment capacity limits (flow <= capacity)"] += 1
            checks["Equipment pressure limits"] += 1
            if r["category"] == "compressor":
                checks["Compressor ratio / discharge pressure / suction limits"] += 1
                checks["Compressor temperature and minimum stable flow"] += 1
                checks["Compressor driver power limits"] += 1
            if r["category"] == "cooler":
                checks["Cooler duty and outlet temperature limits"] += 1
            if r["category"] in ("separator", "filter"):
                checks["Separator/filter liquid rate and feed loading limits"] += 1
            if r["category"] == "dehydration":
                checks["Dehydrator feed loading limits"] += 1
        for r in res["rep"]["pipes"]:
            checks["Pipe class pressure rating in each operating case"] += 1
            checks["Pipe class temperature limits in each operating case"] += 1
            checks["Pipe class wet/dry eligibility in each operating case"] += 1
            checks["Gas velocity limit (25 m/s)"] += 1
            checks["Pressure-loss convergence (8 updates)"] += 1
        for wid, st in res["sinks"]:
            checks["Delivery quality limits (water, free liquid) at every sink"] += 1
            checks["Delivery temperature limits at every sink"] += 1
            checks["Required sink pressure at every sink"] += 1
            if wid.startswith("WG"):
                checks["Well-group boundary flow limits"] += 1
        checks["GRID-TIE metering capacity at full scenario flow"] += 1
    total_checks += sum(checks.values())
    KEYWORDS = {
        "Equipment capacity limits (flow <= capacity)": ["capacity"],
        "Equipment pressure limits": ["pressure", "> max"],
        "Compressor ratio / discharge pressure / suction limits": ["ratio", "discharge", "suction"],
        "Compressor temperature and minimum stable flow": ["temperature", "minimum stable"],
        "Compressor driver power limits": ["power"],
        "Cooler duty and outlet temperature limits": ["duty"],
        "Separator/filter liquid rate and feed loading limits": ["liquid rate"],
        "Dehydrator feed loading limits": ["feed free liquid"],
        "Pipe class pressure rating in each operating case": ["class rating"],
        "Pipe class temperature limits in each operating case": ["class range"],
        "Pipe class wet/dry eligibility in each operating case": ["compatible"],
        "Gas velocity limit (25 m/s)": ["velocity"],
        "Pressure-loss convergence (8 updates)": ["converge"],
        "Delivery quality limits (water, free liquid) at every sink": ["free-liquid", "water content"],
        "Delivery temperature limits at every sink": ["outside"],
        "Required sink pressure at every sink": ["below required"],
        "Well-group boundary flow limits": ["well-group"],
        "GRID-TIE metering capacity at full scenario flow": ["meter"],
    }
    for name, n in checks.items():
        kws = KEYWORDS[name]
        fails = [e for e in errors if any(k in e for k in kws)]
        op_rules.append({"rule": name, "checks_performed": n, "failures": len(fails),
                         "result": "PASS" if not fails else "FAIL",
                         "failure_detail": fails})
    return {
        "cases_checked": SCEN_IDS + [c["case"] for c in n1],
        "geometry_and_layout_rules": rule_records,
        "operating_rules": op_rules,
        "geometry_errors": chk.errors,
        "operating_case_errors": errors,
        "total_checks_performed": total_checks,
        "total_failures": len(chk.errors) + len(errors),
    }


def main():
    chk, eq, roads, segs, normal, n1, lcc, energy, errors = RC.main()
    jdump("equipment.json", equipment_json(eq))
    jdump("pipelines.json", pipelines_json(eq, segs))
    jdump("topology.json", topology_json(eq))
    jdump("site_and_roads.json", site_json(eq, roads))
    jdump("operating_plan.json", operating_json(normal, n1))
    jdump("quantities.json", quantities_json(eq, roads, segs, energy))
    jdump("lifecycle_cost.json", lcc)
    jdump("verification.json", verification(chk, normal, n1, errors))
    print("deliverables written to", OUT)
    return chk, eq, roads, segs, normal, n1, lcc, energy, errors


if __name__ == "__main__":
    main()
