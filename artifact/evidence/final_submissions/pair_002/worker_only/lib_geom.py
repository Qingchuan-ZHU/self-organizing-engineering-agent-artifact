"""Pure-python geometry utilities for the UGS-SYNTH-D01 design.

All coordinates in metres. Footprints are rotated rectangles (convex).
"""
import math

TOL_GEOM = 1e-6


def rotate(px, py, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (px * c - py * s, px * s + py * c)


def rect_polygon(cx, cy, length, width, orient_deg):
    hl, hw = length / 2.0, width / 2.0
    pts = [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]
    return [(cx + rx, cy + ry) for (rx, ry) in (rotate(px, py, orient_deg) for (px, py) in pts)]


def rect_polygon_local(cx, cy, cx_local, cy_local, length, width, orient_deg):
    hl, hw = length / 2.0, width / 2.0
    pts = [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]
    out = []
    for (px, py) in pts:
        lx, ly = px + cx_local, py + cy_local
        rx, ry = rotate(lx, ly, orient_deg)
        out.append((cx + rx, cy + ry))
    return out


def port_position(eq, offset_m):
    rx, ry = rotate(offset_m[0], offset_m[1], eq["orient"])
    return (eq["x"] + rx, eq["y"] + ry)


def poly_area(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _edges(poly):
    n = len(poly)
    return [(poly[i], poly[(i + 1) % n]) for i in range(n)]


def seg_point_dist(a, b, p):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def point_in_poly(poly, p):
    n = len(poly)
    sign = 0
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        cr = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
        if abs(cr) < 1e-9:
            continue
        s = 1 if cr > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def convex_overlap_area(P, Q, tol=1e-9):
    def clip(subject, clipper):
        out = subject
        n = len(clipper)
        for i in range(n):
            A = clipper[i]
            B = clipper[(i + 1) % n]
            ex, ey = B[0] - A[0], B[1] - A[1]
            inp = out
            out = []
            if not inp:
                break
            for j in range(len(inp)):
                C = inp[j]
                Dd = inp[(j + 1) % len(inp)]

                def side(Pt):
                    return ex * (Pt[1] - A[1]) - ey * (Pt[0] - A[0])

                sc, sd = side(C), side(Dd)
                if sc >= -tol:
                    out.append(C)
                if (sc > tol and sd < -tol) or (sc < -tol and sd > tol):
                    t = sc / (sc - sd)
                    out.append((C[0] + t * (Dd[0] - C[0]), C[1] + t * (Dd[1] - C[1])))
        return out

    def ccw(poly):
        a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                for i in range(len(poly)))
        return poly if a > 0 else list(reversed(poly))

    Pc, Qc = ccw(P), ccw(Q)
    inter = clip(Pc, Qc)
    if len(inter) < 3:
        return 0.0
    return poly_area(inter)


def poly_distance(P, Q):
    if convex_overlap_area(P, Q) > 1e-9:
        return 0.0
    best = float("inf")
    for p in P:
        for (a, b) in _edges(Q):
            best = min(best, seg_point_dist(a, b, p))
    for p in Q:
        for (a, b) in _edges(P):
            best = min(best, seg_point_dist(a, b, p))
    return best


def poly_inside_poly(inner, outer, tol=1e-6):
    def on_seg(a, b, p):
        return seg_point_dist(a, b, p) <= tol
    for p in inner:
        if point_in_poly(outer, p):
            continue
        if any(on_seg(a, b, p) for (a, b) in _edges(outer)):
            continue
        return False
    return True
