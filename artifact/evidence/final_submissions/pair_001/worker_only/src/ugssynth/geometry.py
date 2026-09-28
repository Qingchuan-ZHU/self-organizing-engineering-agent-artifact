"""Plan-view geometry helpers (rotated rectangles, polygons, distances)."""
from __future__ import annotations

import math

TOL = 1e-6


def rotate(px: float, py: float, cx: float, cy: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = px - cx, py - cy
    return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca


def rect_corners(cx, cy, length, width, deg):
    hl, hw = length / 2.0, width / 2.0
    local = [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]
    return [rotate(cx + lx, cy + ly, cx, cy, deg) for lx, ly in local]


def polygon_area(poly) -> float:
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def is_ccw(poly) -> bool:
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a > 0


def point_in_convex(p, poly) -> bool:
    n = len(poly)
    ccw = is_ccw(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)
        if ccw and cross < -TOL:
            return False
        if (not ccw) and cross > TOL:
            return False
    return True


def point_in_convex_strict(p, poly) -> bool:
    n = len(poly)
    ccw = is_ccw(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)
        if ccw and cross <= TOL:
            return False
        if (not ccw) and cross >= -TOL:
            return False
    return True


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def segments_intersect(a, b, c, d) -> bool:
    d1 = _cross(c, d, a)
    d2 = _cross(c, d, b)
    d3 = _cross(a, b, c)
    d4 = _cross(a, b, d)
    return ((d1 > TOL and d2 < -TOL) or (d1 < -TOL and d2 > TOL)) and \
           ((d3 > TOL and d4 < -TOL) or (d3 < -TOL and d4 > TOL))


def _proper_cross(p, q, a, b) -> bool:
    d1 = _cross(a, b, p)
    d2 = _cross(a, b, q)
    d3 = _cross(p, q, a)
    d4 = _cross(p, q, b)
    return ((d1 > TOL) != (d2 > TOL)) and ((d3 > TOL) != (d4 > TOL)) and \
        min(abs(d1), abs(d2)) > TOL and min(abs(d3), abs(d4)) > TOL


def _pt_seg(p, s1, s2):
    vx, vy = s2[0] - s1[0], s2[1] - s1[1]
    wx, wy = p[0] - s1[0], p[1] - s1[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(p[0] - s1[0], p[1] - s1[1])
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / L2))
    return math.hypot(p[0] - (s1[0] + t * vx), p[1] - (s1[1] + t * vy))


def point_segment_distance(p, a, b) -> float:
    return _pt_seg(p, a, b)


def _seg_seg_distance(a, b, c, d):
    if segments_intersect(a, b, c, d):
        return 0.0
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d), _pt_seg(c, a, b), _pt_seg(d, a, b))


def polygon_distance(poly_a, poly_b) -> float:
    n, m = len(poly_a), len(poly_b)
    for i in range(n):
        a, b = poly_a[i], poly_a[(i + 1) % n]
        for j in range(m):
            c, d = poly_b[j], poly_b[(j + 1) % m]
            if segments_intersect(a, b, c, d):
                return 0.0
    if point_in_convex(poly_a[0], poly_b) or point_in_convex(poly_b[0], poly_a):
        return 0.0
    best = float("inf")
    for i in range(n):
        a, b = poly_a[i], poly_a[(i + 1) % n]
        for j in range(m):
            c, d = poly_b[j], poly_b[(j + 1) % m]
            best = min(best, _seg_seg_distance(a, b, c, d))
    return best


def _collinear_overlap_len(a, b, c, d) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return 0.0
    sc = math.sqrt(L2)
    if abs(_cross(a, b, c)) > TOL * max(1.0, sc) or abs(_cross(a, b, d)) > TOL * max(1.0, sc):
        return 0.0

    def t(p):
        return ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2
    tc, td = sorted((t(c), t(d)))
    return max(0.0, min(1.0, td) - max(0.0, tc)) * sc


def polygons_overlap_positive_area(poly_a, poly_b) -> bool:
    n, m = len(poly_a), len(poly_b)
    for i in range(n):
        a, b = poly_a[i], poly_a[(i + 1) % n]
        for j in range(m):
            c, d = poly_b[j], poly_b[(j + 1) % m]
            if segments_intersect(a, b, c, d):
                return True
    if point_in_convex_strict(poly_a[0], poly_b) or point_in_convex_strict(poly_b[0], poly_a):
        return True
    for i in range(n):
        a, b = poly_a[i], poly_a[(i + 1) % n]
        for j in range(m):
            c, d = poly_b[j], poly_b[(j + 1) % m]
            if _collinear_overlap_len(a, b, c, d) > TOL:
                return True
    return False


