"""Run all calculations and emit the project deliverables."""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import checks_geom
import costing
import design as design_mod
import engine
import process
from engine import C

OUT = os.path.abspath(os.path.join(HERE, '..', 'deliverables'))
WGS = process.WG_LIST


def fmt(x, n=3):
    return ('%.' + str(n) + 'f') % x


def build_all():
    d = design_mod.build()
    scen = {s['scenario_id']: s for s in C.scenarios}
    order = ['INJ-LOW', 'INJ-MID', 'INJ-HIGH', 'WDR-HIGH', 'WDR-MID', 'WDR-LOW']

    # ---------------- geometry -------------------------------------------------
    gerr, gwarn, ginfo = checks_geom.check_geometry(d)

    # ---------------- normal cases --------------------------------------------
    cases, results, viols = {}, {}, {}
    for sid in order:
        case = process.build_case(d, scen[sid])
        res = process.solve(d, case)
        cases[sid] = case
        results[sid] = res
        viols[sid] = (process.check_case(d, case, res) + process.check_pipes(d, case, res))

    energy_mwh = {sid: sum(results[sid]['energies'].values()) * scen[sid]['annual_hours']
                  for sid in order}

    # ---------------- reliability cases ---------------------------------------
    n1 = []
    rel_specs = []
    for sid in ['INJ-LOW', 'INJ-MID', 'INJ-HIGH']:
        for f in ('INJ-C1', 'INJ-C2', 'INJ-C3'):
            rel_specs.append((sid, f, 'compressor outage - compressor N-1'))
    for f in ('INJ-C1', 'INJ-C2', 'INJ-C3'):
        rel_specs.append(('WDR-LOW', f, 'compressor outage - compressor N-1'))
    for sid in ['WDR-HIGH', 'WDR-MID', 'WDR-LOW']:
        for f in ('SEP-1', 'SEP-2', 'SEP-3', 'DEHY-1', 'DEHY-2', 'DEHY-3'):
            rel_specs.append((sid, f, 'treatment outage - withdrawal N-1'))
    for sid, f, why in rel_specs:
        case = process.build_case(d, scen[sid], 'n1', f)
        res = process.solve(d, case)
        v = process.check_case(d, case, res) + process.check_pipes(d, case, res)
        # retained capacity of the surviving equipment for the failed category
        if f.startswith('INJ-C'):
            cap = sum(d.equipment[e].m['capacity_kg_s']
                      for e in ('INJ-C1', 'INJ-C2', 'INJ-C3') if e != f)
        elif f.startswith('WDR-C'):
            cap = sum(d.equipment[e].m['capacity_kg_s']
                      for e in ('WDR-C1', 'WDR-C2') if e != f)
        elif f.startswith('SEP'):
            cap = sum(d.equipment['SEP-%s' % t].m['capacity_kg_s']
                      for t in '123' if t != f[-1])
        else:
            cap = sum(d.equipment['DEHY-%s' % t].m['capacity_kg_s']
                      for t in '123' if t != f[-1])
        need = 0.7 * scen[sid]['required_total_flow_kg_s']
        if cap < need - 1e-9:
            v = list(v) + ['retained capacity %.1f kg/s < required %.1f kg/s' % (cap, need)]
        c40 = res['eq'].get('INJ-C3')
        n1.append(dict(scenario=sid, failed=f, reason=why,
                       c40_suction_mpa=(round(c40['P_in'], 6) if c40 else None),
                       required_retained_flow_kg_s=round(need, 6),
                       retained_capacity_kg_s=cap,
                       capacity_margin_kg_s=round(cap - need, 6),
                       retained_flow_kg_s=case['required_flow'],
                       retained_fraction=case['required_flow'] / scen[sid]['required_total_flow_kg_s'],
                       violations=v,
                       delivered={iid: dict(P=st['P'], T=st['T'], w=st['w'], fl=st['fl'])
                                  for iid, st in res['delivery'].items()},
                       grid=dict(P=res['pipes']['P32']['P_out']) if 'P32' in res['pipes'] else None,
                       energy_mw=sum(res['energies'].values())))

    # ---------------- quantities and cost -------------------------------------
    q = costing.quantities(d)
    L = costing.lcc(d, energy_mwh)

    return d, scen, order, cases, results, viols, n1, q, L, gerr, ginfo


def write_json(path, obj):
    with open(path, 'w') as fh:
        json.dump(obj, fh, indent=2, sort_keys=False, default=str)


