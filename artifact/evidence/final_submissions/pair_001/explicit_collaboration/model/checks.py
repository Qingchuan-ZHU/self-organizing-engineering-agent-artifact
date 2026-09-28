"""Geometry / topology validation of the design against the published rules."""
import math
import catalog as C
import geometry as G
import design as D
import scenarios as S

TOL = G.TOL


class Checker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.counts = {}

    def count(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n

    def err(self, code, msg):
        self.errors.append((code, msg))

    def warn(self, code, msg):
        self.warnings.append((code, msg))

    def note(self, msg):
        self.info.append(msg)


def build_equipment():
    eq = {}
    for eid, model, centre, orient in D.EQUIPMENT:
        m = C.MODELS[model]
        L = m["footprint_m"]["length"]
        W = m["footprint_m"]["width"]
        poly = G.rect_polygon(centre, L, W, orient)
        maint = m.get("maintenance", {})
        env = None
        if maint.get("clearance_m") is not None:
            env = G.expand_polygon(poly, maint["clearance_m"])
        removal = None
        if maint.get("heavy_maintenance"):
            side = maint["side"]
            ext, trans = maint["removal_envelope_m"]
            # local unit vectors of the four sides (unrotated)
            dirs = {"east": (1.0, 0.0), "west": (-1.0, 0.0),
                    "north": (0.0, 1.0), "south": (0.0, -1.0)}
            d = G.rot(dirs[side], orient)
            t = G.rot((-d[1], d[0]), orient)          # transverse
            # anchor: the two corners of the footprint on that side
            side_pts = [p for p in poly
                        if abs(G.dot(G.sub(p, centre), d) - (L / 2 if side in ("east", "west") else W / 2)) < 1e-9]
            if not side_pts:                           # fall back: max projection
                proj = [G.dot(G.sub(p, centre), d) for p in poly]
                dmax = max(proj)
                side_pts = [p for p in poly if abs(G.dot(G.sub(p, centre), d) - dmax) < 1e-9]
            base = side_pts[0]
            if len(side_pts) > 1:
                base = G.mul(G.add(side_pts[0], side_pts[1]), 0.5)
            c1 = G.add(base, G.mul(t, trans / 2.0))
            c2 = G.add(base, G.mul(t, -trans / 2.0))
            c3 = G.add(c2, G.mul(d, ext))
            c4 = G.add(c1, G.mul(d, ext))
            removal = [c1, c2, c3, c4]
        ports = {}
        for p in m["ports"]:
            pt = G.port_point(centre, orient, p["offset_m"])
            n = G.port_normal(p["offset_m"], L, W, orient)
            ports[p["id"]] = {"pt": pt, "type": p["type"], "normal": n,
                              "max_connections": p.get("maximum_connections", 1)}
        eq[eid] = {"id": eid, "model": model, "model_data": m, "centre": centre,
                   "orientation": orient, "poly": poly, "envelope": env,
                   "removal": removal, "ports": ports,
                   "safety_category": m["safety_category"],
                   "category": m["category"]}
    return eq


def maintenance_envelope(e):
    """Union of routine envelope and removal envelope (as polygon list)."""
    if e["envelope"] is None:
        return []
    if e["removal"] is None:
        return [e["envelope"]]
    return [e["envelope"], e["removal"]]


def envelope_area(e):
    """Area of the union of routine + removal envelopes (approx. by clipping)."""
    polys = maintenance_envelope(e)
    if not polys:
        return 0.0
    routine = e["envelope"]
    area = G.polygon_area(routine)
    if e["removal"] is not None:
        area += G.polygon_area(e["removal"]) - G.polygon_overlap_area(routine, e["removal"])
    return area


def site_polygon():
    return C.SITE["boundary_polygon_m"]


def zone_polys(flag):
    out = []
    for z in C.SITE["no_build_zones"]:
        if z.get(flag):
            out.append((z["zone_id"], z["polygon_m"]))
    return out


def poly_within_site(poly, name, chk):
    site = site_polygon()
    for p in poly:
        if not (min(q[0] for q in site) - TOL <= p[0] <= max(q[0] for q in site) + TOL and
                min(q[1] for q in site) - TOL <= p[1] <= max(q[1] for q in site) + TOL):
            chk.err("SITE", f"{name}: point {p} outside site boundary box")
    # polygon not contained (site is convex: check corners outside impossible
    # for a rectangle whose corners are all inside)


def check_equipment(chk, eq):
    # 1. footprints inside site, outside equipment exclusion zones, no overlap
    for e in eq.values():
        chk.count("footprint_inside_site")
        chk.count("footprint_vs_equipment_exclusion_zones",
                  len(zone_polys("equipment_exclusion")))
        poly_within_site(e["poly"], f"footprint {e['id']}", chk)
        for zid, zpoly in zone_polys("equipment_exclusion"):
            if G.polygon_overlap_area(e["poly"], zpoly) > 1e-9:
                chk.err("ZONE", f"{e['id']} footprint overlaps equipment exclusion zone {zid}")
        if poly_outside_site_interior(e["poly"]):
            chk.err("SITE", f"{e['id']} footprint not fully inside site boundary")
    ids = list(eq)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = eq[ids[i]], eq[ids[j]]
            chk.count("footprint_pair_overlap_test")
            ov = G.polygon_overlap_area(a["poly"], b["poly"])
            if ov > 1e-9:
                chk.err("OVERLAP", f"footprints {a['id']} and {b['id']} overlap ({ov:.3f} m2)")
            chk.count("safety_separation_pair_test")
            sep = G.polygon_distance(a["poly"], b["poly"])
            need = C.SAFETY["minimum_separation_m"][a["safety_category"]][b["safety_category"]]
            if sep < need - 1e-5:
                chk.err("SEPARATION",
                        f"{a['id']}({a['safety_category']}) - {b['id']}({b['safety_category']}): "
                        f"{sep:.3f} m < required {need} m")
    # 2. maintenance envelopes
    for e in eq.values():
        polys = maintenance_envelope(e)
        if not polys:
            continue
        for k, poly in enumerate(polys):
            chk.count("maintenance_envelope_test")
            poly_within_site(poly, f"{e['id']} maintenance envelope", chk)
            if poly_outside_site_interior(poly):
                chk.err("SITE", f"{e['id']} maintenance envelope leaves the site")
            for zid, zpoly in zone_polys("equipment_exclusion"):
                if G.polygon_overlap_area(poly, zpoly) > 1e-9:
                    chk.err("ZONE", f"{e['id']} maintenance envelope enters exclusion zone {zid}")
            for other in eq.values():
                if other["id"] == e["id"]:
                    continue
                ov = G.polygon_overlap_area(poly, other["poly"])
                if ov > 1e-9:
                    chk.err("MAINT",
                            f"{e['id']} maintenance envelope overlaps footprint of {other['id']} ({ov:.3f} m2)")


def poly_outside_site_interior(poly):
    """True when part of the polygon lies outside the site boundary polygon."""
    site = site_polygon()
    # subtract the site: any point of poly strictly outside the site polygon
    for p in poly:
        if not point_in_convex_site(p, site):
            return True
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        # sample along edges
        for t in [k / 20.0 for k in range(21)]:
            p = G.add(a, G.mul(G.sub(b, a), t))
            if not point_in_convex_site(p, site):
                return True
    return False


def point_in_convex_site(p, site):
    n = len(site)
    for i in range(n):
        a, b = site[i], site[(i + 1) % n]
        if G.cross(G.sub(b, a), G.sub(p, a)) < -1e-6:
            return False
    return True


# ----------------------------------------------------------------- roads
def road_polygons(roads):
    out = {}
    for rid, pts, width in roads:
        polys = []
        hw = width / 2.0
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            u = G.unit(G.sub(b, a))
            nrm = (-u[1], u[0])
            a2 = G.add(a, G.mul(u, -hw))
            b2 = G.add(b, G.mul(u, hw))
            polys.append([G.add(a2, G.mul(nrm, hw)), G.add(b2, G.mul(nrm, hw)),
                          G.add(b2, G.mul(nrm, -hw)), G.add(a2, G.mul(nrm, -hw))])
        out[rid] = {"centerline": pts, "width": width, "pieces": polys}
    return out


def check_roads(chk, eq, roads):
    site = site_polygon()
    for rid, r in roads.items():
        chk.count("road_definition_test")
        if r["width"] < 4.0 - TOL:
            chk.err("ROAD", f"{rid}: width {r['width']} < 4 m")
        for poly in r["pieces"]:
            chk.count("road_paved_geometry_test")
            for p in poly:
                if not point_in_convex_site(p, site):
                    chk.err("ROAD", f"{rid} paved area leaves the site at {p}")
            for zid, zpoly in zone_polys("road_exclusion"):
                if G.polygon_overlap_area(poly, zpoly) > 1e-9:
                    chk.err("ROAD", f"{rid} paved area enters road exclusion zone {zid}")
            for e in eq.values():
                ov = G.polygon_overlap_area(poly, e["poly"])
                if ov > 1e-9:
                    chk.err("ROAD", f"{rid} paved area overlaps footprint of {e['id']} ({ov:.3f} m2)")
    # connectivity: build a graph on paved pieces, tolerate touching
    ids = list(roads)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            for pa in roads[ids[i]]["pieces"]:
                for pb in roads[ids[j]]["pieces"]:
                    if G.polygon_distance(pa, pb) <= 1e-6:
                        union(ids[i], ids[j])
    roots = {find(i) for i in ids}
    if len(roots) > 1:
        chk.err("ROAD", f"road network not connected: {len(roots)} groups")
    # ROAD-ENTRANCE must sit on the paved network
    ent = None
    for iface in C.SITE["external_interfaces"]:
        if iface["interface_id"] == "ROAD-ENTRANCE":
            ent = iface["point_m"]
    if ent is not None:
        ok = False
        for rid, r in roads.items():
            for poly in r["pieces"]:
                if not G.in_interior(ent, poly):
                    d = min(G.point_seg_distance(ent, poly[i], poly[(i + 1) % len(poly)])
                            for i in range(len(poly)))
                    if d <= 1e-6:
                        ok = True
                else:
                    ok = True
        if not ok:
            chk.err("ROAD", "ROAD-ENTRANCE is not on the paved road network")
    # access requirements
    for e in eq.values():
        maint = e["model_data"].get("maintenance", {})
        if not maint.get("road_access_required"):
            continue
        polys = maintenance_envelope(e)
        if not polys or not roads:
            continue
        chk.count("road_crane_access_test")
        d = min(G.polygon_distance(poly, q)
                for poly in polys for r in roads.values() for q in r["pieces"])
        if d > C.MAINT["road_access_buffer_m"] + 1e-6:
            chk.err("ACCESS", f"{e['id']}: road access distance {d:.2f} m > "
                              f"{C.MAINT['road_access_buffer_m']} m")
        if maint.get("crane_access_required"):
            if d > C.MAINT["crane_access_buffer_m"] + 1e-6:
                chk.err("ACCESS", f"{e['id']}: crane access distance {d:.2f} m > "
                                  f"{C.MAINT['crane_access_buffer_m']} m")


# ------------------------------------------------------------- pipelines
def seg_rect_intervals(a, b, rect):
    """Parameter intervals of segment a-b that lie inside convex polygon rect."""
    clipped = G._clip([a, b], rect)
    if len(clipped) < 2:
        return None
    d = G.sub(b, a)
    L2 = G.dot(d, d)
    if L2 <= 0:
        return None
    ts = [G.dot(G.sub(p, a), d) / L2 for p in clipped]
    t0, t1 = min(ts), max(ts)
    if t1 - t0 <= 1e-9:
        return None
    return (max(0.0, t0), min(1.0, t1))


def split_for_road_crossings(a, b, base_level, road_pieces):
    """Split a segment so that lengths crossing paved roads are buried."""
    intervals = []
    for rect in road_pieces:
        iv = seg_rect_intervals(a, b, rect)
        if iv:
            intervals.append(iv)
    if not intervals:
        return [(a, b, base_level)]
    intervals.sort()
    merged = []
    for iv in intervals:
        if merged and iv[0] <= merged[-1][1] + 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], iv[1]))
        else:
            merged.append(list(iv))
    out = []
    ts = sorted({0.0, 1.0} | {t for iv in merged for t in iv})
    for t0, t1 in zip(ts, ts[1:]):
        if t1 - t0 <= 1e-12:
            continue
        p0 = G.add(a, G.mul(G.sub(b, a), t0))
        p1 = G.add(a, G.mul(G.sub(b, a), t1))
        inside = any(iv[0] - 1e-9 <= t0 and t1 <= iv[1] + 1e-9 for iv in merged)
        out.append((p0, p1, "buried" if inside else base_level))
    return out


