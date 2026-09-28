"""
UGS-SYNTH-D01 v1.1 - deterministic engineering engine.

Implements, exactly as published in brief/:
  * gas property proxies (Z, mu, rho)
  * Darcy/Swamee-Jain pipe pressure loss with the published fixed-point convention
  * equipment models (compressor, cooler/heater, regulator, separator/filter,
    dehydration, header, closed drain, meter)
  * plan-view geometry (footprints, clearances, removal envelopes, separations,
    roads, pipeline routes, corridors)
  * lifecycle cost build-up

All units are SI-derived as published: m, MPa, degC, kg/s, MW, MWh, MBCU.
"""

import json
import math
import os
from math import cos, hypot, log10, pi, radians, sin, sqrt

# --------------------------------------------------------------------------
# catalogues
# --------------------------------------------------------------------------

def _find_brief():
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(here, '..', '..', 'brief'),
        os.path.join(here, '..', 'brief'),
        'brief', '../brief',
    ]
    for c in cands:
        if os.path.isdir(c):
            return os.path.abspath(c)
    raise RuntimeError('brief/ directory not found')


BRIEF = _find_brief()


def jload(rel):
    with open(os.path.join(BRIEF, rel)) as fh:
        return json.load(fh)


class Catalogs(object):
    def __init__(self):
        self.models = {}
        for fn in ('compressors', 'separators', 'dehydration', 'filters',
                   'thermal_equipment', 'metering_regulation', 'drains', 'headers'):
            for m in jload('equipment_catalog/%s.json' % fn)['models']:
                if m['model_id'] in self.models:
                    raise RuntimeError('duplicate model id ' + m['model_id'])
                self.models[m['model_id']] = m
        self.piping = jload('piping_catalog.json')
        self.site = jload('site.json')
        self.gas = jload('gas_properties.json')
        self.econ = jload('economic_assumptions.json')
        self.safety = jload('safety_requirements.json')
        self.maint = jload('maintenance_requirements.json')
        self.scenarios = jload('operating_scenarios.json')['scenarios']
        self.req = jload('project_requirements.json')
        self.well_groups = jload('well_group_interfaces.json')['well_groups']
        self.diameters = {d['nominal_diameter']: d for d in self.piping['diameters']}
        self.pipe_classes = {c['class_id']: c for c in self.piping['classes']}
        self.levels = self.piping['routing_levels']

    # ---- convenience -----------------------------------------------------
    def model(self, mid):
        return self.models[mid]

    def dn(self, nominal):
        return self.diameters[nominal]

    def pclass(self, cid):
        return self.pipe_classes[cid]

    def interfaces(self):
        """external interface_id -> dict (GRID-TIE, WG-xx, outfall, utilities, road)"""
        out = {}
        for it in self.site['external_interfaces']:
            out[it['interface_id']] = dict(it)
        return out


C = Catalogs()

RU = 8.314462618
MW = C.gas['molecular_weight_kg_mol']
CP = C.gas['heat_capacity_cp_j_kg_k']
K_RATIO = C.gas['specific_heat_ratio']

GEOM_TOL = 1e-6          # geometry tolerance
P_TOL = 1e-5             # pressure tolerance (MPa)
M_TOL = 1e-5             # mass flow tolerance (kg/s)
T_TOL = 1e-4             # temperature tolerance (degC)
W_TOL = 1e-5             # water content tolerance (mg/Sm3)
F_TOL = 1e-9             # free liquid loading tolerance
E_TOL = 1e-6             # power tolerance (MW)

# --------------------------------------------------------------------------
# gas properties
# --------------------------------------------------------------------------

def _z_raw(P, Tc):
    return 0.90 + 0.08 * P / (P + 10.0) + 0.00015 * ((Tc + 273.15) - 293.15)


def zfac(P, Tc):
    lo = C.gas['compressibility_proxy']['minimum']
    hi = C.gas['compressibility_proxy']['maximum']
    return min(hi, max(lo, _z_raw(max(P, 1e-6), Tc)))


