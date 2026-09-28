"""Geometry / safety / maintenance / road validator for the UGS layout."""
import sys, math
sys.path.insert(0, "/workspace/project")
import ugs_core as C
from ugs_design import (load, load_catalog, INSTANCES, ROADS, footprint,
                        port_world, rotate)

cat = load_catalog()
site = load("site.json")
safety = load("safety_requirements.json")
maint_req = load("maintenance_requirements.json")

BOUND = site["boundary_polygon_m"]
SITE = (min(p[0] for p in BOUND), min(p[1] for p in BOUND),
        max(p[0] for p in BOUND), max(p[1] for p in BOUND))
ZONES = site["no_build_zones"]
CORRIDORS = site["routing_corridors"]
INTERFACES = {i["interface_id"]: i for i in site["external_interfaces"]}

viol = []


def eq(name, cond, msg):
    if not cond:
        viol.append(f"[{name}] {msg}")


# --- footprints
FP = {}
for inst in INSTANCES:
    FP[inst["id"]] = footprint(inst, cat)

# 1. within site
for iid, r in FP.items():
    eq("site", C.rect_contains_rect(SITE, r, 0.0),
       f"{iid} footprint {r} outside site {SITE}")

# 2. exclusion interiors
for z in ZONES:
    zr = (min(p[0] for p in z["polygon_m"]), min(p[1] for p in z["polygon_m"]),
          max(p[0] for p in z["polygon_m"]), max(p[1] for p in z["polygon_m"]))
    if z.get("equipment_exclusion"):
        for iid, r in FP.items():
            ov = C.rect_overlap_area(r, zr)
            eq("excl", ov <= 1e-9, f"{iid} footprint overlaps equipment-exclusion zone {z['zone_id']} by {ov:.3f} m2")

# 3. footprint overlaps
ids = list(FP)
for a in range(len(ids)):
    for b in range(a + 1, len(ids)):
        ov = C.rect_overlap_area(FP[ids[a]], FP[ids[b]])
        eq("overlap", ov <= 1e-9, f"{ids[a]} & {ids[b]} footprints overlap by {ov:.3f} m2")

# 4. safety separation
sep_matrix = safety["minimum_separation_m"]
for a in range(len(ids)):
    for b in range(a + 1, len(ids)):
        ia, ib = ids[a], ids[b]
        ca = cat[[i for i in INSTANCES if i["id"] == ia][0]["model_id"]]["safety_category"]
        cb = cat[[i for i in INSTANCES if i["id"] == ib][0]["model_id"]]["safety_category"]
        need = sep_matrix[ca][cb]
        got = C.rect_distance(FP[ia], FP[ib])
        eq("safety", got >= need - 1e-9,
           f"{ia}({ca}) & {ib}({cb}) separation {got:.3f} < {need} m")

# 5. maintenance envelopes
ENV = {}
for inst in INSTANCES:
    iid = inst["id"]; m = cat[inst["model_id"]]
    cl = footprint(inst, cat, m["maintenance"]["clearance_m"])
    rects = [cl]
    if m["maintenance"].get("heavy_maintenance"):
        side = m["maintenance"]["side"]
        ext, tw = m["maintenance"]["removal_envelope_m"]
        # local removal rect on the given side
        L = m["footprint_m"]["length"]; W = m["footprint_m"]["width"]
        if side == "east":
            lx0, lx1, ly0, ly1 = L / 2, L / 2 + ext, -tw / 2, tw / 2
        elif side == "west":
            lx0, lx1, ly0, ly1 = -L / 2 - ext, -L / 2, -tw / 2, tw / 2
        elif side == "north":
            lx0, lx1, ly0, ly1 = -tw / 2, tw / 2, W / 2, W / 2 + ext
        else:
            lx0, lx1, ly0, ly1 = -tw / 2, tw / 2, -W / 2 - ext, -W / 2
        corners = [(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)]
        wc = [rotate(c, inst["o"]) for c in corners]
        xs = [inst["x"] + c[0] for c in wc]; ys = [inst["y"] + c[1] for c in wc]
        rects.append((min(xs), min(ys), max(xs), max(ys)))
    ENV[iid] = rects

