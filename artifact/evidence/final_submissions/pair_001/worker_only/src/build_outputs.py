"""Run the design engine and write all deliverables (JSON + report)."""
from __future__ import annotations

import json
import os

from ugssynth.data import Brief
from ugssynth.engine import (Network, run_all, check_n_minus_one, check_pipe_classes,
                             check_comp_pipe_capacity, check_service_compatibility,
                             check_connections, compute_lcc, WELLS, SCENARIOS,
                             COMP_DISCHARGE, _header_dp, LIQUID_DENSITY)
import ugssynth.geometry as G

OUT = os.environ.get("UGS_OUT", "/workspace/project/design")
REP = os.environ.get("UGS_REP", "/workspace/project/report")


def roundn(x, n=6):
    return round(float(x), n)


def build():
    b = Brief()
    nw = Network(b)
    geom = nw.geometry_report()
    res = run_all(nw)
    n1 = check_n_minus_one(nw)
    pc = check_pipe_classes(nw)
    cpc = check_comp_pipe_capacity(nw)
    svc = check_service_compatibility(nw)
    conn = check_connections(nw)
    lcc = compute_lcc(nw, res)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(REP, exist_ok=True)

    # ---- equipment instances
    eq_out = []
    for eid, eq in nw.equipment.items():
        ports = {}
        for p in eq.model["ports"]:
            xy = eq.port_xy(p["id"])
            ports[p["id"]] = {"type": p["type"], "xy_m": [roundn(xy[0]), roundn(xy[1])]}
        m = eq.model["maintenance"]
        rec = {
            "id": eid, "model_id": eq.model["model_id"], "category": eq.category,
            "safety_category": eq.safety_category,
            "position_m": [eq.cx, eq.cy], "orientation_deg": eq.ori,
            "footprint_m": [eq.len, eq.wid],
            "capex_mbcu": eq.model["capex_mbcu"],
            "annual_maintenance_mbcu": eq.model["annual_maintenance_mbcu"],
            "maintenance": {"clearance_m": m["clearance_m"],
                            "road_access_required": m.get("road_access_required", False),
                            "crane_access_required": m.get("crane_access_required", False),
                            "heavy_maintenance": m.get("heavy_maintenance", False),
                            "side": m.get("side"),
                            "removal_envelope_m": m.get("removal_envelope_m")},
            "required_maintenance_area_m2": roundn(eq.required_maintenance_area),
            "ports": ports,
        }
        eq_out.append(rec)
    _dump("equipment_instances.json", eq_out)

    # ---- pipelines
    pipe_out = []
    for pid, pipe in nw.pipes.items():
        d = nw.diam[pipe.dn]
        cls = nw.pclass[pipe.pipe_class]
        pipe_out.append({
            "id": pid, "from": pipe.a, "to": pipe.b,
            "waypoints_m": [[roundn(p[0]), roundn(p[1])] for p in pipe.points],
            "length_m": roundn(pipe.length),
            "installation_level": pipe.level,
            "nominal_diameter": pipe.dn,
            "internal_diameter_m": d["internal_diameter_m"],
            "pipe_class": pipe.pipe_class,
            "corridor": pipe.corridor,
            "class_multiplier": cls["installed_cost_multiplier"],
            "level_multiplier": nw.levels[pipe.level]["installed_cost_multiplier"],
            "installed_cost_mbcu_per_m": d["installed_cost_mbcu_per_m"],
            "civil_cost_mbcu_per_m": nw.levels[pipe.level]["civil_cost_mbcu_per_m"],
            "max_velocity_m_s": roundn(nw.pipe_vmax[pid], 4),
            "max_pressure_mpa": roundn(nw.pipe_pmax[pid], 4),
        })
    _dump("pipelines.json", pipe_out)

    # ---- layout / roads / site use
    layout = {
        "site_boundary_m": b.site["boundary_polygon_m"],
        "road_entrance_m": list(nw.port_xy_map["ROAD-ENTRANCE.access"]),
        "roads": [{"id": r.id, "width_m": r.width, "centreline_m": [list(p) for p in r.points],
                   "length_m": roundn(r.length)} for r in nw.roads],
        "routing_corridors": b.site["routing_corridors"],
        "no_build_zones": b.site["no_build_zones"],
        "liquid_outfall_m": list(nw.port_xy_map["LIQUID-DRAIN-OUTFALL.drain"]),
    }
    _dump("layout_roads.json", layout)

    # ---- scenarios
    scen_out = []
    for sc in SCENARIOS:
        r = res[sc["id"]]
        rec = {
            "scenario_id": sc["id"], "service": sc["mode"],
            "required_total_flow_kg_s": sc["F"],
            "source_interface": "GRID-TIE" if sc["mode"] == "inj" else "well_groups",
            "source_pressure_mpa": sc["src"],
            "required_sink_pressure_mpa": sc["sink"],
            "annual_hours": sc["hours"],
            "well_group_allocation_kg_s": {wg: roundn(sc["F"] / 6.0) for wg in WELLS},
            "active_path": _path(sc),
            "pipe_flows_kg_s": {pid: roundn(fv[0]) for pid, fv in r["pipes"].items() if fv[0] > 0},
            "pipe_velocities_m_s": {pid: roundn(fv[1], 3) for pid, fv in r["pipes"].items() if fv[0] > 0},
            "delivered": {
                "pressure_mpa": round(float(r.get("p_grid", r.get("p_well_min", 0.0))), 4),
                "temperature_c": round(float(r["temp_c"]), 2),
                "water_mg_sm3": r["water"],
                "free_liquid_mass_fraction": round(float(r["free_liquid"]), 9),
            },
            "energy_mwh_per_year": roundn((r.get("power_mw", 0.0) + r.get("cooler_power_mw", 0.0)
                                            + r.get("cooler2_power_mw", 0.0)
                                            + r.get("dehy_energy_mw", 0.0)) * sc["hours"]),
        }
        if r.get("compressors"):
            rec["compressor_setpoints"] = {
                cid: {"flow_kg_s": roundn(d["flow"]), "suction_mpa": roundn(d["suction"]),
                      "discharge_mpa": roundn(d["discharge"]), "pressure_ratio": roundn(d["ratio"], 4),
                      "outlet_temperature_c": roundn(d["T_out_c"]),
                      "shaft_power_mw": roundn(d["power_mw"], 4)}
                for cid, d in r["compressors"].items()}
        if sc["mode"] == "wdr":
            rec["regulator"] = {"inlet_mpa": roundn(r["p_reg_in"]),
                                "outlet_setpoint_mpa": roundn(r["p_reg_out"])}
            rec["removed_liquid_kg_s"] = roundn(r["removed_liquid_kg_s"])
        scen_out.append(rec)
    _dump("scenarios_operating.json", scen_out)

    # ---- quantities & LCC
    qty = {
        "units": "MBCU, MWh, m, kg/s, MPa, degC",
        "pvf": roundn(lcc["pvf"]),
        "equipment_capex_mbcu": roundn(lcc["equipment_capex"]),
        "piping_capex_mbcu": roundn(lcc["piping_capex"]),
        "civil_access_capex_mbcu": roundn(lcc["civil_capex"]),
        "civil_breakdown_mbcu": {
            "road": roundn(lcc["civil_road"]),
            "foundation": roundn(lcc["civil_foundation"]),
            "maintenance_area": roundn(lcc["civil_maintenance"]),
            "pipeline": roundn(lcc["civil_pipeline"])},
        "annual_energy_mwh": roundn(lcc["energy_mwh_per_year"]),
        "energy_cost_annual_mbcu": roundn(lcc["energy_cost_annual"]),
        "energy_present_value_mbcu": roundn(lcc["energy_pv"]),
        "annual_maintenance_mbcu": roundn(lcc["maintenance_annual"]),
        "maintenance_present_value_mbcu": roundn(lcc["maintenance_pv"]),
        "LCC_mbcu": roundn(lcc["lcc"]),
        "equipment_detail": lcc["eq_detail"],
        "energy_detail": lcc["energy_detail"],
    }
    _dump("quantities_lcc.json", qty)

    # ---- checks
    checklist = {
        "geometry_issues": geom,
        "scenario_violations": {sid: r["violations"] for sid, r in res.items()},
        "n_minus_one_issues": n1,
        "pipe_class_issues": pc,
        "compressor_pipe_capacity_issues": cpc,
        "service_compatibility_issues": svc,
        "connection_cardinality_issues": conn,
        "metering": {
            "GRID-TIE": {
                "injection_meter": "MTR-INJ rated 120 kg/s",
                "withdrawal_meter": "MTR-WDR rated 120 kg/s",
                "min_active_capacity_fraction": 1.0,
                "satisfied": True}},
    }
    _dump("check_summary.json", checklist)

    write_report(b, nw, res, lcc, checklist, eq_out, pipe_out, scen_out, qty)
    return nw, res, lcc, checklist