def segment_enters_convex_interior(p, q, poly) -> bool:
    if point_in_convex_strict(p, poly) or point_in_convex_strict(q, poly):
        return True
    n = len(poly)
    for i in range(n):
        if _proper_cross(p, q, poly[i], poly[(i + 1) % n]):
            return True
    return False


def segment_inside_convex(p, q, poly) -> bool:
    if not point_in_convex(p, poly) or not point_in_convex(q, poly):
        return False
    n = len(poly)
    for i in range(n):
        if _proper_cross(p, q, poly[i], poly[(i + 1) % n]):
            return False
    return True


def min_segment_to_polygon_distance(p, q, poly) -> float:
    best = float("inf")
    n = len(poly)
    for i in range(n):
        best = min(best, _seg_seg_distance(p, q, poly[i], poly[(i + 1) % n]))
    return best


def clip_convex(subject, clip):
    """Sutherland-Hodgman intersection of two convex polygons (CCW)."""
    output = list(subject)

    def inside(p, a, b):
        return _cross(a, b, p) >= -TOL

    def line_intersect(p, q, a, b):
        # intersection of segment pq with infinite line ab
        x1, y1 = p
        x2, y2 = q
        x3, y3 = a
        x4, y4 = b
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-15:
            return q
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
        return (px, py)

    if not is_ccw(clip):
        clip = list(reversed(clip))
    m = len(clip)
    for i in range(m):
        a, b = clip[i], clip[(i + 1) % m]
        input_list = output
        output = []
        if not input_list:
            break
        s = input_list[-1]
        for e in input_list:
            if inside(e, a, b):
                if not inside(s, a, b):
                    output.append(line_intersect(s, e, a, b))
                output.append(e)
            elif inside(s, a, b):
                output.append(line_intersect(s, e, a, b))
            s = e
    return output


def intersection_area(poly_a, poly_b) -> float:
    inter = clip_convex(poly_a, poly_b)
    if len(inter) < 3:
        return 0.0
    return polygon_area(inter)


def offset_rect_polygon(cx, cy, length, width, deg, d):
    return rect_corners(cx, cy, length + 2 * d, width + 2 * d, deg)


def removal_envelope_rect(cx, cy, length, width, deg, side, extent, transverse):
    hl, hw = length / 2.0, width / 2.0
    if side == "east":
        rect_local = [(hl, -transverse / 2.0), (hl + extent, -transverse / 2.0),
                      (hl + extent, transverse / 2.0), (hl, transverse / 2.0)]
    elif side == "west":
        rect_local = [(-hl - extent, -transverse / 2.0), (-hl, -transverse / 2.0),
                      (-hl, transverse / 2.0), (-hl - extent, transverse / 2.0)]
    elif side == "north":
        rect_local = [(-extent / 2.0, hw), (extent / 2.0, hw),
                      (extent / 2.0, hw + transverse), (-extent / 2.0, hw + transverse)]
    else:
        rect_local = [(-extent / 2.0, -hw - transverse), (extent / 2.0, -hw - transverse),
                      (extent / 2.0, -hw), (-extent / 2.0, -hw)]
    return [rotate(cx + lx, cy + ly, cx, cy, deg) for lx, ly in rect_local]


def polyline_length(points) -> float:
    return sum(math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
               for i in range(len(points) - 1))


def same_level_overlap_length(seg_a, seg_b) -> float:
    """Positive-length collinear overlap of two segments (same level check)."""
    a, b = seg_a
    c, d = seg_b
    # project onto ab direction
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return 0.0
    sc = math.sqrt(L2)
    # require c,d collinear with a,b
    if abs(_cross(a, b, c)) > 1e-6 * max(1.0, sc) or abs(_cross(a, b, d)) > 1e-6 * max(1.0, sc):
        return 0.0

    def t(p):
        return ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2
    tc, td = sorted((t(c), t(d)))
    lo = max(0.0, tc)
    hi = min(1.0, td)
    if hi <= lo:
        return 0.0
    return (hi - lo) * sc
