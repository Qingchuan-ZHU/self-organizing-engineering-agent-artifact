"""Scenario operating cases, process propagation, operating-limit checks.

The module builds one operating case per published scenario (and per reliability
case), solves the free setpoints and the passive parallel-path balances, and then
evaluates the network against every published equipment, pipe, boundary and
delivery limit.
"""

import math
from math import pi

import design as design_mod
from engine import (C, CP, K_RATIO, E_TOL, M_TOL, P_TOL, T_TOL, W_TOL, F_TOL,
                    pipe_forward, velocity)

GRID = 'GRID-TIE'
WG_LIST = design_mod.WG_IDS
BRANCH_OF_WG = design_mod.BRANCH_PIPE
TRAIN_PATHS = design_mod.TRAIN_PATHS
TRAIN_LIQ_PIPES = design_mod.TRAIN_LIQ_PIPES
TRAIN_FIXED_DP = design_mod.TRAIN_FIXED_DP_MPA

INLET_PC_SETPOINT = design_mod.INLET_PC_SETPOINT_MPA   # REG-PT setpoint (MPa)
COOL_SETPOINT_C = 58.0             # 2 K margin below the 60 degC delivery limit
REG_MARGIN_MPA = 0.20              # control margin at the delivery regulator
DRAIN_DOMAIN_P_MPA = 1.0           # closed-drain domain = published maximum (1 MPa)
CONDENSATE_DENSITY_KG_M3 = 1000.0  # assumed condensate density (see report)


# --------------------------------------------------------------------------
# passive parallel-path balances
# --------------------------------------------------------------------------

def balanced_parallel_flows(design, paths, level_P, level_T, total, fixed_dp):
    """Passive flow split over parallel paths sharing one pressure difference.

    Each path carries the flow that makes its total head loss (its fixed
    equipment pressure drops plus the flow-dependent pipe losses of that path)
    equal to the same common value, so the split is the equilibrium of the
    declared network and needs no flow-control device.
    """
    names = list(paths)

    def flows_for(K):
        out = []
        for nm in names:
            need = K - fixed_dp[nm]
            if need <= 1e-12:
                out.append(0.0)
                continue
            lo, hi = 0.0, 80.0
            for _ in range(34):
                mid = 0.5 * (lo + hi)
                Pp = level_P
                for pid in paths[nm]:
                    pp = design.pipelines[pid]
                    Pp, _c, _i = pipe_forward(Pp, mid, pp.length, pp.D, pp.eps, level_T)
                if (level_P - Pp) < need:
                    lo = mid
                else:
                    hi = mid
            out.append(0.5 * (lo + hi))
        return out

    base = max(fixed_dp.values())
    lo, hi = base, base + 8.0
    for _ in range(38):
        K = 0.5 * (lo + hi)
        if sum(flows_for(K)) < total:
            lo = K
        else:
            hi = K
    K = 0.5 * (lo + hi)
    return dict(zip(names, flows_for(K)))


def balanced_branch_flows(design, level_P, level_T, total):
    paths = dict((wg, [BRANCH_OF_WG[wg]]) for wg in WG_LIST)
    return balanced_parallel_flows(design, paths, level_P, level_T, total,
                                   dict((wg, 0.0) for wg in WG_LIST))


def balanced_train_flows(design, level_P, level_T, total, active=('1', '2', '3')):
    paths = dict((t, list(TRAIN_PATHS[t])) for t in active)
    fixed = dict((t, TRAIN_FIXED_DP[t]) for t in active)
    return balanced_parallel_flows(design, paths, level_P, level_T, total, fixed)


# --------------------------------------------------------------------------
# case construction
# --------------------------------------------------------------------------

def _alloc_compressor(F):
    """compressor duty split for normal operation.

    The two C60 units (higher efficiency) carry the duty equally and the C40 is
    isolated by its unit valves, which minimises driver power; the C40 is
    started when a C60 is unavailable (reliability cases).  The split is a
    control setpoint, not a passive split.
    """
    return {'INJ-C1': F / 2.0, 'INJ-C2': F / 2.0}


def _alloc_two(F):
    return {'INJ-C1': F / 2.0, 'INJ-C2': F / 2.0}