def _mu_raw(P, Tc):
    return 1.05e-5 * ((Tc + 273.15) / 293.15) ** 0.70 * (1.0 + 0.002 * P)


def visc(P, Tc):
    lo = C.gas['viscosity_proxy']['minimum']
    hi = C.gas['viscosity_proxy']['maximum']
    return min(hi, max(lo, _mu_raw(max(P, 1e-6), Tc)))


def dens(P, Tc):
    P = max(P, 1e-6)
    return (P * 1e6) * MW / (zfac(P, Tc) * RU * (Tc + 273.15))


# --------------------------------------------------------------------------
# hydraulics
# --------------------------------------------------------------------------

def resistance_terms(P, Tc, D, eps):
    """returns (rho, mu) at the given pressure/temperature"""
    return dens(P, Tc), visc(P, Tc)


def friction_factor(Re, eps, D):
    if Re < 2300.0:
        return 64.0 / Re
    return 0.25 / (log10(eps / (3.7 * D) + 5.74 / Re ** 0.9) ** 2)


def velocity(m_dot, P, Tc, D):
    A = pi * D * D / 4.0
    if m_dot == 0.0 or A == 0.0:
        return 0.0
    return abs(m_dot) / (dens(P, Tc) * A)


def dp_at(P_mean, m_dot, L, D, eps, Tc):
    rho, mu = resistance_terms(P_mean, Tc, D, eps)
    A = pi * D * D / 4.0
    v = abs(m_dot) / (rho * A)
    Re = rho * v * D / mu if v > 0 else 0.0
    f = friction_factor(Re, eps, D) if Re > 0 else 0.0
    dP = f * (L / D) * rho * v * v / 2.0
    return dP / 1e6, v, Re, f


def pipe_forward(P_in, m_dot, L, D, eps, Tc, tol=P_TOL, iters=8):
    """published fixed-point convention, downstream direction"""
    P_out = P_in
    converged = False
    info = None
    for _ in range(iters):
        Pm = max(1e-6, 0.5 * (P_in + P_out))
        dP, v, Re, f = dp_at(Pm, m_dot, L, D, eps, Tc)
        P_new = max(1e-6, P_in - dP)
        converged = abs(P_new - P_out) < tol
        P_out = P_new
        info = dict(dP=dP, v=v, Re=Re, f=f, P_mean=Pm)
        if converged:
            break
    return P_out, converged, info


def pipe_backward(P_out, m_dot, L, D, eps, Tc, tol=P_TOL, iters=8):
    """inverse of pipe_forward: solve for the inlet pressure"""
    P_in = P_out
    converged = False
    info = None
    for _ in range(iters):
        Pm = max(1e-6, 0.5 * (P_in + P_out))
        dP, v, Re, f = dp_at(Pm, m_dot, L, D, eps, Tc)
        P_new = P_out + dP
        converged = abs(P_new - P_in) < tol
        P_in = P_new
        info = dict(dP=dP, v=v, Re=Re, f=f, P_mean=Pm)
        if converged:
            break
    return P_in, converged, info


# --------------------------------------------------------------------------
# plan-view geometry
# --------------------------------------------------------------------------

def rot_pt(p, deg):
    r = radians(deg)
    c, s = cos(r), sin(r)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def rect_poly(cx, cy, length, width, deg):
    pts = [(-length / 2.0, -width / 2.0), (length / 2.0, -width / 2.0),
           (length / 2.0, width / 2.0), (-length / 2.0, width / 2.0)]
    return [(cx + rot_pt(p, deg)[0], cy + rot_pt(p, deg)[1]) for p in pts]


def poly_area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def point_in_poly(pt, poly, strict=True):
    """convex polygon (CCW or CW). strict=True -> interior only."""
    n = len(poly)
    # orient
    sgn = 1.0 if poly_area(poly) > 0 else -1.0
    x, y = pt
    inside = True
    on = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cr = sgn * ((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1))
        if cr < -1e-12:
            inside = False
            break
        if abs(cr) <= 1e-12:
            on = True
    if strict:
        return inside and not on
    return inside


