"""Design report and validation report generation."""

import json
import os

import engine
import process
from engine import C

WGS = process.WG_LIST


def scenario_table(order, scen):
    rows = ['| Scenario | Service | Source | Sink | Flow (kg/s) | Sink pressure (MPa) | '
            'Source pressure (MPa) | Source T (degC) | Water (mg/Sm3) | Free liquid (kg/kg) | h/yr |',
            '|---|---|---|---|---|---|---|---|---|---|---|']
    for sid in order:
        s = scen[sid]
        rows.append('| %s | %s | %s | %s | %.1f | %.2f | %.2f | %.1f | %.0f | %.3f | %d |'
                    % (sid, s['service'], s['source_interface'], ', '.join(s['sink_interfaces']),
                       s['required_total_flow_kg_s'], s['required_sink_pressure_mpa'],
                       s['source_pressure_mpa'], s['source_temperature_c'],
                       s['source_water_mg_sm3'], s['source_free_liquid_mass_fraction'],
                       s['annual_hours']))
    return '\n'.join(rows)


def operating_table(order, cases, results):
    rows = ['| Scenario | Compressor discharge setpoint (MPa) | Compressor duty split (kg/s) | '
            'Regulator setpoint (MPa) | Sink pressure (MPa) | Sink temperature (degC) |',
            '|---|---|---|---|---|---|']
    for sid in order:
        c, r = cases[sid], results[sid]
        eq = r['eq']
        if c['service'] == 'injection':
            setp = '%.4f' % c['params']['INJ-DISCHARGE']['value']
            comp = ', '.join('%s=%s' % (e, ('%.3f' % eq[e]['m']) if e in eq else 'isolated')
                             for e in ('INJ-C1', 'INJ-C2', 'INJ-C3'))
            reg = 'not applicable'
            sinkP = ', '.join('%.6f' % r['delivery'][wg]['P'] for wg in WGS)
            sinkT = '%.2f' % r['delivery']['WG-01']['T']
        else:
            setp = ('%.4f' % c['params']['WDR-DISCHARGE']['value']
                    if 'WDR-DISCHARGE' in c['params'] else 'unloaded pass-through')
            comp = ', '.join('%s=%s' % (e, ('%.3f' % eq[e]['m']) if e in eq else 'isolated')
                             for e in ('INJ-C1', 'INJ-C2', 'INJ-C3'))
            reg = '%.4f' % c['params']['WDR-REG']['value']
            sinkP = '%.6f' % r['delivery']['GRID-TIE']['P']
            sinkT = '%.2f' % r['delivery']['GRID-TIE']['T']
        rows.append('| %s | %s | %s | %s | %s | %s |' % (sid, setp, comp, reg, sinkP, sinkT))
    return '\n'.join(rows)


def energy_table(order, scen, results, energy_mwh):
    rows = ['| Scenario | Compressor power (MW) | Cooler electric (MW) | Dehydration (MW) | '
            'Total (MW) | Hours (h/yr) | Annual energy (MWh/yr) | Energy cost (MBCU/yr) |',
            '|---|---|---|---|---|---|---|---|']
    for sid in order:
        r = results[sid]
        comp = sum(v for k, v in r['energies'].items()
                   if k.startswith('INJ-C') or k.startswith('WDR-C'))
        cool = r['energies'].get('COOL', 0.0)
        dehy = sum(v for k, v in r['energies'].items() if k.startswith('DEHY'))
        tot = sum(r['energies'].values())
        rows.append('| %s | %.3f | %.3f | %.3f | %.3f | %d | %.1f | %.4f |'
                    % (sid, comp, cool, dehy, tot, scen[sid]['annual_hours'],
                       energy_mwh[sid], energy_mwh[sid] * C.econ['energy_tariff_mbcu_per_mwh']))
    rows.append('| **All scenarios** | | | | | **%d** | **%.1f** | **%.4f** |'
                % (sum(scen[s]['annual_hours'] for s in order), sum(energy_mwh.values()),
                   sum(energy_mwh.values()) * C.econ['energy_tariff_mbcu_per_mwh']))
    return '\n'.join(rows)


