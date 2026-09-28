"""
UGS-SYNTH-D01 v1.1 shared calculation library.

Implements the deterministic engineering calculation basis from
brief/engineering_calculation_basis.md and brief/engineering_geometry_basis.md.

All quantities SI unless stated: pressure MPa, temperature degC (K inside formulas),
flow kg/s, length m, area m2, power/duty MW, energy MWh, cost MBCU.
"""
from __future__ import annotations

import json
import math
import os

BRIEF = os.path.join(os.path.dirname(__file__), "..", "..", "brief")

R_UNIVERSAL = 8.314462618  # J/(mol K)


def _load(name):
    with open(os.path.join(BRIEF, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------
# Brief data
# ----------------------------------------------------------------------------
CASE = _load("case.json")
GAS = _load("gas_properties.json")
SITE = _load("site.json")
SCENARIOS = _load("operating_scenarios.json")
PROJECT = _load("project_requirements.json")
ECON = _load("economic_assumptions.json")
PIPING = _load("piping_catalog.json")
SAFETY = _load("safety_requirements.json")
MAINT = _load("maintenance_requirements.json")
WELL_GROUPS = _load("well_group_interfaces.json")
DELIVERY_CONTRACT = _load("final_delivery_contract.json")

CATALOG = {}
for _f in ("compressors", "dehydration", "drains", "filters", "headers",
           "metering_regulation", "separators", "thermal_equipment"):
    _data = _load(os.path.join("equipment_catalog", _f + ".json"))
    for _m in _data["models"]:
        CATALOG[_m["model_id"]] = _m

# ----------------------------------------------------------------------------
# Tolerances (engineering_calculation_basis.md)
# ----------------------------------------------------------------------------
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
MIN_PRESSURE_MPA = 1e-6


# ----------------------------------------------------------------------------
# Geometry helpers (axis-aligned rectangles + simple polygons)
# ----------------------------------------------------------------------------
def rotate(pt, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y = pt
    return (c * x - s * y, s * x + c * y)


def rect_polygon(cx, cy, length, width, orient_deg):
    """Footprint polygon: rectangle centred at (cx,cy), length along local x."""
    hx, hy = length / 2.0, width / 2.0
    local = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    return [(cx + p[0], cy + p[1]) for p in (rotate(p, orient_deg) for p in local)]


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def rect_from_bbox(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def poly_area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def _pt_seg(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def seg_seg_distance(p1, p2, p3, p4):
    def _orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    o1, o2 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    o3, o4 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return 0.0
    return min(_pt_seg(p1, p3, p4), _pt_seg(p2, p3, p4),
               _pt_seg(p3, p1, p2), _pt_seg(p4, p1, p2))


def poly_distance(poly_a, poly_b):
    """Shortest boundary-to-boundary distance (0 when overlapping/touching)."""
    for p in poly_a:
        if point_in_poly(p, poly_b):
            return 0.0
    for p in poly_b:
        if point_in_poly(p, poly_a):
            return 0.0
    d = float("inf")
    na, nb = len(poly_a), len(poly_b)
    for i in range(na):
        a1, a2 = poly_a[i], poly_a[(i + 1) % na]
        for j in range(nb):
            b1, b2 = poly_b[j], poly_b[(j + 1) % nb]
            d = min(d, seg_seg_distance(a1, a2, b1, b2))
    return d


def poly_overlap_area(rect_a, rect_b):
    ax0, ay0, ax1, ay1 = bbox(rect_a)
    bx0, by0, bx1, by1 = bbox(rect_b)
    ox = min(ax1, bx1) - max(ax0, bx0)
    oy = min(ay1, by1) - max(ay0, by0)
    return ox * oy if (ox > 0 and oy > 0) else 0.0


def inflate_rect(poly, d):
    x0, y0, x1, y1 = bbox(poly)
    return rect_from_bbox(x0 - d, y0 - d, x1 + d, y1 + d)


# ----------------------------------------------------------------------------
# Gas / pipe hydraulics
# ----------------------------------------------------------------------------
def compressibility(P_mpa, T_c):
    T_K = T_c + 273.15
    z = 0.90 + 0.08 * P_mpa / (P_mpa + 10.0) + 0.00015 * (T_K - 293.15)
    return max(GAS["compressibility_proxy"]["minimum"],
               min(GAS["compressibility_proxy"]["maximum"], z))


def viscosity(P_mpa, T_c):
    T_K = T_c + 273.15
    mu = 1.05e-5 * (T_K / 293.15) ** 0.70 * (1 + 0.002 * P_mpa)
    return max(GAS["viscosity_proxy"]["minimum"],
               min(GAS["viscosity_proxy"]["maximum"], mu))


def density(P_mpa, T_c):
    P = max(P_mpa, MIN_PRESSURE_MPA)
    z = compressibility(P, T_c)
    T_K = T_c + 273.15
    return P * 1e6 * GAS["molecular_weight_kg_mol"] / (z * R_UNIVERSAL * T_K)


DIAMETERS = {d["nominal_diameter"]: d for d in PIPING["diameters"]}
CLASSES = {c["class_id"]: c for c in PIPING["classes"]}
LEVELS = PIPING["routing_levels"]
MAX_GAS_V = PIPING["maximum_gas_velocity_m_s"]
MAX_LIQ_V = PIPING["maximum_liquid_drain_velocity_m_s"]
CP = GAS["heat_capacity_cp_j_kg_k"]
K_RATIO = GAS["specific_heat_ratio"]
LIQUID_DENSITY = 1000.0  # kg/m3 synthetic assumption for drain velocity checks


def darcy_friction(Re, eps_over_D):
    if Re < 2300.0:
        return 64.0 / Re
    return 0.25 / (math.log10(eps_over_D / 3.7 + 5.74 / Re ** 0.9)) ** 2


def velocity(m_dot, rho, D):
    return m_dot / (rho * math.pi * D * D / 4.0)


def pressure_loss(m_dot, D, L, P_in, P_out_trial, T_c, eps):
    """One fixed-point update of the pressure-loss calculation."""
    P_mean = (P_in + P_out_trial) / 2.0
    rho = density(P_mean, T_c)
    mu = viscosity(P_mean, T_c)
    v = velocity(m_dot, rho, D)
    Re = max(rho * v * D / mu, 1e-9)
    f = darcy_friction(Re, eps / D)
    dp = f * (L / D) * rho * v * v / 2.0 / 1e6
    return P_in - dp, {"P_mean": P_mean, "rho": rho, "mu": mu, "v": v,
                       "Re": Re, "f": f, "dp": dp}


def solve_pipe(m_dot, D, L, P_in, T_c, eps):
    """Fixed-point outlet pressure per the calculation basis (max 8 updates)."""
    if L <= 0.0 or m_dot <= 0.0:
        rho = density(P_in, T_c)
        return {"P_out": P_in, "converged": True, "P_mean": P_in,
                "v": 0.0, "Re": 0.0, "f": 0.0, "rho": rho, "dp": 0.0,
                "mu": viscosity(P_in, T_c)}
    P_out = P_in
    converged = False
    info = None
    for _ in range(8):
        new, info = pressure_loss(m_dot, D, L, P_in, P_out, T_c, eps)
        new = max(MIN_PRESSURE_MPA, new)
        if abs(new - P_out) < 1e-5:
            P_out = new
            converged = True
            break
        P_out = new
    _, info = pressure_loss(m_dot, D, L, P_in, P_out, T_c, eps)
    return {"P_out": P_out, "converged": converged, "P_mean": info["P_mean"],
            "v": info["v"], "Re": info["Re"], "f": info["f"], "rho": info["rho"],
            "dp": P_in - P_out, "mu": info["mu"]}


def compressor_performance(m_dot, ratio, T_in_c, eta, eta_driver):
    k = K_RATIO
    T_in_K = T_in_c + 273.15
    x = ratio ** ((k - 1) / k) - 1.0
    T_out_K = T_in_K * (1.0 + x / eta)
    W = m_dot * CP * T_in_K * x / (eta * eta_driver)
    return {"T_out_c": T_out_K - 273.15, "power_mw": W / 1e6, "ratio": ratio}


# ----------------------------------------------------------------------------
# Economics
# ----------------------------------------------------------------------------
def pvf(rate=None, years=None):
    i = ECON["discount_rate"] if rate is None else rate
    n = ECON["project_life_years"] if years is None else years
    if i == 0:
        return float(n)
    return (1.0 - (1.0 + i) ** (-n)) / i


PVF = pvf()
ENERGY_TARIFF = ECON["energy_tariff_mbcu_per_mwh"]
