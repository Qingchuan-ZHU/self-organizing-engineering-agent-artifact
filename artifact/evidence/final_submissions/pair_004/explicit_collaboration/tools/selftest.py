"""Validator self-check: deliberate design mutations must be detected.

These tests demonstrate that the checks applied to the delivered design are not
vacuous - each mutation breaks one published rule and must raise an exception.
"""

import checks_geom
import design as design_mod
import process


def run():
    from engine import C
    scen = {s['scenario_id']: s for s in C.scenarios}
    out = []

    def geometry(d):
        err, _, _ = checks_geom.check_geometry(d)
        return err

    def scenario(d, sid, kind='normal', failed=None):
        case = process.build_case(d, C_scen(d, sid), kind, failed)
        res = process.solve(d, case)
        return (process.check_case(d, case, res) + process.check_pipes(d, case, res))

    def C_scen(d, sid):
        return scen[sid]

    # 1. mass balance: add flow to one well flowline
    d = design_mod.build()
    case = process.build_case(d, scen['INJ-LOW'])
    process.solve(d, case)
    case['flows']['P11'] += 1.0
    v = process.check_case(d, case, process.evaluate(d, case))
    out.append(('mass balance perturbed on one well flowline',
                'must be detected', any('imbalance' in x for x in v),
                [x for x in v if 'imbalance' in x][:1]))

    # 2. footprint overlap
    d = design_mod.build()
    d.equipment['SEP-2'].y = 250.0
    e = geometry(d)
    out.append(('two equipment footprints overlapped',
                'must be detected', any('overlap' in x for x in e),
                [x for x in e if 'overlap' in x][:1]))

    # 3. separation matrix violation
    d = design_mod.build()
    d.equipment['REG-WDR'].x = 615.0
    e = geometry(d)
    out.append(('delivery regulator moved inside the treatment separation distance',
                'must be detected', any('separation' in x for x in e),
                [x for x in e if 'separation' in x][:1]))

    # 4. pipeline routed through a pipeline-exclusion zone
    d = design_mod.build()
    p = d.pipelines['P02']
    p.points = [(640.0, 302.0), (640.0, 325.0), (600.0, 325.0), (600.0, 308.0),
                (346.5, 308.0), (346.5, 378.5)]
    p.levels = ['ground'] * 5
    p.corridors = [None] * 5
    e = geometry(d)
    out.append(('pipeline routed through FUTURE-EXPANSION (pipeline exclusion)',
                'must be detected', any('pipeline_exclusion' in x for x in e),
                [x for x in e if 'pipeline_exclusion' in x][:1]))

    # 5. same-level route overlap
    d = design_mod.build()
    d.pipelines['P04'].points = [(343.5, 378.5), (360.0, 379.0), (360.0, 315.0), (394.0, 315.0)]
    d.pipelines['P04'].levels = ['ground'] * 3
    d.pipelines['P04'].corridors = [None] * 3
    e = geometry(d)
    out.append(('one pipeline laid along another on the same routing level',
                'must be detected', any('overlap' in x and 'same-level' in x for x in e),
                [x for x in e if 'same-level' in x][:1]))

    # 6. undersized grid line -> gas velocity
    d = design_mod.build()
    d.pipelines['P32'].dn = 'DN150'
    v = scenario(d, 'WDR-MID')
    out.append(('outlet metering line undersized to DN150',
                'must be detected', any('velocity' in x for x in v),
                [x for x in v if 'velocity' in x][:1]))

    # 7. pipe class removed from dry service -> compatibility
    d = design_mod.build()
    d.pipelines['P11'].cls = 'CS-DRY-160'
    v = scenario(d, 'WDR-HIGH')
    out.append(('wet-service line given a dry-only pipe class',
                'must be detected', any('wet compatible' in x for x in v),
                [x for x in v if 'compatible' in x][:1]))

    # 8. compressor duty above the pressure-ratio limit
    d = design_mod.build()
    case = process.build_case(d, scen['INJ-HIGH'])
    case['params']['INJ-DISCHARGE'] = {'solve': 'injection_delivery', 'value': 16.0}
    res = process.evaluate(d, case)
    v = process.check_case(d, case, res)
    out.append(('compressor discharge pressure driven above the model limit',
                'must be detected', any('ratio' in x or 'discharge P' in x for x in v),
                [x for x in v if 'ratio' in x or 'discharge P' in x][:1]))

    # 9. dehydration outlet quality degraded above the delivery limit
    d = design_mod.build()
    for t in '123':
        e = d.equipment['DEHY-' + t]
        e.m = dict(e.m)
        e.m['normal_outlet_water_mg_sm3'] = 80.0
    v = scenario(d, 'WDR-MID')
    out.append(('dehydration outlet water raised above the 50 mg/Sm3 delivery limit',
                'must be detected', any('water' in x for x in v),
                [x for x in v if 'water' in x][:1]))

    # 10. delivery temperature limit
    d = design_mod.build()
    case = process.build_case(d, scen['INJ-HIGH'])
    case['modes']['COOL'] = {'mode': 'run', 'T_out': 70.0}
    res = process.solve(d, case)
    v = process.check_case(d, case, res)
    out.append(('aftercooler setpoint raised above the delivery temperature limit',
                'must be detected', any('temperature' in x for x in v),
                [x for x in v if 'temperature' in x][:1]))

    return [dict(mutation=m, expectation=e, detected=bool(x), evidence=ev)
            for (m, e, x, ev) in out]


if __name__ == '__main__':
    for r in run():
        print('%-70s detected=%s' % (r['mutation'], r['detected']))
