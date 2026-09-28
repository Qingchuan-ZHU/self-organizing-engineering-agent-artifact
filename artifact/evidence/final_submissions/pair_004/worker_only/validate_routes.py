"""Validate routed pipelines: site/exclusion/footprint clearance + overlap rules."""
import sys, math
sys.path.insert(0, "/workspace/project")
import ugs_core as C
from ugs_design import load, load_catalog, INSTANCES, footprint
import router, nets

cat = load_catalog()
site = load("site.json")
TOL = 1e-6

B = site["boundary_polygon_m"]
SITE = (min(p[0] for p in B), min(p[1] for p in B), max(p[0] for p in B), max(p[1] for p in B))
EXCL = []
for z in site["no_build_zones"]:
    if z.get("pipeline_exclusion"):
        xs = [p[0] for p in z["polygon_m"]]; ys = [p[1] for p in z["polygon_m"]]
        EXCL.append((min(xs), min(ys), max(xs), max(ys)))
FP = {i["id"]: footprint(i, cat) for i in INSTANCES}

res = router.route_all(nets.NETS)

viol = []
segs = []   # (net_id, level, p, q)
for nid, r in res.items():
    if r["status"] != "ok":
        viol.append(f"{nid} not routed: {r['status']}")
        continue
    pts = r["pts"]
    lvl = r["level"]
    for k in range(len(pts) - 1):
        p, q = pts[k], pts[k + 1]
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        if L <= TOL:
            viol.append(f"{nid} zero-length segment {p}->{q}")
            continue
        segs.append((nid, lvl, p, q, L))
        # site containment (axis aligned)
        if not (SITE[0] - TOL <= min(p[0], q[0]) and max(p[0], q[0]) <= SITE[2] + TOL and
                SITE[1] - TOL <= min(p[1], q[1]) and max(p[1], q[1]) <= SITE[3] + TOL):
            viol.append(f"{nid} segment {p}->{q} outside site")
        for zr in EXCL:
            if C.seg_intersects_rect_interior(p, q, zr):
                viol.append(f"{nid} segment {p}->{q} enters pipeline_exclusion {zr}")
        for iid, fr in FP.items():
            if C.seg_intersects_rect_interior(p, q, fr):
                viol.append(f"{nid} segment {p}->{q} crosses footprint {iid}")

# overlap between same-level segments
def overlap_len(a, b):
    (a1, a2), (b1, b2) = a, b
    return max(0.0, min(a1[1], b1[1]) - max(a1[0], b1[0]))

for i in range(len(segs)):
    for j in range(i + 1, len(segs)):
        n1, l1, p1, q1, L1 = segs[i]
        n2, l2, p2, q2, L2 = segs[j]
        if l1 != l2:
            continue
        h1 = abs(p1[1] - q1[1]) <= TOL
        h2 = abs(p2[1] - q2[1]) <= TOL
        v1 = abs(p1[0] - q1[0]) <= TOL
        v2 = abs(p2[0] - q2[0]) <= TOL
        if h1 and h2 and abs(p1[1] - p2[1]) <= TOL:
            xa = (min(p1[0], q1[0]), max(p1[0], q1[0]))
            xb = (min(p2[0], q2[0]), max(p2[0], q2[0]))
            ov = max(0.0, min(xa[1], xb[1]) - max(xa[0], xb[0]))
            if ov > TOL:
                viol.append(f"overlap {ov:.3f} m level={l1} between {n1} and {n2}")
        if v1 and v2 and abs(p1[0] - p2[0]) <= TOL:
            ya = (min(p1[1], q1[1]), max(p1[1], q1[1]))
            yb = (min(p2[1], q2[1]), max(p2[1], q2[1]))
            ov = max(0.0, min(ya[1], yb[1]) - max(ya[0], yb[0]))
            if ov > TOL:
                viol.append(f"overlap {ov:.3f} m level={l1} between {n1} and {n2}")

# endpoint checks against nets definition
for n in nets.NETS:
    r = res[n["id"]]
    if r["status"] != "ok":
        continue
    pts = r["pts"]
    d0 = math.hypot(pts[0][0] - n["start"][0], pts[0][1] - n["start"][1])
    d1 = math.hypot(pts[-1][0] - n["end"][0], pts[-1][1] - n["end"][1])
    if d0 > TOL or d1 > TOL:
        viol.append(f"{n['id']} endpoints off by {d0:.3f}/{d1:.3f}")

tot = sum(s[4] for s in segs)
print(f"segments: {len(segs)}  total length: {tot:.1f} m")
if viol:
    print(f"{len(viol)} VIOLATIONS")
    for v in viol[:80]:
        print(" -", v)
else:
    print("ALL ROUTE CHECKS PASS")