def seg_pt_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 0:
        return hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = max(0.0, min(1.0, t))
    return hypot(px - (ax + t * dx), py - (ay + t * dy))


def seg_seg_dist(a, b, c, d):
    # fast check for proper intersection
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1 = cross(c, d, a)
    d2 = cross(c, d, b)
    d3 = cross(a, b, c)
    d4 = cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(seg_pt_dist(a, c, d), seg_pt_dist(b, c, d),
               seg_pt_dist(c, a, b), seg_pt_dist(d, a, b))


def poly_poly_dist(p1, p2):
    """0 if the (convex) polygons intersect; else min edge-edge distance"""
    if positive_overlap(p1, p2):
        return 0.0
    best = float('inf')
    for i in range(len(p1)):
        a, b = p1[i], p1[(i + 1) % len(p1)]
        for j in range(len(p2)):
            c, d = p2[j], p2[(j + 1) % len(p2)]
            best = min(best, seg_seg_dist(a, b, c, d))
    return best


def positive_overlap(p1, p2):
    """True when two convex polygons share a region of positive area."""
    for v in p1:
        if point_in_poly(v, p2, strict=True):
            return True
    for v in p2:
        if point_in_poly(v, p1, strict=True):
            return True
    # proper edge crossings
    for i in range(len(p1)):
        a, b = p1[i], p1[(i + 1) % len(p1)]
        for j in range(len(p2)):
            c, d = p2[j], p2[(j + 1) % len(p2)]
            if proper_cross(a, b, c, d):
                return True
    return False


