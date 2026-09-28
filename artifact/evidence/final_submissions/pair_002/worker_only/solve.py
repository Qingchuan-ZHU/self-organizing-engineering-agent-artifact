"""Build + geometry checks for the UGS-SYNTH-D01 design."""
import json, math, os, sys
import lib_geom as G
import ugscat as U
import design as D

TOL = 1e-6


def port_normal(eq, offset_m):
    """Outward unit normal (site frame) of a port on the footprint boundary."""
    L = eq["m"]["footprint_m"]["length"]
    W = eq["m"]["footprint_m"]["width"]
    lx, ly = offset_m
    if abs(lx) >= L / 2 - 1e-9:
        n = (1.0 if lx > 0 else -1.0, 0.0)
    elif abs(ly) >= W / 2 - 1e-9:
        n = (0.0, 1.0 if ly > 0 else -1.0)
    else:
        return None
    return G.rotate(n[0], n[1], eq["orient"])


def build():
    equip = {}
    for eid, (model, x, y, orient) in D.EQUIPMENT.items():
        m = U.CAT[model]
        eq = dict(id=eid, model=model, x=x, y=y, orient=orient, m=m)
        eq["poly"] = G.rect_polygon(x, y, m["footprint_m"]["length"], m["footprint_m"]["width"], orient)
        eq["ports"] = {}
        for p in m["ports"]:
            eq["ports"][p["id"]] = dict(type=p["type"], pos=G.port_position(eq, p["offset_m"]),
                                        normal=port_normal(eq, p["offset_m"]), offset=p["offset_m"])
        equip[eid] = eq

    ifaces = {}
    for it in U.SITE["external_interfaces"]:
        ifaces[it["interface_id"]] = dict(id=it["interface_id"], pos=tuple(it["point_m"]),
                                          port_type=it["port_type"],
                                          maximum_connections=it.get("maximum_connections", 1),
                                          maximum_flow_kg_s=it.get("maximum_flow_kg_s"))

    def endpoint(ref):
        eid, pid = ref.split(".")
        if eid in equip:
            p = equip[eid]["ports"][pid]
            return p["pos"], p["normal"]
        return ifaces[eid]["pos"], None

    pipes = {}
    for pid, spec in D.PIPES.items():
        pa, na = endpoint(spec["a"])
        pb, nb = endpoint(spec["b"])
        pts = [pa]
        if na is not None:
            pts.append((pa[0] + na[0] * D.STUB, pa[1] + na[1] * D.STUB))
        pts += [tuple(p) for p in spec["via"]]
        if nb is not None:
            pts.append((pb[0] + nb[0] * D.STUB, pb[1] + nb[1] * D.STUB))
        pts.append(pb)
        segs = [dict(a=pts[i], b=pts[i + 1], level=spec["level"]) for i in range(len(pts) - 1)]
        pipes[pid] = dict(id=pid, spec=spec, pts=pts, segs=segs,
                          length=sum(math.dist(s["a"], s["b"]) for s in segs))
    return equip, ifaces, pipes


def envelopes(eq):
    m = eq["m"]["maintenance"]
    out = []
    cl = m["clearance_m"]
    clr = G.rect_polygon(eq["x"], eq["y"], eq["m"]["footprint_m"]["length"] + 2 * cl,
                         eq["m"]["footprint_m"]["width"] + 2 * cl, eq["orient"])
    out.append(("clearance", clr))
    if m.get("heavy_maintenance"):
        ext, wid = m["removal_envelope_m"]
        side = m["side"]
        L = eq["m"]["footprint_m"]["length"]
        W = eq["m"]["footprint_m"]["width"]
        if side == "east":
            cx, cy, el, ew = L / 2 + ext / 2, 0.0, ext, wid
        elif side == "west":
            cx, cy, el, ew = -(L / 2 + ext / 2), 0.0, ext, wid
        elif side == "north":
            cx, cy, el, ew = 0.0, W / 2 + ext / 2, wid, ext
        else:
            cx, cy, el, ew = 0.0, -(W / 2 + ext / 2), wid, ext
        out.append(("removal", G.rect_polygon_local(eq["x"], eq["y"], cx, cy, el, ew, eq["orient"])))
    return out


