"""Plan-view geometry, layout, separation, road and pipeline-route checks.

Each rule is evaluated independently and its outcome is recorded so that the
validation report can publish computed pass/fail statuses rather than asserted ones.
"""

from engine import (C, GEOM_TOL, hypot, point_in_poly, poly_area, poly_poly_dist,
                    positive_overlap, rect_poly, seg_inside_convex_len, seg_len,
                    seg_seg_dist, collinear_overlap_len, rot_pt)


def site_poly():
    return [tuple(p) for p in C.site['boundary_polygon_m']]


def zone_polys(flag):
    out = []
    for z in C.site['no_build_zones']:
        if z.get(flag):
            out.append((z['zone_id'], [tuple(p) for p in z['polygon_m']]))
    return out


def corridor_polys():
    out = {}
    for c in C.site['routing_corridors']:
        out[c['corridor_id']] = dict(poly=[tuple(p) for p in c['polygon_m']],
                                     levels=set(c['allowed_routing_levels']),
                                     co=c['allows_co_routing'])
    return out


def road_parts(design):
    """paved geometry of every road as a list of convex quads.

    The paving is the centreline swept by half the width on both sides, with
    square joins at interior vertices (mitered joins for perpendicular roads).
    """
    parts = []
    for rid, pts, w in design.road_centre_lines:
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = hypot(dx, dy)
            ux, uy = dx / L, dy / L
            nx, ny = -uy * w / 2.0, ux * w / 2.0
            # end caps: the swept paving includes the ends of the centreline
            e0 = -w / 2.0 if i == 0 else 0.0
            e1 = w / 2.0 if i == len(pts) - 2 else 0.0
            a0 = (a[0] + ux * e0, a[1] + uy * e0)
            b0 = (b[0] + ux * e1, b[1] + uy * e1)
            parts.append((rid, [(a0[0] + nx, a0[1] + ny), (b0[0] + nx, b0[1] + ny),
                                (b0[0] - nx, b0[1] - ny), (a0[0] - nx, a0[1] - ny)]))
        for v in pts[1:-1]:
            parts.append((rid, rect_poly(v[0], v[1], w, w, 0)))
    return parts