for iid, rects in ENV.items():
    for r in rects:
        eq("maint-site", C.rect_contains_rect(SITE, r, 0.0), f"{iid} maintenance rect {r} outside site")
    for z in ZONES:
        zr = (min(p[0] for p in z["polygon_m"]), min(p[1] for p in z["polygon_m"]),
              max(p[0] for p in z["polygon_m"]), max(p[1] for p in z["polygon_m"]))
        if z.get("equipment_exclusion"):
            for r in rects:
                ov = C.rect_overlap_area(r, zr)
                eq("maint-excl", ov <= 1e-9, f"{iid} maintenance rect overlaps {z['zone_id']} by {ov:.3f}")
    # clear of other footprints
    for jid, fr in FP.items():
        if jid == iid:
            continue
        for r in rects:
            ov = C.rect_overlap_area(r, fr)
            eq("maint-clear", ov <= 1e-9, f"{iid} maintenance rect overlaps footprint {jid} by {ov:.3f}")

# 6. roads
road_rects = []
road_cls = {}
for rd in ROADS:
    pts = rd["pts"]; w = rd["width"]; hw = w / 2
    eq("road-width", w >= 4.0, f"{rd['id']} width {w} < 4")
    rrs = []
    for k in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[k], pts[k + 1]
        rrs.append((min(x0, x1) - hw, min(y0, y1) - hw, max(x0, x1) + hw, max(y0, y1) + hw))
    road_cls[rd["id"]] = rrs
    for r in rrs:
        eq("road-site", C.rect_contains_rect(SITE, r, 0.0), f"{rd['id']} paved {r} outside site")
        for z in ZONES:
            zr = (min(p[0] for p in z["polygon_m"]), min(p[1] for p in z["polygon_m"]),
                  max(p[0] for p in z["polygon_m"]), max(p[1] for p in z["polygon_m"]))
            if z.get("road_exclusion"):
                ov = C.rect_overlap_area(r, zr)
                eq("road-excl", ov <= 1e-9, f"{rd['id']} paved overlaps road-exclusion {z['zone_id']} by {ov:.3f}")
        for iid, fr in FP.items():
            ov = C.rect_overlap_area(r, fr)
            eq("road-clear", ov <= 1e-9, f"{rd['id']} paved overlaps footprint {iid} by {ov:.3f}")
    road_rects.extend(rrs)

# connectivity: build graph of road rects (touching/overlap)
def touch(a, b):
    return C.rect_distance(a, b) <= 1e-9

node_rects = []
for rd in ROADS:
    for r in road_cls[rd["id"]]:
        node_rects.append((rd["id"], r))
# union-find
parent = list(range(len(node_rects)))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for a in range(len(node_rects)):
    for b in range(a + 1, len(node_rects)):
        if touch(node_rects[a][1], node_rects[b][1]):
            union(a, b)
groups = {}
for a, (rid, r) in enumerate(node_rects):
    groups.setdefault(find(a), []).append((rid, r))
eq("road-net", len(groups) == 1, f"road network has {len(groups)} disconnected groups")

# entrance contained in network
ent = INTERFACES["ROAD-ENTRANCE"]["point_m"]
ent_in = any(C.rect_distance((ent[0], ent[1], ent[0], ent[1]), r) <= 1e-6 for _, r in node_rects)
eq("road-entrance", ent_in, "ROAD-ENTRANCE not contained in any paved road")

# road access
def min_dist_to_road(rect):
    return min(C.rect_distance(r, rect) for r in road_rects)

for inst in INSTANCES:
    iid = inst["id"]; m = cat[inst["model_id"]]
    mm = m["maintenance"]
    if mm.get("road_access_required"):
        d = min(min_dist_to_road(r) for r in ENV[iid])
        eq("road-access", d <= maint_req["road_access_buffer_m"] + 1e-9,
           f"{iid} road access distance {d:.3f} > {maint_req['road_access_buffer_m']}")
    if mm.get("crane_access_required"):
        d = min(min_dist_to_road(r) for r in ENV[iid])
        eq("crane-access", d <= maint_req["crane_access_buffer_m"] + 1e-9,
           f"{iid} crane access distance {d:.3f} > {maint_req['crane_access_buffer_m']}")

if viol:
    print(f"{len(viol)} VIOLATIONS")
    for v in viol:
        print(" -", v)
else:
    print("ALL GEOMETRY/SAFETY/MAINTENANCE/ROAD CHECKS PASS")

print(f"instances: {len(INSTANCES)}")