def seg_rect(a, b, hw):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L == 0:
        return [(ax, ay)] * 4
    ux, uy = dx / L, dy / L
    px, py = -uy * hw, ux * hw
    return [(ax + px, ay + py), (bx + px, by + py), (bx - px, by - py), (ax - px, ay - py)]


def on_boundary(poly, p, tol=1e-6):
    n = len(poly)
    return any(G.seg_point_dist(poly[i], poly[(i + 1) % n], p) <= tol for i in range(n))


def seg_enters_poly(s, poly, margin=1e-6):
    a, b = s["a"], s["b"]
    for k in range(1, 80):
        t = k / 80.0
        pt = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        if G.point_in_poly(poly, pt) and not on_boundary(poly, pt, 1e-9):
            d = min(G.seg_point_dist(poly[i], poly[(i + 1) % len(poly)], pt) for i in range(len(poly)))
            if d > margin:
                return True
    return False


def seg_overlap_length(s1, s2):
    a1, b1 = s1["a"], s1["b"]
    a2, b2 = s2["a"], s2["b"]
    d1 = (b1[0] - a1[0], b1[1] - a1[1])
    l1 = math.hypot(*d1)
    if l1 < 1e-9:
        return 0.0
    u = (d1[0] / l1, d1[1] / l1)
    for p in (a2, b2):
        if abs((p[0] - a1[0]) * u[1] - (p[1] - a1[1]) * u[0]) > 1e-6:
            return 0.0

    def proj(p):
        return (p[0] - a1[0]) * u[0] + (p[1] - a1[1]) * u[1]
    t2 = sorted([proj(a2), proj(b2)])
    return max(0.0, min(l1, t2[1]) - max(0.0, t2[0]))


