"""UGS-SYNTH-D01 library.

Deterministic implementation of the published v1.1 calculation basis, geometry basis
and network semantics of brief/.  Everything is in SI-derived units used by the brief:
metres, MPa, degC, kg/s, MW, MWh, MBCU.

This module contains no design decisions; the proposed design lives in ugs_design.py.
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_brief():
    cands = [os.path.join(HERE, "..", "brief"), os.path.join(HERE, "brief"),
             os.path.join(HERE, "..", "..", "brief"), os.path.join(os.getcwd(), "brief"),
             os.path.join(os.getcwd(), "..", "brief")]
    for c in cands:
        if os.path.isdir(c) and os.path.isfile(os.path.join(c, "case.json")):
            return os.path.abspath(c)
    raise RuntimeError("brief/ directory not found; looked in %s" % cands)


BRIEF = _find_brief()

TOL = {
    "mass_flow": 1e-5,
    "pressure": 1e-5,
    "temperature": 1e-4,
    "geometry": 1e-6,
    "overlap": 1e-6,
    "velocity": 1e-6,
    "power": 1e-6,
    "water": 1e-5,
    "free_liquid": 1e-9,
    "lcc": 1e-8,
}

RU = 8.314462618


# --------------------------------------------------------------------------------------
# brief loading
# --------------------------------------------------------------------------------------
def _load(rel):
    with open(os.path.join(BRIEF, rel), "r") as fh:
        return json.load(fh)


def load_brief():
    b = {}
    models = {}
    for name in (
        "compressors",
        "dehydration",
        "drains",
        "filters",
        "headers",
        "metering_regulation",
        "separators",
        "thermal_equipment",
    ):
        for m in _load("equipment_catalog/%s.json" % name)["models"]:
            models[m["model_id"]] = m
    b["models"] = models
    pc = _load("piping_catalog.json")
    b["piping"] = pc
    b["classes"] = {c["class_id"]: c for c in pc["classes"]}
    b["dn"] = {d["nominal_diameter"]: d for d in pc["diameters"]}
    b["routing_levels"] = pc["routing_levels"]
    b["max_gas_v"] = pc["maximum_gas_velocity_m_s"]
    b["max_liquid_v"] = pc["maximum_liquid_drain_velocity_m_s"]
    b["site"] = _load("site.json")
    b["scenarios"] = _load("operating_scenarios.json")["scenarios"]
    b["gas"] = _load("gas_properties.json")
    b["safety"] = _load("safety_requirements.json")["minimum_separation_m"]
    b["maint"] = _load("maintenance_requirements.json")
    b["econ"] = _load("economic_assumptions.json")
    b["req"] = _load("project_requirements.json")
    b["wg"] = _load("well_group_interfaces.json")
    return b


# --------------------------------------------------------------------------------------
# gas properties
# --------------------------------------------------------------------------------------
def Z_of(P, T_c, gas):
    z = 0.90 + 0.08 * P / (P + 10.0) + 0.00015 * (T_c + 273.15 - 293.15)
    return min(max(z, gas["compressibility_proxy"]["minimum"]), gas["compressibility_proxy"]["maximum"])


def mu_of(P, T_c, gas):
    mu = 1.05e-5 * ((T_c + 273.15) / 293.15) ** 0.70 * (1.0 + 0.002 * P)
    return min(max(mu, gas["viscosity_proxy"]["minimum"]), gas["viscosity_proxy"]["maximum"])


def rho_of(P, T_c, gas):
    Pc = max(P, 1e-6)
    return Pc * 1e6 * gas["molecular_weight_kg_mol"] / (Z_of(Pc, T_c, gas) * RU * (T_c + 273.15))


# --------------------------------------------------------------------------------------
# pipelines
# --------------------------------------------------------------------------------------
def pipe_outlet_state(D, eps, L, m_dot, P_in, T_c, gas, max_iter=8):
    """Fixed-point pressure-loss convention of engineering_calculation_basis.md."""
    P_out = P_in
    iters = 0
    converged = False
    while iters < max_iter:
        P_mean = (P_in + P_out) / 2.0
        rho = rho_of(P_mean, T_c, gas)
        mu = mu_of(P_mean, T_c, gas)
        A = math.pi * D * D / 4.0
        v = m_dot / (rho * A)
        Re = rho * v * D / mu
        if Re < 2300.0:
            f = 64.0 / Re if Re > 0 else 0.0
        else:
            arg = eps / (3.7 * D) + 5.74 / Re ** 0.9
            f = 0.25 / (math.log10(arg) ** 2)
        dP = f * (L / D) * rho * v * v / 2.0 / 1e6
        new_P = max(1e-6, P_in - dP)
        iters += 1
        if abs(new_P - P_out) < 1e-5:
            P_out = new_P
            converged = True
            break
        P_out = new_P
    # final states at the converged mean pressure
    P_mean = (P_in + P_out) / 2.0
    rho = rho_of(P_mean, T_c, gas)
    mu = mu_of(P_mean, T_c, gas)
    A = math.pi * D * D / 4.0
    v = m_dot / (rho * A)
    Re = rho * v * D / mu
    if Re < 2300.0:
        f = 64.0 / Re if Re > 0 else 0.0
    else:
        arg = eps / (3.7 * D) + 5.74 / Re ** 0.9
        f = 0.25 / (math.log10(arg) ** 2)
    dP = f * (L / D) * rho * v * v / 2.0 / 1e6
    return {
        "P_out": P_out,
        "dP": dP,
        "v": v,
        "Re": Re,
        "f": f,
        "rho": rho,
        "mu": mu,
        "converged": converged,
        "iters": iters,
    }


# --------------------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------------------
def rot(p, ang_deg):
    a = math.radians(ang_deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def rect_poly(cx, cy, L, W, orient):
    pts = [(-L / 2.0, -W / 2.0), (L / 2.0, -W / 2.0), (L / 2.0, W / 2.0), (-L / 2.0, W / 2.0)]
    out = []
    for p in pts:
        r = rot(p, orient)
        out.append((cx + r[0], cy + r[1]))
    return out


def to_local(p, cx, cy, orient):
    """global -> local (rotate by -orient about centre)."""
    return rot((p[0] - cx, p[1] - cy), -orient)


def seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def poly_len(pts):
    return sum(seg_len(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def poly_area(P):
    s = 0.0
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]
        x2, y2 = P[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def seg_seg_dist(p1, p2, q1, q2):
    """Minimum distance between two closed segments (0 if they intersect)."""
    def d_pt_seg(p, a, b):
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 <= 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / L2
        t = min(1.0, max(0.0, t))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    d1 = _cross(p1, p2, q1)
    d2 = _cross(p1, p2, q2)
    d3 = _cross(q1, q2, p1)
    d4 = _cross(q1, q2, p2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(
        d_pt_seg(p1, q1, q2),
        d_pt_seg(p2, q1, q2),
        d_pt_seg(q1, p1, p2),
        d_pt_seg(q2, p1, p2),
    )


def poly_dist(A, B):
    """Minimum boundary-to-boundary distance between two polygons (0 if touching/overlapping)."""
    best = float("inf")
    for i in range(len(A)):
        a1, a2 = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            b1, b2 = B[j], B[(j + 1) % len(B)]
            best = min(best, seg_seg_dist(a1, a2, b1, b2))
    return best


def clip_convex(subject, clipper):
    """Sutherland-Hodgman convex clip of subject polygon by convex clipper polygon."""
    def inside(p, a, b):
        return _cross(a, b, p) >= -1e-12

    out = list(subject)
    n = len(clipper)
    for i in range(n):
        a = clipper[i]
        b = clipper[(i + 1) % n]
        inp = out
        out = []
        if not inp:
            break
        for k in range(len(inp)):
            cur = inp[k]
            prv = inp[k - 1]
            cur_in = inside(cur, a, b)
            prv_in = inside(prv, a, b)
            if cur_in:
                if not prv_in:
                    out.append(line_isect(prv, cur, a, b))
                out.append(cur)
            elif prv_in:
                out.append(line_isect(prv, cur, a, b))
    return out


def line_isect(p, q, a, b):
    d1 = (q[0] - p[0], q[1] - p[1])
    d2 = (b[0] - a[0], b[1] - a[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-15:
        return p
    t = ((a[0] - p[0]) * d2[1] - (a[1] - p[1]) * d2[0]) / den
    return (p[0] + t * d1[0], p[1] + t * d1[1])


def poly_overlap_area(A, B):
    inter = clip_convex(A, B)
    if len(inter) < 3:
        return 0.0
    return poly_area(inter)


def _ccw(P):
    s = 0.0
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]
        x2, y2 = P[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return P if s >= 0 else P[::-1]


def point_in_poly_strict(p, P, tol=1e-9):
    P = _ccw(P)
    n = len(P)
    for i in range(n):
        if _cross(P[i], P[(i + 1) % n], p) <= tol:
            return False
    return True


def poly_inside_poly(inner, outer):
    """True when no point of `inner` lies outside `outer` (boundary contact allowed)."""
    outer = _ccw(outer)
    for p in inner:
        if not point_in_or_on(p, outer):
            return False
    # check midpoints of inner edges too
    for i in range(len(inner)):
        a, b = inner[i], inner[(i + 1) % len(inner)]
        m = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if not point_in_or_on(m, outer):
            return False
    return True


def point_in_or_on(p, P, tol=1e-6):
    P = _ccw(P)
    n = len(P)
    for i in range(n):
        if _cross(P[i], P[(i + 1) % n], p) < -tol:
            return False
    return True


def rect_from_center_local(cx, cy, orient, u0, u1, v0, v1):
    pts = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    out = []
    for p in pts:
        r = rot(p, orient)
        out.append((cx + r[0], cy + r[1]))
    return out


def footprint_poly(inst, model):
    return rect_poly(inst["x"], inst["y"], model["footprint_m"]["length"], model["footprint_m"]["width"], inst.get("orientation_deg", 0))


def expanded_poly(inst, model, d):
    return rect_poly(
        inst["x"],
        inst["y"],
        model["footprint_m"]["length"] + 2 * d,
        model["footprint_m"]["width"] + 2 * d,
        inst.get("orientation_deg", 0),
    )


def removal_poly(inst, model):
    """Rectangular removal envelope adjoining the footprint on maintenance.side."""
    md = model.get("maintenance", {})
    if not md.get("heavy_maintenance"):
        return None
    L = model["footprint_m"]["length"]
    W = model["footprint_m"]["width"]
    ext, wid = md["removal_envelope_m"]
    side = md["side"]
    if side == "east":
        u0, u1, v0, v1 = L / 2.0, L / 2.0 + ext, -wid / 2.0, wid / 2.0
    elif side == "west":
        u0, u1, v0, v1 = -L / 2.0 - ext, -L / 2.0, -wid / 2.0, wid / 2.0
    elif side == "north":
        u0, u1, v0, v1 = -wid / 2.0, wid / 2.0, W / 2.0, W / 2.0 + ext
    elif side == "south":
        u0, u1, v0, v1 = -wid / 2.0, wid / 2.0, -W / 2.0 - ext, -W / 2.0
    else:
        raise ValueError("bad side %s" % side)
    return rect_from_center_local(inst["x"], inst["y"], inst.get("orientation_deg", 0), u0, u1, v0, v1)


def union_area_same_frame(rectA, rectB):
    """Area of union of two convex polygons (generic, via clipped triangulation-free
    decomposition: A + B - A^B using polygon clipping)."""
    return poly_area(rectA) + poly_area(rectB) - poly_overlap_area(rectA, rectB)


def port_xy(inst, model, port_id):
    for p in model["ports"]:
        if p["id"] == port_id:
            r = rot(p["offset_m"], inst.get("orientation_deg", 0))
            return (inst["x"] + r[0], inst["y"] + r[1])
    raise KeyError(port_id)


def seg_in_poly_interior(p, q, P):
    """True if segment p-q passes through the strict interior of convex polygon P."""
    # generic: clip segment against polygon using convex half-plane clipping
    n = len(P)
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for i in range(n):
        a = P[i]
        b = P[(i + 1) % n]
        nx, ny = (b[1] - a[1]), -(b[0] - a[0])  # outward-ish for CCW polygon
        # polygon built CCW -> interior is left of each edge (cross >= 0)
        ex, ey = b[0] - a[0], b[1] - a[1]
        # f(t) = cross(edge, point - a) >= ... compute
        f0 = ex * (p[1] - a[1]) - ey * (p[0] - a[0])
        f1 = ex * ((p[1] + dy) - a[1]) - ey * ((p[0] + dx) - a[0])
        # interior is f > 0
        if abs(f1 - f0) < 1e-15:
            if f0 <= 0:
                return False
            continue
        t = -f0 / (f1 - f0)
        if f1 - f0 > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t1 < t0:
            return False
    if t1 - t0 <= 1e-9:
        return False
    mid = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
    # only positive-length interior portion counts; test a point strictly inside
    tm = (t0 + t1) / 2.0
    pt = (p[0] + tm * dx, p[1] + tm * dy)
    return point_in_poly_strict(pt, P, 1e-9)


def collinear_overlap_len(p1, p2, q1, q2, tol=1e-6):
    """Positive-length overlap of two collinear segments (0 otherwise)."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    L1 = math.hypot(*d1)
    if L1 < tol:
        return 0.0
    u = (d1[0] / L1, d1[1] / L1)
    for pt in (q1, q2):
        cross = abs((pt[0] - p1[0]) * u[1] - (pt[1] - p1[1]) * u[0])
        if cross > tol:
            return 0.0
    def proj(pt):
        return (pt[0] - p1[0]) * u[0] + (pt[1] - p1[1]) * u[1]
    a0, a1 = 0.0, L1
    b0, b1 = proj(q1), proj(q2)
    lo = max(min(a0, a1), min(b0, b1))
    hi = min(max(a0, a1), max(b0, b1))
    return max(0.0, hi - lo) if hi - lo > tol else 0.0


def road_paved_rectangles(road):
    """List of rectangles (4-point polygons) approximating the swept paved area."""
    w = road["width_m"]
    rects = []
    pts = road["centerline_m"]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        nx, ny = -dy / L * w / 2.0, dx / L * w / 2.0
        rects.append([(a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), (b[0] + nx, b[1] + ny), (a[0] + nx, a[1] + ny)])
    return rects


def rect_rect_touch(A, B, tol=1e-9):
    """True when two convex polygons touch or overlap."""
    return poly_overlap_area(A, B) > tol or poly_dist(A, B) <= 1e-9


def poly_poly_min_dist(A, B):
    return poly_dist(A, B)


# --------------------------------------------------------------------------------------
# economics
# --------------------------------------------------------------------------------------
def pvf(econ):
    i = econ["discount_rate"]
    N = econ["project_life_years"]
    if abs(i) < 1e-12:
        return float(N)
    return (1.0 - (1.0 + i) ** (-N)) / i
