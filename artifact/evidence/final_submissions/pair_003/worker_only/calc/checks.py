"""
Geometry, safety, maintenance, road and route validators.
"""
from __future__ import annotations

import math

import ugslib as U
import design as D
from ugslib import (bbox, point_in_poly, poly_area,
                    poly_overlap_area, poly_distance, seg_seg_distance)


def R(x0, y0, x1, y1):
    return (x0, y0, x1, y1)


def equip_rect(eid):
    e = D.EQUIPMENT[eid]
    m = e["model"]
    x0, y0, x1, y1 = bbox(U.rect_polygon(e["cx"], e["cy"],
                                         m["footprint_m"]["length"],
                                         m["footprint_m"]["width"],
                                         e["orientation_deg"]))
    return (x0, y0, x1, y1)


def rect_dist(a, b):
    """Distance between two axis-aligned rectangles (0 if overlapping)."""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def rect_contains(outer, inner, tol=1e-6):
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and
            inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def rect_overlap_area(a, b):
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    return ox * oy if (ox > 1e-9 and oy > 1e-9) else 0.0


def maintenance_rects(eid):
    """Required maintenance envelope = routine clearance envelope (union of the
    rectangular clearance ring) union the heavy-maintenance removal envelope."""
    e = D.EQUIPMENT[eid]
    m = e["model"]
    fp = equip_rect(eid)
    clr = m["maintenance"]["clearance_m"]
    rects = [R(fp[0] - clr, fp[1] - clr, fp[2] + clr, fp[3] + clr)]
    mt = m["maintenance"]
    if mt.get("heavy_maintenance"):
        ext, tw = mt["removal_envelope_m"]
        side = mt["side"]
        # local direction rotated with the equipment
        dirs = {"east": (1, 0), "west": (-1, 0), "north": (0, 1), "south": (0, -1)}
        d = U.rotate(dirs[side], e["orientation_deg"])
        if abs(d[0]) > 0.5:  # along x
            if d[0] > 0:
                rr = R(fp[2], e["cy"] - tw / 2.0, fp[2] + ext, e["cy"] + tw / 2.0)
            else:
                rr = R(fp[0] - ext, e["cy"] - tw / 2.0, fp[0], e["cy"] + tw / 2.0)
        else:  # along y
            if d[1] > 0:
                rr = R(e["cx"] - tw / 2.0, fp[3], e["cx"] + tw / 2.0, fp[3] + ext)
            else:
                rr = R(e["cx"] - tw / 2.0, fp[1] - ext, e["cx"] + tw / 2.0, fp[1])
        rects.append(rr)
    return rects


def envelope_area(eid):
    """Area of the union of the required maintenance envelope rectangles."""
    rs = maintenance_rects(eid)
    area = (rs[0][2] - rs[0][0]) * (rs[0][3] - rs[0][1])
    for r in rs[1:]:
        a = (r[2] - r[0]) * (r[3] - r[1])
        area += a - rect_overlap_area(rs[0], r)
    return area


# ---------------------------------------------------------------------------
SITE_RECT = (0.0, 0.0, 700.0, 450.0)
ZONES = U.SITE["no_build_zones"]


def zone_rects(flag):
    out = []
    for z in ZONES:
        if z.get(flag):
            out.append((z["zone_id"], bbox(z["polygon_m"])))
    return out


