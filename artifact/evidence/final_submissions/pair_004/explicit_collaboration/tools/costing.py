"""Quantities take-off and lifecycle-cost build-up (published LCC basis)."""

from engine import C, pvf


def quantities(design):
    q = dict(equipment_count=len(design.equipment),
             equipment_by_category={},
             pipe_length_total_m=0.0,
             pipe_length_by_dn={},
             pipe_length_by_class={},
             pipe_length_by_level={},
             pipe_count=len(design.pipelines),
             road_length_m=0.0)
    for e in design.equipment.values():
        q['equipment_by_category'][e.category] = q['equipment_by_category'].get(e.category, 0) + 1
    for p in design.pipelines.values():
        q['pipe_length_total_m'] += p.length
        q['pipe_length_by_dn'][p.dn] = q['pipe_length_by_dn'].get(p.dn, 0.0) + p.length
        q['pipe_length_by_class'][p.cls] = q['pipe_length_by_class'].get(p.cls, 0.0) + p.length
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            q['pipe_length_by_level'][lvl] = q['pipe_length_by_level'].get(lvl, 0.0) + L
    q['road_length_m'] = sum(((p[i + 1][0] - p[i][0]) ** 2 + (p[i + 1][1] - p[i][1]) ** 2) ** 0.5
                             for _, p, _ in design.road_centre_lines
                             for i in range(len(p) - 1))
    q['footprint_area_m2'] = sum(e.m['footprint_m']['length'] * e.m['footprint_m']['width']
                                 for e in design.equipment.values())
    q['maintenance_area_m2'] = sum(e.maintenance_data()['area']
                                   for e in design.equipment.values())
    return q


def lcc(design, scenario_energy_mwh):
    ec = C.econ
    f = pvf()
    equip_capex = 0.0
    equip_lines = []
    for eid, e in sorted(design.equipment.items()):
        equip_capex += e.m['capex_mbcu']
        equip_lines.append(dict(id=eid, model=e.model_id, category=e.category,
                                capex_mbcu=e.m['capex_mbcu'],
                                annual_maintenance_mbcu=e.m['annual_maintenance_mbcu']))
    pipe_capex = 0.0
    civil_pipe = 0.0
    pipe_lines = []
    for pid, p in sorted(design.pipelines.items()):
        c = 0.0
        civil = 0.0
        for i, (a, b, lvl, cid) in enumerate(p.segments()):
            L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            c += (L * C.dn(p.dn)['installed_cost_mbcu_per_m']
                  * C.pclass(p.cls)['installed_cost_multiplier']
                  * C.levels[lvl]['installed_cost_multiplier'])
            civil += L * C.levels[lvl]['civil_cost_mbcu_per_m']
        pipe_capex += c
        civil_pipe += civil
        pipe_lines.append(dict(id=pid, dn=p.dn, cls=p.cls, length_m=p.length,
                               capex_mbcu=c, civil_mbcu=civil))
    q = quantities(design)
    civil = (q['road_length_m'] * ec['civil']['road_mbcu_per_m']
             + q['footprint_area_m2'] * ec['civil']['foundation_mbcu_per_m2']
             + q['maintenance_area_m2'] * ec['civil']['maintenance_area_mbcu_per_m2']
             + civil_pipe)
    annual_energy_mwh = sum(scenario_energy_mwh.values())
    energy_cost = annual_energy_mwh * ec['energy_tariff_mbcu_per_mwh']
    energy_pv = energy_cost * f
    annual_maint = sum(e.m['annual_maintenance_mbcu'] for e in design.equipment.values())
    maint_pv = annual_maint * f
    total = equip_capex + pipe_capex + civil + energy_pv + maint_pv
    return dict(
        equipment_capex_mbcu=equip_capex,
        piping_capex_mbcu=pipe_capex,
        civil_access_capex_mbcu=civil,
        civil_components=dict(roads_mbcu=q['road_length_m'] * ec['civil']['road_mbcu_per_m'],
                              foundations_mbcu=q['footprint_area_m2'] * ec['civil']['foundation_mbcu_per_m2'],
                              maintenance_area_mbcu=q['maintenance_area_m2'] * ec['civil']['maintenance_area_mbcu_per_m2'],
                              pipeline_civil_mbcu=civil_pipe),
        annual_energy_mwh=annual_energy_mwh,
        energy_cost_per_year_mbcu=energy_cost,
        energy_present_value_mbcu=energy_pv,
        annual_maintenance_mbcu=annual_maint,
        maintenance_present_value_mbcu=maint_pv,
        pvf=f, discount_rate=ec['discount_rate'], project_life_years=ec['project_life_years'],
        energy_tariff_mbcu_per_mwh=ec['energy_tariff_mbcu_per_mwh'],
        operating_hours_per_year=sum(s['annual_hours'] for s in C.scenarios),
        lcc_mbcu=total,
        equipment_lines=equip_lines, pipeline_lines=pipe_lines)