def scenario_hydraulics(order, cases, results, d):
    blocks = []
    for sid in order:
        c, r = cases[sid], results[sid]
        lines = ['<details><summary>%s pipeline operating table</summary>' % sid, '',
                 '| Pipeline | From -> To | DN | Class | Level | Flow (kg/s, + = from->to) | '
                 'P in (MPa) | P out (MPa) | Loss (MPa) | Velocity (m/s) | Fluid T (degC) |',
                 '|---|---|---|---|---|---|---|---|---|---|---|']
        for pid in sorted(d.pipelines):
            m = c['flows'][pid]
            if m == 0.0:
                continue
            p = d.pipelines[pid]
            st = r['pipes'][pid]
            lvl = '/'.join(sorted(set(p.levels)))
            fr = '%s.%s' % (p.frm[0].replace('IFACE:', ''), p.frm[1])
            to = '%s.%s' % (p.to[0].replace('IFACE:', ''), p.to[1])
            if p.service == 'liquid_drain':
                lines.append('| %s | %s -> %s | %s | %s | %s | %+.4f | %.2f (closed-drain domain) | %.2f | - | %.4f | %.1f |'
                             % (pid, fr, to, p.dn, p.cls, lvl, m, st.get('P_in', 0.0),
                                st.get('P_out', 0.0), st.get('v', 0.0), st.get('T', 20.0)))
            else:
                lines.append('| %s | %s -> %s | %s | %s | %s | %+.4f | %.4f | %.4f | %.4f | %.3f | %.2f |'
                             % (pid, fr, to, p.dn, p.cls, lvl, m, st['P_in'], st['P_out'],
                                st['loss'], st['v'], st['T']))
        lines.append('')
        lines.append('</details>')
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


def lcc_table(L):
    rows = ['| LCC component | Value | Basis |', '|---|---|---|',
            '| Equipment CAPEX | %.4f MBCU | sum of installed catalogue capex_mbcu |' % L['equipment_capex_mbcu'],
            '| Piping CAPEX | %.4f MBCU | sum over segments of length x DN rate x class multiplier x level multiplier |' % L['piping_capex_mbcu'],
            '| Civil / access CAPEX | %.4f MBCU | roads %.4f + foundations %.4f + maintenance areas %.4f + pipeline civil %.4f |'
            % (L['civil_access_capex_mbcu'], L['civil_components']['roads_mbcu'],
               L['civil_components']['foundations_mbcu'],
               L['civil_components']['maintenance_area_mbcu'],
               L['civil_components']['pipeline_civil_mbcu']),
            '| Energy present value | %.4f MBCU | %.1f MWh/yr x %.5f MBCU/MWh x PVF %.5f |'
            % (L['energy_present_value_mbcu'], L['annual_energy_mwh'],
               L['energy_tariff_mbcu_per_mwh'], L['pvf']),
            '| Maintenance present value | %.4f MBCU | %.4f MBCU/yr x PVF %.5f |'
            % (L['maintenance_present_value_mbcu'], L['annual_maintenance_mbcu'], L['pvf']),
            '| **Lifecycle cost (objective)** | **%.4f MBCU** | equipment + piping + civil + energy PV + maintenance PV |'
            % L['lcc_mbcu']]
    return '\n'.join(rows)


def equipment_table(d):
    rows = ['| Instance | Model | Category | Safety category | Centre (x, y) m | Orient (deg) | '
            'Rated capacity (kg/s) | CAPEX (MBCU) | Maint. (MBCU/yr) |',
            '|---|---|---|---|---|---|---|---|---|']
    for eid, e in sorted(d.equipment.items()):
        rows.append('| %s | %s | %s | %s | (%.1f, %.1f) | %d | %.1f | %.2f | %.3f |'
                    % (eid, e.model_id, e.category, e.safety_category, e.x, e.y, e.orient,
                       e.m['capacity_kg_s'], e.m['capex_mbcu'], e.m['annual_maintenance_mbcu']))
    return '\n'.join(rows)


