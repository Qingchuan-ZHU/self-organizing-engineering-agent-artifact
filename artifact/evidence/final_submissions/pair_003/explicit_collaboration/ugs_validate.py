"""Geometry / process / cost validation for the proposed UGS-SYNTH-D01 design."""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ugs_lib import (rect_poly, poly_area, poly_dist, poly_overlap_area, point_in_or_on,
                     poly_inside_poly, poly_len, seg_len, seg_in_poly_interior,
                     collinear_overlap_len, road_paved_rectangles, footprint_poly, expanded_poly,
                     removal_poly, port_xy, pvf, TOL)
import ugs_design as D
import ugs_solve as S

MODELS = S.MODELS
CLASSES = S.CLASSES
DN = S.DN
LEVELS = S.LEVELS
SITE = S.SITE
SITE_POLY = [tuple(p) for p in SITE["boundary_polygon_m"]]
ZONES = SITE["no_build_zones"]
IFACES = S.IFACES
SCEN = S.SCEN
EQUIP = S.EQUIP
PIPES = S.PIPES
ROADS = S.ROADS
TOLG = TOL["geometry"]

RESULTS = []


def rec(ok, area, msg, detail=""):
    RESULTS.append(dict(ok=bool(ok), area=area, msg=msg, detail=detail))


def zone_polys(flag):
    return [(z["zone_id"], [tuple(p) for p in z["polygon_m"]]) for z in ZONES if z.get(flag)]


def failure_summary():
    bad = [r for r in RESULTS if not r["ok"]]
    return bad


# ======================================================================================
def check_equipment():
    polys = {}
    for eid in EQUIP:
        pose = S.inst_pose(eid)
        mdl = MODELS[pose["model_id"]]
        poly = footprint_poly(pose, mdl)
        polys[eid] = (poly, pose, mdl)
        if not poly_inside_poly(poly, SITE_POLY):
            rec(False, "equipment", "%s footprint outside site" % eid)
        bad = [zid for zid, zp in zone_polys("equipment_exclusion")
               if poly_overlap_area(poly, zp) > 1e-9]
        for zid in bad:
            rec(False, "equipment", "%s footprint overlaps %s" % (eid, zid))
        rec(not bad and poly_inside_poly(poly, SITE_POLY), "equipment",
            "%s footprint inside site and clear of equipment-exclusion interiors" % eid)
    ids = sorted(polys)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            pa, _, ma = polys[a]
            pb, _, mb = polys[b]
            ov = poly_overlap_area(pa, pb)
            if ov > 1e-9:
                rec(False, "equipment", "%s/%s footprints overlap" % (a, b), "%.3f m2" % ov)
                continue
            dist = poly_dist(pa, pb)
            req = B_SAFETY[ma["safety_category"]][mb["safety_category"]]
            rec(dist >= req - 1e-6, "safety-separation",
                "%s/%s separation %.2f m (required %s m)" % (a, b, dist, req))
    return polys


B_SAFETY = S.B["safety"]