def build_segments(chk, eq, pipes, roads=None):
    """Return list of segment dicts with resolved endpoints."""
    road_pieces = []
    if roads:
        for r in roads.values():
            road_pieces.extend(r["pieces"])
    segs = []
    for pid, src, dst, waypoints, dn, cls, level, service, note in pipes:
        sn, sp = src
        dn_, dp = dst
        s_pt = port_point_of(eq, sn, sp)
        d_pt = port_point_of(eq, dn_, dp)
        pts = [tuple(p) for p in waypoints]
        if G.dist(pts[0], s_pt) > 1e-6:
            chk.err("PIPE", f"{pid}: first waypoint {pts[0]} != source port {s_pt}")
        if G.dist(pts[-1], d_pt) > 1e-6:
            chk.err("PIPE", f"{pid}: last waypoint {pts[-1]} != destination port {d_pt}")
        pts = G.simplify(pts)
        cur = S.PIPES[pid]
        k = 0
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if G.dist(a, b) <= TOL:
                chk.err("PIPE", f"{pid}: zero length segment {a}->{b}")
                continue
            for a2, b2, lvl in split_for_road_crossings(a, b, cur["level"], road_pieces):
                segs.append({"pipe": pid, "seg": k, "a": a2, "b": b2, "level": lvl,
                             "dn": cur["dn"], "class": cur["class"],
                             "service": cur["service"], "src": src, "dst": dst,
                             "nseg": len(pts) - 1})
                k += 1
    return segs