def build_case(design, scen, kind='normal', failed=None):
    sid = scen['scenario_id'] + ('' if kind == 'normal' else ' N-1:' + str(failed))
    F = scen['required_total_flow_kg_s']
    if kind != 'normal' and failed:
        F = 0.7 * F                      # retained flow, reliability requirement
    flows = {pid: 0.0 for pid in design.pipelines}
    modes = {}
    params = {}
    alloc = dict(_alloc_compressor(F))

    def set_compressor_flows(a):
        for e, pid_s, pid_d in (('INJ-C1', 'P03', 'P06'), ('INJ-C2', 'P04', 'P07'),
                                ('INJ-C3', 'P05', 'P08')):
            flows[pid_s] = a.get(e, 0.0)
            flows[pid_d] = a.get(e, 0.0)

    if kind == 'n1' and failed in ('INJ-C1', 'INJ-C2', 'INJ-C3'):
        live = [e for e in ('INJ-C1', 'INJ-C2', 'INJ-C3') if e != failed]
        if 'INJ-C3' in live:
            c60 = min(60.0, F - 10.0)
            alloc = dict((e, c60 if e != 'INJ-C3' else F - c60) for e in live)
        else:
            alloc = dict((e, F / 2.0) for e in live)
        modes.pop(failed, None)

    if scen['service'] == 'injection':
        flows['P01'] = F
        flows['P02'] = F
        set_compressor_flows(alloc)
        flows['P09'] = F
        flows['P10'] = F
        for wg in WG_LIST:
            flows[BRANCH_OF_WG[wg]] = F / 6.0
        for eid in alloc:
            modes[eid] = {'mode': 'run', 'P_out': 0.0}
        modes['COOL'] = {'mode': 'run', 'T_out': COOL_SETPOINT_C}
        params['INJ-DISCHARGE'] = {'solve': 'injection_delivery', 'value': None}
    else:
        for wg in WG_LIST:
            flows[BRANCH_OF_WG[wg]] = -F / 6.0
        flows['L1'] = F
        set_compressor_flows(alloc)
        flows['L2'] = F
        for t in '123':
            for pid in TRAIN_PATHS[t]:
                flows[pid] = F / 3.0
        flows['P30'] = F
        flows['P31'] = F
        flows['P32'] = F
        for t in '123':
            liq = (F / 3.0) * scen['source_free_liquid_mass_fraction'] * 0.9995
            for pid in TRAIN_LIQ_PIPES[t]:
                flows[pid] = liq
        if scen['required_sink_pressure_mpa'] > scen['source_pressure_mpa']:
            for e in alloc:
                modes[e] = {'mode': 'run', 'P_out': 0.0}
            params['WDR-DISCHARGE'] = {'solve': 'regulator_inlet', 'value': None}
        else:
            for e in alloc:
                modes[e] = {'mode': 'pass'}
        params['WDR-REG'] = {'solve': 'grid_delivery', 'value': None}
        if kind == 'n1' and failed in ('SEP-1', 'SEP-2', 'SEP-3',
                                       'DEHY-1', 'DEHY-2', 'DEHY-3'):
            tr = failed[-1]
            for t in '123':
                for pid in list(TRAIN_PATHS[t]) + list(TRAIN_LIQ_PIPES[t]):
                    flows[pid] = 0.0
            live = [t for t in '123' if t != tr]
            for t in live:
                liq = (F / 2.0) * scen['source_free_liquid_mass_fraction'] * 0.9995
                for pid in TRAIN_PATHS[t]:
                    flows[pid] = F / 2.0
                for pid in TRAIN_LIQ_PIPES[t]:
                    flows[pid] = liq
    return dict(id=sid, scen=scen, service=scen['service'], kind=kind,
                failed=failed, flows=flows, modes=modes, params=params,
                required_flow=F, hours=scen['annual_hours'],
                source=dict(P=scen['source_pressure_mpa'],
                            T=scen['source_temperature_c'],
                            w=scen['source_water_mg_sm3'],
                            fl=scen['source_free_liquid_mass_fraction']),
                sink_P=scen['required_sink_pressure_mpa'])


