"""UGS-SYNTH-D01 v1.1 design engine.

Builds the physical model, validates geometry and hydraulics for every
scenario, and computes lifecycle cost (LCC).
"""
from __future__ import annotations

import math

from . import geometry as G
from .data import Brief
from .model import EQUIPMENT, INTERFACES, PIPES, ROADS
from .physics import (GasProperties, compressor_outlet_temperature,
                      compressor_power_mw, pipe_velocity, regulator_outlet_temperature,
                      solve_pipe_exit_pressure)

WELLS = ["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"]
TOL = 1e-6


class Equipment:
    def __init__(self, eq_id, model, x, y, ori):
        self.id = eq_id
        self.model = model
        self.category = model["category"]
        self.safety_category = model["safety_category"]
        self.len = model["footprint_m"]["length"]
        self.wid = model["footprint_m"]["width"]
        self.ori = ori
        self.cx, self.cy = x, y

    @property
    def polygon(self):
        return G.rect_corners(self.cx, self.cy, self.len, self.wid, self.ori)

    @property
    def area(self):
        return self.len * self.wid

    def port_xy(self, port_id):
        for p in self.model["ports"]:
            if p["id"] == port_id:
                ox, oy = p["offset_m"]
                return G.rotate(self.cx + ox, self.cy + oy, self.cx, self.cy, self.ori)
        raise KeyError(f"{self.id}:{port_id}")

    @property
    def clearance_polygon(self):
        c = self.model["maintenance"]["clearance_m"]
        return G.offset_rect_polygon(self.cx, self.cy, self.len, self.wid, self.ori, c)

    @property
    def removal_rect(self):
        m = self.model["maintenance"]
        if not m.get("heavy_maintenance"):
            return None
        ext, tr = m["removal_envelope_m"]
        return G.removal_envelope_rect(self.cx, self.cy, self.len, self.wid,
                                       self.ori, m["side"], ext, tr)

    @property
    def maintenance_pieces(self):
        pieces = [self.clearance_polygon]
        if self.removal_rect is not None:
            pieces.append(self.removal_rect)
        return pieces

    @property
    def maintenance_area(self):
        if self.removal_rect is None:
            return G.polygon_area(self.clearance_polygon)
        return (G.polygon_area(self.clearance_polygon) + G.polygon_area(self.removal_rect)
                - G.intersection_area(self.clearance_polygon, self.removal_rect))

    @property
    def required_maintenance_area(self):
        return max(0.0, self.maintenance_area - self.area)


class Pipe:
    def __init__(self, spec, xy_map):
        self.id = spec["id"]
        self.a = spec["from"]
        self.b = spec["to"]
        self.level = spec["level"]
        self.dn = spec["dn"]
        self.pipe_class = spec["class"]
        self.corridor = spec["corridor"]
        pts = [xy_map[self.a]] + [tuple(w) for w in spec["waypoints"]] + [xy_map[self.b]]
        self.points = pts
        self.length = G.polyline_length(pts)
        self.segments = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


class Road:
    def __init__(self, spec):
        self.id = spec["id"]
        self.width = spec["width"]
        self.points = [tuple(p) for p in spec["points"]]
        self.segments = [(self.points[i], self.points[i + 1])
                         for i in range(len(self.points) - 1)]
        self.length = G.polyline_length(self.points)