def equipment_register(d):
    rows = []
    for eid, e in sorted(d.equipment.items()):
        m = e.m
        rows.append(dict(
            instance_id=eid, model_id=e.model_id, category=e.category,
            safety_category=e.safety_category,
            centre_x_m=e.x, centre_y_m=e.y, orientation_deg=e.orient,
            footprint_length_m=m['footprint_m']['length'],
            footprint_width_m=m['footprint_m']['width'],
            rated_capacity_kg_s=m['capacity_kg_s'],
            capex_mbcu=m['capex_mbcu'],
            annual_maintenance_mbcu=m['annual_maintenance_mbcu'],
            maintenance_clearance_m=m['maintenance']['clearance_m'],
            heavy_maintenance=bool(m['maintenance'].get('heavy_maintenance')),
            road_access_required=bool(m['maintenance'].get('road_access_required')),
            crane_access_required=bool(m['maintenance'].get('crane_access_required')),
            required_maintenance_area_m2=round(e.maintenance_data()['area'], 3),
            ports=dict((p['id'], dict(type=p['type'],
                                      x_m=round(e.port_xy(p['id'])[0], 6),
                                      y_m=round(e.port_xy(p['id'])[1], 6)))
                       for p in m['ports']),
            catalogue_limits=dict(
                (k, v) for k, v in m.items()
                if k in ('maximum_pressure_mpa', 'pressure_drop_mpa',
                         'pressure_drop_at_capacity_mpa', 'maximum_branch_connections',
                         'maximum_suction_pressure_mpa', 'maximum_discharge_pressure_mpa',
                         'maximum_pressure_ratio', 'minimum_stable_flow_kg_s',
                         'efficiency_proxy', 'driver_efficiency', 'maximum_power_mw',
                         'maximum_suction_temperature_c', 'maximum_discharge_temperature_c',
                         'maximum_duty_mw', 'minimum_outlet_temperature_c',
                         'maximum_outlet_temperature_c', 'electric_power_fraction_of_duty',
                         'normal_outlet_water_mg_sm3', 'energy_mw_per_kg_s',
                         'maximum_feed_free_liquid_fraction', 'liquid_removal_efficiency',
                         'maximum_liquid_rate_kg_s', 'jt_temperature_coefficient_k_per_mpa'))))
    return rows


def pipeline_table(d):
    rows = []
    for pid, p in sorted(d.pipelines.items()):
        segs = []
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            segs.append(dict(level=lvl, corridor=cid,
                             points=[[round(a[0], 6), round(a[1], 6)],
                                     [round(b[0], 6), round(b[1], 6)]],
                             length_m=round(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5, 6)))
        rows.append(dict(pipeline_id=pid,
                         from_port='%s.%s' % (p.frm[0].replace('IFACE:', ''), p.frm[1]),
                         to_port='%s.%s' % (p.to[0].replace('IFACE:', ''), p.to[1]),
                         service=p.service, nominal_diameter=p.dn,
                         internal_diameter_m=p.D, pipe_class=p.cls,
                         roughness_m=p.eps, total_length_m=round(p.length, 6),
                         segments=segs))
    return rows


def svg_layout(d, path):
    SX, SY = 700.0, 450.0
    W, H = 980, 640
    sc = min((W - 40) / SX, (H - 40) / SY)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d">' % (W, H, W, H),
           '<rect width="100%" height="100%" fill="white"/>',
           '<g transform="translate(20,%d) scale(%f,%f)">'
           % (H - 20, sc, -sc)]
    site = C.site['boundary_polygon_m']
    out.append('<polygon points="%s" fill="#f7f9fc" stroke="#333" stroke-width="1.2"/>'
               % ' '.join('%f,%f' % (p[0], p[1]) for p in site))
    for z in C.site['no_build_zones']:
        cols = []
        if z.get('equipment_exclusion'):
            cols.append('#f6d7d7')
        if z.get('pipeline_exclusion'):
            cols.append('#e8d7f6')
        fill = cols[0] if cols else 'none'
        out.append('<polygon points="%s" fill="%s" fill-opacity="0.7" stroke="#b06" '
                   'stroke-width="0.6"/>'
                   % (' '.join('%f,%f' % (p[0], p[1]) for p in z['polygon_m']), fill))
        out.append('<text x="%f" y="%f" font-size="9" fill="#a05" transform="scale(1,-1)">%s</text>'
                   % (z['polygon_m'][0][0] + 2, -(z['polygon_m'][0][1] + 10), z['zone_id']))
    for c in C.site['routing_corridors']:
        out.append('<polygon points="%s" fill="none" stroke="#0aa" stroke-dasharray="4,3" '
                   'stroke-width="0.8"/>'
                   % ' '.join('%f,%f' % (p[0], p[1]) for p in c['polygon_m']))
    for rid, pts, w in d.road_centre_lines:
        out.append('<polyline points="%s" fill="none" stroke="#666" stroke-width="%f" '
                   'stroke-linecap="square"/>'
                   % (' '.join('%f,%f' % p for p in pts), w))
    col = {'ground': '#1f77b4', 'buried': '#8c564b', 'rack_low': '#2ca02c',
           'rack_high': '#9467bd'}
    for pid, p in sorted(d.pipelines.items()):
        c = '#d62728' if p.service == 'liquid_drain' else col[p.levels[0]]
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.1" '
                   'fill-opacity="0.9"/>'
                   % (' '.join('%f,%f' % q for q in p.points), c))
    for eid, e in sorted(d.equipment.items()):
        fp = e.fp
        out.append('<polygon points="%s" fill="#ffd27f" stroke="#7a4b00" stroke-width="0.7"/>'
                   % ' '.join('%f,%f' % q for q in fp))
        out.append('<text x="%f" y="%f" font-size="7.5" fill="#3a2400" '
                   'transform="scale(1,-1)">%s</text>'
                   % (e.x - 8, -(e.y - 1), eid))
    for iid, it in [(x['interface_id'], x) for x in C.site['external_interfaces']]:
        x, y = it['point_m']
        out.append('<circle cx="%f" cy="%f" r="2.2" fill="#111"/>' % (x, y))
        out.append('<text x="%f" y="%f" font-size="7.5" fill="#111" '
                   'transform="scale(1,-1)">%s</text>' % (x + 3, -(y + 3), iid))
    out.append('</g>')
    out.append('<g font-family="sans-serif" font-size="11">'
               '<text x="20" y="16">UGS-SYNTH-D01 v1.1 proposed design - plan view '
               '(metres); blue=ground gas, red=liquid drain, grey=roads</text></g>')
    out.append('</svg>')
    open(path, 'w').write('\n'.join(out))