# --------------------------------------------------------------------------
# propagation
# --------------------------------------------------------------------------

def _state(P, T, w, fl):
    return dict(P=P, T=T, w=w, fl=fl)


def evaluate(design, case):
    flows = case['flows']
    modes = case['modes']
    params = case['params']
    Pdis_inj = params.get('INJ-DISCHARGE', {}).get('value')
    Pdis_wdr = params.get('WDR-DISCHARGE', {}).get('value')
    Preg = params.get('WDR-REG', {}).get('value')

    nodes = set(design.equipment)
    for p in design.pipelines.values():
        for ref in (p.frm, p.to):
            if ref[0].startswith('IFACE:'):
                nodes.add(ref[0])
    edges = {}
    for pid, m in flows.items():
        if m == 0.0:
            continue
        p = design.pipelines[pid]
        u, v = (p.frm, p.to) if m > 0 else (p.to, p.frm)
        edges.setdefault(u[0], []).append((v[0], pid, abs(m), u[1], v[1]))
        edges.setdefault(v[0], [])
    indeg = {n: 0 for n in nodes}
    for u in edges:
        for (v, pid, m, up, vp) in edges[u]:
            indeg[v] = indeg.get(v, 0) + 1
    order, stack = [], sorted([n for n in nodes if indeg.get(n, 0) == 0])
    seen = set()
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        order.append(n)
        for (v, pid, m, up, vp) in sorted(edges.get(n, [])):
            indeg[v] -= 1
            if indeg[v] == 0:
                stack.append(v)
    if len(order) != len(nodes):
        raise RuntimeError('process graph not acyclic in case %s' % case['id'])

    arriving = {}
    res_del = {}
    res_ports = {}
    res_eq = {}
    viol = []
    energies = {}
    note = viol.append
    src = case['source']

    for n in order:
        eq = design.equipment.get(n)
        inc = list(arriving.get(n, {}).values())
        if eq is None:
            if inc:
                tot = sum(m for (_, m, _s) in inc)
                res_del[n.split(':', 1)[1]] = _state(
                    min(x['P'] for (_, _, x) in inc),
                    sum(m * x['T'] for (_, m, x) in inc) / tot,
                    sum(m * x['w'] for (_, m, x) in inc) / tot,
                    sum(m * x['fl'] for (_, m, x) in inc) / tot)
                continue                    # sink interface
            st = _state(src['P'], src['T'], src['w'], src['fl'])
        else:
            if not inc:
                continue                    # isolated equipment in this case
            tot = sum(m for (_, m, _s) in inc)
            P_in = min(s['P'] for (_, _, s) in inc)
            T_in = sum(m * s['T'] for (_, m, s) in inc) / tot
            w_in = sum(m * s['w'] for (_, m, s) in inc) / tot
            fl_in = sum(m * s['fl'] for (_, m, s) in inc) / tot
            m_in = tot
            st = _state(P_in, T_in, w_in, fl_in)
            cat = eq.category
            md = eq.m
            res_eq[eq.id] = dict(m=m_in, P_in=P_in, T_in=T_in, w_in=w_in,
                                 fl_in=fl_in, category=cat, model=eq.model_id,
                                 ports_in=sorted(arriving[n]))

            if cat == 'compressor':
                mode = modes.get(eq.id, {'mode': 'pass'})
                if mode['mode'] == 'pass':
                    P_out, T_out, W, r = P_in, T_in, 0.0, 1.0
                else:
                    P_out = Pdis_inj if case['service'] == 'injection' else Pdis_wdr
                    r = P_out / P_in
                    ex = r ** ((K_RATIO - 1.0) / K_RATIO) - 1.0
                    eta = md['efficiency_proxy']
                    T_out = (T_in + 273.15) * (1.0 + ex / eta) - 273.15
                    W = (m_in * CP * (T_in + 273.15) * ex /
                         (eta * md['driver_efficiency']) / 1e6)
                    energies[eq.id] = W
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                if mode['mode'] == 'run' and m_in < md['minimum_stable_flow_kg_s'] - M_TOL:
                    note('%s: flow %.4f < min stable %.1f'
                         % (eq.id, m_in, md['minimum_stable_flow_kg_s']))
                if P_in > md['maximum_suction_pressure_mpa'] + P_TOL:
                    note('%s: suction P %.4f > max %.1f'
                         % (eq.id, P_in, md['maximum_suction_pressure_mpa']))
                if P_out > md['maximum_discharge_pressure_mpa'] + P_TOL:
                    note('%s: discharge P %.4f > max %.1f'
                         % (eq.id, P_out, md['maximum_discharge_pressure_mpa']))
                if r > md['maximum_pressure_ratio'] + 1e-9:
                    note('%s: ratio %.4f > max %.2f' % (eq.id, r, md['maximum_pressure_ratio']))
                if T_in > md['maximum_suction_temperature_c'] + T_TOL:
                    note('%s: suction T %.2f > max %.1f'
                         % (eq.id, T_in, md['maximum_suction_temperature_c']))
                if T_out > md['maximum_discharge_temperature_c'] + T_TOL:
                    note('%s: discharge T %.2f > max %.1f'
                         % (eq.id, T_out, md['maximum_discharge_temperature_c']))
                if mode['mode'] == 'run' and W > md['maximum_power_mw'] + E_TOL:
                    note('%s: driver power %.3f > max %.1f'
                         % (eq.id, W, md['maximum_power_mw']))
                res_eq[eq.id].update(r=r, P_out=P_out, T_out=T_out, W=W, mode=mode['mode'])
                st = _state(P_out, T_out, w_in, fl_in)

            elif cat == 'header':
                dp = md['pressure_drop_at_capacity_mpa'] * (m_in / md['capacity_kg_s']) ** 2
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                P_out = P_in - dp
                res_eq[eq.id].update(dp=dp, P_out=P_out)
                st = _state(P_out, T_in, w_in, fl_in)

            elif cat == 'cooler':
                mode = modes.get(eq.id, {'mode': 'run', 'T_out': T_in})
                T_set = mode.get('T_out', T_in)
                T_out = min(T_in, T_set)
                duty = m_in * CP * abs(T_in - T_out) / 1e6
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                if duty > md['maximum_duty_mw'] + E_TOL:
                    note('%s: duty %.3f > max %.1f' % (eq.id, duty, md['maximum_duty_mw']))
                if T_out < md['minimum_outlet_temperature_c'] - T_TOL:
                    note('%s: outlet T %.2f < min %.1f'
                         % (eq.id, T_out, md['minimum_outlet_temperature_c']))
                if P_in > md['maximum_pressure_mpa'] + P_TOL:
                    note('%s: pressure %.3f > max %.1f' % (eq.id, P_in, md['maximum_pressure_mpa']))
                P_out = P_in - md.get('pressure_drop_mpa', 0.0)
                W = duty * md['electric_power_fraction_of_duty']
                energies[eq.id] = W
                res_eq[eq.id].update(duty=duty, T_out=T_out, P_out=P_out, W=W)
                st = _state(P_out, T_out, w_in, fl_in)

            elif cat in ('separator', 'filter'):
                if P_in > md['maximum_pressure_mpa'] + P_TOL:
                    note('%s: pressure %.3f > max %.1f' % (eq.id, P_in, md['maximum_pressure_mpa']))
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                if fl_in > md['maximum_feed_free_liquid_fraction'] + F_TOL:
                    note('%s: feed liquid %.3e > max %.3g'
                         % (eq.id, fl_in, md['maximum_feed_free_liquid_fraction']))
                liq = m_in * fl_in * md['liquid_removal_efficiency']
                if liq > md['maximum_liquid_rate_kg_s'] + M_TOL:
                    note('%s: liquid rate %.4f > max %.2f'
                         % (eq.id, liq, md['maximum_liquid_rate_kg_s']))
                fl_out = fl_in * (1.0 - md['liquid_removal_efficiency'])
                P_out = P_in - md.get('pressure_drop_mpa', 0.0)
                res_eq[eq.id].update(liquid=liq, fl_out=fl_out, P_out=P_out)
                st = _state(P_out, T_in, w_in, fl_out)

            elif cat == 'dehydration':
                if P_in > md['maximum_pressure_mpa'] + P_TOL:
                    note('%s: pressure %.3f > max %.1f' % (eq.id, P_in, md['maximum_pressure_mpa']))
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                if fl_in > md['maximum_feed_free_liquid_fraction'] + F_TOL:
                    note('%s: feed liquid %.3e > max %.3g'
                         % (eq.id, fl_in, md['maximum_feed_free_liquid_fraction']))
                P_out = P_in - md.get('pressure_drop_mpa', 0.0)
                w_out = md['normal_outlet_water_mg_sm3']
                energies[eq.id] = m_in * md['energy_mw_per_kg_s']
                res_eq[eq.id].update(w_out=w_out, P_out=P_out, W=energies[eq.id])
                st = _state(P_out, T_in, w_out, fl_in)

            elif cat == 'regulator':
                if P_in > md['maximum_pressure_mpa'] + P_TOL:
                    note('%s: pressure %.3f > max %.1f' % (eq.id, P_in, md['maximum_pressure_mpa']))
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                setp = modes.get(eq.id, {}).get('P_out')
                if setp is None and eq.id == 'REG-WDR':
                    setp = Preg
                if setp is None:
                    setp = P_in
                P_out = min(setp, P_in)
                T_out = T_in - md['jt_temperature_coefficient_k_per_mpa'] * (P_in - P_out)
                res_eq[eq.id].update(P_out=P_out, T_out=T_out, setpoint=setp,
                                     dp=P_in - P_out)
                st = _state(P_out, T_out, w_in, fl_in)

            elif cat == 'meter':
                if P_in > md['maximum_pressure_mpa'] + P_TOL:
                    note('%s: pressure %.3f > max %.1f' % (eq.id, P_in, md['maximum_pressure_mpa']))
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: flow %.4f > capacity %.1f' % (eq.id, m_in, md['capacity_kg_s']))
                P_out = P_in - md.get('pressure_drop_mpa', 0.0)
                res_eq[eq.id].update(P_out=P_out)
                st = _state(P_out, T_in, w_in, fl_in)

            elif cat == 'closed_drain':
                if m_in > md['capacity_kg_s'] + M_TOL:
                    note('%s: liquid flow %.4f > capacity %.2f'
                         % (eq.id, m_in, md['capacity_kg_s']))
                if DRAIN_DOMAIN_P_MPA > md['maximum_pressure_mpa'] + P_TOL:
                    note('%s: drain domain %.2f MPa > model limit %.2f'
                         % (eq.id, DRAIN_DOMAIN_P_MPA, md['maximum_pressure_mpa']))
                res_eq[eq.id].update(P_out=DRAIN_DOMAIN_P_MPA, T_out=T_in)
                st = _state(DRAIN_DOMAIN_P_MPA, T_in, w_in, fl_in)
            else:
                raise RuntimeError('unhandled category ' + cat)

        # ---- distribute to downstream pipelines
        for (v, pid, m, up, vp) in edges.get(n, []):
            p = design.pipelines[pid]
            if eq is not None and up in ('liquid_out', 'drain_out'):
                # idealised integral letdown into the closed-drain pressure domain
                nxt = _state(DRAIN_DOMAIN_P_MPA, st['T'], st['w'], st['fl'])
            elif p.service == 'liquid_drain':
                nxt = _state(DRAIN_DOMAIN_P_MPA, st['T'], st['w'], st['fl'])
            else:
                P2, conv, info = pipe_forward(st['P'], m, p.length, p.D, p.eps, st['T'])
                vmax = max(velocity(m, st['P'], st['T'], p.D),
                           velocity(m, P2, st['T'], p.D))
                if not conv:
                    note('%s: pressure loss did not converge' % pid)
                if vmax > C.piping['maximum_gas_velocity_m_s'] + 1e-6:
                    note('%s: gas velocity %.3f > %.1f m/s'
                         % (pid, vmax, C.piping['maximum_gas_velocity_m_s']))
                res_ports[pid] = dict(m=m, P_in=st['P'], P_out=P2, T=st['T'],
                                      loss=st['P'] - P2, v=vmax,
                                      w=st['w'], fl=st['fl'])
                nxt = _state(P2, st['T'], st['w'], st['fl'])
            arriving.setdefault(v, {})[vp] = (pid, m, nxt)
            if p.service == 'liquid_drain':
                A = pi * p.D * p.D / 4.0
                res_ports.setdefault(pid, {})
                res_ports[pid].update(
                    m=m, T=st['T'], P_in=DRAIN_DOMAIN_P_MPA, P_out=DRAIN_DOMAIN_P_MPA,
                    # conservative reading: the only published density formulation is
                    # the gas proxy, evaluated in the declared drain domain
                    v=velocity(m, DRAIN_DOMAIN_P_MPA, st['T'], p.D),
                    v_condensate=abs(m) / (CONDENSATE_DENSITY_KG_M3 * A))
    return dict(case=case, eq=res_eq, pipes=res_ports, violations=viol,
                energies=energies, arriving=arriving, delivery=res_del)


