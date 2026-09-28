import json, math, itertools
TOL = 1e-6
def load(p):
    with open(p) as fh: return json.load(fh)
PIPES = load("submission/deliverables/pipelines.json")
SROADS = load("submission/deliverables/site_and_roads.json")
EQ = load("submission/deliverables/equipment.json")

def sub(a,b): return (a[0]-b[0], a[1]-b[1])
def mul(a,k): return (a[0]*k, a[1]*k)
def cross(a,b): return a[0]*b[1]-a[1]*b[0]
def dot(a,b): return a[0]*b[0]+a[1]*b[1]
def dist(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])

def seg_int_point(p1,p2,p3,p4):
    d = sub(p2,p1); e = sub(p4,p3); den = cross(d,e)
    if abs(den) < 1e-15: return None
    t = cross(sub(p3,p1), e)/den; u = cross(sub(p3,p1), d)/den
    if -1e-9 <= t <= 1+1e-9 and -1e-9 <= u <= 1+1e-9:
        return (p1[0]+t*d[0], p1[1]+t*d[1])
    return None

segs = []
for p in PIPES:
    for s in p["segments"]:
        segs.append((p["pipeline_id"], p["segments"][0]["installation_level"], tuple(s["from_m"]), tuple(s["to_m"])))

# crossings between DIFFERENT pipelines at the same level, not at a shared endpoint
crossings = []
for i in range(len(segs)):
    pa, la, a1, a2 = segs[i]
    for j in range(i+1, len(segs)):
        pb, lb, b1, b2 = segs[j]
        if pa == pb or la != lb: continue
        pt = seg_int_point(a1,a2,b1,b2)
        if pt is None: continue
        # skip if the intersection is at a shared endpoint
        if (dist(pt,a1) < 1e-6 or dist(pt,a2) < 1e-6) and (dist(pt,b1) < 1e-6 or dist(pt,b2) < 1e-6):
            continue
        crossings.append((pa, pb, la, (round(pt[0],2), round(pt[1],2))))
print("same-level crossings between different pipelines:", len(crossings))
for c in crossings: print("   ", c)

# pipeline / road overlaps at grade
roads = {r["road_id"]: ([tuple(x) for x in r["centreline_m"]], r["width_m"]) for r in SROADS["roads"]}
def seg_road_hits(level, a, b):
    hits = []
    for rid, (cl, w) in roads.items():
        hw = w/2.0
        # paved rectangle for a single-segment centreline
        u = sub(cl[1], cl[0]); n1 = math.hypot(*u); u = (u[0]/n1, u[1]/n1)
        nrm = (-u[1], u[0])
        corners = [(cl[0][0]+nrm[0]*hw, cl[0][1]+nrm[1]*hw), (cl[1][0]+nrm[0]*hw, cl[1][1]+nrm[1]*hw),
                   (cl[1][0]-nrm[0]*hw, cl[1][1]-nrm[1]*hw), (cl[0][0]-nrm[0]*hw, cl[0][1]-nrm[1]*hw)]
        inside = lambda p: (min(c[0] for c in corners) < p[0] < max(c[0] for c in corners)
                            or min(c[1] for c in corners) < p[1] < max(c[1] for c in corners))
        pts = []
        for k in range(4):
            q = seg_int_point(a,b,corners[k],corners[(k+1)%4])
            if q is not None: pts.append(q)
        # midpoint test
        m = ((a[0]+b[0])/2,(a[1]+b[1])/2)
        inx = min(c[0] for c in corners) <= m[0] <= max(c[0] for c in corners)
        iny = min(c[1] for c in corners) <= m[1] <= max(c[1] for c in corners)
        if pts or (inx and iny):
            hits.append(rid)
    return hits

print("\ngas pipelines overlapping roads (model level):")
for pa, la, a, b in segs:
    if pa.startswith("P3"): continue
    h = seg_road_hits(la, a, b)
    if h: print("   ", pa, la, a, b, h)
print("\nburied (drain) pipelines overlapping roads:")
for pa, la, a, b in segs:
    if not pa.startswith("P3"): continue
    h = seg_road_hits(la, a, b)
    if h: print("   ", pa, la, a, b, h)