def proper_cross(a, b, c, d):
    def cr(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2 = cr(c, d, a), cr(c, d, b)
    d3, d4 = cr(a, b, c), cr(a, b, d)
    return ((d1 > 1e-12) != (d2 > 1e-12)) and ((d3 > 1e-12) != (d4 > 1e-12))


def seg_inside_convex_len(p, q, poly):
    """length of the part of segment p-q strictly inside the convex polygon"""
    n = len(poly)
    sgn = 1.0 if poly_area(poly) > 0 else -1.0
    lo, hi = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        # f(t) = sgn*((x2-x1)*(y(t)-y1) - (y2-y1)*(x(t)-x1)) >= 0 inside
        nx, ny = sgn * -(y2 - y1), sgn * (x2 - x1)
        c = sgn * ((x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1))
        elen = hypot(x2 - x1, y2 - y1)
        INSET = 1e-9 * elen          # 1e-9 m inward inset -> strict interior
        a = nx * dx + ny * dy
        b = c - INSET
        if abs(a) < 1e-15:
            if b < 0:
                return 0.0
        else:
            t = -b / a
            if a > 0:
                lo = max(lo, t)
            else:
                hi = min(hi, t)
        if lo >= hi:
            return 0.0
    L = hypot(dx, dy)
    return max(0.0, (hi - lo) * L)


def segments_of(points):
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def seg_len(a, b):
    return hypot(b[0] - a[0], b[1] - a[1])


def collinear_overlap_len(a, b, c, d, tol=1e-9):
    """positive overlap length of two collinear segments (0 otherwise)"""
    vx, vy = b[0] - a[0], b[1] - a[1]
    L1 = hypot(vx, vy)
    if L1 < tol:
        return 0.0
    ux, uy = vx / L1, vy / L1
    # c and d distance from line a-b
    def perp(p):
        return abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux)
    if perp(c) > 1e-6 or perp(d) > 1e-6:
        return 0.0
    def proj(p):
        return (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
    tc, td = sorted((proj(c), proj(d)))
    lo = max(0.0, tc)
    hi = min(L1, td)
    return max(0.0, hi - lo)


# --------------------------------------------------------------------------
# design object
# --------------------------------------------------------------------------

class Equipment(object):
    def __init__(self, eid, model_id, x, y, orient):
        self.id = eid
        self.model_id = model_id
        self.m = C.model(model_id)
        self.x, self.y, self.orient = float(x), float(y), float(orient)
        self.category = self.m['category']
        self.safety_category = self.m['safety_category']

    # ---- geometry -------------------------------------------------------
    @property
    def fp(self):
        f = self.m['footprint_m']
        return rect_poly(self.x, self.y, f['length'], f['width'], self.orient)

    def port_xy(self, pid):
        for p in self.m['ports']:
            if p['id'] == pid:
                o = p['offset_m']
                r = rot_pt(o, self.orient)
                return (self.x + r[0], self.y + r[1])
        raise KeyError('%s has no port %s' % (self.id, pid))

    def port_type(self, pid):
        for p in self.m['ports']:
            if p['id'] == pid:
                return p['type']
        raise KeyError(pid)

    @property
    def clearance_poly(self):
        d = self.m['maintenance']['clearance_m']
        f = self.m['footprint_m']
        return rect_poly(self.x, self.y, f['length'] + 2 * d, f['width'] + 2 * d, self.orient)

    @property
    def removal_poly(self):
        md = self.m['maintenance']
        if not md.get('heavy_maintenance'):
            return None
        f = self.m['footprint_m']
        L, W = f['length'], f['width']
        ext, tw = md['removal_envelope_m']
        side = md['side']
        if side == 'east':
            local = [(L / 2.0, -tw / 2.0), (L / 2.0 + ext, -tw / 2.0),
                     (L / 2.0 + ext, tw / 2.0), (L / 2.0, tw / 2.0)]
        elif side == 'west':
            local = [(-L / 2.0, -tw / 2.0), (-L / 2.0 - ext, -tw / 2.0),
                     (-L / 2.0 - ext, tw / 2.0), (-L / 2.0, tw / 2.0)]
        elif side == 'north':
            local = [(-ext / 2.0, W / 2.0), (ext / 2.0, W / 2.0),
                     (ext / 2.0, W / 2.0 + tw), (-ext / 2.0, W / 2.0 + tw)]
        elif side == 'south':
            local = [(-ext / 2.0, -W / 2.0), (ext / 2.0, -W / 2.0),
                     (ext / 2.0, -W / 2.0 - tw), (-ext / 2.0, -W / 2.0 - tw)]
        else:
            raise ValueError(side)
        return [(self.x + rot_pt(p, self.orient)[0], self.y + rot_pt(p, self.orient)[1])
                for p in local]

    def maintenance_polys(self):
        out = [self.clearance_poly]
        r = self.removal_poly
        if r is not None:
            out.append(r)
        return out

    def maintenance_data(self):
        f = self.m['footprint_m']
        d = self.m['maintenance']['clearance_m']
        fp_area = f['length'] * f['width']
        cl = (f['length'] + 2 * d) * (f['width'] + 2 * d)
        env_area = cl
        md = self.m['maintenance']
        if md.get('heavy_maintenance'):
            ext, tw = md['removal_envelope_m']
            env_area += ext * tw
            # subtract overlap of removal rect with clearance rect (local coords)
            side = md['side']
            L, W = f['length'], f['width']
            if side in ('east', 'west'):
                ov_x = max(0.0, min(d, ext))
                ov_y = max(0.0, min(tw / 2.0, W / 2.0 + d) - max(-tw / 2.0, -W / 2.0 - d))
                env_area -= ov_x * ov_y
            else:
                ov_y = max(0.0, min(d, ext))
                ov_x = max(0.0, min(tw / 2.0, L / 2.0 + d) - max(-tw / 2.0, -L / 2.0 - d))
                env_area -= ov_x * ov_y
        return dict(area=max(0.0, env_area - fp_area), fp_area=fp_area)

    def maintenance_flags(self):
        md = self.m['maintenance']
        return bool(md.get('road_access_required')), bool(md.get('crane_access_required'))


class Pipeline(object):
    """port-to-port physical pipeline; one diameter and pipe class."""

    def __init__(self, pid, frm, to, dn, cls, points, levels, corridors=None,
                 service='gas'):
        self.id = pid
        self.frm = frm            # (equipment_id, port_id) or ('IFACE:ID', port_id)
        self.to = to
        self.dn = dn
        self.cls = cls
        self.points = [tuple(map(float, p)) for p in points]
        self.levels = list(levels)
        self.corridors = list(corridors) if corridors else [None] * len(levels)
        self.service = service    # 'gas' or 'liquid_drain'
        if len(self.levels) != len(self.points) - 1:
            raise ValueError('levels/points mismatch in %s' % pid)
        if len(self.corridors) != len(self.levels):
            raise ValueError('corridor mismatch in %s' % pid)

    @property
    def length(self):
        return sum(seg_len(self.points[i], self.points[i + 1])
                   for i in range(len(self.points) - 1))

    @property
    def D(self):
        return C.dn(self.dn)['internal_diameter_m']

    @property
    def eps(self):
        return C.pclass(self.cls)['roughness_m']

    def segments(self):
        for i in range(len(self.points) - 1):
            yield (self.points[i], self.points[i + 1], self.levels[i], self.corridors[i])


class Design(object):
    def __init__(self):
        self.equipment = {}       # id -> Equipment
        self.pipelines = {}       # id -> Pipeline
        self.road_centre_lines = []   # (road_id, points, width)
        self.maxh2o = 50.0
        self.maxfl = 1e-4
        self.temp_limits = (-10.0, 60.0)

    def add(self, eid, model_id, x, y, orient=0):
        e = Equipment(eid, model_id, x, y, orient)
        if eid in self.equipment:
            raise ValueError('duplicate equipment ' + eid)
        self.equipment[eid] = e
        return e

    def add_pipe(self, pid, frm, to, dn, cls, points, levels, corridors=None,
                 service='gas'):
        if pid in self.pipelines:
            raise ValueError('duplicate pipeline ' + pid)
        p = Pipeline(pid, frm, to, dn, cls, points, levels, corridors, service)
        self.pipelines[pid] = p
        return p

    # ---- port resolution -------------------------------------------------
    def port_xy(self, ref):
        kind, pid = ref
        if kind.startswith('IFACE:'):
            iid = kind.split(':', 1)[1]
            for it in C.site['external_interfaces']:
                if it['interface_id'] == iid:
                    return tuple(it['point_m'])
            raise KeyError(iid)
        if kind not in self.equipment:
            raise KeyError(kind)
        return self.equipment[kind].port_xy(pid)

    def port_refs(self):
        """all interface ports available for piping"""
        out = {}
        for it in C.site['external_interfaces']:
            if it['port_type'] in ('gas_bidirectional', 'gas_in', 'gas_out',
                                   'drain_in', 'drain_out'):
                out['IFACE:%s' % it['interface_id']] = it
        return out

    # ---- equipment port internal topology --------------------------------
    def eq_in_ports(self, e):
        t = {'compressor': ['suction'], 'separator': ['gas_in'], 'filter': ['gas_in'],
             'dehydration': ['gas_in'], 'cooler': ['gas_in'], 'heater': ['gas_in'],
             'regulator': ['gas_in'], 'meter': ['gas_in'], 'closed_drain': ['drain_in']}
        if e.category == 'header':
            return [p['id'] for p in e.m['ports']]
        return t[e.category]

    def eq_out_ports(self, e):
        t = {'compressor': ['discharge'], 'separator': ['gas_out', 'liquid_out'],
             'filter': ['gas_out', 'liquid_out'], 'dehydration': ['gas_out'],
             'cooler': ['gas_out'], 'heater': ['gas_out'], 'regulator': ['gas_out'],
             'meter': ['gas_out'], 'closed_drain': ['drain_out']}
        if e.category == 'header':
            return [p['id'] for p in e.m['ports']]
        return t[e.category]


# --------------------------------------------------------------------------
# LCC helpers
# --------------------------------------------------------------------------

def pvf():
    i = C.econ['discount_rate']
    n = C.econ['project_life_years']
    if i == 0:
        return float(n)
    return (1.0 - (1.0 + i) ** (-n)) / i