# --------------------------------------------------------------------------
# setpoint solution
# --------------------------------------------------------------------------

def _grid_pressure(res):
    s = res['pipes'].get('P32')
    return s['P_out'] if s and s['m'] > 0 else 0.0


def _reg_inlet(res):
    e = res['eq'].get('REG-WDR')
    return e['P_in'] if e else 0.0


def _worst_delivery(design, case, res):
    worst = None
    for wg in WG_LIST:
        s = res['pipes'].get(BRANCH_OF_WG[wg])
        if s and s['m'] > 0:
            d = s['P_out'] - case['sink_P']
            if worst is None or d < worst[0]:
                worst = (d, wg)
    return worst


def _solve_setpoints(design, case):
    p = case['params']
    if 'INJ-DISCHARGE' in p:
        lo, hi = case['sink_P'], case['sink_P'] + 8.0
        p['INJ-DISCHARGE']['value'] = hi
        for _ in range(46):
            mid = 0.5 * (lo + hi)
            p['INJ-DISCHARGE']['value'] = mid
            res = evaluate(design, case)
            w = _worst_delivery(design, case, res)
            if w is None:
                break
            if w[0] > 0.0:
                hi = mid
            else:
                lo = mid
        p['INJ-DISCHARGE']['value'] = hi
    if 'WDR-REG' in p:
        # the delivery regulator is solved against the delivered boundary
        # pressure, and the compressor discharge is then trimmed to give the
        # regulator a positive letdown; the pair is iterated because the
        # downstream loss depends slightly on the pressure level
        def solve_reg():
            lo, hi = 3.0, 12.0
            for _ in range(46):
                mid = 0.5 * (lo + hi)
                p['WDR-REG']['value'] = mid
                if _grid_pressure(evaluate(design, case)) >= case['sink_P']:
                    hi = mid
                else:
                    lo = mid
            p['WDR-REG']['value'] = hi

        def solve_discharge():
            base = p['WDR-REG']['value']
            lo2, hi2 = base, base + 6.0
            for _ in range(46):
                mid = 0.5 * (lo2 + hi2)
                p['WDR-DISCHARGE']['value'] = mid
                if _reg_inlet(evaluate(design, case)) >= base + REG_MARGIN_MPA:
                    hi2 = mid
                else:
                    lo2 = mid
            p['WDR-DISCHARGE']['value'] = hi2

        if 'WDR-DISCHARGE' in p:
            # bootstrap value high enough for the regulator to reach its setpoint
            p['WDR-DISCHARGE']['value'] = max(case['sink_P'] + 1.0,
                                              case['scen']['source_pressure_mpa'])
        for _ in range(3):
            solve_reg()
            if 'WDR-DISCHARGE' in p:
                solve_discharge()
        solve_reg()