def port_point_of(eq, node, port):
    if node in eq:
        return eq[node]["ports"][port]["pt"]
    iface = C.INTERFACES[node]
    return tuple(iface["point_m"])


def check_pipelines(chk, eq, segs, pipes):
    # segment geometry
    for s in segs:
        chk.count("pipeline_segment_test")
        poly_within_site([s["a"], s["b"]], f"{s['pipe']} seg{s['seg']}", chk)
        pts = [G.add(s["a"], G.mul(G.sub(s["b"], s["a"]), t / 10.0)) for t in range(11)]
        for p in pts:
            if not point_in_convex_site(p, site_polygon()):
                chk.err("PIPE", f"{s['pipe']} seg{s['seg']}: leaves the site")
                break
        for zid, zpoly in zone_polys("pipeline_exclusion"):
            if G.seg_enters_polygon_interior(s["a"], s["b"], zpoly):
                chk.err("PIPE", f"{s['pipe']} seg{s['seg']}: enters pipeline exclusion zone {zid}")
        for e in eq.values():
            if s["src"][0] == e["id"] or s["dst"][0] == e["id"]:
                # allow the segment to start/end on the footprint boundary
                if _touches_only(s, e["poly"]):
                    continue
            if G.seg_enters_polygon_interior(s["a"], s["b"], e["poly"]):
                chk.err("PIPE", f"{s['pipe']} seg{s['seg']}: crosses footprint of {e['id']}")
    # overlap rule
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if a["level"] != b["level"]:
                continue
            chk.count("same_level_overlap_pair_test")
            ov = G.collinear_overlap(a["a"], a["b"], b["a"], b["b"])
            if ov > 1e-6:
                same = (a["pipe"] == b["pipe"])
                chk.err("OVERLAP",
                        f"{a['pipe']} seg{a['seg']} and {b['pipe']} seg{b['seg']} "
                        f"overlap {ov:.3f} m at level {a['level']}"
                        + (" (self overlap)" if same else ""))
    # corridors
    corr = {c["corridor_id"]: c for c in C.SITE["routing_corridors"]}
    for s in segs:
        if "corridor" in s and s["corridor"]:
            c = corr[s["corridor"]]
            if s["level"] not in c["allowed_routing_levels"]:
                chk.err("CORRIDOR", f"{s['pipe']}: level {s['level']} not allowed in {s['corridor']}")
            if not (G.in_interior(s["a"], c["polygon_m"]) and G.in_interior(s["b"], c["polygon_m"])):
                chk.err("CORRIDOR", f"{s['pipe']}: segment not inside interior of {s['corridor']}")