def active_stages(d, case):
    """ordered stages of the active flow path(s) for one operating case"""
    flows = case['flows']
    nodes = set(d.equipment)
    for p in d.pipelines.values():
        for ref in (p.frm, p.to):
            if ref[0].startswith('IFACE:'):
                nodes.add(ref[0])
    edges = {}
    for pid, m in flows.items():
        if m == 0.0:
            continue
        p = d.pipelines[pid]
        u, v = (p.frm, p.to) if m > 0 else (p.to, p.frm)
        edges.setdefault(u[0], []).append(v[0])
    indeg = {n: 0 for n in nodes}
    for u in edges:
        for v in edges[u]:
            indeg[v] = indeg.get(v, 0) + 1
    depth = {n: 0 for n in nodes}
    changed = True
    while changed:
        changed = False
        for u in edges:
            for v in edges[u]:
                if depth[v] < depth[u] + 1:
                    depth[v] = depth[u] + 1
                    changed = True
    stages = {}
    for n in nodes:
        if indeg.get(n, 0) == 0 and not edges.get(n):
            continue                      # unused boundary
        if n not in edges and indeg.get(n, 0) == 0:
            continue
        if indeg.get(n, 0) == 0 and n.startswith('IFACE:'):
            stages.setdefault(0, []).append(n.replace('IFACE:', ''))
        elif n in edges or indeg.get(n, 0) > 0:
            stages.setdefault(depth[n], []).append(n.replace('IFACE:', ''))
    return [sorted(stages[k]) for k in sorted(stages)]