def _delivery_error(case, res):
    """largest deviation of a delivered sink pressure from its requirement"""
    sinks = set(case['scen']['sink_interfaces'])
    err = 0.0
    for iid, st in res['delivery'].items():
        if iid in sinks:
            err = max(err, abs(st['P'] - case['sink_P']))
    return err


def solve(design, case):
    """solve the free setpoints and the passive parallel-path balances"""
    F = case['required_flow']
    _solve_setpoints(design, case)
    for _ in range(6):
        res = evaluate(design, case)
        err = _delivery_error(case, res)
        changed = False
        key = BRANCH_OF_WG['WG-01']
        if case['service'] == 'injection':
            lvl_P, lvl_T = res['pipes'][key]['P_in'], res['pipes'][key]['T']
        else:
            lvl_P, lvl_T = case['source']['P'], case['source']['T']
        fl = balanced_branch_flows(design, lvl_P, lvl_T, F)
        newb = dict(fl) if case['service'] == 'injection' else \
            dict((k, -v) for k, v in fl.items())
        for wg in WG_LIST:
            if abs(newb[wg] - case['flows'][BRANCH_OF_WG[wg]]) > 1e-7:
                case['flows'][BRANCH_OF_WG[wg]] = newb[wg]
                changed = True
        if case['service'] == 'withdrawal':
            active = tuple(t for t in '123'
                           if abs(case['flows'][TRAIN_PATHS[t][0]]) > 1e-12)
            if len(active) > 1:
                hdr = res['eq'].get('HDR-E')
                if hdr is not None:
                    tf = balanced_train_flows(design, hdr['P_out'], hdr['T_in'], F, active)
                    for t in active:
                        liq = tf[t] * case['source']['fl'] * 0.9995
                        for pid in TRAIN_PATHS[t]:
                            if abs(tf[t] - case['flows'][pid]) > 1e-7:
                                case['flows'][pid] = tf[t]
                                changed = True
                        for pid in TRAIN_LIQ_PIPES[t]:
                            case['flows'][pid] = liq
        if not changed and err < 1e-9:
            break
        _solve_setpoints(design, case)
    return evaluate(design, case)