def check_geometry(equip, ifaces, pipes):
    issues = []
    site = [tuple(p) for p in U.SITE["boundary_polygon_m"]]
    zones = U.SITE["no_build_zones"]
    zone_polys = {z["zone_id"]: [tuple(p) for p in z["polygon_m"]] for z in zones}
    eq_zones = [z for z in zones if z["equipment_exclusion"]]
    road_zones = [z for z in zones if z["road_exclusion"]]
    pipe_zones = [z for z in zones if z["pipeline_exclusion"]]

    ids = list(equip.keys())
    for eid in ids:
        eq = equip[eid]
        if not G.poly_inside_poly(eq["poly"], site):
            issues.append(f"{eid}: footprint not within site")
        for z in eq_zones:
            if G.convex_overlap_area(eq["poly"], zone_polys[z["zone_id"]]) > 1e-9:
                issues.append(f"{eid}: footprint in equipment-exclusion {z['zone_id']}")
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = equip[ids[i]], equip[ids[j]]
            if G.convex_overlap_area(a["poly"], b["poly"]) > 1e-9:
                issues.append(f"overlap footprint {a['id']} <-> {b['id']}")
            need = U.SAFETY["minimum_separation_m"][a["m"]["safety_category"]][b["m"]["safety_category"]]
            dst = G.poly_distance(a["poly"], b["poly"])
            if dst < need - 1e-6:
                issues.append(f"separation {a['id']}<->{b['id']} = {dst:.4f} < {need}")

    env_by_eq = {eid: envelopes(equip[eid]) for eid in ids}
    for eid in ids:
        for kind, poly in env_by_eq[eid]:
            if not G.poly_inside_poly(poly, site):
                issues.append(f"{eid}: {kind} envelope not within site")
            for z in eq_zones:
                if G.convex_overlap_area(poly, zone_polys[z["zone_id"]]) > 1e-9:
                    issues.append(f"{eid}: {kind} envelope in equipment-exclusion {z['zone_id']}")
            for oid in ids:
                if oid == eid:
                    continue
                if G.convex_overlap_area(poly, equip[oid]["poly"]) > 1e-9:
                    issues.append(f"{eid}: {kind} envelope overlaps footprint {oid}")

    for pid, p in pipes.items():
        for si, s in enumerate(p["segs"]):
            if math.dist(s["a"], s["b"]) <= 1e-6:
                issues.append(f"{pid} seg{si}: zero length")
            for pt in (s["a"], s["b"]):
                x, y = pt
                if x < -1e-6 or x > 700 + 1e-6 or y < -1e-6 or y > 450 + 1e-6:
                    issues.append(f"{pid} seg{si}: point outside site bbox {pt}")
            if not G.poly_inside_poly([s["a"], s["b"]], site):
                issues.append(f"{pid} seg{si}: segment outside site")
            for z in pipe_zones:
                if seg_enters_poly(s, zone_polys[z["zone_id"]]):
                    issues.append(f"{pid} seg{si}: enters pipeline-exclusion {z['zone_id']}")
            for eid in ids:
                if seg_enters_poly(s, equip[eid]["poly"]):
                    issues.append(f"{pid} seg{si}: crosses footprint {eid}")

    seglist = [(pid, si, s) for pid, p in pipes.items() for si, s in enumerate(p["segs"])]
    for i in range(len(seglist)):
        for j in range(i + 1, len(seglist)):
            p1, i1, s1 = seglist[i]
            p2, i2, s2 = seglist[j]
            if p1 == p2:
                continue
            if s1["level"] != s2["level"]:
                continue
            ov = seg_overlap_length(s1, s2)
            if ov > 1e-6:
                issues.append(f"same-level overlap {p1}[{i1}] ~ {p2}[{i2}] len {ov:.3f}")
    for pid, p in pipes.items():
        for i in range(len(p["segs"])):
            for j in range(i + 1, len(p["segs"])):
                ov = seg_overlap_length(p["segs"][i], p["segs"][j])
                if ov > 1e-6:
                    issues.append(f"self overlap {pid}[{i}]~[{j}] len {ov:.3f}")

    road_polys = {}
    for rid, r in D.ROADS.items():
        hw = r["width"] / 2.0
        rects = [seg_rect(r["pts"][i], r["pts"][i + 1], hw) for i in range(len(r["pts"]) - 1)]
        road_polys[rid] = rects
        for rc in rects:
            for corner in rc:
                x, y = corner
                if x < -1e-6 or x > 700 + 1e-6 or y < -1e-6 or y > 450 + 1e-6:
                    issues.append(f"road {rid}: outside site {corner}")
            for z in road_zones:
                if G.convex_overlap_area(rc, zone_polys[z["zone_id"]]) > 1e-9:
                    issues.append(f"road {rid}: in road-exclusion {z['zone_id']}")
            for eid in ids:
                if G.convex_overlap_area(rc, equip[eid]["poly"]) > 1e-9:
                    issues.append(f"road {rid}: overlaps footprint {eid}")

    allrects = [(rid, rc) for rid, rs in road_polys.items() for rc in rs]
    n = len(allrects)
    parent = list(range(n))

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for i in range(n):
        for j in range(i + 1, n):
            if G.convex_overlap_area(allrects[i][1], allrects[j][1]) > 1e-9 or G.poly_distance(allrects[i][1], allrects[j][1]) < 1e-6:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), set()).add(allrects[i][0])
    if len(groups) != 1:
        issues.append(f"road network not connected: {[sorted(v) for v in groups.values()]}")
    entrance = None
    for it in U.SITE["external_interfaces"]:
        if it["interface_id"] == "ROAD-ENTRANCE":
            entrance = tuple(it["point_m"])
    if not any(G.point_in_poly(rc, entrance) for _, rc in allrects):
        issues.append("ROAD-ENTRANCE point not within paved road geometry")

    for eid in ids:
        m = equip[eid]["m"]["maintenance"]
        mn = min(min(G.poly_distance(poly, rc) for _, rc in allrects) for _, poly in env_by_eq[eid])
        if m.get("road_access_required") and mn > U.MAINT["road_access_buffer_m"] + 1e-6:
            issues.append(f"{eid}: road access {mn:.2f} > {U.MAINT['road_access_buffer_m']}")
        if m.get("crane_access_required") and mn > U.MAINT["crane_access_buffer_m"] + 1e-6:
            issues.append(f"{eid}: crane access {mn:.2f} > {U.MAINT['crane_access_buffer_m']}")
    return issues, road_polys, env_by_eq, allrects