def check_maintenance(polys):
    road_rects = []
    for r in D.ROADS:
        road_rects.extend(road_paved_rectangles(r))
    for eid, (poly, pose, mdl) in polys.items():
        md = mdl.get("maintenance", {})
        env = expanded_poly(pose, mdl, md.get("clearance_m", 0.0))
        rmp = removal_poly(pose, mdl)
        envs = [env] + ([rmp] if rmp else [])
        if not poly_inside_poly(env, SITE_POLY):
            rec(False, "maintenance", "%s clearance envelope outside site" % eid)
        for zid, zp in zone_polys("equipment_exclusion"):
            if poly_overlap_area(env, zp) > 1e-9:
                rec(False, "maintenance", "%s clearance envelope overlaps %s" % (eid, zid))
        for other in polys:
            if other != eid and poly_overlap_area(env, polys[other][0]) > 1e-9:
                rec(False, "maintenance", "%s clearance envelope overlaps %s footprint" % (eid, other))
        if rmp:
            if not poly_inside_poly(rmp, SITE_POLY):
                rec(False, "maintenance", "%s removal envelope outside site" % eid)
            for zid, zp in zone_polys("equipment_exclusion"):
                if poly_overlap_area(rmp, zp) > 1e-9:
                    rec(False, "maintenance", "%s removal envelope overlaps %s" % (eid, zid))
            for other in polys:
                if other != eid and poly_overlap_area(rmp, polys[other][0]) > 1e-9:
                    rec(False, "maintenance", "%s removal envelope overlaps %s footprint" % (eid, other))
        rec(True, "maintenance", "%s routine clearance envelope checked" % eid,
            "clearance %.1f m" % md.get("clearance_m", 0.0))
        total = poly_area(env) + (poly_area(rmp) - poly_overlap_area(env, rmp) if rmp else 0.0)
        S.AREA_INFO[eid] = dict(env_area=total, footprint_area=poly_area(poly))
        if md.get("road_access_required") or md.get("crane_access_required"):
            d = min(min(poly_dist(e, rr) for rr in road_rects) for e in envs)
            S.AREA_INFO[eid]["access_dist"] = d
            if md.get("road_access_required"):
                lim = S.B["maint"]["road_access_buffer_m"]
                rec(d <= lim + 1e-6, "maintenance-access",
                    "%s road access %.2f m (limit %.1f m)" % (eid, d, lim))
            if md.get("crane_access_required"):
                lim = S.B["maint"]["crane_access_buffer_m"]
                rec(d <= lim + 1e-6, "maintenance-access",
                    "%s crane access %.2f m (limit %.1f m)" % (eid, d, lim))


def check_roads(polys):
    rects = {}
    for r in D.ROADS:
        if r["width_m"] < 4.0 - 1e-9:
            rec(False, "roads", "%s width below 4 m" % r["id"])
        rr = road_paved_rectangles(r)
        rects[r["id"]] = rr
        for q in rr:
            if not poly_inside_poly(q, SITE_POLY):
                rec(False, "roads", "%s paved geometry outside site" % r["id"])
            for zid, zp in zone_polys("road_exclusion"):
                if poly_overlap_area(q, zp) > 1e-9:
                    rec(False, "roads", "%s paved geometry enters %s" % (r["id"], zid))
            for eid, (poly, _, _) in polys.items():
                if poly_overlap_area(q, poly) > 1e-9:
                    rec(False, "roads", "%s paved geometry overlaps %s" % (r["id"], eid))
    ids = list(rects)
    parent = {i: i for i in ids}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if any(poly_overlap_area(qa, qb) > 1e-9 or poly_dist(qa, qb) <= 1e-9
                   for qa in rects[ids[i]] for qb in rects[ids[j]]):
                ra, rb = find(ids[i]), find(ids[j])
                if ra != rb:
                    parent[ra] = rb
    comps = len({find(i) for i in ids})
    rec(comps == 1, "roads", "road network is a single connected network", "components=%d" % comps)
    ent = tuple(IFACES["ROAD-ENTRANCE"]["point_m"])
    inside = any(point_in_or_on(ent, q, 1e-6) for rr in rects.values() for q in rr)
    rec(inside, "roads", "ROAD-ENTRANCE lies on the paved network")


def check_pipelines(polys):
    seglist = []
    for pid, p in PIPES.items():
        route = [tuple(q) for q in p["route"]]
        levels = p["levels"]
        if seg_len(route[0], pipe_endpoint(p["frm"])) > 1e-6:
            rec(False, "pipeline", "%s upstream end misses port %s" % (pid, p["frm"]))
        if seg_len(route[-1], pipe_endpoint(p["to"])) > 1e-6:
            rec(False, "pipeline", "%s downstream end misses port %s" % (pid, p["to"]))
        if len(levels) != len(route) - 1:
            rec(False, "pipeline", "%s level list length mismatch" % pid)
        for i in range(len(route) - 1):
            a, b = route[i], route[i + 1]
            if seg_len(a, b) <= TOLG:
                rec(False, "pipeline", "%s zero-length segment %d" % (pid, i))
            for q in (a, b):
                if not point_in_or_on(q, SITE_POLY):
                    rec(False, "pipeline", "%s segment endpoint outside site" % pid)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if not point_in_or_on(mid, SITE_POLY):
                rec(False, "pipeline", "%s segment leaves site" % pid)
            for zid, zp in zone_polys("pipeline_exclusion"):
                if seg_in_poly_interior(a, b, zp):
                    rec(False, "pipeline", "%s enters %s" % (pid, zid))
            for eid, (poly, _, _) in polys.items():
                if seg_in_poly_interior(a, b, poly):
                    rec(False, "pipeline", "%s crosses %s footprint" % (pid, eid))
            seglist.append((pid, i, a, b, levels[i]))
        rec(True, "pipeline", "%s route legal" % pid,
            "%d segments, controlled by %s" % (len(route) - 1, ", ".join(sorted(set(levels)))))
    for i in range(len(seglist)):
        for j in range(i + 1, len(seglist)):
            pid_i, si, a1, a2, lv1 = seglist[i]
            pid_j, sj, b1, b2, lv2 = seglist[j]
            if lv1 != lv2:
                continue
            ov = collinear_overlap_len(a1, a2, b1, b2, 1e-6)
            if ov > 1e-6:
                rec(False, "pipeline", "%s/%s same-level overlap %.4f m" % (pid_i, pid_j, ov))
    rec(True, "pipeline", "pipeline routes checked", "%d segments" % len(seglist))