class Network:
    def __init__(self, brief: Brief):
        self.b = brief
        self.gas = GasProperties(brief.gas)
        self.equipment = {eid: Equipment(eid, brief.catalog[mdl], x, y, o)
                          for eid, (mdl, x, y, o) in EQUIPMENT.items()}
        self.port_xy_map = {}
        for eid, eq in self.equipment.items():
            for p in eq.model["ports"]:
                self.port_xy_map[f"{eid}.{p['id']}"] = eq.port_xy(p["id"])
        for iface, (port, x, y) in INTERFACES.items():
            self.port_xy_map[f"{iface}.{port}"] = (x, y)
        self.pipes = {pid: Pipe(spec, self.port_xy_map) for pid, spec in PIPES.items()}
        self.roads = [Road(r) for r in ROADS]

        self.diam = {d["nominal_diameter"]: d for d in brief.piping["diameters"]}
        self.pclass = {c["class_id"]: c for c in brief.piping["classes"]}
        self.levels = brief.piping["routing_levels"]
        self.zones = brief.site["no_build_zones"]
        self.corridors = {c["corridor_id"]: c for c in brief.site["routing_corridors"]}
        self.site_poly = [tuple(p) for p in brief.site["boundary_polygon_m"]]
        self.pipe_pmax = {pid: 0.0 for pid in self.pipes}
        self.pipe_vmax = {pid: 0.0 for pid in self.pipes}
        self.pipe_tmax = {pid: -1e9 for pid in self.pipes}
        self.pipe_tmin = {pid: 1e9 for pid in self.pipes}

    # ------------------------------------------------------------------ geo
    def geometry_report(self):
        b = self.b
        issues = []
        site = self.site_poly

        def pt_ok(p):
            return G.point_in_convex(p, site)

        for eid, eq in self.equipment.items():
            poly = eq.polygon
            for p in poly:
                if not pt_ok(p):
                    issues.append(f"[footprint-outside] {eid} corner {p}")
            for z in self.zones:
                if z.get("equipment_exclusion"):
                    zp = [tuple(q) for q in z["polygon_m"]]
                    if self._poly_in_poly(poly, zp):
                        issues.append(f"[footprint-in-zone] {eid} in {z['zone_id']}")
        ids = list(self.equipment)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = self.equipment[ids[i]].polygon
                c = self.equipment[ids[j]].polygon
                if G.polygons_overlap_positive_area(a, c):
                    issues.append(f"[footprint-overlap] {ids[i]} {ids[j]}")

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                e1, e2 = self.equipment[ids[i]], self.equipment[ids[j]]
                req = b.safety["minimum_separation_m"][e1.safety_category][e2.safety_category]
                d = G.polygon_distance(e1.polygon, e2.polygon)
                if d < req - 1e-6:
                    issues.append(f"[separation] {ids[i]}/{ids[j]} d={d:.3f} < {req}")

        for eid, eq in self.equipment.items():
            for piece in eq.maintenance_pieces:
                for p in piece:
                    if not pt_ok(p):
                        issues.append(f"[maint-outside] {eid} corner {p}")
                for z in self.zones:
                    if z.get("equipment_exclusion"):
                        zp = [tuple(q) for q in z["polygon_m"]]
                        if self._poly_in_poly(piece, zp):
                            issues.append(f"[maint-in-zone] {eid} in {z['zone_id']}")
            for other_id, other in self.equipment.items():
                if other_id == eid:
                    continue
                for piece in eq.maintenance_pieces:
                    if G.polygons_overlap_positive_area(piece, other.polygon):
                        issues.append(f"[maint-hits-equipment] {eid} envelope on {other_id}")

        for pid, pipe in self.pipes.items():
            if pipe.length <= TOL:
                issues.append(f"[pipe-zero-length] {pid}")
            endpoint_eqs = set()
            for end in (pipe.a, pipe.b):
                head = end.split(".")[0]
                if head in self.equipment:
                    endpoint_eqs.add(head)
            for seg in pipe.segments:
                p, q = seg
                if not (pt_ok(p) and pt_ok(q)):
                    issues.append(f"[pipe-outside] {pid} {p}->{q}")
                for z in self.zones:
                    if z.get("pipeline_exclusion"):
                        zp = [tuple(t) for t in z["polygon_m"]]
                        if G.segment_enters_convex_interior(p, q, zp):
                            issues.append(f"[pipe-in-zone] {pid} in {z['zone_id']}")
                for eid, eq in self.equipment.items():
                    if eid in endpoint_eqs:
                        continue
                    if G.segment_enters_convex_interior(p, q, eq.polygon):
                        issues.append(f"[pipe-crosses-equipment] {pid} through {eid}")

        plist = list(self.pipes.values())
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                pa, pb = plist[i], plist[j]
                if pa.level != pb.level:
                    continue
                if pa.corridor and pb.corridor and pa.corridor == pb.corridor \
                        and self.corridors[pa.corridor]["allows_co_routing"]:
                    continue
                for s1 in pa.segments:
                    for s2 in pb.segments:
                        ov = G.same_level_overlap_length(s1, s2)
                        if ov > TOL:
                            issues.append(f"[same-level-overlap] {pa.id} {pb.id} len={ov:.3f}")

        # ---- roads
        for r in self.roads:
            if r.width < 4.0 - 1e-9:
                issues.append(f"[road-too-narrow] {r.id}")
            for seg in r.segments:
                a, b2 = seg
                if not (pt_ok(a) and pt_ok(b2)):
                    issues.append(f"[road-outside] {r.id} {a}->{b2}")
                for z in self.zones:
                    if z.get("road_exclusion"):
                        zp = [tuple(t) for t in z["polygon_m"]]
                        if G.min_segment_to_polygon_distance(a, b2, zp) < r.width / 2 - 1e-9:
                            issues.append(f"[road-in-zone] {r.id} {z['zone_id']}")
                for eid, eq in self.equipment.items():
                    if G.min_segment_to_polygon_distance(a, b2, eq.polygon) < r.width / 2 - 1e-9:
                        issues.append(f"[road-hits-equipment] {r.id} {eid}")
        # connectivity to entrance
        connected = self._road_network()
        ent = self.port_xy_map["ROAD-ENTRANCE.access"]
        if not any(G.point_segment_distance(ent, *seg) <= r.width / 2 + 1e-6
                   for r in connected for seg in r.segments):
            issues.append("[road-network] not connected to ROAD-ENTRANCE")

        # access buffers
        mreq = b.maintenance
        for eid, eq in self.equipment.items():
            mnt = eq.model["maintenance"]
            if not mnt.get("road_access_required"):
                continue
            best = float("inf")
            for piece in eq.maintenance_pieces:
                for r in connected:
                    for seg in r.segments:
                        d = G.min_segment_to_polygon_distance(seg[0], seg[1], piece)
                        best = min(best, max(0.0, d - r.width / 2))
            if best > mreq["road_access_buffer_m"] + 1e-9:
                issues.append(f"[road-access] {eid} d={best:.3f} > {mreq['road_access_buffer_m']}")
            if mnt.get("crane_access_required") and best > mreq["crane_access_buffer_m"] + 1e-9:
                issues.append(f"[crane-access] {eid} d={best:.3f} > {mreq['crane_access_buffer_m']}")
        return issues

    @staticmethod
    def _poly_in_poly(inner, outer):
        if any(G.point_in_convex_strict(p, outer) for p in inner):
            return True
        n = len(inner)
        for i in range(n):
            if G.segment_enters_convex_interior(inner[i], inner[(i + 1) % n], outer):
                return True
        return False

    def _road_network(self):
        # union-find on roads by paved-geometry touch/overlap
        parent = list(range(len(self.roads)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            parent[find(x)] = find(y)

        for i in range(len(self.roads)):
            for j in range(i + 1, len(self.roads)):
                ri, rj = self.roads[i], self.roads[j]
                joined = False
                for s1 in ri.segments:
                    for s2 in rj.segments:
                        d = G._seg_seg_distance(s1[0], s1[1], s2[0], s2[1]) \
                            if hasattr(G, "_seg_seg_distance") else None
                        if d is None:
                            from .geometry import point_segment_distance  # noqa
                            d = min(point_segment_distance(s1[0], *s2),
                                    point_segment_distance(s1[1], *s2),
                                    point_segment_distance(s2[0], *s1),
                                    point_segment_distance(s2[1], *s1))
                        if d <= (ri.width + rj.width) / 2 + 1e-6:
                            joined = True
                            break
                    if joined:
                        break
                if joined:
                    union(i, j)
        groups = {}
        for i in range(len(self.roads)):
            groups.setdefault(find(i), []).append(self.roads[i])
        # the component containing the entrance road (first road touching entrance)
        ent = self.port_xy_map["ROAD-ENTRANCE.access"]
        comp = []
        for root, roads in groups.items():
            for r in roads:
                if any(G.point_segment_distance(ent, *seg) <= r.width / 2 + 1e-6
                       for seg in r.segments):
                    comp = roads
                    break
            if comp:
                break
        return comp

# ===========================================================================
# Hydraulic scenario solver
# ===========================================================================
COOLER_TARGET_C = 55.0
LIQUID_DENSITY = 1000.0  # assumed (not published); used only for drain velocity
INJ_COMPS = ["CMP1", "CMP2", "CMP3"]
COMP_DISCHARGE = {"CMP1": "PCMP-DH1", "CMP2": "PCMP-DH2", "CMP3": "PCMP-DH3"}


def _pipe_loss(nw, pid, m_dot, t_c, p_in):
    nw.pipe_pmax[pid] = max(nw.pipe_pmax[pid], p_in)
    nw.pipe_tmax[pid] = max(nw.pipe_tmax[pid], t_c)
    nw.pipe_tmin[pid] = min(nw.pipe_tmin[pid], t_c)
    if m_dot <= 0:
        return p_in, 0.0, 0.0
    pipe = nw.pipes[pid]
    d = nw.diam[pipe.dn]["internal_diameter_m"]
    eps = nw.pclass[pipe.pipe_class]["roughness_m"]
    r = solve_pipe_exit_pressure(p_in, t_c, m_dot, pipe.length, d, eps, nw.gas)
    nw.pipe_vmax[pid] = max(nw.pipe_vmax[pid], r["v"])
    return r["p_out"], r["v"], r["dp"]


def _header_dp(nw, eq_id, m_dot):
    m = nw.equipment[eq_id].model
    return m["pressure_drop_at_capacity_mpa"] * (m_dot / m["capacity_kg_s"]) ** 2


def _required_pDH(nw, F, sink_p):
    tt = COOLER_TARGET_C
    pDH = sink_p + 1.0
    for _ in range(60):
        p = pDH
        p, _, _ = _pipe_loss(nw, "PDH-CLR", F, 100.0, p)
        p -= nw.equipment["CLR1"].model["pressure_drop_mpa"]
        p, _, _ = _pipe_loss(nw, "PWP-CLR", F, tt, p)
        p -= _header_dp(nw, "WP", F)
        p, _, _ = _pipe_loss(nw, "PWH-WP", F, tt, p)
        p -= _header_dp(nw, "WH", F)
        pw = min(_pipe_loss(nw, f"PWG{i}", F / 6.0, tt, p)[0] for i in range(1, 7))
        err = sink_p - pw
        pDH += err
        if abs(err) < 1e-9:
            break
    return pDH


def solve_injection(nw, F, sink_p, hours, active):
    rec = {"mode": "injection", "F": F, "hours": hours, "violations": [],
           "power_mw": 0.0, "cooler_duty_mw": 0.0, "cooler_power_mw": 0.0,
           "pipes": {}, "compressors": {}}
    gas = nw.gas
    t = 25.0
    p = 6.5
    p, v, _ = _pipe_loss(nw, "PGRID-INJ", F, t, p)
    rec["pipes"]["PGRID-INJ"] = (F, v)
    p -= nw.equipment["MTR-INJ"].model["pressure_drop_mpa"]
    p, v, _ = _pipe_loss(nw, "PINJ-X", F, t, p)
    rec["pipes"]["PINJ-X"] = (F, v)
    pX = p - _header_dp(nw, "X", F)
    rec["pMTRINJ_out"] = p + 0.0
    p_s = {}
    for cid, f in active:
        ps, vs, _ = _pipe_loss(nw, f"PX-{cid}", f, t, pX)
        rec["pipes"][f"PX-{cid}"] = (f, vs)
        p_s[cid] = ps
    pDH = _required_pDH(nw, F, sink_p)
    rec["pDH"] = pDH
    # delivery-side velocities at final pDH
    tt = COOLER_TARGET_C
    p = pDH
    p, v, _ = _pipe_loss(nw, "PDH-CLR", F, 100.0, p)
    rec["pipes"]["PDH-CLR"] = (F, v)
    p -= nw.equipment["CLR1"].model["pressure_drop_mpa"]
    p, v, _ = _pipe_loss(nw, "PWP-CLR", F, tt, p)
    rec["pipes"]["PWP-CLR"] = (F, v)
    rec["pWP"] = p - _header_dp(nw, "WP", F)
    p -= _header_dp(nw, "WP", F)
    p, v, _ = _pipe_loss(nw, "PWH-WP", F, tt, p)
    rec["pipes"]["PWH-WP"] = (F, v)
    p -= _header_dp(nw, "WH", F)
    rec["pWH"] = p
    well_ps = {}
    for i, wg in enumerate(WELLS, start=1):
        pw, vw, _ = _pipe_loss(nw, f"PWG{i}", F / 6.0, tt, p)
        rec["pipes"][f"PWG{i}"] = (F / 6.0, vw)
        well_ps[wg] = pw
    rec["well_pressures"] = well_ps
    rec["p_well_min"] = min(well_ps.values())
    # compressors
    total_power = 0.0
    t_disch = []
    dhdp = _header_dp(nw, "DH", F)
    for cid, f in active:
        cm = nw.equipment[cid].model
        pd_i = pDH + dhdp + 0.3
        for _ in range(6):
            pout, _, _ = _pipe_loss(nw, COMP_DISCHARGE[cid], f, 100.0, pd_i)
            pd_i = pDH + dhdp + (pd_i - pout)
        ratio = pd_i / p_s[cid]
        tout = compressor_outlet_temperature(t, ratio, gas.k, cm["efficiency_proxy"])
        pw = compressor_power_mw(f, gas.cp, t, ratio, gas.k, cm["efficiency_proxy"],
                                 cm["driver_efficiency"])
        total_power += pw
        t_disch.append((f, tout))
        rec["compressors"][cid] = {"flow": f, "suction": p_s[cid], "discharge": pd_i,
                                   "ratio": ratio, "T_out_c": tout, "power_mw": pw}
        vpc = _pipe_loss(nw, COMP_DISCHARGE[cid], f, 100.0, pd_i)[1]
        rec["pipes"][COMP_DISCHARGE[cid]] = (f, vpc)
        if f > cm["capacity_kg_s"] + 1e-6:
            rec["violations"].append(f"{cid} flow {f} > cap")
        if f < cm["minimum_stable_flow_kg_s"] - 1e-6:
            rec["violations"].append(f"{cid} flow {f} < min stable")
        if pd_i > cm["maximum_discharge_pressure_mpa"] + 1e-6:
            rec["violations"].append(f"{cid} discharge {pd_i:.3f} > max")
        if p_s[cid] > cm["maximum_suction_pressure_mpa"] + 1e-6:
            rec["violations"].append(f"{cid} suction {p_s[cid]:.3f} > max")
        if ratio > cm["maximum_pressure_ratio"] + 1e-6:
            rec["violations"].append(f"{cid} ratio {ratio:.3f} > max")
        if tout > cm["maximum_discharge_temperature_c"] + 1e-6:
            rec["violations"].append(f"{cid} T {tout:.2f} > max")
        if pw > cm["maximum_power_mw"] + 1e-6:
            rec["violations"].append(f"{cid} power {pw:.3f} > max")
    t_dh = sum(f * tt2 for f, tt2 in t_disch) / sum(f for f, _ in t_disch)
    t_out = min(t_dh, COOLER_TARGET_C)
    duty = max(0.0, F * gas.cp * (t_dh - t_out) / 1e6)
    cl = nw.equipment["CLR1"].model
    if duty > cl["maximum_duty_mw"] + 1e-6:
        rec["violations"].append(f"cooler duty {duty:.3f} > max")
    if t_out < cl["minimum_outlet_temperature_c"] - 1e-6:
        rec["violations"].append("cooler outlet below min")
    if F > cl["capacity_kg_s"] + 1e-6:
        rec["violations"].append("cooler flow > cap")
    rec["power_mw"] = total_power
    rec["cooler_duty_mw"] = duty
    rec["cooler_power_mw"] = duty * cl["electric_power_fraction_of_duty"]
    rec["t_well_c"] = t_out
    # delivery quality
    rec["water"] = 40.0
    rec["free_liquid"] = 0.0
    rec["temp_c"] = t_out
    _check_delivery(nw, rec, t_out, 40.0, 0.0, sink_p, "wells", rec["p_well_min"])
    return rec


def _check_delivery(nw, rec, temp_c, water, fl, sink_req, where, p_delivered, mode="ge"):
    lim = nw.b.requirements["gas_delivery_requirements"]
    if water > lim["maximum_water_content_mg_sm3"] + 1e-6:
        rec["violations"].append(f"water {water} > limit")
    if fl > lim["maximum_free_liquid_mass_fraction"] + 1e-9:
        rec["violations"].append(f"free liquid {fl} > limit")
    lo, hi = lim["temperature_limits_c"]
    if temp_c < lo - 1e-4 or temp_c > hi + 1e-4:
        rec["violations"].append(f"temperature {temp_c:.2f} outside [{lo},{hi}]")
    if mode == "ge" and p_delivered < sink_req - 1e-5:
        rec["violations"].append(f"delivery pressure {p_delivered:.3f} < {sink_req}")


def _required_reg_out(nw, F, grid_p, t_c=20.0):
    p = grid_p + 0.5
    for _ in range(40):
        p2 = p
        p2 -= _pipe_loss(nw, "PREG-MTR", F, t_c, p2)[2]
        p2 -= nw.equipment["MTR-WDR"].model["pressure_drop_mpa"]
        p2 -= _pipe_loss(nw, "PMTR-GRID", F, t_c, p2)[2]
        err = grid_p - p2
        p += err
        if abs(err) < 1e-9:
            break
    return p


def solve_withdrawal(nw, F, sink_p, hours, active, use_comps, source_p, fl_in):
    rec = {"mode": "withdrawal", "F": F, "hours": hours, "violations": [],
           "power_mw": 0.0, "dehy_energy_mw": 0.0, "pipes": {}, "compressors": {}}
    gas = nw.gas
    t = 20.0
    src = source_p
    well_ps = {}
    for i, wg in enumerate(WELLS, start=1):
        pw, vw, _ = _pipe_loss(nw, f"PWG{i}", F / 6.0, t, src)
        rec["pipes"][f"PWG{i}"] = (F / 6.0, vw)
        well_ps[wg] = pw
    rec["well_pressures"] = well_ps
    pWH = min(well_ps.values()) - _header_dp(nw, "WH", F)
    p, v, _ = _pipe_loss(nw, "PWH-WP", F, t, pWH)
    rec["pipes"]["PWH-WP"] = (F, v)
    p -= _header_dp(nw, "WP", F)
    train_ps = []
    for i in range(1, 4):
        f3 = F / 3.0
        p2, v2, _ = _pipe_loss(nw, f"PWP-SEP{i}", f3, t, p)
        rec["pipes"][f"PWP-SEP{i}"] = (f3, v2)
        p2 -= nw.equipment[f"SEP{i}"].model["pressure_drop_mpa"]
        p2, v2, _ = _pipe_loss(nw, f"PSEP-DHY{i}", f3, t, p2)
        rec["pipes"][f"PSEP-DHY{i}"] = (f3, v2)
        p2 -= nw.equipment[f"DHY{i}"].model["pressure_drop_mpa"]
        p2, v2, _ = _pipe_loss(nw, f"PDHY-X{i}", f3, t, p2)
        rec["pipes"][f"PDHY-X{i}"] = (f3, v2)
        train_ps.append(p2)
        if f3 > nw.equipment[f"SEP{i}"].model["capacity_kg_s"] + 1e-6:
            rec["violations"].append(f"SEP{i} flow > cap")
        if f3 > nw.equipment[f"DHY{i}"].model["capacity_kg_s"] + 1e-6:
            rec["violations"].append(f"DHY{i} flow > cap")
    pX = min(train_ps) - _header_dp(nw, "X", F)
    rec["pX"] = pX
    # removed liquid / drains
    removed = F * fl_in * nw.equipment["SEP1"].model["liquid_removal_efficiency"]
    rec["removed_liquid_kg_s"] = removed
    per_sep_liq = removed / 3.0
    for i in range(1, 4):
        if per_sep_liq > nw.equipment[f"SEP{i}"].model["maximum_liquid_rate_kg_s"] + 1e-6:
            rec["violations"].append(f"SEP{i} liquid > max")
        d = nw.diam[nw.pipes[f"PSEP-DRN{i}"].dn]["internal_diameter_m"]
        area = math.pi * d * d / 4.0
        vd = per_sep_liq / (LIQUID_DENSITY * area)
        rec["pipes"][f"PSEP-DRN{i}"] = (per_sep_liq, vd)
        nw.pipe_vmax[f"PSEP-DRN{i}"] = max(nw.pipe_vmax[f"PSEP-DRN{i}"], vd)
        if per_sep_liq > nw.equipment[f"DRN{i}"].model["capacity_kg_s"] + 1e-6:
            rec["violations"].append(f"DRN{i} liquid > capacity")
        if vd > nw.b.piping["maximum_liquid_drain_velocity_m_s"] + 1e-6:
            rec["violations"].append(f"PSEP-DRN{i} velocity {vd:.4f} > max")
        dout = nw.diam[nw.pipes[f"PDRN-OUT{i}"].dn]["internal_diameter_m"]
        vout = per_sep_liq / (LIQUID_DENSITY * math.pi * dout * dout / 4.0)
        rec["pipes"][f"PDRN-OUT{i}"] = (per_sep_liq, vout)
        nw.pipe_vmax[f"PDRN-OUT{i}"] = max(nw.pipe_vmax[f"PDRN-OUT{i}"], vout)
    if removed > nw.b.site["external_interfaces"][-1].get("maximum_flow_kg_s", 1e9):
        rec["violations"].append("outfall flow > limit")
    rec["dehy_energy_mw"] = F * nw.equipment["DHY1"].model["energy_mw_per_kg_s"]
    # pressure control to the grid (DH -> CLR2 -> Y -> REG -> meter -> GRID)
    cl2 = nw.equipment["CLR2"].model
    dhdp = _header_dp(nw, "DH", F)
    ydp = _header_dp(nw, "Y", F)
    reg = nw.equipment["REG1"].model
    jt = reg["jt_temperature_coefficient_k_per_mpa"]
    reg_out = _required_reg_out(nw, F, sink_p, 20.0)
    pDH = reg_out + 1.0
    p_reg_in = reg_out + 1.0
    t_reg_in = 20.0
    t_pre_cool = 20.0
    total_power = 0.0
    for _outer in range(8):
        if use_comps:
            ph = reg_out + 0.6
            for _ in range(12):
                q = ph
                q -= _pipe_loss(nw, "PDH-CLR2", F, 60.0, q)[2]
                q -= cl2["pressure_drop_mpa"]
                q -= _pipe_loss(nw, "PCLR2-Y", F, t_pre_cool, q)[2]
                q -= ydp
                q -= _pipe_loss(nw, "PY-REG", F, t_reg_in, q)[2]
                ph += reg_out - q
            pDH = ph
            p_s = {}
            total_power = 0.0
            t_disch = []
            comp_rec = {}
            for cid, f in active:
                ps, vs, _ = _pipe_loss(nw, f"PX-{cid}", f, t, pX)
                p_s[cid] = ps
                cm = nw.equipment[cid].model
                pd_i = pDH + dhdp + 0.2
                for _ in range(6):
                    pout, _, _ = _pipe_loss(nw, COMP_DISCHARGE[cid], f, t, pd_i)
                    pd_i = pDH + dhdp + (pd_i - pout)
                ratio = pd_i / ps
                tout = compressor_outlet_temperature(t, ratio, gas.k, cm["efficiency_proxy"])
                pw = compressor_power_mw(f, gas.cp, t, ratio, gas.k, cm["efficiency_proxy"],
                                         cm["driver_efficiency"])
                total_power += pw
                t_disch.append((f, tout))
                comp_rec[cid] = {"flow": f, "suction": ps, "discharge": pd_i,
                                 "ratio": ratio, "T_out_c": tout, "power_mw": pw}
            t_pre_cool = sum(f * tt for f, tt in t_disch) / sum(f for f, _ in t_disch)
            t_reg_in = min(t_pre_cool, COOLER_TARGET_C)
            p_reg_in = (pDH - _pipe_loss(nw, "PDH-CLR2", F, t_pre_cool, pDH)[2]
                        - cl2["pressure_drop_mpa"] - ydp
                        - _pipe_loss(nw, "PY-REG", F, t_reg_in, pDH)[2])
            rec["compressors"] = comp_rec
            rec["power_mw"] = total_power
        else:
            p_reg_in = (pX - _pipe_loss(nw, "PX-Y", F, t, pX)[2] - ydp)
            p_reg_in -= _pipe_loss(nw, "PY-REG", F, t, p_reg_in)[2]
            t_reg_in = t
        t_reg_out = regulator_outlet_temperature(t_reg_in, p_reg_in, reg_out, jt)
        new_reg = _required_reg_out(nw, F, sink_p, t_reg_out)
        if abs(new_reg - reg_out) < 1e-10:
            reg_out = new_reg
            break
        reg_out = new_reg
    # record cooling / velocities for the low path
    if use_comps:
        for cid, f in active:
            rec["pipes"][f"PX-{cid}"] = (f, _pipe_loss(nw, f"PX-{cid}", f, t, pX[cid] if False else pX)[1])
            rec["pipes"][COMP_DISCHARGE[cid]] = (f, _pipe_loss(nw, COMP_DISCHARGE[cid], f, t,
                                                               rec["compressors"][cid]["discharge"])[1])
    else:
        rec["pipes"]["PX-Y"] = (F, _pipe_loss(nw, "PX-Y", F, t, pX)[1])
    if use_comps:
        rec["pipes"]["PDH-CLR2"] = (F, _pipe_loss(nw, "PDH-CLR2", F, t_pre_cool, pDH)[1])
        rec["pipes"]["PCLR2-Y"] = (F, _pipe_loss(nw, "PCLR2-Y", F, t_reg_in, pDH)[1])
    rec["pipes"]["PY-REG"] = (F, _pipe_loss(nw, "PY-REG", F, t_reg_in, p_reg_in)[1])
    duty2 = max(0.0, F * gas.cp * (t_pre_cool - t_reg_in) / 1e6)
    if use_comps:
        if duty2 > cl2["maximum_duty_mw"] + 1e-6:
            rec["violations"].append(f"CLR2 duty {duty2:.3f} > max")
        if F > cl2["capacity_kg_s"] + 1e-6:
            rec["violations"].append("CLR2 flow > cap")
        if t_reg_in < cl2["minimum_outlet_temperature_c"] - 1e-6:
            rec["violations"].append("CLR2 outlet below min")
    else:
        duty2 = 0.0
    rec["cooler2_duty_mw"] = duty2
    rec["cooler2_power_mw"] = duty2 * cl2["electric_power_fraction_of_duty"]
    rec["p_reg_in"] = p_reg_in
    rec["p_reg_out"] = reg_out
    if reg_out > p_reg_in + 1e-6:
        rec["violations"].append(f"regulator inlet {p_reg_in:.3f} < set {reg_out:.3f}")
    if p_reg_in > reg["maximum_pressure_mpa"] + 1e-6:
        rec["violations"].append("regulator inlet > max pressure")
    if F > reg["capacity_kg_s"] + 1e-6:
        rec["violations"].append("regulator flow > cap")
    if rec.get("compressors"):
        for cid, d in rec["compressors"].items():
            cm = nw.equipment[cid].model
            if d["flow"] > cm["capacity_kg_s"] + 1e-6:
                rec["violations"].append(f"{cid} flow > cap")
            if d["flow"] < cm["minimum_stable_flow_kg_s"] - 1e-6:
                rec["violations"].append(f"{cid} flow < min stable")
            if d["discharge"] > cm["maximum_discharge_pressure_mpa"] + 1e-6:
                rec["violations"].append(f"{cid} discharge > max")
            if d["ratio"] > cm["maximum_pressure_ratio"] + 1e-6:
                rec["violations"].append(f"{cid} ratio {d['ratio']:.3f} > max")
            if d["T_out_c"] > cm["maximum_discharge_temperature_c"] + 1e-6:
                rec["violations"].append(f"{cid} T > max")
    t_reg_out = regulator_outlet_temperature(t_reg_in, p_reg_in, reg_out, jt)
    p = reg_out
    p, v, _ = _pipe_loss(nw, "PREG-MTR", F, t_reg_out, p)
    rec["pipes"]["PREG-MTR"] = (F, v)
    p -= nw.equipment["MTR-WDR"].model["pressure_drop_mpa"]
    p, v, _ = _pipe_loss(nw, "PMTR-GRID", F, t_reg_out, p)
    rec["pipes"]["PMTR-GRID"] = (F, v)
    rec["p_grid"] = p
    rec["temp_c"] = t_reg_out
    rec["water"] = nw.equipment["DHY1"].model["normal_outlet_water_mg_sm3"]
    fl_out = fl_in * (1 - nw.equipment["SEP1"].model["liquid_removal_efficiency"])
    rec["free_liquid"] = fl_out
    if p_reg_in > nw.equipment["MTR-WDR"].model["maximum_pressure_mpa"] + 1e-6:
        rec["violations"].append("wdr meter pressure > max")
    _check_delivery(nw, rec, t_reg_out, rec["water"], fl_out, sink_p, "grid", p)
    return rec


# ===========================================================================
# Scenario orchestration, N-1 checks, pipe-class checks
# ===========================================================================
SCENARIOS = [
    {"id": "INJ-LOW",  "mode": "inj", "F": 120.0, "sink": 8.5,  "hours": 900,  "src": 6.5,  "fl": 0.0,  "water": 40.0},
    {"id": "INJ-MID",  "mode": "inj", "F": 100.0, "sink": 11.0, "hours": 1300, "src": 6.5,  "fl": 0.0,  "water": 40.0},
    {"id": "INJ-HIGH", "mode": "inj", "F": 75.0,  "sink": 13.5, "hours": 600,  "src": 6.5,  "fl": 0.0,  "water": 40.0},
    {"id": "WDR-HIGH", "mode": "wdr", "F": 120.0, "sink": 6.0,  "hours": 500,  "src": 12.0, "fl": 0.01, "water": 220.0, "comps": False},
    {"id": "WDR-MID",  "mode": "wdr", "F": 100.0, "sink": 6.0,  "hours": 900,  "src": 8.0,  "fl": 0.01, "water": 220.0, "comps": False},
    {"id": "WDR-LOW",  "mode": "wdr", "F": 70.0,  "sink": 6.0,  "hours": 800,  "src": 4.5,  "fl": 0.01, "water": 220.0, "comps": True},
]


def _load_split(nw, comp_ids, F):
    """Assign flow to compressors evenly across the smallest efficient set."""
    units = sorted(comp_ids, key=lambda c: -nw.equipment[c].model["efficiency_proxy"])
    for k in range(1, len(units) + 1):
        chosen = units[:k]
        caps = [nw.equipment[c].model["capacity_kg_s"] for c in chosen]
        mins = [nw.equipment[c].model["minimum_stable_flow_kg_s"] for c in chosen]
        if sum(caps) < F - 1e-9:
            continue
        share = F / k
        if share > min(caps) + 1e-9:
            continue
        if share < max(mins) - 1e-9:
            continue
        return [(c, F / k) for c in chosen]
    # fallback greedy
    out, rem = [], F
    for c in units:
        cap = nw.equipment[c].model["capacity_kg_s"]
        take = min(rem, cap)
        rem -= take
        if take > 1e-9:
            out.append((c, take))
        if rem <= 1e-9:
            break
    return out


def run_all(nw):
    results = {}
    comp_ids = ["CMP1", "CMP2", "CMP3"]
    for sc in SCENARIOS:
        if sc["mode"] == "inj":
            active = _load_split(nw, comp_ids, sc["F"])
            results[sc["id"]] = solve_injection(nw, sc["F"], sc["sink"], sc["hours"], active)
        else:
            active = _load_split(nw, comp_ids, sc["F"]) if sc.get("comps") else []
            results[sc["id"]] = solve_withdrawal(nw, sc["F"], sc["sink"], sc["hours"],
                                                 active, sc.get("comps", False),
                                                 sc["src"], sc["fl"])
        results[sc["id"]]["scenario"] = sc
    return results


def check_n_minus_one(nw):
    issues = []
    gas = nw.gas
    comps = ["CMP1", "CMP2", "CMP3"]
    caps = [nw.equipment[c].model["capacity_kg_s"] for c in comps]
    total_cap = sum(caps)
    for sc in SCENARIOS:
        if sc["mode"] == "inj" or (sc["mode"] == "wdr" and sc["sink"] > sc["src"]):
            need = 0.7 * sc["F"]
            worst = total_cap - max(caps)
            if worst < need - 1e-6:
                issues.append(f"[n-1 compression] {sc['id']} capacity {worst} < {need}")
            if total_cap < sc["F"] - 1e-6:
                issues.append(f"[cap] {sc['id']} total cap {total_cap} < {sc['F']}")
        if sc["mode"] == "wdr":
            for cat, ids in (("separator", ["SEP1", "SEP2", "SEP3"]),
                             ("dehydration", ["DHY1", "DHY2", "DHY3"])):
                ccaps = [nw.equipment[i].model["capacity_kg_s"] for i in ids]
                tot = sum(ccaps)
                worst = tot - max(ccaps)
                need = 0.7 * sc["F"]
                if worst < need - 1e-6:
                    issues.append(f"[n-1 {cat}] {sc['id']} capacity {worst} < {need}")
    return issues


def check_pipe_classes(nw):
    issues = []
    for pid, pipe in nw.pipes.items():
        cls = nw.pclass[pipe.pipe_class]
        pmax = nw.pipe_pmax[pid]
        if pmax > cls["maximum_allowable_pressure_mpa"] + 1e-6:
            issues.append(f"[pipe-rating] {pid} {pmax:.3f} > {cls['maximum_allowable_pressure_mpa']}")
        if nw.pipe_tmax[pid] > cls["temperature_limits_c"][1] + 1e-4 or \
           nw.pipe_tmin[pid] < cls["temperature_limits_c"][0] - 1e-4:
            issues.append(f"[pipe-temp] {pid} T out of class range")
        vmax = nw.pipe_vmax[pid]
        is_drain = pipe.pipe_class == "CS-WET-100" and "DRN" in pid
        if is_drain:
            if vmax > nw.b.piping["maximum_liquid_drain_velocity_m_s"] + 1e-6:
                issues.append(f"[drain-vel] {pid} v={vmax:.4f} > max")
        else:
            if vmax > nw.b.piping["maximum_gas_velocity_m_s"] + 1e-6:
                issues.append(f"[gas-vel] {pid} v={vmax:.3f} > max")
        # service compatibility
        if "GRID" in pid or True:
            pass
    return issues


# ===========================================================================
# Lifecycle cost
# ===========================================================================
def compute_lcc(nw, results):
    b = nw.b
    econ = b.economics
    i = econ["discount_rate"]
    N = econ["project_life_years"]
    pvf = N if i == 0 else (1 - (1 + i) ** (-N)) / i

    # equipment capex / maintenance
    eq_capex = 0.0
    eq_maint = 0.0
    eq_detail = {}
    for eid, eq in nw.equipment.items():
        c = eq.model["capex_mbcu"]
        m = eq.model["annual_maintenance_mbcu"]
        eq_capex += c
        eq_maint += m
        eq_detail[eid] = {"model": eq.model["model_id"], "capex": c, "maint": m}

    # piping capex
    pipe_capex = 0.0
    pipe_detail = {}
    for pid, pipe in nw.pipes.items():
        d = nw.diam[pipe.dn]
        cls = nw.pclass[pipe.pipe_class]
        lvl = nw.levels[pipe.level]
        cost = pipe.length * d["installed_cost_mbcu_per_m"] * cls["installed_cost_multiplier"] \
            * lvl["installed_cost_multiplier"]
        pipe_capex += cost
        pipe_detail[pid] = {"length": pipe.length, "dn": pipe.dn, "class": pipe.pipe_class,
                            "level": pipe.level, "cost": cost}

    # civil / access
    road_len = sum(r.length for r in nw.roads)
    civil_road = road_len * econ["civil"]["road_mbcu_per_m"]
    civil_found = sum(eq.area for eq in nw.equipment.values()) * econ["civil"]["foundation_mbcu_per_m2"]
    civil_maint = sum(eq.required_maintenance_area for eq in nw.equipment.values()) \
        * econ["civil"]["maintenance_area_mbcu_per_m2"]
    civil_pipe = sum(pipe.length * nw.levels[pipe.level]["civil_cost_mbcu_per_m"]
                     for pipe in nw.pipes.values())
    civil = civil_road + civil_found + civil_maint + civil_pipe

    # energy
    energy_mwh = 0.0
    energy_detail = {}
    for sid, r in results.items():
        h = r["hours"]
        comp = r.get("power_mw", 0.0)
        cool = r.get("cooler_power_mw", 0.0)
        cool2 = r.get("cooler2_power_mw", 0.0)
        dehy = r.get("dehy_energy_mw", 0.0)
        e = (comp + cool + cool2 + dehy) * h
        energy_mwh += e
        energy_detail[sid] = {"comp_mw": comp, "cool_mw": cool + cool2, "dehy_mw": dehy,
                              "hours": h, "mwh": e}
    energy_cost_annual = energy_mwh * econ["energy_tariff_mbcu_per_mwh"]
    energy_pv = energy_cost_annual * pvf

    maint_pv = eq_maint * pvf
    lcc = eq_capex + pipe_capex + civil + energy_pv + maint_pv
    return {
        "pvf": pvf,
        "equipment_capex": eq_capex,
        "piping_capex": pipe_capex,
        "civil_capex": civil,
        "civil_road": civil_road,
        "civil_foundation": civil_found,
        "civil_maintenance": civil_maint,
        "civil_pipeline": civil_pipe,
        "energy_mwh_per_year": energy_mwh,
        "energy_cost_annual": energy_cost_annual,
        "energy_pv": energy_pv,
        "maintenance_annual": eq_maint,
        "maintenance_pv": maint_pv,
        "lcc": lcc,
        "eq_detail": eq_detail,
        "pipe_detail": pipe_detail,
        "energy_detail": energy_detail,
    }


# ===========================================================================
# Greedy pipe sizing optimiser
# ===========================================================================
def _reset_tracking(nw):
    nw.pipe_pmax = {pid: 0.0 for pid in nw.pipes}
    nw.pipe_vmax = {pid: 0.0 for pid in nw.pipes}
    nw.pipe_tmax = {pid: -1e9 for pid in nw.pipes}
    nw.pipe_tmin = {pid: 1e9 for pid in nw.pipes}


def check_comp_pipe_capacity(nw):
    issues = []
    rep = {"suction": (6.5, 25.0), "discharge": (13.5, 55.0)}
    for cid in ["CMP1", "CMP2", "CMP3"]:
        cm = nw.equipment[cid].model
        cap = cm["capacity_kg_s"]
        for pid, side in [(f"PX-{cid}", "suction"), (COMP_DISCHARGE[cid], "discharge")]:
            pm, tm = rep[side]
            rho = nw.gas.density(pm, tm)
            d = nw.diam[nw.pipes[pid].dn]["internal_diameter_m"]
            v = cap / (rho * math.pi * d * d / 4.0)
            if v > nw.b.piping["maximum_gas_velocity_m_s"] + 1e-6:
                issues.append(f"[comp-pipe-cap] {pid} v={v:.1f} at cap")
    return issues


def evaluate(nw, dns):
    for pid, dn in dns.items():
        nw.pipes[pid].dn = dn
    _reset_tracking(nw)
    res = run_all(nw)
    vio = []
    for sid, r in res.items():
        vio += [f"{sid}: {v}" for v in r["violations"]]
    vio += check_n_minus_one(nw)
    vio += check_pipe_classes(nw)
    vio += check_comp_pipe_capacity(nw)
    lcc = compute_lcc(nw, res)
    return lcc, vio, res


def optimise_pipe_sizes(nw, max_passes=6):
    order = [d["nominal_diameter"] for d in nw.b.piping["diameters"]]
    dns = {pid: pipe.dn for pid, pipe in nw.pipes.items()}

    def run(dns):
        for pid, dn in dns.items():
            nw.pipes[pid].dn = dn
        _reset_tracking(nw)
        res = run_all(nw)
        vio = []
        for sid, r in res.items():
            vio += [f"{sid}: {v}" for v in r["violations"]]
        vio += check_n_minus_one(nw)
        vio += check_pipe_classes(nw)
        vio += check_comp_pipe_capacity(nw)
        lcc = compute_lcc(nw, res)
        return lcc["lcc"], vio, res

    best_lcc, best_vio, best_res = run(dns)
    for _pass in range(max_passes):
        improved = False
        for pid in list(nw.pipes):
            cur = dns[pid]
            cur_idx = order.index(cur)
            best_local = (best_lcc, cur)
            for cand in order:
                if cand == cur:
                    continue
                trial = dict(dns)
                trial[pid] = cand
                lcc, vio, res = run(trial)
                if vio:
                    continue
                if lcc < best_local[0] - 1e-9:
                    best_local = (lcc, cand)
            if best_local[1] != cur:
                dns[pid] = best_local[1]
                # update current best
                best_lcc, best_vio, best_res = run(dns)
                improved = True
        if not improved:
            break
    best_lcc, best_vio, best_res = run(dns)
    return dns, best_lcc, best_res


WET_SERVICE_PIPES = {"PWG1", "PWG2", "PWG3", "PWG4", "PWG5", "PWG6", "PWH-WP",
                     "PWP-SEP1", "PWP-SEP2", "PWP-SEP3",
                     "PSEP-DHY1", "PSEP-DHY2", "PSEP-DHY3"}


def check_service_compatibility(nw):
    issues = []
    for pid, pipe in nw.pipes.items():
        cls = nw.pclass[pipe.pipe_class]
        if pid in WET_SERVICE_PIPES:
            if not cls["wet_gas_compatible"]:
                issues.append(f"[service] {pid} carries wet gas but class is not wet-compatible")
        elif pid.startswith("PSEP-DRN") or pid.startswith("PDRN-OUT"):
            if not cls["liquid_drain_compatible"]:
                issues.append(f"[service] {pid} is a liquid drain but class is not liquid-compatible")
        else:
            if not cls["dry_gas_compatible"]:
                issues.append(f"[service] {pid} carries dry gas but class is not dry-compatible")
        # temperature rating
        if nw.pipe_tmax[pid] > cls["temperature_limits_c"][1] + 1e-4 or \
           nw.pipe_tmin[pid] < cls["temperature_limits_c"][0] - 1e-4:
            issues.append(f"[service-temp] {pid} outside class temperature range")
    return issues


# ===========================================================================
# Connection / cardinality / port-compatibility checks
# ===========================================================================
_IFACE_MAX_CONN = {
    "GRID-TIE": 2, "LIQUID-DRAIN-OUTFALL": 8,
    "WG-01": 1, "WG-02": 1, "WG-03": 1, "WG-04": 1, "WG-05": 1, "WG-06": 1,
}

_COMPAT = {
    "gas_out": {"gas_in", "gas_bidirectional"},
    "gas_bidirectional": {"gas_in", "gas_bidirectional"},
    "liquid_out": {"drain_in"},
    "drain_out": {"drain_in"},
}


def _endpoint_type(nw, end):
    head, port = end.split(".")
    if head in nw.equipment:
        for pp in nw.equipment[head].model["ports"]:
            if pp["id"] == port:
                return pp["type"]
    # interface
    for e in nw.b.site["external_interfaces"]:
        if e["interface_id"] == head:
            return e["port_type"]
    return None


def check_connections(nw):
    issues = []
    counts = {}
    header_conn = {}
    for pid, pipe in nw.pipes.items():
        for end in (pipe.a, pipe.b):
            head, port = end.split(".")
            counts[end] = counts.get(end, 0) + 1
            if head in nw.equipment and nw.equipment[head].category == "header":
                header_conn[head] = header_conn.get(head, 0) + 1
    for end, c in counts.items():
        head, port = end.split(".")
        if head in nw.equipment:
            eq = nw.equipment[head]
            if eq.category == "header":
                limit = 1  # each branch port is a single connection
            else:
                limit = 1
                for pp in eq.model["ports"]:
                    if pp["id"] == port:
                        limit = pp.get("maximum_connections", 1)
            if c > limit:
                issues.append(f"[cardinality] {end} {c} > {limit}")
        else:
            limit = _IFACE_MAX_CONN.get(head, 1)
            if c > limit:
                issues.append(f"[cardinality] {end} {c} > {limit}")
    # header branch-count limit
    for h, c in header_conn.items():
        mbc = nw.equipment[h].model["maximum_branch_connections"]
        if c > mbc:
            issues.append(f"[header-branches] {h} {c} > {mbc}")
    # port compatibility
    for pid, pipe in nw.pipes.items():
        ta = _endpoint_type(nw, pipe.a)
        tb = _endpoint_type(nw, pipe.b)
        ok = (tb in _COMPAT.get(ta, set())) or (ta in _COMPAT.get(tb, set()))
        if not ok:
            issues.append(f"[port-compat] {pid} {ta} -> {tb}")
    return issues