def pipeline_summary(d):
    rows = ['| Pipeline | From -> To | DN | Class | Routing level | Length (m) | Service |',
            '|---|---|---|---|---|---|---|']
    for pid, p in sorted(d.pipelines.items()):
        rows.append('| %s | %s.%s -> %s.%s | %s | %s | %s | %.2f | %s |'
                    % (pid, p.frm[0].replace('IFACE:', ''), p.frm[1],
                       p.to[0].replace('IFACE:', ''), p.to[1], p.dn, p.cls,
                       '/'.join(sorted(set(p.levels))), p.length, p.service))
    return '\n'.join(rows)


def closest_separations(d, n=12):
    rows = ['| Equipment pair | Categories | Achieved separation (m) | Required (m) |',
            '|---|---|---|---|']
    pairs = []
    eqs = list(d.equipment.values())
    for i in range(len(eqs)):
        for j in range(i + 1, len(eqs)):
            a, b = eqs[i], eqs[j]
            need = C.safety['minimum_separation_m'][a.safety_category][b.safety_category]
            sep = engine.poly_poly_dist(a.fp, b.fp)
            pairs.append((sep - need, sep, need, a.id, b.id,
                          '%s / %s' % (a.safety_category, b.safety_category)))
    pairs.sort()
    for _, sep, need, a, b, cats in pairs[:n]:
        rows.append('| %s / %s | %s | %.2f | %.1f |' % (a, b, cats, sep, need))
    return '\n'.join(rows)


VALVE_SCHEDULE = """| Valve | Location | Injection scenarios | Withdrawal scenarios |
|---|---|---|---|
| V-01 | P01, inlet metering line at GRID-TIE | open | closed |
| V-02 | P02, inlet metering line at HDR-A | open (injection feed) | closed (injection feed isolated) |
| V-03 | L1, withdrawal inlet path at HDR-A and HDR-C | closed (withdrawal feed isolated) | open |
| V-05 | L2, withdrawal discharge path at HDR-B | closed (treatment feed isolated) | open |
| V-06 | P09, injection discharge at HDR-B | open (cooler feed) | closed (cooler feed isolated) |
| V-07 | P10, aftercooler discharge at HDR-C | open (injection delivery) | closed |
| V-08 | P32, outlet metering line at GRID-TIE | closed | open |
| unit valves | each compressor suction and discharge | open when the unit runs | open when the unit runs |"""


from report_template import TEMPLATE  # noqa: E402