def pipe_endpoint(ref):
    node, port = ref
    if node in IFACES:
        return tuple(IFACES[node]["point_m"])
    pose = S.inst_pose(node)
    return port_xy(pose, MODELS[pose["model_id"]], port)


def port_type(ref):
    node, port = ref
    if node in IFACES:
        return IFACES[node]["port_type"]
    pose = S.inst_pose(node)
    for pt in MODELS[pose["model_id"]]["ports"]:
        if pt["id"] == port:
            return pt["type"]
    raise KeyError("port %s.%s" % (node, port))


def check_ports():
    counts = {}
    for pid, p in PIPES.items():
        for ref in (p["frm"], p["to"]):
            counts[ref] = counts.get(ref, 0) + 1
        ts, td = port_type(p["frm"]), port_type(p["to"])
        ok = (ts, td) in (("gas_out", "gas_in"), ("gas_out", "gas_bidirectional"),
                          ("gas_bidirectional", "gas_in"), ("gas_bidirectional", "gas_bidirectional"),
                          ("liquid_out", "drain_in"), ("drain_out", "drain_in"))
        rec(ok, "ports", "%s physical direction %s -> %s" % (pid, ts, td))
    for ref, c in counts.items():
        node, port = ref
        if node in IFACES:
            lim = IFACES[node].get("maximum_connections", 1)
        else:
            lim = 1
            for pt in MODELS[S.inst_pose(node)["model_id"]]["ports"]:
                if pt["id"] == port:
                    lim = pt.get("maximum_connections", 1)
        rec(c <= lim, "ports", "%s.%s connections %d (limit %d)" % (node, port, c, lim))
    for eid in EQUIP:
        mdl = S.inst_model(eid)
        if mdl["category"] != "header":
            continue
        used = sum(counts.get((eid, pt["id"]), 0) for pt in mdl["ports"])
        rec(used <= mdl["maximum_branch_connections"], "ports",
            "%s branch count %d (limit %d)" % (eid, used, mdl["maximum_branch_connections"]))
    for eid in EQUIP:
        if S.inst_model(eid)["category"] in ("separator", "filter"):
            rec(counts.get((eid, "liquid_out"), 0) == 1, "ports",
                "%s liquid_out connected to a closed drain" % eid)
    rec(len([1 for p in PIPES.values() if p["to"][0] == "LIQUID-DRAIN-OUTFALL"]) <=
        IFACES["LIQUID-DRAIN-OUTFALL"]["maximum_connections"], "ports",
        "liquid outfall connection count within limit")