# --------------------------------------------------------------------------
# delivery / boundary / mass-balance checks
# --------------------------------------------------------------------------

def check_case(design, case, res):
    v = list(res['violations'])
    limits = C.req['gas_delivery_requirements']
    tmin, tmax = limits['temperature_limits_c']
    sinks = set(case['scen']['sink_interfaces'])
    for iid, st in res['delivery'].items():
        if iid not in sinks:
            continue
        if st['w'] > limits['maximum_water_content_mg_sm3'] + W_TOL:
            v.append('%s: water %.4f > %.1f mg/Sm3'
                     % (iid, st['w'], limits['maximum_water_content_mg_sm3']))
        if st['fl'] > limits['maximum_free_liquid_mass_fraction'] + F_TOL:
            v.append('%s: free liquid %.3e > %.3e'
                     % (iid, st['fl'], limits['maximum_free_liquid_mass_fraction']))
        if st['T'] > tmax + T_TOL or st['T'] < tmin - T_TOL:
            v.append('%s: temperature %.2f outside [%.1f, %.1f]' % (iid, st['T'], tmin, tmax))
        if st['P'] < case['sink_P'] - P_TOL:
            v.append('%s: delivered pressure %.6f < required %.3f'
                     % (iid, st['P'], case['sink_P']))
    if case['service'] == 'injection':
        for wg in WG_LIST:
            m = res['pipes'][BRANCH_OF_WG[wg]]['m']
            if m > 25.0 + M_TOL:
                v.append('%s: flow %.3f > 25 kg/s' % (wg, m))
        if res['pipes']['P01']['m'] > 160.0 + M_TOL:
            v.append('GRID-TIE: flow > 160 kg/s')
        cap = design.equipment['MTR-INJ'].m['capacity_kg_s']
        if cap < case['required_flow'] - M_TOL:
            v.append('GRID-TIE: active meter rated capacity %.1f below scenario flow %.1f'
                     % (cap, case['required_flow']))
        carried = res['eq'].get('MTR-INJ', {}).get('m', 0.0)
        if carried < case['required_flow'] - M_TOL:
            v.append('GRID-TIE: only %.4f kg/s passes the inlet meter against %.4f exchanged'
                     % (carried, case['required_flow']))
    else:
        for wg in WG_LIST:
            if abs(res['pipes'][BRANCH_OF_WG[wg]]['m']) > 25.0 + M_TOL:
                v.append('%s: flow > 25 kg/s' % wg)
        if abs(res['pipes']['P32']['m']) > 160.0 + M_TOL:
            v.append('GRID-TIE: flow > 160 kg/s')
        cap = design.equipment['MTR-WDR'].m['capacity_kg_s']
        if cap < case['required_flow'] - M_TOL:
            v.append('GRID-TIE: active meter rated capacity %.1f below scenario flow %.1f'
                     % (cap, case['required_flow']))
        carried = res['eq'].get('MTR-WDR', {}).get('m', 0.0)
        if carried < case['required_flow'] - M_TOL:
            v.append('GRID-TIE: only %.4f kg/s passes the outlet meter against %.4f exchanged'
                     % (carried, case['required_flow']))
        out = sum(res['pipes'][q]['m'] for q in ('P39', 'P40', 'P41') if q in res['pipes'])
        if out > 10.0 + M_TOL:
            v.append('LIQUID-DRAIN-OUTFALL: flow %.3f > 10 kg/s' % out)
    # mass balance at every active equipment item
    for eid, e in design.equipment.items():
        bank = {}
        for pid, m in case['flows'].items():
            if m == 0.0:
                continue
            pp = design.pipelines[pid]
            for ref, sign in ((pp.frm, +1.0), (pp.to, -1.0)):
                if ref[0] == eid:
                    bank[ref[1]] = bank.get(ref[1], 0.0) + sign * m
        if not bank:
            continue
        if e.category == 'closed_drain':
            lost = sum(bank.values())
        else:
            lost = sum(val for k, val in bank.items() if k != 'liquid_out')
        if abs(lost) > M_TOL:
            v.append('%s: mass imbalance %.6f kg/s' % (eid, lost))
    return v