def check_geometry():
    issues = []
    # --- footprints -------------------------------------------------------
    for eid in D.EQUIPMENT:
        r = equip_rect(eid)
        if not rect_contains(SITE_RECT, r, tol=1e-6):
            issues.append(f"{eid}: footprint outside site boundary")
        if r[0] < 0 or r[1] < 0 or r[2] > 700 or r[3] > 450:
            issues.append(f"{eid}: footprint outside site boundary (edge)")
        for zid, zr in zone_rects("equipment_exclusion"):
            if rect_overlap_area(r, zr) > 1e-9:
                issues.append(f"{eid}: footprint overlaps equipment-exclusion zone {zid}")
    ids = list(D.EQUIPMENT)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = equip_rect(ids[i]), equip_rect(ids[j])
            if rect_overlap_area(a, b) > 1e-9:
                issues.append(f"{ids[i]} / {ids[j]}: footprint overlap")
    # --- safety separation ------------------------------------------------
    sep = U.SAFETY["minimum_separation_m"]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            ca = D.EQUIPMENT[ids[i]]["safety_category"]
            cb = D.EQUIPMENT[ids[j]]["safety_category"]
            need = sep[ca][cb]
            got = rect_dist(equip_rect(ids[i]), equip_rect(ids[j]))
            if got < need - 1e-6:
                issues.append(f"{ids[i]} / {ids[j]}: separation {got:.3f} m < {need} m "
                              f"({ca}/{cb})")
    # --- maintenance envelopes -------------------------------------------
    for eid in D.EQUIPMENT:
        for k, r in enumerate(maintenance_rects(eid)):
            if not rect_contains(SITE_RECT, r, tol=1e-6):
                issues.append(f"{eid}: maintenance envelope {k} outside site")
            for zid, zr in zone_rects("equipment_exclusion"):
                if rect_overlap_area(r, zr) > 1e-9:
                    issues.append(f"{eid}: maintenance envelope {k} overlaps exclusion {zid}")
            for other in D.EQUIPMENT:
                if other == eid:
                    continue
                if rect_overlap_area(r, equip_rect(other)) > 1e-9:
                    issues.append(f"{eid}: maintenance envelope {k} overlaps {other} footprint")
    return issues


def road_rects(road):
    cl = road["centreline"]
    w2 = road["width_m"] / 2.0
    rects = []
    for i in range(len(cl) - 1):
        (x1, y1), (x2, y2) = cl[i], cl[i + 1]
        if abs(y2 - y1) < 1e-9:  # horizontal
            rects.append((min(x1, x2) - w2, y1 - w2, max(x1, x2) + w2, y1 + w2))
        elif abs(x2 - x1) < 1e-9:
            rects.append((x1 - w2, min(y1, y2) - w2, x1 + w2, max(y1, y2) + w2))
        else:
            raise ValueError("non axis-aligned road segment")
    return rects


def check_roads():
    issues = []
    for road in D.ROADS:
        if road["width_m"] < 4.0 - 1e-9:
            issues.append(f"{road['id']}: road width < 4 m")
        for r in road_rects(road):
            if not rect_contains(SITE_RECT, r, tol=1e-6):
                issues.append(f"{road['id']}: paved geometry outside site")
            for zid, zr in zone_rects("road_exclusion"):
                if rect_overlap_area(r, zr) > 1e-9:
                    issues.append(f"{road['id']}: paved geometry in road-exclusion {zid}")
            for eid in D.EQUIPMENT:
                if rect_overlap_area(r, equip_rect(eid)) > 1e-9:
                    issues.append(f"{road['id']}: paved geometry overlaps {eid}")
    # connectivity + ROAD-ENTRANCE
    rects = [(road["id"], r) for road in D.ROADS for r in road_rects(road)]
    n = len(rects)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if rect_overlap_area(rects[i][1], rects[j][1]) > 1e-12 or \
               rect_dist(rects[i][1], rects[j][1]) < 1e-9:
                parent[find(i)] = find(j)
    ent = D.boundary_xy("ROAD-ENTRANCE")
    comps = set(find(i) for i in range(n))
    ent_comp = None
    for i, (rid, r) in enumerate(rects):
        if r[0] - 1e-9 <= ent[0] <= r[2] + 1e-9 and r[1] - 1e-9 <= ent[1] <= r[3] + 1e-9:
            ent_comp = find(i)
    if len(comps) > 1:
        issues.append(f"road network not connected ({len(comps)} components)")
    if ent_comp is None:
        issues.append("road network does not contain ROAD-ENTRANCE")
    return issues


def check_maintenance_access():
    issues = []
    roads = [(road["id"], r) for road in D.ROADS for r in road_rects(road)]
    rb = U.MAINT["road_access_buffer_m"]
    cb = U.MAINT["crane_access_buffer_m"]
    info = {}
    for eid in D.EQUIPMENT:
        m = D.EQUIPMENT[eid]["model"]
        mt = m["maintenance"]
        dists = []
        for k, env in enumerate(maintenance_rects(eid)):
            d = min(rect_dist(env, r) for _, r in roads)
            dists.append(d)
        d = min(dists)
        info[eid] = d
        if mt.get("road_access_required") and d > rb + 1e-6:
            issues.append(f"{eid}: road access distance {d:.2f} m > {rb} m")
        if mt.get("crane_access_required") and d > cb + 1e-6:
            issues.append(f"{eid}: crane access distance {d:.2f} m > {cb} m")
    return issues, info