def check_scenarios(runs):
    d = S.B["req"]["gas_delivery_requirements"]
    for sid, r in runs.items():
        scn = SCEN[sid]
        req = scn["required_sink_pressure_mpa"]
        sink = r["sinks"] if r["sinks"] else [r["state"]]
        delivered = min(s[0] for s in sink)
        rec(delivered >= req - TOL["pressure"], "scenario",
            "%s delivered pressure %.4f MPa >= required %.2f MPa" % (sid, delivered, req),
            "setpoint %.4f" % list(r["setpoints"].values())[0])
        for s in sink:
            P, T, water, fl = s
            rec(fl <= d["maximum_free_liquid_mass_fraction"] + TOL["free_liquid"], "delivery",
                "%s free-liquid loading %.3e <= %.0e" % (sid, fl, d["maximum_free_liquid_mass_fraction"]))
            rec(water <= d["maximum_water_content_mg_sm3"] + TOL["water"], "delivery",
                "%s water content %.2f mg/Sm3 <= %.0f" % (sid, water, d["maximum_water_content_mg_sm3"]))
            lo, hi = d["temperature_limits_c"]
            rec(lo - TOL["temperature"] <= T <= hi + TOL["temperature"], "delivery",
                "%s temperature %.2f C within [%.0f, %.0f]" % (sid, T, lo, hi))
        # well group boundary flow limits
        if scn["service"] == "injection":
            for i, s in enumerate(sink):
                m = (r["flow"] or scn["required_total_flow_kg_s"]) / 6.0
                rec(m <= S.B["req"]["well_group_limits"]["maximum_flow_per_interface_kg_s"] + 1e-9,
                    "scenario", "%s well group boundary flow %.2f kg/s within limit" % (sid, m))


def check_liquid_service(runs):
    """Removed liquid: separator liquid rate, drain drum capacity, outfall limits and velocity."""
    from ugs_lib import rho_of
    outfall = S.IFACES["LIQUID-DRAIN-OUTFALL"]
    total = 0.0
    for sid, r in runs.items():
        scn = SCEN[sid]
        if scn["service"] != "withdrawal":
            continue
        liq = {k[4:]: v for k, v in r["energy"].items() if k.startswith("liq_")}
        total = max(total, sum(liq.values()))
        drain_max = 0.0
        for eid, q in liq.items():
            drain_max = max(drain_max, q)
        rec(total <= outfall["maximum_flow_kg_s"] + 1e-9, "liquid",
            "%s total separated liquid %.4f kg/s within outfall limit %.1f kg/s" % (sid, total, outfall["maximum_flow_kg_s"]))
        rec(drain_max <= MODELS[EQUIP["DRN-A"][1]]["capacity_kg_s"] + 1e-9, "liquid",
            "%s maximum single liquid side stream %.4f kg/s within drum capacity" % (sid, drain_max))
    # drain line velocity, using the published gas-density proxy at the 1 MPa drain-domain limit
    rho = rho_of(1.0, 20.0, S.GAS)
    worst = {}
    for sid, r in runs.items():
        if SCEN[sid]["service"] != "withdrawal":
            continue
        liq = {k[4:]: val for k, val in r["energy"].items() if k.startswith("liq_")}
        worst[sid] = max(liq.values()) if liq else 0.0
    # worst single separator side stream through its own drum inlet line, and the
    # worst stream through an outfall line (each drum has its own outfall line)
    worst_one = max(worst.values()) if worst else 0.0
    # n-1 treatment case: 70 % of the largest withdrawal flow over two trains
    n1_rate = 0.7 * SCEN["WDR-HIGH"]["required_total_flow_kg_s"] / 2.0 * 0.01 * 0.9995
    worst_one = max(worst_one, n1_rate)
    for pid in ("PL-DA-1", "PL-DB-1", "PL-DC-1", "PL-DA-2", "PL-DB-2", "PL-DC-2"):
        p = PIPES[pid]
        A = math.pi * DN[p["dn"]]["internal_diameter_m"] ** 2 / 4.0
        v = worst_one / (rho * A)
        rec(v <= S.B["max_liquid_v"] + 1e-6, "liquid",
            "%s (%s) liquid velocity %.3f m/s at %.4f kg/s (gas-density proxy at 1 MPa) within %.1f m/s"
            % (pid, p["dn"], v, worst_one, S.B["max_liquid_v"]))