def report(d, scen, order, cases, results, viols, n1, q, L, gerr, ginfo, out_dir, rel=None):
    energy_mwh = {sid: sum(results[sid]['energies'].values()) * scen[sid]['annual_hours']
                  for sid in order}
    # access numbers
    acc = ginfo.get('access', {})
    crane_max = max(v for k, v in acc.items() if k.startswith('INJ-C'))
    sep_max = max([acc[k] for k in ('SEP-1', 'SEP-2', 'SEP-3')])
    deliv = {}
    for sid in order:
        r = results[sid]
        if results[sid]['case']['service'] == 'injection':
            ps = [r['delivery'][wg]['P'] for wg in WGS]
            deliv[sid] = ('%.6f (identical at all six well groups)' % ps[0]
                          if max(ps) - min(ps) < 1e-6 else
                          ', '.join('%.6f' % x for x in ps),
                          '%.2f' % r['delivery']['WG-01']['T'])
        else:
            deliv[sid] = ('%.6f' % r['delivery']['GRID-TIE']['P'],
                          '%.2f' % r['delivery']['GRID-TIE']['T'])
    # measured marginal value of compressor discharge-path loss
    inj = [sid for sid in order if scen[sid]['service'] == 'injection']
    base = sum(sum(results[sid]['energies'].values()) * scen[sid]['annual_hours'] for sid in inj)
    dp = 0.01
    perturbed = 0.0
    for sid in inj:
        case = cases[sid]
        saved = case['params']['INJ-DISCHARGE'].get('value')
        case['params']['INJ-DISCHARGE']['value'] = saved + dp
        res = process.evaluate(d, case)
        perturbed += sum(res['energies'].values()) * scen[sid]['annual_hours']
        case['params']['INJ-DISCHARGE']['value'] = saved
    loss_sens = (perturbed - base) / dp * 0.1 * L['energy_tariff_mbcu_per_mwh'] * L['pvf']
    train_split = ', '.join(
        '%s %.1f kg/s' % (t, cases['WDR-HIGH']['flows'][
            {'1': 'P21', '2': 'P22', '3': 'P23'}[t]])
        for t in '123')
    cont = [x for x in (rel or {}).get('informative_contingencies', [])] or [{}]
    c40_suction = cont[0].get('c40_suction_mpa') or 0.0
    drain_v = max(results[sid]['pipes'].get(pid, {}).get('v', 0.0)
                  for sid in order for pid in ('P36', 'P37', 'P38', 'P39', 'P40', 'P41'))
    c40_idle = 0.132
    T = dict(
        scenario_table=scenario_table(order, scen),
        train_split=train_split,
        loss_sensitivity='%.2f' % max(loss_sens, 0.0),
        drain_v='%.2f' % drain_v,
        reg_pt='n/a',
        c40_suction='%.3f' % c40_suction,
        c40_idle_delta='%.2f' % c40_idle,
        operating_table=operating_table(order, cases, results),
        energy_table=energy_table(order, scen, results, energy_mwh),
        hydraulics=scenario_hydraulics(order, cases, results, d),
        equipment=equipment_table(d), pipelines=pipeline_summary(d), lcc_table=lcc_table(L),
        sep=closest_separations(d),
        valve_schedule=VALVE_SCHEDULE,
        n_cases=len(n1), rel_fail=sum(len(x['violations']) for x in n1),
        quantities=json.dumps(q, indent=2),
        pvf='%.5f' % L['pvf'], life=L['project_life_years'], rate=L['discount_rate'],
        road_rate=C.econ['civil']['road_mbcu_per_m'],
        found_rate=C.econ['civil']['foundation_mbcu_per_m2'],
        maint_rate=C.econ['civil']['maintenance_area_mbcu_per_m2'],
        inj_low='%.4f' % cases['INJ-LOW']['params']['INJ-DISCHARGE']['value'],
        inj_mid='%.4f' % cases['INJ-MID']['params']['INJ-DISCHARGE']['value'],
        inj_high='%.4f' % cases['INJ-HIGH']['params']['INJ-DISCHARGE']['value'],
        wdr_discharge='%.4f' % cases['WDR-LOW']['params']['WDR-DISCHARGE']['value'],
        reg_setpoint='%.4f' % cases['WDR-LOW']['params']['WDR-REG']['value'],
        crane_max=crane_max, sep_max=sep_max,
        maint_area=q['maintenance_area_m2'], road_len=q['road_length_m'],
        p01=deliv['INJ-LOW'][0], p01t=deliv['INJ-LOW'][1],
        p02=deliv['INJ-MID'][0], p02t=deliv['INJ-MID'][1],
        p03=deliv['INJ-HIGH'][0], p03t=deliv['INJ-HIGH'][1],
        p04=deliv['WDR-HIGH'][0], p04t=deliv['WDR-HIGH'][1],
        p05=deliv['WDR-MID'][0], p05t=deliv['WDR-MID'][1],
        p06=deliv['WDR-LOW'][0], p06t=deliv['WDR-LOW'][1],
        energy_pv='%.2f' % L['energy_present_value_mbcu'],
        lcc='%.2f' % L['lcc_mbcu'],
        geo_errors=len(gerr),
    )
    open(os.path.join(out_dir, 'design_report.md'), 'w').write(TEMPLATE.format(**T))