def _touches_only(s, poly):
    """True when the segment only touches the polygon boundary (no interior)."""
    return not G.seg_enters_polygon_interior(s["a"], s["b"], poly)


def check_topology(chk, eq, pipes):
    used = {}
    for pid, src, dst, wp, dn, cls, level, service, note in pipes:
        for node, port in (src, dst):
            key = (node, port)
            used.setdefault(key, []).append(pid)
    for (node, port), plist in used.items():
        chk.count("port_connection_test")
        if node in C.INTERFACES:
            continue
        if len(plist) > 1:
            chk.err("CARD", f"port {node}.{port} used by {len(plist)} pipelines: {plist}")
    for e in eq.values():
        for port, meta in e["ports"].items():
            key = (e["id"], port)
            if len(used.get(key, [])) > meta["max_connections"]:
                chk.err("CARD", f"{e['id']}.{port} exceeds maximum_connections")
    for iname, iface in C.INTERFACES.items():
        if iface["port_type"] in ("utility_in", "road_access"):
            continue
        n = len(used.get((iname, iface["port_id"]), []))
        mx = iface.get("maximum_connections", 1)
        if n > mx:
            chk.err("CARD", f"interface {iname} has {n} connections > {mx}")
    # compatibility of port types
    for pid, src, dst, wp, dn, cls, level, service, note in pipes:
        chk.count("port_compatibility_test")
        st = port_type_of(eq, src)
        dt = port_type_of(eq, dst)
        pair = (st, dt)
        allowed = {("gas_out", "gas_in"), ("gas_out", "gas_bidirectional"),
                   ("gas_bidirectional", "gas_in"), ("gas_bidirectional", "gas_bidirectional"),
                   ("liquid_out", "drain_in"), ("drain_out", "drain_in")}
        if pair not in allowed and (dt, st) not in allowed:
            chk.err("PORTTYPE", f"{pid}: incompatible port types {st} -> {dt}")
        elif pair not in allowed:
            # listed in reverse order; still a legal physical connection
            pass
    # every separator liquid_out connected, every drain_out routed
    for e in eq.values():
        if e["category"] in ("separator", "filter"):
            chk.count("separator_liquid_connection_test")
            key = (e["id"], "liquid_out")
            if not used.get(key):
                chk.err("LIQUID", f"{e['id']}.liquid_out is not connected to a closed drain")


def port_type_of(eq, nodeport):
    node, port = nodeport
    if node in eq:
        return eq[node]["ports"][port]["type"]
    return C.INTERFACES[node]["port_type"]


def run():
    chk = Checker()
    eq = build_equipment()
    check_equipment(chk, eq)
    roads = road_polygons(D.ROADS)
    check_roads(chk, eq, roads)
    segs = build_segments(chk, eq, D.PIPELINES, roads)
    check_pipelines(chk, eq, segs, D.PIPELINES)
    check_topology(chk, eq, D.PIPELINES)
    return chk, eq, roads, segs


if __name__ == "__main__":
    chk, eq, roads, segs = run()
    print(f"equipment {len(eq)}  pipelines {len(D.PIPELINES)}  segments {len(segs)}")
    print(f"errors: {len(chk.errors)}")
    for code, msg in chk.errors[:80]:
        print("  ", code, msg)
    print(f"warnings: {len(chk.warnings)}")
    for code, msg in chk.warnings[:20]:
        print("  ", code, msg)