def check_pipes(design, case, res):
    v = []
    for pid, m in case['flows'].items():
        if m == 0.0 or pid not in res['pipes']:
            continue
        p = design.pipelines[pid]
        st = res['pipes'][pid]
        pc = C.pclass(p.cls)
        Pmax = max(st.get('P_in', 0.0), st.get('P_out', st.get('P_in', 0.0)))
        if Pmax > pc['maximum_allowable_pressure_mpa'] + P_TOL:
            v.append('%s: pressure %.3f > class %s rating %.1f'
                     % (pid, Pmax, p.cls, pc['maximum_allowable_pressure_mpa']))
        T = st.get('T', 20.0)
        lo, hi = pc['temperature_limits_c']
        if T > hi + T_TOL or T < lo - T_TOL:
            v.append('%s: temperature %.2f outside class %s limits [%.0f, %.0f]'
                     % (pid, T, p.cls, lo, hi))
        if p.service == 'liquid_drain':
            if not pc['liquid_drain_compatible']:
                v.append('%s: class %s not liquid-drain compatible' % (pid, p.cls))
            if DRAIN_DOMAIN_P_MPA > pc['maximum_allowable_pressure_mpa'] + P_TOL:
                v.append('%s: drain domain %.2f MPa > class %s rating %.1f'
                         % (pid, DRAIN_DOMAIN_P_MPA, p.cls,
                            pc['maximum_allowable_pressure_mpa']))
            lvel = st.get('v', 0.0)
            if lvel > C.piping['maximum_liquid_drain_velocity_m_s'] + 1e-6:
                v.append('%s: liquid-drain velocity %.3f > %.1f m/s (gas-density convention)'
                         % (pid, lvel, C.piping['maximum_liquid_drain_velocity_m_s']))
            continue
        dry = (st.get('w', 0.0) <= C.req['gas_delivery_requirements']['maximum_water_content_mg_sm3'] + W_TOL
               and st.get('fl', 0.0) <= C.req['gas_delivery_requirements']['maximum_free_liquid_mass_fraction'] + F_TOL)
        if dry and not pc['dry_gas_compatible']:
            v.append('%s: dry gas but class %s not dry compatible' % (pid, p.cls))
        if not dry and not pc['wet_gas_compatible']:
            v.append('%s: wet gas but class %s not wet compatible' % (pid, p.cls))
    return v
