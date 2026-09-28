"""UGS-SYNTH-D01 v1.1 - deterministic calculation-basis implementation.

This module implements the public v1.1 engineering calculation and geometry
basis of the case:

  * gas property proxies (Z, viscosity, density)
  * pipe hydraulics with the published fixed-point convention
  * compressor / regulator / cooler / heater / dehydration / header models
  * polygon geometry for footprints, maintenance envelopes, zones and routes
  * lifecycle cost (LCC) arithmetic

Every formula that appears here is taken from
``brief/engineering_calculation_basis.md`` and ``brief/engineering_geometry_basis.md``.
Units are the published ones: MPa, degC, kg/s, MW, MWh, m, MBCU.

Nothing in this module is project specific: it is a reusable implementation of
the published rules and it is used both by the design builder and by the
independent verification pass.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# ----------------------------------------------------------------------------
# constants published by the case
# ----------------------------------------------------------------------------

R_UNIVERSAL = 8.314462618

# numerical conventions (engineering_calculation_basis.md, "Numerical conventions")
TOL_MASS_FLOW_KG_S = 1e-5
TOL_PRESSURE_MPA = 1e-5
TOL_TEMPERATURE_C = 1e-4
TOL_GEOMETRY_M = 1e-6
TOL_OVERLAP_M = 1e-6
TOL_VELOCITY_M_S = 1e-6
TOL_POWER_MW = 1e-6
TOL_WATER_MG_SM3 = 1e-5
TOL_LIQUID_LOADING = 1e-9
TOL_LCC_MBCU = 1e-8

MIN_PRESSURE_MPA = 1e-6

# hydraulic convergence convention
HYDRAULIC_MAX_UPDATES = 8
HYDRAULIC_CONVERGENCE_MPA = 1e-5


class CaseData:
    """Container for the published case data files."""

    def __init__(self, brief_dir: Path):
        self.brief_dir = Path(brief_dir)
        self.case = self._json("case.json")
        self.project_requirements = self._json("project_requirements.json")
        self.economic_assumptions = self._json("economic_assumptions.json")
        self.gas_properties = self._json("gas_properties.json")
        self.operating_scenarios = self._json("operating_scenarios.json")
        self.piping_catalog = self._json("piping_catalog.json")
        self.safety_requirements = self._json("safety_requirements.json")
        self.maintenance_requirements = self._json("maintenance_requirements.json")
        self.site = self._json("site.json")
        self.well_group_interfaces = self._json("well_group_interfaces.json")
        self.final_delivery_contract = self._json("final_delivery_contract.json")

        self.models = {}
        cat_dir = self.brief_dir / "equipment_catalog"
        for path in sorted(cat_dir.glob("*.json")):
            data = json.loads(path.read_text())
            for model in data["models"]:
                key = model["model_id"]
                assert key not in self.models, f"duplicate model id {key}"
                self.models[key] = model

        self.scenarios = {s["scenario_id"]: s for s in self.operating_scenarios["scenarios"]}
        self.diameters = {d["nominal_diameter"]: d for d in self.piping_catalog["diameters"]}
        self.pipe_classes = {c["class_id"]: c for c in self.piping_catalog["classes"]}
        self.routing_levels = self.piping_catalog["routing_levels"]
        self.interfaces = {i["interface_id"]: i for i in self.site["external_interfaces"]}
        self.corridors = {c["corridor_id"]: c for c in self.site["routing_corridors"]}
        self.zones = {z["zone_id"]: z for z in self.site["no_build_zones"]}

    def _json(self, name: str):
        return json.loads((self.brief_dir / name).read_text())

    # -- frequently used published constants ---------------------------------

    @property
    def site_boundary(self):
        return [tuple(p) for p in self.site["boundary_polygon_m"]]

    @property
    def max_gas_velocity(self) -> float:
        return self.piping_catalog["maximum_gas_velocity_m_s"]

    @property
    def max_liquid_drain_velocity(self) -> float:
        return self.piping_catalog["maximum_liquid_drain_velocity_m_s"]

    @property
    def road_access_buffer_m(self) -> float:
        return self.maintenance_requirements["road_access_buffer_m"]

    @property
    def crane_access_buffer_m(self) -> float:
        return self.maintenance_requirements["crane_access_buffer_m"]

    def min_separation_m(self, cat_a: str, cat_b: str) -> float:
        return self.safety_requirements["minimum_separation_m"][cat_a][cat_b]

    def pvf(self) -> float:
        i = self.economic_assumptions["discount_rate"]
        n = self.economic_assumptions["project_life_years"]
        if abs(i) < 1e-15:
            return float(n)
        return (1.0 - (1.0 + i) ** (-n)) / i


# ----------------------------------------------------------------------------
# gas properties
# ----------------------------------------------------------------------------


class Gas:
    """Published gas property proxies (synthetic, deterministic)."""

    def __init__(self, gas_properties: dict):
        self.gp = gas_properties
        self.mw = gas_properties["molecular_weight_kg_mol"]
        self.cp = gas_properties["heat_capacity_cp_j_kg_k"]
        self.k = gas_properties["specific_heat_ratio"]
        self.z_min = gas_properties["compressibility_proxy"]["minimum"]
        self.z_max = gas_properties["compressibility_proxy"]["maximum"]
        self.mu_min = gas_properties["viscosity_proxy"]["minimum"]
        self.mu_max = gas_properties["viscosity_proxy"]["maximum"]

    @staticmethod
    def kelvin(t_c: float) -> float:
        return t_c + 273.15

    def z(self, p_mpa: float, t_c: float) -> float:
        p = max(MIN_PRESSURE_MPA, p_mpa)
        t_k = self.kelvin(t_c)
        z_raw = 0.90 + 0.08 * p / (p + 10.0) + 0.00015 * (t_k - 293.15)
        return min(self.z_max, max(self.z_min, z_raw))

    def mu(self, p_mpa: float, t_c: float) -> float:
        p = max(MIN_PRESSURE_MPA, p_mpa)
        t_k = self.kelvin(t_c)
        mu_raw = 1.05e-5 * (t_k / 293.15) ** 0.70 * (1.0 + 0.002 * p)
        return min(self.mu_max, max(self.mu_min, mu_raw))

    def rho(self, p_mpa: float, t_c: float) -> float:
        p = max(MIN_PRESSURE_MPA, p_mpa)
        t_k = self.kelvin(t_c)
        return (p * 1e6) * self.mw / (self.z(p, t_c) * R_UNIVERSAL * t_k)


# ----------------------------------------------------------------------------
# pipe hydraulics
# ----------------------------------------------------------------------------


def darcy_friction_factor(re: float, rel_roughness: float) -> float:
    """64/Re for Re < 2300, Swamee-Jain otherwise."""
    if re < 2300.0:
        return 64.0 / max(re, 1e-12)
    return 0.25 / (math.log10(rel_roughness / 3.7 + 5.74 / re**0.9)) ** 2


class PipeLossResult:
    __slots__ = ("p_out_mpa", "converged", "updates", "velocity_m_s", "reynolds", "friction_factor",
                 "rho_kg_m3", "dp_mpa", "p_mean_mpa", "flow", "direction")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def pipe_pressure_loss(gas: Gas, p_in_mpa: float, t_c: float, m_dot_kg_s: float,
                                      length_m: float, internal_diameter_m: float,
                                      roughness_m: float) -> PipeLossResult:
    area = math.pi * internal_diameter_m**2 / 4.0
    p_out = p_in_mpa
    converged = False
    updates = 0
    rho = v = re = f = dp = p_mean = 0.0
    for i in range(1, HYDRAULIC_MAX_UPDATES + 1):
        updates = i
        p_mean = max(MIN_PRESSURE_MPA, (p_in_mpa + p_out) / 2.0)
        rho = gas.rho(p_mean, t_c)
        v = m_dot_kg_s / (rho * area) if m_dot_kg_s > 0 else 0.0
        mu = gas.mu(p_mean, t_c)
        re = rho * v * internal_diameter_m / mu if v > 0 else 0.0
        f = darcy_friction_factor(re, roughness_m / internal_diameter_m) if v > 0 else 0.0
        dp_pa = f * (length_m / internal_diameter_m) * rho * v * v / 2.0 if v > 0 else 0.0
        dp = dp_pa / 1e6
        p_new = max(MIN_PRESSURE_MPA, p_in_mpa - dp)
        if abs(p_new - p_out) < HYDRAULIC_CONVERGENCE_MPA:
            p_out = p_new
            converged = True
            break
        p_out = p_new
    return PipeLossResult(p_out_mpa=p_out, converged=converged, updates=updates, velocity_m_s=v,
                          reynolds=re, friction_factor=f, rho_kg_m3=rho, dp_mpa=p_in_mpa - p_out,
                          p_mean_mpa=p_mean)


# ----------------------------------------------------------------------------
# equipment models
# ----------------------------------------------------------------------------


def compressor_outlet_temperature_c(t_in_c: float, ratio: float, k: float, eta: float) -> float:
    t_in_k = Gas.kelvin(t_in_c)
    t_out_k = t_in_k * (1.0 + (ratio ** ((k - 1.0) / k) - 1.0) / eta)
    return t_out_k - 273.15


def compressor_power_mw(m_dot_kg_s: float, t_in_c: float, ratio: float, k: float, eta: float,
                        eta_driver: float, cp: float) -> float:
    t_in_k = Gas.kelvin(t_in_c)
    w = m_dot_kg_s * cp * t_in_k * (ratio ** ((k - 1.0) / k) - 1.0) / (eta * eta_driver)
    return w / 1e6


def regulator_outlet_temperature_c(t_in_c: float, p_in_mpa: float, p_out_mpa: float,
                                   jt_k_per_mpa: float) -> float:
    return t_in_c - jt_k_per_mpa * (p_in_mpa - p_out_mpa)


def cooler_duty_mw(m_dot_kg_s: float, cp: float, t_in_c: float, t_out_c: float) -> float:
    return m_dot_kg_s * cp * abs(t_out_c - t_in_c) / 1e6


def separator_outlet_loading(f_in: float, removal_efficiency: float) -> float:
    return f_in * (1.0 - removal_efficiency)


def header_pressure_drop_mpa(m_dot_kg_s: float, capacity_kg_s: float,
                             drop_at_capacity_mpa: float) -> float:
    if m_dot_kg_s <= 0:
        return 0.0
    return drop_at_capacity_mpa * (m_dot_kg_s / capacity_kg_s) ** 2


# ----------------------------------------------------------------------------
# geometry primitives (plan view, metres)
# ----------------------------------------------------------------------------


def rotate_point(pt, angle_deg, center):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    dx, dy = pt[0] - center[0], pt[1] - center[1]
    return (center[0] + dx * c - dy * s, center[1] + dx * s + dy * c)


def rotate_points(pts, angle_deg, center):
    return [rotate_point(p, angle_deg, center) for p in pts]


def rect_polygon(cx, cy, length_m, width_m, angle_deg):
    hx, hy = length_m / 2.0, width_m / 2.0
    pts = [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]
    return rotate_points(pts, angle_deg, (cx, cy))


def expand_rect_polygon(cx, cy, length_m, width_m, angle_deg, d):
    """Minkowski sum of the (rotated) rectangle with a square of half-width d.

    The published rule expands every side outward by ``clearance`` with
    straight/mitered corner joins, which for a rectangle equals this offset.
    """
    return rect_polygon(cx, cy, length_m + 2.0 * d, width_m + 2.0 * d, angle_deg)


def polygon_area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def ensure_ccw(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return poly if a > 0 else list(reversed(poly))


def _clip_halfplane(poly, a, b, c, tol):
    """Keep the part of ``poly`` with a*x + b*y >= c (inside of the edge line,
    allowing boundary slack)."""
    if not poly:
        return []
    out = []
    n = len(poly)
    for i in range(n):
        p = poly[i]
        q = poly[(i + 1) % n]
        dp = a * p[0] + b * p[1] - c
        dq = a * q[0] + b * q[1] - c
        if dp >= -tol:
            out.append(p)
        if (dp < -tol < dq) or (dp > tol > dq):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def convex_intersection(poly_a, poly_b, tol=0.0):
    """Intersection of two convex polygons (CCW), by half-plane clipping."""
    a = ensure_ccw(poly_a)
    b = ensure_ccw(poly_b)
    out = list(a)
    n = len(b)
    for i in range(n):
        p1 = b[i]
        p2 = b[(i + 1) % n]
        # edge direction; interior is to the left for CCW
        ex, ey = p2[0] - p1[0], p2[1] - p1[1]
        # inward normal
        nx, ny = -ey, ex
        c = nx * p1[0] + ny * p1[1]
        out = _clip_halfplane(out, nx, ny, c, tol)
        if not out:
            return []
    return out


def convex_intersection_area(poly_a, poly_b, tol=0.0):
    inter = convex_intersection(poly_a, poly_b, tol)
    return polygon_area(inter) if inter else 0.0


def point_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll <= 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / ll
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def polygons_distance(poly_a, poly_b):
    """Shortest boundary-to-boundary distance; 0 when the polygons touch/overlap."""
    if convex_intersection(poly_a, poly_b):
        return 0.0
    best = float("inf")
    for p in poly_a:
        n = len(poly_b)
        for i in range(n):
            d = point_segment_distance(p, poly_b[i], poly_b[(i + 1) % n])
            best = min(best, d)
    for p in poly_b:
        n = len(poly_a)
        for i in range(n):
            d = point_segment_distance(p, poly_a[i], poly_a[(i + 1) % n])
            best = min(best, d)
    return best


def point_in_convex(poly, pt, tol=TOL_GEOMETRY_M):
    """Return +1 strictly inside (deeper than tol), 0 on the boundary within tol,
    -1 outside."""
    a = ensure_ccw(poly)
    depth = float("inf")
    n = len(a)
    for i in range(n):
        p1 = a[i]
        p2 = a[(i + 1) % n]
        ex, ey = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -ey, ex
        ln = math.hypot(nx, ny)
        signed = (nx * (pt[0] - p1[0]) + ny * (pt[1] - p1[1])) / ln
        depth = min(depth, signed)
    if depth > tol:
        return 1
    if depth >= -tol:
        return 0
    return -1


def segment_inside_convex_length(poly, a, b, tol=TOL_GEOMETRY_M):
    """Length of the part of segment [a, b] that is strictly inside ``poly``
    (i.e. deeper than ``tol`` from every edge)."""
    poly_ccw = ensure_ccw(poly)
    total = math.hypot(b[0] - a[0], b[1] - a[1])
    if total <= 0:
        return 0.0
    t0, t1 = 0.0, 1.0
    for i in range(len(poly_ccw)):
        p1 = poly_ccw[i]
        p2 = poly_ccw[(i + 1) % len(poly_ccw)]
        ex, ey = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -ey, ex
        ln = math.hypot(nx, ny)
        nx, ny = nx / ln, ny / ln
        # signed distance of the segment start, and rate of change
        f0 = nx * (a[0] - p1[0]) + ny * (a[1] - p1[1])
        f1 = nx * (b[0] - p1[0]) + ny * (b[1] - p1[1])
        df = f1 - f0
        # require signed distance > tol
        if abs(df) < 1e-15:
            if f0 <= tol:
                return 0.0
            continue
        t_star = (tol - f0) / df
        if df > 0:  # distance increasing with t -> t must exceed t_star
            t0 = max(t0, t_star)
        else:
            t1 = min(t1, t_star)
        if t1 <= t0:
            return 0.0
    return max(0.0, (t1 - t0) * total)


def segment_polygon_intersection_length(poly, a, b):
    """Length of the intersection of segment [a, b] with a convex polygon
    (including boundary)."""
    poly_ccw = ensure_ccw(poly)
    total = math.hypot(b[0] - a[0], b[1] - a[1])
    if total <= 0:
        return 0.0
    t0, t1 = 0.0, 1.0
    for i in range(len(poly_ccw)):
        p1 = poly_ccw[i]
        p2 = poly_ccw[(i + 1) % len(poly_ccw)]
        ex, ey = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -ey, ex
        ln = math.hypot(nx, ny)
        nx, ny = nx / ln, ny / ln
        f0 = nx * (a[0] - p1[0]) + ny * (a[1] - p1[1])
        f1 = nx * (b[0] - p1[0]) + ny * (b[1] - p1[1])
        df = f1 - f0
        if abs(df) < 1e-15:
            if f0 < 0:
                return 0.0
            continue
        t_star = -f0 / df
        if df > 0:
            t0 = max(t0, t_star)
        else:
            t1 = min(t1, t_star)
        if t1 <= t0:
            return 0.0
    return max(0.0, (t1 - t0) * total)


def collinear_overlap_length(seg1, seg2):
    """Positive-length overlap of two collinear segments (0 otherwise)."""
    (a1, a2), (b1, b2) = seg1, seg2
    d1 = (a2[0] - a1[0], a2[1] - a1[1])
    d2 = (b2[0] - b1[0], b2[1] - b1[1])
    l1 = math.hypot(*d1)
    l2 = math.hypot(*d2)
    if l1 <= 0 or l2 <= 0:
        return 0.0
    # parallel?
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) > 1e-9 * l1 * l2:
        return 0.0
    # collinear? distance of b1 from line a
    dist = abs((b1[0] - a1[0]) * d1[1] - (b1[1] - a1[1]) * d1[0]) / l1
    if dist > 1e-6:
        return 0.0
    u1 = (d1[0] / l1, d1[1] / l1)
    tb = [((p[0] - a1[0]) * u1[0] + (p[1] - a1[1]) * u1[1]) for p in (b1, b2)]
    lo, hi = min(tb), max(tb)
    lo = max(lo, 0.0)
    hi = min(hi, l1)
    return max(0.0, hi - lo)


def polyline_length(points):
    return sum(math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
               for i in range(len(points) - 1))


def segment_rect_polygons(a, b, half_width):
    """Paved-road geometry of one centreline segment: the segment swept by
    half the width (Minkowski sum of the segment and a square of half-width)."""
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy)
    if ln <= 0:
        return [(x1 - half_width, y1 - half_width), (x1 + half_width, y1 - half_width),
                (x1 + half_width, y1 + half_width), (x1 - half_width, y1 + half_width)]
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    return [
        (x1 - ux * half_width + nx * half_width, y1 - uy * half_width + ny * half_width),
        (x2 + ux * half_width + nx * half_width, y2 + uy * half_width + ny * half_width),
        (x2 + ux * half_width - nx * half_width, y2 + uy * half_width - ny * half_width),
        (x1 - ux * half_width - nx * half_width, y1 - uy * half_width - ny * half_width),
    ]


def polygon_min_distance_to_region(poly, region_polys):
    """Minimum polygon-to-polygon distance from ``poly`` to any polygon of
    ``region_polys`` (0 if any of them touches/overlaps)."""
    best = float("inf")
    for rp in region_polys:
        best = min(best, polygons_distance(poly, rp))
    return best


def point_in_polygon(poly, pt):
    """Ray-casting inclusion test (works for non-convex polygons)."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)):
            x_int = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_int:
                inside = not inside
        j = i
    return inside