def main():
    import report as report_mod
    import csv as _csv
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    d, scen, order, cases, results, viols, n1, q, L, gerr, ginfo = build_all()

    write_json(os.path.join(OUT, 'equipment_register.json'), equipment_register(d))
    write_json(os.path.join(OUT, 'process_topology.json'),
               dict(interfaces=C.site['external_interfaces'],
                    routing_corridors=C.site['routing_corridors'],
                    no_build_zones=C.site['no_build_zones'],
                    pipelines=pipeline_table(d)))
    write_json(os.path.join(OUT, 'quantities.json'), q)
    write_json(os.path.join(OUT, 'lcc.json'), L)

    ops = {}
    for sid in order:
        c, r = cases[sid], results[sid]
        ops[sid] = dict(
            scenario=c['scen'],
            active_equipment=sorted(r['eq'].keys()),
            setpoints={k: v.get('value') for k, v in c['params'].items()},
            active_stages=active_stages(d, c),
            pipeline_flows={pid: m for pid, m in sorted(c['flows'].items()) if m != 0.0},
            pipeline_hydraulics={pid: dict((k, round(v, 6) if isinstance(v, float) else v)
                                           for k, v in st.items())
                                 for pid, st in sorted(r['pipes'].items())},
            equipment={eid: dict((k, round(v, 6) if isinstance(v, float) else v)
                                 for k, v in st.items())
                       for eid, st in sorted(r['eq'].items())},
            delivered={iid: dict((k, round(v, 6)) for k, v in st.items())
                       for iid, st in r['delivery'].items()},
            energy_mw={k: round(v, 6) for k, v in sorted(r['energies'].items())},
            annual_energy_mwh=round(sum(r['energies'].values()) * c['hours'], 3),
            checks_passed=(len(viols[sid]) == 0),
            exceptions=viols[sid])
    write_json(os.path.join(OUT, 'scenario_operations.json'), ops)

    # informative contingency (not a published requirement): the C40 running in
    # withdrawal service with one C60 unavailable in WDR-HIGH
    cont = process.build_case(d, scen['WDR-HIGH'], 'n1', 'INJ-C1')
    cres = process.solve(d, cont)
    c40p = cres['eq']['INJ-C3']['P_in'] if 'INJ-C3' in cres['eq'] else None
    contingency = dict(description=('C40 in withdrawal service with one C60 unavailable in '
                                    'WDR-HIGH (no published N-1 requirement; informative)'),
                       c40_suction_mpa=(round(c40p, 6) if c40p else None),
                       c40_suction_limit_mpa=d.equipment['INJ-C3'].m['maximum_suction_pressure_mpa'],
                       retained_flow_kg_s=cont['required_flow'],
                       grid_tie_pressure_mpa=round(cres['delivery']['GRID-TIE']['P'], 6),
                       exceptions=(process.check_case(d, cont, cres) +
                                   process.check_pipes(d, cont, cres)))
    rel = dict(requirement=C.req['reliability_requirements'], cases=n1,
               informative_contingencies=[contingency])
    write_json(os.path.join(OUT, 'reliability_cases.json'), rel)

    reg = equipment_register(d)
    keys = ['instance_id', 'model_id', 'category', 'safety_category', 'centre_x_m',
            'centre_y_m', 'orientation_deg', 'footprint_length_m', 'footprint_width_m',
            'rated_capacity_kg_s', 'capex_mbcu', 'annual_maintenance_mbcu',
            'maintenance_clearance_m', 'heavy_maintenance', 'road_access_required',
            'crane_access_required', 'required_maintenance_area_m2']
    with open(os.path.join(OUT, 'equipment_register.csv'), 'w', newline='') as fh:
        w = _csv.DictWriter(fh, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        for r in reg:
            w.writerow(r)
    with open(os.path.join(OUT, 'pipeline_schedule.csv'), 'w', newline='') as fh:
        w = _csv.writer(fh)
        w.writerow(['pipeline_id', 'from_port', 'to_port', 'service', 'nominal_diameter',
                    'internal_diameter_m', 'pipe_class', 'length_m', 'segments_json'])
        for row in pipeline_table(d):
            w.writerow([row['pipeline_id'], row['from_port'], row['to_port'], row['service'],
                        row['nominal_diameter'], row['internal_diameter_m'], row['pipe_class'],
                        round(row['total_length_m'], 3), json.dumps(row['segments'])])

    svg_layout(d, os.path.join(OUT, 'layout.svg'))

    with open(os.path.join(OUT, 'well_group_allocations.csv'), 'w', newline='') as fh:
        w = _csv.writer(fh)
        w.writerow(['scenario'] + WGS + ['total'])
        for sid in order:
            c = cases[sid]
            vals = [abs(c['flows'][process.BRANCH_OF_WG[wg]]) for wg in WGS]
            w.writerow([sid] + ['%.6f' % v for v in vals] + ['%.6f' % sum(vals)])

    import selftest
    mutations = selftest.run()
    val = dict(validator_self_check=mutations,
               geometry_errors=gerr,
               geometry_rules=ginfo.get('rules'),
               geometry_contingency=contingency,
               geometry_info=dict(road_length_m=ginfo.get('road_length_m'),
                                  maintenance_area_m2=ginfo.get('maint_area'),
                                  access_clearances_m=ginfo.get('access')),
               scenario_violations={k: v for k, v in viols.items()},
               reliability_violations={('%s|%s' % (x['scenario'], x['failed'])): x['violations']
                                       for x in n1},
               all_scenarios_clean=all(len(v) == 0 for v in viols.values()),
               all_reliability_cases_clean=all(len(x['violations']) == 0 for x in n1))
    write_json(os.path.join(OUT, 'validation_results.json'), val)

    report_mod.report(d, scen, order, cases, results, viols, n1, q, L, gerr, ginfo, OUT, rel)
    report_mod.validation_md(d, gerr, ginfo, viols, n1, order, OUT, mutations, rel)
    print('LCC = %.4f MBCU; scenario exceptions = %d; reliability exceptions = %d; '
          'mutation tests detected %d/%d'
          % (L['lcc_mbcu'], sum(len(v) for v in viols.values()),
             sum(len(x['violations']) for x in n1),
             sum(1 for m in mutations if m['detected']), len(mutations)))
    return d, L


if __name__ == '__main__':
    main()
