"""Orthogonal pipeline router on a 0.25 m grid.

A* shortest path avoiding equipment-footprint interiors and pipeline-exclusion
zone interiors.  Reuse of a grid EDGE by a later net is heavily penalised, which
prevents collinear same-level overlap (crossings share only a node, not an edge).
"""
import heapq, math
import ugs_core as C
from ugs_design import load, load_catalog, INSTANCES, footprint

CS = 0.25
SITE_W, SITE_H = 700.0, 450.0
NX = int(round(SITE_W / CS)) + 1   # 2801
NY = int(round(SITE_H / CS)) + 1   # 1801

cat = load_catalog()
site = load("site.json")


def _ix(x):
    return int(round(x / CS))


def _w(i):
    return i * CS


def build_blocked():
    blocked = bytearray(NX * NY)

    def block_rect(x0, y0, x1, y1):
        i0 = max(0, math.floor(x0 / CS) + 1) if (x0 / CS) == math.floor(x0 / CS) else math.ceil(x0 / CS)
        # block nodes strictly inside
        i0 = math.floor(min(x0, x1) / CS) + 1
        i1 = math.ceil(max(x0, x1) / CS) - 1
        j0 = math.floor(min(y0, y1) / CS) + 1
        j1 = math.ceil(max(y0, y1) / CS) - 1
        for j in range(max(0, j0), min(NY - 1, j1) + 1):
            base = j * NX
            for i in range(max(0, i0), min(NX - 1, i1) + 1):
                blocked[base + i] = 1

    for inst in INSTANCES:
        x0, y0, x1, y1 = footprint(inst, cat)
        block_rect(x0, y0, x1, y1)
    for z in site["no_build_zones"]:
        if z.get("pipeline_exclusion"):
            xs = [p[0] for p in z["polygon_m"]]; ys = [p[1] for p in z["polygon_m"]]
            block_rect(min(xs), min(ys), max(xs), max(ys))
    return blocked


BLOCKED = build_blocked()


def node_of(x, y):
    return _ix(x), _ix(y)


def route(start, goal, penal, blocked=BLOCKED, weight=2000):
    sx, sy = node_of(*start)
    gx, gy = node_of(*goal)

    def free(i, j):
        return 0 <= i < NX and 0 <= j < NY and not blocked[j * NX + i]

    if not free(sx, sy):
        # nudge outward along the smaller displacement direction
        return None, "start blocked"
    if not free(gx, gy):
        return None, "goal blocked"

    start_n = (sx, sy)
    goal_n = (gx, gy)
    h = lambda n: abs(n[0] - gx) + abs(n[1] - gy)
    gdist = {start_n: 0.0}
    prev = {}
    pq = [(h(start_n), 0.0, start_n)]
    closed = set()
    while pq:
        f, g, n = heapq.heappop(pq)
        if n in closed:
            continue
        closed.add(n)
        if n == goal_n:
            # reconstruct
            path = [n]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            path.reverse()
            return path, "ok"
        i, j = n
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if not free(ni, nj):
                continue
            m = (ni, nj)
            if m in closed:
                continue
            u, v = (min(n, m), max(n, m))
            w = weight * penal.get((u, v), 0)
            ng = g + 1.0 + w
            if ng < gdist.get(m, float("inf")):
                gdist[m] = ng
                prev[m] = n
                heapq.heappush(pq, (ng + h(m), ng, m))
    return None, "unroutable"


def simplify(path):
    pts = [(_w(i), _w(j)) for (i, j) in path]
    # merge collinear consecutive
    out = [pts[0]]
    for p in pts[1:]:
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (a[0] == b[0] == p[0]) or (a[1] == b[1] == p[1]):
                out[-1] = p
                continue
        out.append(p)
    return out


def route_all(nets):
    penal = {}
    results = {}
    for net in nets:
        path, status = route(net["start"], net["end"], penal)
        if path is None:
            results[net["id"]] = dict(status=status, pts=None, level=None)
            continue
        for k in range(len(path) - 1):
            u, v = path[k], path[k + 1]
            key = (min(u, v), max(u, v))
            penal[key] = penal.get(key, 0) + 1
        results[net["id"]] = dict(status="ok", pts=simplify(path),
                                  level=net.get("level", "ground"))
    return results
