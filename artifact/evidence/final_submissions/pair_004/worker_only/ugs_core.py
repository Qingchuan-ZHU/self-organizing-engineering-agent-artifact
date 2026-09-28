"""UGS-SYNTH-D01 v1.1 - core physics and planar geometry helpers.

Physics per brief/engineering_calculation_basis.md.
Geometry per brief/engineering_geometry_basis.md.
All coordinates in metres, pressures in MPa, temperatures in degC, flows in kg/s.
"""
import math

R_U = 8.314462618  # J/(mol K)
GEOM_TOL = 1e-6


# ---------------------------------------------------------------- gas physics
def c_to_k(t_c):
    return t_c + 273.15


def z_factor(P_mpa, T_c, gp):
    Tk = c_to_k(T_c)
    P = max(P_mpa, 1e-6)
    z = 0.90 + 0.08 * P / (P + 10.0) + 0.00015 * (Tk - 293.15)
    lo = gp["compressibility_proxy"]["minimum"]
    hi = gp["compressibility_proxy"]["maximum"]
    return min(max(z, lo), hi)


def viscosity(P_mpa, T_c, gp):
    Tk = c_to_k(T_c)
    P = max(P_mpa, 1e-6)
    mu = 1.05e-5 * (Tk / 293.15) ** 0.70 * (1.0 + 0.002 * P)
    lo = gp["viscosity_proxy"]["minimum"]
    hi = gp["viscosity_proxy"]["maximum"]
    return min(max(mu, lo), hi)


def density(P_mpa, T_c, gp):
    P = max(P_mpa, 1e-6)
    Tk = c_to_k(T_c)
    Z = z_factor(P, T_c, gp)
    MW = gp["molecular_weight_kg_mol"]
    return (P * 1e6) * MW / (Z * R_U * Tk)


def friction_factor(Re, eps, D):
    if Re < 2300.0:
        return 64.0 / Re
    x = eps / (3.7 * D) + 5.74 / (Re ** 0.9)
    return 0.25 / (math.log10(x) ** 2)


def gas_velocity(P_mpa, T_c, m_dot, D, gp):
    rho = density(P_mpa, T_c, gp)
    A = math.pi * D * D / 4.0
    return m_dot / (rho * A)


def pipe_pressure_loss_mpa(P_in, m_dot, D, L, eps, T_c, gp):
    """Fixed-point outlet pressure. Returns dict with P_out, converged, iters, v, Re, f."""
    P_out = P_in
    converged = False
    iters = 0
    v = 0.0
    Re = 0.0
    f = 0.0
    if m_dot <= 0 or L <= 0:
        return {"P_out": P_in, "converged": True, "iters": 0, "v": 0.0, "Re": 0.0, "f": 0.0}
    for it in range(9):
        P_mean = max((P_in + P_out) / 2.0, 1e-6)
        rho = density(P_mean, T_c, gp)
        mu = viscosity(P_mean, T_c, gp)
        A = math.pi * D * D / 4.0
        v = m_dot / (rho * A)
        Re = rho * v * D / mu
        f = friction_factor(Re, eps, D)
        dP = f * (L / D) * rho * v * v / 2.0 / 1e6
        newP = max(1e-6, P_in - dP)
        if abs(newP - P_out) < 1e-5:
            P_out = newP
            converged = True
            break
        P_out = newP
        iters = it + 1
    return {"P_out": P_out, "converged": converged, "iters": iters,
            "v": v, "Re": Re, "f": f}


def compressor_outlet_temp(T_in_c, r, k, eta):
    return c_to_k(T_in_c) * (1.0 + (r ** ((k - 1.0) / k) - 1.0) / eta) - 273.15


def compressor_power_mw(m_dot, cp, T_in_c, r, k, eta, eta_driver):
    Tk = c_to_k(T_in_c)
    W = m_dot * cp * Tk * (r ** ((k - 1.0) / k) - 1.0) / (eta * eta_driver)
    return W / 1e6


def present_value_factor(i, n):
    if i == 0:
        return float(n)
    return (1.0 - (1.0 + i) ** (-n)) / i


# -------------------------------------------------------------- planar geometry
# Everything reduces to axis-aligned rectangles because equipment orientation
# options are only 0 and 90 degrees and all zones / corridors are axis aligned.

def rect(x0, y0, x1, y1):
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def rect_area(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def rect_intersect(a, b):
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1])
    x1 = min(a[2], b[2]); y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def rect_overlap_area(a, b):
    r = rect_intersect(a, b)
    return 0.0 if r is None else rect_area(r)


def rect_distance(a, b):
    """Shortest boundary-to-boundary distance (0 if touching/overlapping)."""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def rect_union_area(a, b):
    return rect_area(a) + rect_area(b) - rect_overlap_area(a, b)


def point_in_rect_interior(p, r, tol=GEOM_TOL):
    return (r[0] + tol < p[0] < r[2] - tol) and (r[1] + tol < p[1] < r[3] - tol)


def seg_intersects_rect_interior(p, q, r, tol=GEOM_TOL):
    """True if segment p-q enters the interior of rect r by more than tol."""
    # Liang-Barsky style clipping: compute the parametric interval inside r.
    x0, y0, x1, y1 = r
    x0 += tol; y0 += tol; x1 -= tol; y1 -= tol
    if x1 <= x0 or y1 <= y0:
        return False
    t0, t1 = 0.0, 1.0
    dx = q[0] - p[0]
    dy = q[1] - p[1]
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < 1e-15:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                if t > t1:
                    return False
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return False
                if t < t1:
                    t1 = t
    return t1 > t0


def rect_contains_rect(outer, inner, tol=GEOM_TOL):
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and
            inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)