# ---------------------------------------------------------------------------
def seg_rects(route, width=0.0):
    out = []
    for i in range(len(route) - 1):
        (x1, y1), (x2, y2) = route[i], route[i + 1]
        out.append((min(x1, x2) - width, min(y1, y2) - width,
                    max(x1, x2) + width, max(y1, y2) + width))
    return out


def check_pipelines():
    issues = []
    tol = 1e-6
    for pid, p in D.PIPELINES.items():
        route = p["route"]
        s = D.pipe_endpoint(pid, "src")
        d = D.pipe_endpoint(pid, "dst")
        if math.dist(route[0], s) > tol:
            issues.append(f"{pid}: route start {route[0]} != source port {s}")
        if math.dist(route[-1], d) > tol:
            issues.append(f"{pid}: route end {route[-1]} != destination port {d}")
        for i in range(len(route) - 1):
            L = math.dist(route[i], route[i + 1])
            if L <= tol:
                issues.append(f"{pid}: segment {i} length {L} <= tolerance")
        # inside site / outside pipeline exclusion / no footprint crossing
        for i, r in enumerate(seg_rects(route)):
            if not rect_contains(SITE_RECT, r, tol=1e-6):
                issues.append(f"{pid}: segment {i} outside site")
            for zid, zr in zone_rects("pipeline_exclusion"):
                if rect_overlap_area(r, zr) > tol:
                    issues.append(f"{pid}: segment {i} enters pipeline-exclusion {zid}")
            for eid in D.EQUIPMENT:
                ov = rect_overlap_area(r, equip_rect(eid))
                if ov > 1e-9:
                    issues.append(f"{pid}: segment {i} crosses footprint of {eid} "
                                  f"(overlap area {ov:.4f})")
    # same-level overlap
    keys = []
    for pid, p in D.PIPELINES.items():
        for i in range(len(p["route"]) - 1):
            keys.append((pid, i, p["level"], p["route"][i], p["route"][i + 1], p["corridor"]))
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            pa, ia, la, p1, p2, ca = keys[a]
            pb, ib, lb, p3, p4, cb_ = keys[b]
            if la != lb:
                continue
            if pa == pb and ia != ib:
                pass  # self overlap handled below
            if ca is not None and ca == cb_:
                cor = next(c for c in U.SITE["routing_corridors"] if c["corridor_id"] == ca)
                if cor["allows_co_routing"] and la in cor["allowed_routing_levels"]:
                    continue
            ov = _overlap_length(p1, p2, p3, p4)
            if ov > 1e-6:
                if pa == pb:
                    issues.append(f"{pa}: self overlap of segments {ia}/{ib} length {ov:.4f}")
                else:
                    issues.append(f"{pa} seg{ia} / {pb} seg{ib}: same-level overlap {ov:.4f} m")
    # corridor declaration validity
    for pid, p in D.PIPELINES.items():
        if p["corridor"] is None:
            continue
        cor = next(c for c in U.SITE["routing_corridors"] if c["corridor_id"] == p["corridor"])
        if p["level"] not in cor["allowed_routing_levels"]:
            issues.append(f"{pid}: level {p['level']} not allowed in corridor {p['corridor']}")
        cx0, cy0, cx1, cy1 = bbox(cor["polygon_m"])
        for pt in p["route"]:
            if not (cx0 <= pt[0] <= cx1 and cy0 <= pt[1] <= cy1):
                issues.append(f"{pid}: waypoint {pt} outside corridor {p['corridor']}")
    return issues


def _overlap_length(p1, p2, p3, p4):
    """Length of positive overlap between two collinear axis-aligned segments."""
    def axis(a, b):
        if abs(a[1] - b[1]) < 1e-12:
            return "h", a[1]
        if abs(a[0] - b[0]) < 1e-12:
            return "v", a[0]
        return None, None

    o1, c1 = axis(p1, p2)
    o2, c2 = axis(p3, p4)
    if o1 is None or o2 is None or o1 != o2:
        return 0.0
    if abs(c1 - c2) > 1e-7:
        return 0.0
    if o1 == "h":
        a0, a1 = sorted([p1[0], p2[0]])
        b0, b1 = sorted([p3[0], p4[0]])
    else:
        a0, a1 = sorted([p1[1], p2[1]])
        b0, b1 = sorted([p3[1], p4[1]])
    return max(0.0, min(a1, b1) - max(a0, b0))