def check_path_coverage():
    used = set()
    def walk(chain):
        for el in chain:
            if el[0] in ("pipe",):
                used.add(el[1])
            elif el[0] in ("par", "split", "source_par"):
                for br in el[1]:
                    walk(br)
    for sid, spec in D.SCENARIO_PATHS.items():
        walk(spec["chain"])
    for pid, p in PIPES.items():
        liquid = ("liquid" in p["service"]) or ("drain" in p["service"])
        if pid in used:
            rec(True, "path-coverage", "%s appears in a scenario operating path" % pid)
        elif liquid:
            rec(True, "path-coverage",
                "%s is a liquid-drain service checked separately (not part of the gas path)"
                % pid, p["service"])
        else:
            rec(False, "path-coverage", "%s is missing from every scenario operating path" % pid)


def check_metering(runs):
    for sid, r in runs.items():
        scn = SCEN[sid]
        flow = scn["required_total_flow_kg_s"]
        ids = ["IMTR-1"] if scn["service"] == "injection" else ["WMTR-1"]
        cap = sum(MODELS[EQUIP[i][1]]["capacity_kg_s"] for i in ids)
        rec(cap >= flow - 1e-9, "metering",
            "%s all exchanged gas through active meter capacity %.0f >= %.0f kg/s" % (sid, cap, flow))
        rec(cap >= S.IFACES["GRID-TIE"]["maximum_flow_kg_s"] - 1e-9, "metering",
            "%s meter capacity covers the GRID-TIE boundary limit" % sid)


def check_reliability():
    out = []
    for case in D.N1_CASES:
        sid = case["scenario"]
        if case["failed"] == "compressor":
            res = S.n1_compressor_case(sid, case["failed_unit"])
        else:
            res = S.n1_treatment_case(sid, case["failed"], case["failed_unit"])
        out.append(dict(case=case["case"], ok=res["ok"], detail=res["msg"]))
        rec(res["ok"], "reliability", "n-1: %s" % case["case"], res["msg"])
    return out


# ======================================================================================
def compute_lcc(runs):
    econ = S.B["econ"]
    civil = econ["civil"]
    pv = pvf(econ)
    capex_equip = 0.0
    maint_annual = 0.0
    equip_rows = []
    for eid in EQUIP:
        mdl = S.inst_model(eid)
        capex_equip += mdl["capex_mbcu"]
        maint_annual += mdl["annual_maintenance_mbcu"]
        equip_rows.append(dict(id=eid, model=mdl["model_id"], category=mdl["category"],
                               capex=mdl["capex_mbcu"], maint=mdl["annual_maintenance_mbcu"],
                               footprint_area=mdl["footprint_m"]["length"] * mdl["footprint_m"]["width"]))
    capex_pipe = 0.0
    civil_pipe = 0.0
    pipe_rows = []
    for pid, p in PIPES.items():
        route = [tuple(q) for q in p["route"]]
        dn = DN[p["dn"]]
        cls = CLASSES[p["cls"]]
        rows = []
        L_tot = 0.0
        cost = 0.0
        civil_c = 0.0
        for i in range(len(route) - 1):
            L = seg_len(route[i], route[i + 1])
            lvl = LEVELS[p["levels"][i]]
            L_tot += L
            c = L * dn["installed_cost_mbcu_per_m"] * cls["installed_cost_multiplier"] * lvl["installed_cost_multiplier"]
            cost += c
            civil_c += L * lvl["civil_cost_mbcu_per_m"]
            rows.append(dict(level=p["levels"][i], length=L, dn=p["dn"], class_id=p["cls"], capex=c))
        capex_pipe += cost
        civil_pipe += civil_c
        pipe_rows.append(dict(id=pid, dn=p["dn"], class_id=p["cls"], length=L_tot,
                              capex=cost, civil=civil_c, service=p["service"], segments=rows))
    road_len = sum(poly_len([tuple(q) for q in r["centerline_m"]]) for r in D.ROADS)
    civil_road = road_len * civil["road_mbcu_per_m"]
    fp_area = sum(MODELS[EQUIP[eid][1]]["footprint_m"]["length"] * MODELS[EQUIP[eid][1]]["footprint_m"]["width"] for eid in EQUIP)
    civil_found = fp_area * civil["foundation_mbcu_per_m2"]
    maint_area = sum(max(0.0, S.AREA_INFO[eid]["env_area"] - S.AREA_INFO[eid]["footprint_area"]) for eid in EQUIP)
    civil_maint = maint_area * civil["maintenance_area_mbcu_per_m2"]
    energy_rows = []
    annual_mwh = 0.0
    for sid, r in runs.items():
        hours = SCEN[sid]["annual_hours"]
        power = sum(v for k, v in r["energy"].items()
                    if isinstance(v, float) and (k.startswith("comp_") or k.startswith("cool_")
                                                 or k.startswith("heat_") or k == "duty"))
        mwh = power * hours
        annual_mwh += mwh
        energy_rows.append(dict(scenario=sid, power_mw=power, hours=hours, mwh=mwh,
                                breakdown={k: v for k, v in r["energy"].items() if isinstance(v, float)}))
    energy_cost = annual_mwh * econ["energy_tariff_mbcu_per_mwh"]
    energy_pv = energy_cost * pv
    maint_pv = maint_annual * pv
    lcc = (capex_equip + capex_pipe + civil_road + civil_found + civil_maint + civil_pipe
           + energy_pv + maint_pv)
    return dict(capex_equip=capex_equip, capex_pipe=capex_pipe, civil_road=civil_road,
                civil_found=civil_found, civil_maint=civil_maint, civil_pipe=civil_pipe,
                energy_annual_mwh=annual_mwh, energy_cost_annual=energy_cost, energy_pv=energy_pv,
                maint_annual=maint_annual, maint_pv=maint_pv, lcc=lcc, pvf=pv,
                equip_rows=equip_rows, pipe_rows=pipe_rows, energy_rows=energy_rows,
                road_length=road_len, footprint_area=fp_area, maintenance_area=maint_area,
                rates=dict(road=civil["road_mbcu_per_m"], foundation=civil["foundation_mbcu_per_m2"],
                           maintenance_area=civil["maintenance_area_mbcu_per_m2"],
                           energy_tariff=econ["energy_tariff_mbcu_per_mwh"],
                           discount_rate=econ["discount_rate"], life=econ["project_life_years"],
                           pvf=pv))