def check_geometry(design):
    """returns (errors, warnings, info) with info['rules'] = per-rule outcomes"""
    err, warn = [], []
    info = {}
    rules = []

    def mark(name, first, detail=''):
        rules.append(dict(rule=name,
                          status='pass' if len(err) == first else 'FAIL',
                          detail=detail))

    site = site_poly()
    eq_zones = zone_polys('equipment_exclusion')
    pipe_zones = zone_polys('pipeline_exclusion')
    road_zones = zone_polys('road_exclusion')
    eqs = list(design.equipment.values())

    # 1 ------------------------------------------------------- footprints
    first = len(err)
    for e in eqs:
        fp = e.fp
        for v in fp:
            if not point_in_poly(v, site, strict=False):
                err.append('%s: footprint outside site at %s' % (e.id, v))
                break
    mark('equipment footprint inside the site boundary', first,
         '%d instances checked against the site polygon' % len(eqs))

    first = len(err)
    for e in eqs:
        for zid, zp in eq_zones:
            if positive_overlap(e.fp, zp):
                err.append('%s: footprint overlaps equipment_exclusion %s' % (e.id, zid))
    mark('footprints outside equipment-exclusion interiors', first,
         '%d no-build zones tested' % len(eq_zones))

    first = len(err)
    for i in range(len(eqs)):
        for j in range(i + 1, len(eqs)):
            if positive_overlap(eqs[i].fp, eqs[j].fp):
                err.append('footprints overlap: %s / %s' % (eqs[i].id, eqs[j].id))
    mark('no positive-area overlap between footprints', first,
         '%d footprint pairs tested' % (len(eqs) * (len(eqs) - 1) // 2))

    # 2 ------------------------------------------------------- separations
    first = len(err)
    worst = None
    for i in range(len(eqs)):
        for j in range(i + 1, len(eqs)):
            a, b = eqs[i], eqs[j]
            need = C.safety['minimum_separation_m'][a.safety_category][b.safety_category]
            sep = poly_poly_dist(a.fp, b.fp)
            info.setdefault('sep', {})[(a.id, b.id)] = (sep, need)
            if worst is None or sep - need < worst[0]:
                worst = (sep - need, a.id, b.id, sep, need)
            if sep < need - GEOM_TOL:
                err.append('separation %s/%s = %.3f m < required %.1f m'
                           % (a.id, b.id, sep, need))
    mark('minimum separation matrix satisfied for every equipment pair', first,
         'closest pair %s/%s: %.2f m against %.1f m required'
         % (worst[1], worst[2], worst[3], worst[4]))

    # 3 ------------------------------------------------ maintenance envelopes
    first = len(err)
    for e in eqs:
        md = e.maintenance_data()
        info.setdefault('maint_area', {})[e.id] = md['area']
        for tag, mp in zip(('clearance', 'removal'), e.maintenance_polys()):
            for v in mp:
                if not point_in_poly(v, site, strict=False):
                    err.append('%s: %s envelope outside site at %s' % (e.id, tag, v))
                    break
            for zid, zp in eq_zones:
                if positive_overlap(mp, zp):
                    err.append('%s: %s envelope overlaps equipment_exclusion %s'
                               % (e.id, tag, zid))
            for o in eqs:
                if o.id == e.id:
                    continue
                if positive_overlap(mp, o.fp):
                    err.append('%s: maintenance envelope overlaps footprint of %s'
                               % (e.id, o.id))
    mark('required maintenance envelopes inside site, clear of exclusions and footprints',
         first)

    # 4 ------------------------------------------------------- roads
    parts = road_parts(design)
    first = len(err)
    for rid, pts, w in design.road_centre_lines:
        if w < 4.0 - 1e-9:
            err.append('road %s width %.2f m < 4 m' % (rid, w))
    mark('road width at least 4 m', first)

    first = len(err)
    for rid, quad in parts:
        for v in quad:
            if not point_in_poly(v, site, strict=False):
                err.append('road %s paved geometry outside site at %s' % (rid, v))
                break
    mark('paved road geometry inside the site boundary', first)

    first = len(err)
    for rid, quad in parts:
        for zid, zp in road_zones:
            if positive_overlap(quad, zp):
                err.append('road %s paved geometry in road_exclusion %s' % (rid, zid))
    mark('paved road geometry outside road-exclusion interiors', first)

    first = len(err)
    for rid, quad in parts:
        for e in eqs:
            if positive_overlap(quad, e.fp):
                err.append('road %s paved geometry overlaps footprint of %s' % (rid, e.id))
    mark('paved road geometry clear of equipment footprints', first)

    first = len(err)
    n = len(parts)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if positive_overlap(parts[i][1], parts[j][1]) or \
               poly_poly_dist(parts[i][1], parts[j][1]) <= GEOM_TOL:
                union(i, j)
    comps = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    ent = [it for it in C.site['external_interfaces']
           if it['interface_id'] == 'ROAD-ENTRANCE'][0]
    ep = tuple(ent['point_m'])
    ent_part = None
    for i, (rid, quad) in enumerate(parts):
        if point_in_poly(ep, quad, strict=False):
            ent_part = i
            break
    if ent_part is None:
        err.append('ROAD-ENTRANCE point is not on any paved road geometry')
    elif len(comps) > 1:
        err.append('road network has %d disconnected components' % len(comps))
    info['road_length_m'] = sum(seg_len(p[i], p[i + 1])
                                for _, p, _ in design.road_centre_lines
                                for i in range(len(p) - 1))
    mark('road network connected and containing ROAD-ENTRANCE', first,
         '%d paved parts in %d component(s), centreline length %.0f m'
         % (n, len(comps), info['road_length_m']))

    first = len(err)
    for e in eqs:
        road_req, crane_req = e.maintenance_flags()
        if not (road_req or crane_req):
            continue
        dmin = min(poly_poly_dist(mp, q) for mp in e.maintenance_polys()
                   for _, q in parts)
        limit = (C.maint['crane_access_buffer_m'] if crane_req
                 else C.maint['road_access_buffer_m'])
        info.setdefault('access', {})[e.id] = dmin
        if dmin > limit + GEOM_TOL:
            err.append('%s: maintenance envelope to road distance %.2f m > %.2f m'
                       % (e.id, dmin, limit))
    mark('road-access and crane-access buffers to required maintenance envelopes', first,
         ', '.join('%s %.2f m' % (k, v) for k, v in sorted(info['access'].items())))

    # 5 ------------------------------------------------------- pipelines
    corr = corridor_polys()
    used_ports = {}
    first = len(err)
    for p in design.pipelines.values():
        pa = design.port_xy(p.frm)
        pb = design.port_xy(p.to)
        if seg_len(p.points[0], pa) > GEOM_TOL:
            err.append('%s: start %s does not match port %s' % (p.id, p.points[0], pa))
        if seg_len(p.points[-1], pb) > GEOM_TOL:
            err.append('%s: end %s does not match port %s' % (p.id, p.points[-1], pb))
        for k in (p.frm, p.to):
            used_ports.setdefault(k, []).append(p.id)
    mark('pipeline endpoints coincide with their port coordinates (1e-6 m)', first)

    first = len(err)
    for p in design.pipelines.values():
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            L = seg_len(a, b)
            if L <= GEOM_TOL:
                err.append('%s: segment %d length <= tolerance' % (p.id, i))
            if L > 1e6:
                err.append('%s: segment %d implausible' % (p.id, i))
    mark('every route segment longer than the geometry tolerance', first,
         '%d pipelines, %d segments, %.0f m total'
         % (len(design.pipelines), sum(len(p.points) - 1 for p in design.pipelines.values()),
            sum(p.length for p in design.pipelines.values())))

    first = len(err)
    for p in design.pipelines.values():
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            if not (point_in_poly(a, site, strict=False) and
                    point_in_poly(b, site, strict=False)):
                err.append('%s: segment %d outside site' % (p.id, i))
    mark('route segments within the site boundary', first,
         '%d segments tested against the site polygon' % sum(len(p.points) - 1 for p in design.pipelines.values()))

    first = len(err)
    for p in design.pipelines.values():
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            for zid, zp in pipe_zones:
                if seg_inside_convex_len(a, b, zp) > GEOM_TOL:
                    err.append('%s: segment %d enters pipeline_exclusion %s'
                               % (p.id, i, zid))
    mark('route segments outside pipeline-exclusion interiors', first)

    first = len(err)
    for p in design.pipelines.values():
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            for e in eqs:
                if seg_inside_convex_len(a, b, e.fp) > GEOM_TOL:
                    err.append('%s: segment %d crosses footprint of %s' % (p.id, i, e.id))
    mark('route segments do not cross equipment-footprint interiors', first)

    first = len(err)
    for p in design.pipelines.values():
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            if cid is None:
                continue
            if cid not in corr:
                err.append('%s: unknown corridor %s' % (p.id, cid))
                continue
            cd = corr[cid]
            if lvl not in cd['levels']:
                err.append('%s: level %s not allowed in corridor %s' % (p.id, lvl, cid))
            if seg_inside_convex_len(a, b, cd['poly']) < seg_len(a, b) - GEOM_TOL:
                err.append('%s: segment %d not inside corridor %s' % (p.id, i, cid))
    mark('declared corridors contain their segments and allow their levels', first,
         'no segment declares a corridor in this design')

    first = len(err)
    segs = []
    for p in design.pipelines.values():
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            segs.append((p.id, i, a, b, lvl, cid))
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            p1, k1, a1, b1, l1, c1 = segs[i]
            p2, k2, a2, b2, l2, c2 = segs[j]
            if l1 != l2:
                continue
            ov = collinear_overlap_len(a1, b1, a2, b2)
            if ov <= GEOM_TOL:
                continue
            shared = (c1 is not None and c1 == c2 and corr.get(c1, {}).get('co'))
            if not shared:
                err.append('same-level overlap %.3f m: %s seg%d / %s seg%d (%s)'
                           % (ov, p1, k1, p2, k2, l1))
    mark('no positive-length same-level route overlap (including self-overlap)', first)

    first = len(err)
    for ref, pids in used_ports.items():
        kind, port = ref
        if kind.startswith('IFACE:'):
            iid = kind.split(':', 1)[1]
            it = [x for x in C.site['external_interfaces'] if x['interface_id'] == iid][0]
            lim = it.get('maximum_connections', 1)
        else:
            lim = 1
            for pt in design.equipment[kind].m['ports']:
                if pt['id'] == port:
                    lim = pt.get('maximum_connections', 1)
        if len(pids) > lim:
            err.append('port %s.%s has %d connections (limit %d)'
                       % (kind, port, len(pids), lim))
    mark('port connection cardinality within published limits', first,
         '%d connected ports tested' % len(used_ports))

    first = len(err)
    for p in design.pipelines.values():
        tt = port_type_of(design, p.frm)
        tf = port_type_of(design, p.to)
        ok = ((tt == 'gas_out' and tf in ('gas_in', 'gas_bidirectional')) or
              (tt == 'gas_bidirectional' and tf in ('gas_in', 'gas_bidirectional')) or
              (tt == 'liquid_out' and tf == 'drain_in') or
              (tt == 'drain_out' and tf == 'drain_in'))
        if not ok:
            err.append('%s: incompatible port pair %s -> %s' % (p.id, tt, tf))
    mark('port-type compatibility of every physical connection', first)

    info['rules'] = rules
    return err, warn, info


def port_type_of(design, ref):
    kind, port = ref
    if kind.startswith('IFACE:'):
        iid = kind.split(':', 1)[1]
        it = [x for x in C.site['external_interfaces'] if x['interface_id'] == iid][0]
        return it['port_type']
    return design.equipment[kind].port_type(port)
