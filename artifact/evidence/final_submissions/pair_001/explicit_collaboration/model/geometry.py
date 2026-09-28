"""Plan-view geometry helpers (pure python, no external libraries).

Conventions used throughout:
  * coordinates in metres in the site coordinate system;
  * a footprint is a rectangle described by its centre, its catalogue
    ``length``/``width`` and an ``orientation_deg`` rotation applied
    counter-clockwise about the centre;
  * local port offsets and maintenance sides rotate with the equipment.
"""
import math

TOL = 1e-6


# ---------------------------------------------------------------- vectors
def rot(pt, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def norm(a):
    return math.hypot(a[0], a[1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(a):
    n = norm(a)
    return (0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


# ------------------------------------------------------------- rectangles
def rect_polygon(centre, length, width, orientation_deg):
    """Closed CCW polygon (4 points) of a rotated rectangle."""
    hl, hw = length / 2.0, width / 2.0
    local = [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]
    return [add(centre, rot(p, orientation_deg)) for p in local]


def port_point(centre, orientation_deg, offset):
    return add(centre, rot(offset, orientation_deg))


def port_normal(offset, length, width, orientation_deg):
    """Outward unit normal of a port that lies on the rectangle boundary.

    Local offsets in the catalog sit on the rectangle edge (|x| == length/2
    or |y| == width/2).  A corner port is given the diagonal normal.
    """
    hl, hw = length / 2.0, width / 2.0
    nx = 0.0
    ny = 0.0
    if abs(abs(offset[0]) - hl) < 1e-9:
        nx = math.copysign(1.0, offset[0])
    if abs(abs(offset[1]) - hw) < 1e-9:
        ny = math.copysign(1.0, offset[1])
    n = rot((nx, ny), orientation_deg)
    return unit(n)


# --------------------------------------------------------------- polygons
def in_interior(pt, poly):
    """True when pt is strictly inside poly (boundary => False)."""
    n = len(poly)
    # boundary test
    for i in range(n):
        if point_seg_distance(pt, poly[i], poly[(i + 1) % n]) <= TOL:
            return False
    # winding / crossing test
    inside = False
    x, y = pt
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xin > x:
                inside = not inside
    return inside


def point_seg_distance(p, a, b):
    ab = sub(b, a)
    L2 = dot(ab, ab)
    if L2 == 0:
        return dist(p, a)
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / L2))
    proj = add(a, mul(ab, t))
    return dist(p, proj)


def _orient(a, b, c):
    v = cross(sub(b, a), sub(c, a))
    if abs(v) < 1e-12:
        return 0
    return 1 if v > 0 else -1


def _on_seg(a, b, p):
    return (min(a[0], b[0]) - TOL <= p[0] <= max(a[0], b[0]) + TOL and
            min(a[1], b[1]) - TOL <= p[1] <= max(a[1], b[1]) + TOL)


def seg_intersection_params(p, q, a, b):
    """Parameters t (on pq) of intersections between segment pq and ab."""
    out = []
    d1 = _orient(a, b, p)
    d2 = _orient(a, b, q)
    d3 = _orient(p, q, a)
    d4 = _orient(p, q, b)
    pq = sub(q, p)
    ab = sub(b, a)
    if d1 == 0 and _on_seg(a, b, p):
        out.append(0.0)
    if d2 == 0 and _on_seg(a, b, q):
        out.append(1.0)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 and d2 and d3 and d4:
        den = cross(pq, ab)
        if abs(den) > 1e-15:
            t = cross(sub(a, p), ab) / den
            if -TOL <= t <= 1 + TOL:
                out.append(min(1.0, max(0.0, t)))
    return out


def seg_enters_polygon_interior(p, q, poly):
    """True when segment pq has any part strictly inside a convex polygon."""
    if in_interior(p, poly) or in_interior(q, poly):
        return True
    ts = {0.0, 1.0}
    n = len(poly)
    for i in range(n):
        ts.update(seg_intersection_params(p, q, poly[i], poly[(i + 1) % n]))
    ts = sorted(ts)
    for t0, t1 in zip(ts, ts[1:]):
        if t1 - t0 <= 1e-9:
            continue
        mid = add(p, mul(sub(q, p), 0.5 * (t0 + t1)))
        if in_interior(mid, poly):
            return True
    return False


def seg_seg_distance(p1, p2, p3, p4):
    if seg_intersection_params(p1, p2, p3, p4):
        return 0.0
    d = min(point_seg_distance(p1, p3, p4), point_seg_distance(p2, p3, p4),
            point_seg_distance(p3, p1, p2), point_seg_distance(p4, p1, p2))
    return d


def polygon_distance(poly_a, poly_b):
    """Shortest boundary-to-boundary distance (0 if they touch/overlap)."""
    na, nb = len(poly_a), len(poly_b)
    best = float("inf")
    for i in range(na):
        for j in range(nb):
            best = min(best, seg_seg_distance(poly_a[i], poly_a[(i + 1) % na],
                                              poly_b[j], poly_b[(j + 1) % nb]))
    if any(in_interior(p, poly_b) for p in poly_a) or any(in_interior(p, poly_a) for p in poly_b):
        return 0.0
    return best


def _clip(subject, clipper):
    """Sutherland-Hodgman convex clip (clipper CCW)."""
    def inside(p, a, b):
        return cross(sub(b, a), sub(p, a)) >= -1e-12

    def inter(p, q, a, b):
        pq = sub(q, p)
        ab = sub(b, a)
        den = cross(pq, ab)
        if abs(den) < 1e-15:
            return q
        t = cross(sub(a, p), ab) / den
        return add(p, mul(pq, t))

    out = list(subject)
    n = len(clipper)
    # ensure clipper is CCW
    area2 = 0.0
    for i in range(n):
        x1, y1 = clipper[i]
        x2, y2 = clipper[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    clip = clipper if area2 > 0 else list(reversed(clipper))
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        if not out:
            return []
        new = []
        for k in range(len(out)):
            p = out[k - 1]
            q = out[k]
            if inside(q, a, b):
                if not inside(p, a, b):
                    new.append(inter(p, q, a, b))
                new.append(q)
            elif inside(p, a, b):
                new.append(inter(p, q, a, b))
        out = new
    return out


def polygon_area(poly):
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def polygon_overlap_area(poly_a, poly_b):
    if not poly_a or not poly_b:
        return 0.0
    inter = _clip(poly_a, poly_b)
    return polygon_area(inter) if len(inter) >= 3 else 0.0


def expand_polygon(pts, d):
    """Straight/mitered outward offset of a CCW convex polygon by distance d."""
    n = len(pts)
    # ensure CCW
    area2 = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                for i in range(n))
    if area2 < 0:
        pts = list(reversed(pts))
    out = []
    for i in range(n):
        p_prev = pts[(i - 1) % n]
        p = pts[i]
        p_next = pts[(i + 1) % n]
        e1 = unit(sub(p, p_prev))
        e2 = unit(sub(p_next, p))
        n1 = (e1[1], -e1[0])   # outward for CCW
        n2 = (e2[1], -e2[0])
        bis = unit(add(n1, n2))
        if norm(bis) < 1e-12:
            out.append(add(p, mul(n1, d)))
            continue
        cosang = dot(bis, n1)
        miter = d / max(cosang, 1e-6)
        if miter > 10 * d:      # limit miter spikes on sharp corners
            miter = 10 * d
        out.append(add(p, mul(bis, miter)))
    return out


def polyline_length(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def simplify(pts):
    """Remove collinear/duplicate intermediate points."""
    out = []
    for p in pts:
        if out and dist(out[-1], p) < 1e-9:
            continue
        out.append(p)
    changed = True
    while changed and len(out) > 2:
        changed = False
        for i in range(1, len(out) - 1):
            a, b, c = out[i - 1], out[i], out[i + 1]
            if abs(cross(sub(b, a), sub(c, b))) < 1e-9 and dot(sub(b, a), sub(c, b)) > 0:
                del out[i]
                changed = True
                break
    return out


def collinear_overlap(p1, p2, p3, p4):
    """Length of the shared collinear part of two segments (0 when not collinear)."""
    d1 = sub(p2, p1)
    d2 = sub(p4, p3)
    if abs(cross(d1, d2)) > 1e-9 * max(1.0, norm(d1) * norm(d2)):
        return 0.0
    if abs(cross(sub(p3, p1), d1)) > 1e-9 * max(1.0, norm(d1)):
        return 0.0
    u = unit(d1)
    def proj(p):
        return dot(sub(p, p1), u)
    a0, a1 = sorted((0.0, dot(d1, u)))
    b0, b1 = sorted((proj(p3), proj(p4)))
    lo, hi = max(a0, b0), min(a1, b1)
    return max(0.0, hi - lo)