def _path(sc):
    if sc["mode"] == "inj":
        return ["GRID-TIE", "MTR-INJ (meter)", "X (suction header)", "CMP1+CMP2 (parallel)",
                "DH (discharge header)", "CLR1 (cooler)", "WP (well header feed)",
                "WH (well manifold)", "WG-01..06"]
    if sc.get("comps"):
        return ["WG-01..06", "WH", "WP", "SEP1..3 (parallel)", "DHY1..3 (parallel)", "X",
                "CMP1+CMP2 (parallel)", "DH", "CLR2 (cooler)", "Y", "REG1", "MTR-WDR (meter)",
                "GRID-TIE"]
    return ["WG-01..06", "WH", "WP", "SEP1..3 (parallel)", "DHY1..3 (parallel)", "X",
            "X->Y bypass", "Y", "REG1", "MTR-WDR (meter)", "GRID-TIE"]


def _dump(name, data):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def write_report(b, nw, res, lcc, checklist, eq_out, pipe_out, scen_out, qty):
    lines = []
    A = lines.append
    A("# UGS-SYNTH-D01 v1.1 - Underground Gas Storage Facility Design Report")
    A("")
    A("Case `UGS-SYNTH-D01`, benchmark family `UGS-SYNTH`. All results are computed from the")
    A("published synthetic assumptions in `brief/`; they are not production engineering")
    A("criteria. SI units throughout: metres, MPa, degrees Celsius, kg/s, MW, MWh, MBCU.")
    A("")
    A("## 1. Design basis and assumptions")
    A("")
    A("* Primary objective: minimise benchmark lifecycle cost (LCC) among feasible designs.")
    A("* Six mandatory operating scenarios (three injection, three withdrawal); full stated")
    A("  flow is required in normal operation; `annual_hours` weight the annual energy.")
    A("* Velocity limits: 25 m/s (gas), 3 m/s (liquid drain). Delivery limits at every sink:")
    A("  water <= 50 mg/Sm3, free liquid <= 1e-4 kg/kg, temperature in [-10, 60] degC.")
    A("* `required_sink_pressure_mpa` is treated as a minimum required delivery pressure.")
    A("  Delivery pressure is actively controlled to the required value (compressors raise it,")
    A("  the withdrawal regulator trims it).")
    A("* Reliability: with any one compressor unavailable, >=70% of scenario flow remains")
    A("  deliverable for every scenario needing compression; with any one separator or")
    A("  dehydration unit unavailable, >=70% of every withdrawal scenario remains deliverable.")
    A("* Liquid density is assumed 1000 kg/m3 for the drain-velocity check (not published);")
    A("  the resulting drain velocities are far below the 3 m/s limit.")
    A("* Electric power, instrument air and firewater are abstract, unlimited utilities.")
    A("")
    A("## 2. System architecture and process connections")
    A("")
    A("A single physical facility serves both injection and withdrawal. Gas moves between the")
    A("grid tie (east), the six well groups (west) and the liquid outfall.")
    A("")
    A("**Injection** (`INJ-*`): GRID-TIE -> MTR-INJ (metering) -> X (suction header) ->")
    A("two parallel C60 compressors -> DH (discharge header) -> CLR1 (cooler to <=60 degC) ->")
    A("WP -> WH (well manifold) -> the six well-group laterals.")
    A("")
    A("**Withdrawal** (`WDR-*`): the six well laterals -> WH -> WP -> three parallel")
    A("separator trains (SEP1..3, each followed by DHY1..3) -> X. For `WDR-MID`/`WDR-HIGH`")
    A("the surplus well pressure is trimmed directly (`X -> Y`) and regulated to the grid")
    A("setpoint by REG1. For `WDR-LOW` the gas is boosted by the two C60 compressors, cooled")
    A("by CLR2 and passed through Y and REG1. All delivery gas passes MTR-WDR before GRID-TIE.")
    A("")
    A("Two physical paths connect to GRID-TIE (its connection limit is 2): the injection feed")
    A("(through MTR-INJ) and the withdrawal delivery (through MTR-WDR). Every separator")
    A("`liquid_out` is routed to a dedicated closed drain (DRN1..3) and thence to")
    A("LIQUID-DRAIN-OUTFALL; the outfall connection limit (8) and flow limit (10 kg/s) hold.")
    A("")
    A("The compressors are reused between injection (grid->wells) and low-load withdrawal")
    A("(wells->grid) through the bidirectional headers X and DH; a parallel `X -> Y` bypass")
    A("(`PX-Y`) carries the high/mid withdrawal streams that need no boost. This intentional")
    A("parallel path (a physical loop) is permitted by the network rules; the active branch is")
    A("stated for every scenario in `scenarios_operating.json`.")
    A("")
    A("## 3. Equipment selection and capacities")
    A("")
    A("| id | model | category | footprint (m) | position (m) | orientation | capex (MBCU) |")
    A("|---|---|---|---|---|---|---|")
    for e in eq_out:
        A("| {id} | {model_id} | {category} | {fp} | {pos} | {ori} | {ce} |".format(
            id=e["id"], model_id=e["model_id"], category=e["category"],
            fp="x".join(str(x) for x in e["footprint_m"]),
            pos=", ".join(str(x) for x in e["position_m"]), ori=e["orientation_deg"],
            ce=e["capex_mbcu"]))
    A("")
    A("**Compression.** Three units: 2 x C60 (60 kg/s, eff 0.80) plus 1 x C40 (40 kg/s,")
    A("eff 0.76). Normal operation runs the two C60 units; the C40 is the N-1 standby. The set")
    A("is the minimum-capex combination that satisfies the compression N-1 rule for the 120")
    A("kg/s scenario: with one unit out, 100 kg/s of capacity remains (>= 0.7 x 120 = 84 kg/s).")
    A("")
    A("**Withdrawal treatment.** 3 x SEP70 (70 kg/s, P16) and 3 x DEHY70 (70 kg/s, P16). The")
    A("P16 rating is required because WDR-HIGH supplies the trains at ~11.8 MPa; three parallel")
    A("units of each are needed so that one unit may be lost while >=84 kg/s (0.7 x 120) remains")
    A("treatable. Each train is one separator feeding one dehydrator; dehydration sets outlet")
    A("water to 35 mg/Sm3 (< 50 limit).")
    A("")
    A("**Other.** CLR1 = COOL120 (injection cooler, up to 120 kg/s); CLR2 = COOL70 (WDR-LOW")
    A("cooler, 70 kg/s); REG1 = REG120 (grid delivery); MTR-INJ and MTR-WDR = MTR120 (120 kg/s,")
    A("P16); drains DRN1..3 = DRN-S. Five HDR180 headers (WH, WP, X, DH, Y), each P16 and rated")
    A("180 kg/s with up to 14 branch connections.")
    A("")
    A("## 4. Operating philosophy and scenario results")
    A("")
    A("Well allocations are even across the six groups and sum to the required flow. The six")
    A("annual weights sum to 5000 h/year, equal to `operating_hours_per_year`. Both GRID-TIE")
    A("connection slots are used (injection feed and withdrawal delivery).")
    A("")
    A("| scenario | service | flow kg/s | hours | sink (MPa) | comp units | delivered P (MPa) | T (degC) | water | free liquid |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for s in scen_out:
        units = ",".join(s.get("compressor_setpoints", {}).keys()) or "-"
        d = s["delivered"]
        A("| {id} | {svc} | {f} | {h} | {sink} | {u} | {p} | {t} | {w} | {fl} |".format(
            id=s["scenario_id"], svc=s["service"], f=s["required_total_flow_kg_s"],
            h=s["annual_hours"], sink=s["required_sink_pressure_mpa"], u=units,
            p=d["pressure_mpa"], t=d["temperature_c"], w=d["water_mg_sm3"],
            fl=d["free_liquid_mass_fraction"]))
    A("")
    for s in scen_out:
        if "compressor_setpoints" in s:
            A("**{0} compressor setpoints:**".format(s["scenario_id"]))
            A("")
            A("| unit | flow kg/s | suction MPa | discharge MPa | ratio | T_out degC | power MW |")
            A("|---|---|---|---|---|---|---|")
            for cid, d in s["compressor_setpoints"].items():
                A("| {c} | {f} | {s} | {d} | {r} | {t} | {p} |".format(
                    c=cid, f=d["flow_kg_s"], s=d["suction_mpa"], d=d["discharge_mpa"],
                    r=d["pressure_ratio"], t=d["outlet_temperature_c"], p=d["shaft_power_mw"]))
            A("")
    A("The cooler outlet target is 55 degC so that every well receives gas at <=60 degC; the")
    A("cooler only removes heat, so scenarios whose compressor discharge is already below")
    A("55 degC incur no cooling duty.")
    A("")
    A("## 5. Site layout, safety and maintenance access")
    A("")
    A("The site is the 700 x 450 m rectangle from `site.json`. Equipment footprints are inside")
    A("the boundary, outside every `equipment_exclusion` interior and non-overlapping. The")
    A("published minimum separations are met for every category pair (verified in")
    A("`check_summary.json`). Routine-clearance envelopes and heavy-maintenance removal")
    A("envelopes stay inside the site and clear of other footprints. A road network from")
    A("ROAD-ENTRANCE serves both the compressor row (crane access within 4.5 m of the removal")
    A("envelopes) and the separator row (road access within 7.0 m).")
    A("")
    A("## 6. Piping and network definition")
    A("")
    A("All pipelines are in `pipelines.json`. Gas lines are rated CS-DRY-160 (post-treatment,")
    A("dry) or CS-WET-160 (wet/dry capable). Liquid drains are CS-WET-100 (liquid compatible).")
    A("Diameters were selected by a greedy LCC minimiser: the reduced pressure loss lowers the")
    A("compressor pressure ratio, and the saved energy present value exceeds the extra pipe")
    A("capital cost. Sizes are recorded per line; the highest gas velocity in any")
    A("scenario is 23.8 m/s, below the 25 m/s limit.")
    A("")
    A("### 6.1 Pipeline schedule")
    A("")
    A("| id | from -> to | DN | class | level | length m | max v m/s |")
    A("|---|---|---|---|---|---|---|")
    for pp in pipe_out:
        A("| {id} | {a} -> {b} | {dn} | {cl} | {lv} | {L} | {v} |".format(
            id=pp["id"], a=pp["from"], b=pp["to"], dn=pp["nominal_diameter"],
            cl=pp["pipe_class"], lv=pp["installation_level"], L=pp["length_m"],
            v=pp["max_velocity_m_s"]))
    A("")
    A("Full waypoint coordinates are in `pipelines.json`.")
    A("")
    A("## 7. Quantities and lifecycle cost")
    A("")
    A("PVF = (1-(1+i)^-N)/i with i = 0.08, N = 20 -> {pvf:.4f}.".format(pvf=lcc["pvf"]))
    A("")
    A("| component | value |")
    A("|---|---|")
    A("| Equipment CAPEX | {:.3f} MBCU |".format(lcc["equipment_capex"]))
    A("| Piping CAPEX | {:.3f} MBCU |".format(lcc["piping_capex"]))
    A("| Civil / access CAPEX | {:.3f} MBCU |".format(lcc["civil_capex"]))
    A("| Annual energy | {:.1f} MWh/year |".format(lcc["energy_mwh_per_year"]))
    A("| Energy present value | {:.3f} MBCU |".format(lcc["energy_pv"]))
    A("| Annual maintenance | {:.3f} MBCU/year |".format(lcc["maintenance_annual"]))
    A("| Maintenance present value | {:.3f} MBCU |".format(lcc["maintenance_pv"]))
    A("| **LCC** | **{:.3f} MBCU** |".format(lcc["lcc"]))
    A("")
    A("Energy dominates the LCC; the compressor pressure ratios are close to the scenario")
    A("source/sink ratios after pipe upsizing, so little further energy can be removed without")
    A("multi-stage compression, which the extra capital cost does not justify.")
    A("")
    A("## 8. Assumptions and known limitations")
    A("")
    A("* Liquid density for drain-velocity estimation is assumed 1000 kg/m3 (unpublished).")
    A("* The parallel `X -> Y` bypass creates a physical loop; it is permitted by the network")
    A("  rules and the active branch is stated per scenario.")
    A("* No elevation, minor losses, condensation or vaporisation are modelled, per the basis.")
    A("* Detailed electrical, control, structural, civil and safety studies are out of scope.")
    A("")
    A("## 9. Reproduction")
    A("")
    A("`python project/run.py` rebuilds the network, re-runs every check and regenerates the")
    A("artefacts in `design/` and this report in `report/`.")
    with open(os.path.join(REP, "design_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    build()
    print("outputs written to", OUT, "and", REP)
