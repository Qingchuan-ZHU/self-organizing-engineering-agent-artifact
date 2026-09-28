"""Build, verify and report the UGS-SYNTH-D01 design.

Usage:  python build.py [--brief DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ugs_basis as B
import ugs_design as D
from ugs_check import Design
import ugs_operate as O
import ugs_cost as C


def main():
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    ap.add_argument("--brief", default=str(here.parent.parent / "brief"))
    ap.add_argument("--out", default=str(here.parent / "deliverables"))
    args = ap.parse_args()

    brief = Path(args.brief).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    case = B.CaseData(brief)
    design = Design(case, D.EQUIPMENT, D.PIPES, D.ROADS)

    # ---------------- geometry / layout verification ----------------------
    design.check_connections()
    design.check_equipment_geometry()
    design.check_maintenance_envelopes()
    design.check_roads()
    design.check_road_access()
    design.check_pipeline_geometry()

    # ---------------- scenario verification -------------------------------
    plans = O.build_plans(design)
    normal, variants, results = [], [], []
    for plan in plans:
        p, m = O.run_plan(design, plan)
        results.append((p, m))
        if plan["kind"] == "normal":
            normal.append((plan, m))
        else:
            variants.append((plan, m))
        for name, ok, detail in m.checks:
            design.add(f"[{plan['id']}] {name}", ok, detail)

    C.check_pipes_against_service(design, [m for _, m in normal] + [m for _, m in variants])
    lcc = C.compute_lcc(design, [m for _, m in normal])

    # N-1 summary: retained flow fraction actually demonstrated
    n1 = []
    for plan, m in variants:
        scen_flow = case.scenarios[plan["id"].split("/")[0]]["required_total_flow_kg_s"]
        retained = plan["source"]["flow"]
        n1.append(dict(case=plan["id"], kind=plan["kind"], outage=plan["outage"],
                       retained_kg_s=retained, fraction=retained / scen_flow))

    failures = [r for r in design.results if not r.ok]
    write_jsons(out, case, design, results, lcc, n1)
    write_layout_svg(out, design, design)
    write_report(out, case, design, results, normal, n1, lcc)

    hdr = f"{'FAIL' if failures else 'PASS'}: {len(design.results)} checks, {len(failures)} failed"
    print(hdr)
    for r in failures[:60]:
        print("  -", r.name, "|", r.detail)
    print(f"LCC = {lcc['lcc_mbcu']:.3f} MBCU")
    print(f"  equipment CAPEX   {lcc['equipment_capex_mbcu']:10.3f}")
    print(f"  piping CAPEX      {lcc['piping_capex_mbcu']:10.3f}")
    print(f"  civil/access      {lcc['civil_capex_mbcu']:10.3f}")
    print(f"  energy PV         {lcc['energy_pv_mbcu']:10.3f}  ({lcc['annual_energy_mwh']:.0f} MWh/a)")
    print(f"  maintenance PV    {lcc['maintenance_pv_mbcu']:10.3f}")
    return 0 if not failures else 1


def write_jsons(out, case, design, results, lcc, n1):
    design_doc = dict(
        case=case.case,
        units=dict(length="m", pressure="MPa", temperature="degC", flow="kg/s",
                   free_liquid_loading="kg liquid/kg gas", water_content="mg/Sm3",
                   power="MW", energy="MWh", cost="MBCU"),
        equipment=[
            dict(tag=n.tag, model_id=n.model["model_id"], category=n.category,
                 safety_category=n.safety_category, x_m=n.x, y_m=n.y, orientation_deg=n.o,
                 footprint_m=dict(length=n.length_m, width=n.width_m),
                 ports={pid: [round(v[0], 6), round(v[1], 6), v[2]] for pid, v in n.ports.items()},
                 role=n.role)
            for n in design.nodes.values()],
        pipelines=[
            dict(tag=p.tag, from_ref=list(p.a), to_ref=list(p.b),
                 from_endpoint=[round(p.points[0][0], 6), round(p.points[0][1], 6)],
                 to_endpoint=[round(p.points[-1][0], 6), round(p.points[-1][1], 6)],
                 nominal_diameter=p.dn, internal_diameter_m=case.diameters[p.dn]["internal_diameter_m"],
                 pipe_class=p.cls, service=p.service, length_m=round(p.length_m, 6),
                 segments=[dict(p0=[round(a[0], 6), round(a[1], 6)], p1=[round(b[0], 6), round(b[1], 6)],
                                level=lvl, length_m=round(math.hypot(b[0] - a[0], b[1] - a[1]), 6))
                           for (a, b, lvl, i) in p.segments()],
                 role=p.role)
            for p in design.pipes.values()],
        roads=[dict(tag=r["tag"], width_m=r["width_m"], centreline=r["pts"], role=r["role"])
               for r in design.roads],
        scenarios=[],
        lifecycle_cost=lcc,
        n1_summary=n1,
    )
    for plan, m in results:
        entry = dict(scenario_id=plan["id"], service=plan["service"],
                     hours=plan["hours"], kind=plan["kind"],
                     source={k: v for k, v in plan["source"].items()},
                     sink_required_pressure_mpa=plan["sink_required_mpa"],
                     setpoints={k: round(v, 6) for k, v in plan.items()
                                if k.startswith(("compressor_discharge", "regulator_outlet",
                                                 "boost_discharge", "cooler_outlet"))},
                     well_group_flows={w: round(plan["well_alloc"][w], 6) for w in O.WELLS},
                     train_flows={O.TRAINS[i][0]: round(plan["source"]["flow"] / len(plan["trains"]), 6)
                                  for i in plan["trains"]} if plan["service"] == "withdrawal" else {},
                     unit_flows={k: round(v, 6) for k, v in m.unit_flow.items()},
                     unit_states={k: {kk: (round(vv, 6) if isinstance(vv, float) else vv)
                                      for kk, vv in v.items()}
                                  for k, v in m.state.items()},
                     pipe_flows={t: round(res.flow, 6) for t, res in m.pipe_state.items()},
                     liquid_pipe_flows={t: round(f, 6) for t, f in m.liquid_pipe_flow.items()},
                     node_pressure_mpa={k: round(v.get("p_out", v.get("p", float("nan"))), 6)
                                        for k, v in m.state.items()},
                     node_temperature_c={k: round(v.get("t_out", v.get("t", float("nan"))), 4)
                                         for k, v in m.state.items()},
                     energy_mwh=round(m.energy_mwh, 6))
        design_doc["scenarios"].append(entry)
    (out / "design.json").write_text(json.dumps(design_doc, indent=2, sort_keys=False))


def write_report(out, case, design, results, normal, n1, lcc):
    lines = []
    add = lines.append
    add("# UGS-SYNTH-D01 - verification log\n")
    add(f"Automatically generated by `tools/build.py`. {len(design.results)} rule checks were")
    add("evaluated against the published v1.1 calculation and geometry basis; every value in")
    add("this file is recomputed from the brief data and the design definition.\n")
    fails = [r for r in design.results if not r.ok]
    add(f"* checks evaluated: **{len(design.results)}**")
    add(f"* failures: **{len(fails)}**\n")
    if fails:
        add("## Failures\n")
        for r in fails:
            add(f"* {r.name} - {r.detail}")
        add("")
    # checks by area
    areas = {}
    for r in design.results:
        key = r.name.split(":")[0]
        if key.startswith("["):
            key = "scenario: " + r.name.split("]")[0][1:].split("/")[0]
        elif key.startswith("segment"):
            key = "pipeline route"
        elif key.startswith("same-level"):
            key = "pipeline level rules"
        elif key.startswith(("separation", "no footprint overlap", "footprint")):
            key = "equipment layout"
        elif key.startswith(("clearance", "removal")):
            key = "maintenance geometry"
        elif key.startswith(("paved", "road", "ROAD", "crane")):
            key = "roads and access"
        a = areas.setdefault(key, [0, 0])
        a[0] += 1
        if not r.ok:
            a[1] += 1
    add("## Checks by area\n")
    add("| area | checks | failed |")
    add("|---|---|---|")
    for k in sorted(areas):
        add(f"| {k} | {areas[k][0]} | {areas[k][1]} |")
    add("")
    add("## Scenario setpoints and results\n")
    add("Setpoints are the operating values the design fixes for the scenario; the well-group and")
    add("GRID-TIE pressures are the values computed by marching the declared path.\n")
    add("| scenario | kind | setpoints | sink pressure (MPa) | energy (MWh) |")
    add("|---|---|---|---|---|")
    for plan, m in results:
        sp = []
        for k, v in plan.items():
            if k.startswith("compressor_discharge_setpoint"):
                sp.append(f"compressor discharge {v:.4f} MPa")
            if k.startswith("boost_discharge_setpoint"):
                sp.append(f"boost discharge {v:.4f} MPa")
            if k.startswith("regulator_outlet_setpoint"):
                sp.append(f"regulator outlet {v:.4f} MPa")
            if k == "cooler_outlet_c":
                sp.append(f"aftercooler outlet {v:.1f} degC")
        if plan["service"] == "injection":
            pmin = min(m.state[w]["p"] for w in O.WELLS)
            sink = f"{pmin:.4f} (min over 6 well groups, required {plan['sink_required_mpa']:g})"
        else:
            sink = f"{m.state['GRID-TIE']['p']:.4f} (required {plan['sink_required_mpa']:g})"
        add(f"| {plan['id']} | {plan['kind']} | {'; '.join(sp)} | {sink} | {m.energy_mwh:.1f} |")
    add("")
    add("## N-1 demonstration\n")
    add("| case | failed unit | retained flow (kg/s) | fraction of scenario flow |")
    add("|---|---|---|---|")
    for row in n1:
        add(f"| {row['case']} | {row['outage']} | {row['retained_kg_s']:.3f} | {row['fraction']:.3f} |")
    add("")
    add("## Lifecycle cost\n")
    add(f"* present-value factor ({case.economic_assumptions['discount_rate']:.2%}, "
        f"{case.economic_assumptions['project_life_years']} years): {lcc['pvf']:.6f}")
    add(f"* equipment CAPEX: {lcc['equipment_capex_mbcu']:.4f} MBCU")
    add(f"* piping CAPEX: {lcc['piping_capex_mbcu']:.4f} MBCU")
    add(f"* civil / access CAPEX: {lcc['civil_capex_mbcu']:.4f} MBCU "
        f"(roads {lcc['civil_breakdown']['roads']:.4f}, foundations "
        f"{lcc['civil_breakdown']['foundations']:.4f}, maintenance envelopes "
        f"{lcc['civil_breakdown']['maintenance_area']:.4f}, pipeline civil "
        f"{lcc['civil_breakdown']['pipeline_civil']:.4f})")
    add(f"* energy: {lcc['annual_energy_mwh']:.1f} MWh/a -> "
        f"{lcc['energy_annual_cost_mbcu']:.4f} MBCU/a -> PV {lcc['energy_pv_mbcu']:.4f} MBCU")
    add(f"* maintenance: {lcc['equipment_maintenance_mbcu_per_year']:.4f} MBCU/a -> PV "
        f"{lcc['maintenance_pv_mbcu']:.4f} MBCU")
    add(f"* **LCC = {lcc['lcc_mbcu']:.4f} MBCU**\n")
    add("## Quantities\n")
    q = lcc["quantities"]
    add(f"* equipment by model: {q['equipment']}")
    add(f"* pipeline length: {q['pipe_length_total_m']:.1f} m")
    add(f"* pipeline length by installation level: "
        f"{{{', '.join(f'{k}: {v:.1f} m' for k, v in sorted(q['pipe_length_by_level'].items()))}}}")
    add(f"* pipeline length by diameter: "
        f"{{{', '.join(f'{k}: {v:.1f} m' for k, v in sorted(q['pipe_length_by_dn'].items()))}}}")
    add(f"* road centreline length: {q['road_length_m']:.1f} m")
    add(f"* equipment footprint area: {q['footprint_area_m2']:.1f} m2")
    add(f"* required maintenance-envelope area: {q['maintenance_area_m2']:.1f} m2")
    (out / "verification.md").write_text("\n".join(lines) + "\n")

    csv = ["check,result,detail"]
    for r in design.results:
        csv.append(f'"{r.name}","{"ok" if r.ok else "FAIL"}","{r.detail}"')
    (out / "checks.csv").write_text("\n".join(csv) + "\n")


def write_layout_svg(out, case, design):
    """Plan-view drawing of the site, equipment, roads and pipeline routes."""
    case = design.case
    W, H = 700.0, 450.0
    scale = 1.5
    pad = 40
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'width="{int(W*scale+2*pad)}" height="{int(H*scale+2*pad+70)}" '
             f'viewBox="0 0 {W+2*pad/scale:.1f} {H+2*pad/scale+48:.1f}">']
    parts.append(f'<g transform="translate({pad/scale:.2f},{pad/scale:.2f}) scale(1,-1) '
                 f'translate(0,{-H:.1f})">')
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fbfbf7" stroke="#333" '
                 f'stroke-width="1.5"/>')
    for z in case.site["no_build_zones"]:
        pts = " ".join(f"{p[0]},{p[1]}" for p in z["polygon_m"])
        parts.append(f'<polygon points="{pts}" fill="#e8e0d8" stroke="#b0a090" '
                     f'stroke-dasharray="4 3" stroke-width="0.8"/>')
    for c in case.site["routing_corridors"]:
        pts = " ".join(f"{p[0]},{p[1]}" for p in c["polygon_m"])
        parts.append(f'<polygon points="{pts}" fill="none" stroke="#88a" stroke-dasharray="2 4" '
                     f'stroke-width="0.7"/>')
    for r in design.roads:
        pts = " ".join(f"{p[0]},{p[1]}" for p in r["pts"])
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#999" '
                     f'stroke-width="{r["width_m"]}" stroke-linecap="square" opacity="0.55"/>')
    level_colour = {"ground": "#c0392b", "buried": "#2e86c1", "rack_low": "#7d3c98",
                    "rack_high": "#1e8449"}
    for tag, pl in design.pipes.items():
        for (p0, p1, lvl, idx) in pl.segments():
            parts.append(f'<line x1="{p0[0]:.2f}" y1="{p0[1]:.2f}" x2="{p1[0]:.2f}" '
                         f'y2="{p1[1]:.2f}" stroke="{level_colour[lvl]}" stroke-width="1.1"/>')
    for tag, n in design.nodes.items():
        pts = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in n.footprint)
        parts.append(f'<polygon points="{pts}" fill="#f7d9a0" stroke="#7a5c1e" '
                     f'stroke-width="0.8"/>')
    for tag, iface in case.interfaces.items():
        x, y = iface["point_m"]
        parts.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#111"/>')
    parts.append("</g>")
    # labels are drawn in an unflipped frame so the text reads correctly
    def label(x, y, text, size=5.5, colour="#5a4010", anchor="middle"):
        return (f'<text x="{pad/scale + x:.2f}" y="{pad/scale + (H - y):.2f}" '
                f'font-size="{size}" fill="{colour}" text-anchor="{anchor}">{text}</text>')

    for z in case.site["no_build_zones"]:
        x, y = z["polygon_m"][0]
        parts.append(label(x + 3, y + 10, z["zone_id"], 7, "#7a6a5a", "start"))
    for tag, n in design.nodes.items():
        parts.append(label(n.x, n.y, tag))
    for tag, iface in case.interfaces.items():
        x, y = iface["point_m"]
        parts.append(label(x, y - 7, tag, 6.5, "#111", "middle"))
    # legend (drawn below the site, in the same unflipped frame)
    parts.append(label(4, -6, "UGS-SYNTH-D01 plan view - coordinates in m, site 700 x 450 m",
                       9, "#111", "start"))
    entries = [("pipeline: ground", "#c0392b"), ("pipeline: buried", "#2e86c1"),
               ("pipeline: rack_low", "#7d3c98"), ("pipeline: rack_high", "#1e8449"),
               ("equipment footprint", "#f7d9a0"), ("road", "#999"),
               ("no-build zone", "#e8e0d8")]
    for i, (txt, col) in enumerate(entries):
        x = 4 + i * 95
        parts.append(f'<rect x="{pad/scale + x:.2f}" y="{pad/scale + H + 16:.2f}" width="9" '
                     f'height="9" fill="{col}" stroke="#444" stroke-width="0.5"/>')
        parts.append(label(x + 12, -24, txt, 7.5, "#222", "start"))
    parts.append("</svg>")
    (out / "layout.svg").write_text("\n".join(parts))


if __name__ == "__main__":
    raise SystemExit(main())