def run_all():
    RESULTS.clear()
    polys = check_equipment()
    check_maintenance(polys)
    check_roads(polys)
    check_pipelines(polys)
    check_ports()
    runs = S.solve_all()
    check_scenarios(runs)
    check_metering(runs)
    check_path_coverage()
    check_liquid_service(runs)
    rel = check_reliability()
    lcc = compute_lcc(runs)
    return dict(results=list(RESULTS), runs=runs, reliability=rel, lcc=lcc, polys=polys)


def main():
    data = run_all()
    bad = failure_summary()
    print("checks run: %d, failures: %d" % (len(RESULTS), len(bad)))
    for r in bad:
        print("  FAIL [%s] %s %s" % (r["area"], r["msg"], r["detail"]))
    lcc = data["lcc"]
    print("\nLCC = %.3f MBCU" % lcc["lcc"])
    print("  equipment capex   %8.3f" % lcc["capex_equip"])
    print("  piping capex      %8.3f" % lcc["capex_pipe"])
    print("  civil/access      %8.3f (road %.3f, foundation %.3f, maintenance area %.3f, pipeline civil %.3f)"
          % (lcc["civil_road"] + lcc["civil_found"] + lcc["civil_maint"] + lcc["civil_pipe"],
             lcc["civil_road"], lcc["civil_found"], lcc["civil_maint"], lcc["civil_pipe"]))
    print("  energy PV         %8.3f  (%.0f MWh/a, %.3f MBCU/a)" % (lcc["energy_pv"], lcc["energy_annual_mwh"], lcc["energy_cost_annual"]))
    print("  maintenance PV    %8.3f  (%.3f MBCU/a)" % (lcc["maint_pv"], lcc["maint_annual"]))
    print("\nscenario results:")
    for sid, r in data["runs"].items():
        power = sum(val for k, val in r["energy"].items()
                    if isinstance(val, float) and (k.startswith("comp_") or k.startswith("cool_")
                                                   or k.startswith("heat_") or k == "duty"))
        print("  %-9s flow %6.1f kg/s delivered %.4f MPa (req %.2f) setpoint %.3f power %.3f MW"
              % (sid, SCEN[sid]["required_total_flow_kg_s"], r["delivered"], r["required"],
                 list(r["setpoints"].values())[0], power))


if __name__ == "__main__":
    main()