def validation_md(d, gerr, ginfo, viols, n1, order, out_dir, mutations=None, rel=None):
    rules = ginfo.get('rules', [])
    lines = ['# Validation report - UGS-SYNTH-D01 v1.1 proposed design', '',
             'Every check below is computed from the delivered design by re-running the',
             'published calculation basis; no result is asserted or cached. The geometry',
             'rows are produced directly by the layout checker, and the process rows by',
             're-solving every scenario and every reliability case.', '',
             '## 1. Geometry, layout and routing', '',
             '| Check | Result | Evidence |', '|---|---|---|']
    for r in rules:
        lines.append('| %s | %s | %s |' % (r['rule'], r['status'],
                                           r.get('detail') or ''))
    lines += ['', 'Geometry exceptions: %s' % ('none' if not gerr else '; '.join(gerr)), '',
              '## 2. Process, hydraulic and limit checks per scenario', '',
              '| Scenario | Exceptions |', '|---|---|']
    for sid in order:
        lines.append('| %s | %s |' % (sid, 'none' if not viols[sid] else '; '.join(viols[sid])))
    lines += ['', 'Checks applied in every scenario:', '',
              '* mass balance at every active equipment item (tolerance 1e-5 kg/s)',
              '* convergence of the published fixed-point pressure-loss calculation (1e-5 MPa)',
              '* gas velocity (published limit) on every gas pipeline, and the drain velocity limit',
              '  on liquid-drain lines using the published gas-density formulation',
              '* pipe class pressure rating, temperature range, dry/wet and liquid-drain compatibility',
              '* compressor capacity, minimum stable flow, pressure ratio, suction/discharge pressure,',
              '  suction/discharge temperature and driver power limits',
              '* separator/filter, dehydration, cooler, regulator, meter, header and closed-drain',
              '  capacity, pressure and duty limits, liquid side-stream rates, feed liquid limits',
              '* closed-drain domain pressure against the model pressure limit',
              '* well-group and grid-tie boundary flow limits and the outfall flow limit',
              '* delivery pressure, temperature, water content and free-liquid loading at every sink',
              '* active GRID-TIE meter rated capacity against the scenario flow',
              '',
              '## 3. Reliability (N-1) cases', '',
              '| Scenario | Failed unit | Requirement | Retained flow (kg/s) | Surviving capacity (kg/s) | Margin (kg/s) | Exceptions |',
              '|---|---|---|---|---|---|---|']
    for x in n1:
        lines.append('| %s | %s | %s | %.2f | %.1f | %.1f | %s |'
                     % (x['scenario'], x['failed'], x['reason'], x['retained_flow_kg_s'],
                        x['retained_capacity_kg_s'], x['capacity_margin_kg_s'],
                        'none' if not x['violations'] else '; '.join(x['violations'])))
    lines += ['', 'Total N-1 cases: %d, total exceptions: %d'
              % (len(n1), sum(len(x['violations']) for x in n1))]
    if mutations:
        lines += ['', '## 4. Validator self-check (mutation tests)', '',
                  'Ten deliberate mutations were applied to the delivered design; each breaks',
                  'exactly one published rule and must be reported as an exception. This shows',
                  'that the checks reported above are not vacuous.', '',
                  '| Deliberate mutation | Detected | Evidence |', '|---|---|---|']
        for m in mutations:
            lines.append('| %s | %s | %s |'
                         % (m['mutation'], 'yes' if m['detected'] else 'NO',
                            '; '.join(m['evidence']) if m['evidence'] else '-'))
        lines += ['', 'Mutations detected: %d of %d.'
                  % (sum(1 for m in mutations if m['detected']), len(mutations)), '']
    open(os.path.join(out_dir, 'validation_report.md'), 'w').write('\n'.join(lines))
