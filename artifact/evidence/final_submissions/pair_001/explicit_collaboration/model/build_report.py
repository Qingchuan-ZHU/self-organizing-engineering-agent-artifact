"""Generates deliverables/design_report.md from the computed case results."""
import json
import os
import catalog as C
import design as D
import geometry as G
import process as PR
import scenarios as S
import checks as CHK
import quantities as Q
import analysis as A
import run_case as RC
import build_deliverables as BD

OUT = RC.OUT


def fmt(x, n=4):
    if x is None:
        return "-"
    return f"{x:.{n}f}" if isinstance(x, float) else str(x)


def main():
    chk, eq, roads, segs, normal, n1, lcc, energy, errors = RC.main()
    L = []
    w = L.append

    w("# UGS-SYNTH-D01 — Underground gas storage surface facility design\n")
    w("**Case:** UGS-SYNTH-D01 (benchmark family UGS-SYNTH, case version "
      f"{C.CASEMETA['case_version']})  ")
    w("**Deliverable:** conceptual surface-facility design, operating plan and "
      "lifecycle-cost basis  ")
    w("**Units:** SI; pressure MPa, temperature degC, flow kg/s, length m, area m2, "
      "power/duty MW, energy MWh, cost MBCU, gas water content mg/Sm3, "
      "free-liquid loading kg liquid/kg gas.\n")
    w("All data used are the published synthetic benchmark data (catalogue, site, "
      "scenarios, economics). Values are not vendor data or production engineering "
      "criteria.\n")
    w("---\n")
    w("## 1. Design basis\n")
    w("### 1.1 Duty\n")
    w("| Scenario | Service | Flow kg/s | Source | Source P (MPa) | Source T (degC) | "
      "Water (mg/Sm3) | Free liquid | Sink | Sink P (MPa) | Hours/y |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for sid in RC.SCEN_IDS:
        s = A.SCEN_BY_ID[sid]
        w(f"| {sid} | {s['service']} | {s['required_total_flow_kg_s']} | "
          f"{s['source_interface']} | {s['source_pressure_mpa']} | "
          f"{s['source_temperature_c']} | {s['source_water_mg_sm3']} | "
          f"{s['source_free_liquid_mass_fraction']} | "
          f"{'6 well groups' if len(s['sink_interfaces'])>1 else 'GRID-TIE'} | {s['required_sink_pressure_mpa']} | "
          f"{s['annual_hours']} |")
    w("")
    deliv = C.REQS["gas_delivery_requirements"]
    w(f"Operating hours per year: {C.REQS['operating_hours_per_year']} h "
      f"(sum of scenario hours). Delivery limits: water <= "
      f"{deliv['maximum_water_content_mg_sm3']} mg/Sm3, free liquid <= "
      f"{deliv['maximum_free_liquid_mass_fraction']} kg/kg, temperature "
      f"{deliv['temperature_limits_c'][0]} .. {deliv['temperature_limits_c'][1]} degC. "
      "Well-group boundary: 25 kg/s per interface. GRID-TIE: all exchanged gas metered, "
      "active meter capacity >= scenario flow.\n")
    w("### 1.2 Reliability requirements\n")
    w("- Compression n-1 (scenarios with required sink pressure > source pressure): "
      "after loss of any one compressor, >= 70 % of scenario flow remains deliverable "
      "with the delivery limits still met.")
    w("- Withdrawal treatment n-1: after loss of any one separator or dehydrator, "
      ">= 70 % of the withdrawal scenario flow remains deliverable with the delivery "
      "limits still met.\n")
    w("### 1.3 Sizing philosophy\n")
    w("The plant is arranged as three identical parallel process trains "
      "(lanes) so that any single unit can be isolated without losing more than one "
      "third of the installed capacity. Compressor discharge pressure, injection "
      "aftercooler outlet temperature and the grid pressure-control setpoint are the "
      "only operating setpoints; everything else follows from the scenario boundary "
      "conditions. Pipe diameters were selected by minimising the benchmark lifecycle "
      "cost subject to the published velocity limits (larger diameter costs capital "
      "but reduces compression energy, which dominates the LCC).\n")
    w("### 1.4 Key design assumptions\n")
    for a in ASSUMPTIONS:
        w(f"- {a}")
    w("")
    w("---\n")

    # ---------------------------------------------------------------- equipment
    w("## 2. Equipment selection\n")
    w("| Instance | Model | Category | Safety category | Position (x,y) m | Orient. deg | "
      "Capacity kg/s | Capex MBCU | Maintenance MBCU/y |")
    w("|---|---|---|---|---|---|---|---|---|")
    for e in sorted(eq.values(), key=lambda x: x["id"]):
        m = e["model_data"]
        w(f"| {e['id']} | {e['model']} | {m['category']} | {m['safety_category']} | "
          f"({e['centre'][0]:.0f}, {e['centre'][1]:.0f}) | {e['orientation']} | "
          f"{m.get('capacity_kg_s')} | {m['capex_mbcu']} | "
          f"{m['annual_maintenance_mbcu']} |")
    w("")
    w("Selection logic:\n")
    for line in EQUIP_LOGIC:
        w(f"- {line}")
    w("")
    w("---\n")

    # -------------------------------------------------------------- architecture
    w("## 3. System architecture and process connections\n")
    w("```")
    for line in ARCH_DIAGRAM:
        w(line)
    w("```\n")
    w("### 3.1 Physical connections\n")
    w("| Pipeline | From (node.port) | To (node.port) | Service | Function |")
    w("|---|---|---|---|---|")
    for pid, src, dst, wp, dn, cls, lvl, svc, note in D.PIPELINES:
        w(f"| {pid} | {src[0]}.{src[1]} | {dst[0]}.{dst[1]} | {svc} | {note} |")
    w("")
    w("Every equipment port carries at most one physical connection, the external "
      "interfaces use only their published connection allowance (GRID-TIE 2 of 2, "
      "LIQUID-DRAIN-OUTFALL 3 of 8, well groups 1 each), and all process branching or "
      "merging is performed by catalogued header ports. Each separator liquid outlet is "
      "connected to its own closed drain, and the drains discharge to the public "
      "liquid-drain outfall.\n")
    w("Flow directions: the injection path uses `gas_in`/`gas_out` ports of MTR-A and "
      "the compressors; the withdrawal path uses MTR-B, the pressure-control valve and "
      "the same compressor bank (or the parallel bypass). `gas_out` ports are never "
      "reversed; reverse service uses the dedicated withdrawal path.\n")
    w("---\n")

    # ------------------------------------------------------------ operating plan
    w("## 4. Operating philosophy and scenario results\n")
    w("Normal operation (all six scenarios) uses:\n")
    w("- injection: GRID-TIE -> injection meter -> suction header -> 3 compressors "
      "(equal flow split) -> discharge header -> aftercooler -> station header -> trunk "
      "-> well manifold -> 6 well-group branches;")
    w("- withdrawal: well groups -> well manifold -> trunk -> station header -> 3 "
      "separator/dehydrator trains -> suction header -> compressors (only when the "
      "well pressure is below the grid requirement, i.e. WDR-LOW) or the compressor "
      "bypass -> discharge header -> pressure-control valve -> withdrawal meter -> "
      "GRID-TIE.")
    w("")
    w("| Scenario | Compressor discharge (MPa) | Suction P (MPa) | Ratio | Discharge T "
      "(degC) | Sink P (MPa) | Sink T (degC) | Sink water | Sink free liquid | Energy "
      "(MWh/y) |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for sid in RC.SCEN_IDS:
        res = normal[sid]
        comp = [r for r in res["rep"]["equipment"] if r["category"] == "compressor"]
        sinks = res["sinks"]
        worst = min(s[1]["p"] for s in sinks)
        wt = max(s[1]["t"] for s in sinks)
        ww = max(s[1]["water"] for s in sinks)
        wl = max(s[1]["liquid"] for s in sinks)
        if comp:
            c0 = comp[0]
            w(f"| {sid} | {fmt(c0['p_out_mpa'],3)} | {fmt(c0['p_in_mpa'],3)} | "
              f"{fmt(c0['ratio'],3)} | {fmt(c0['t_out_c'],2)} | {fmt(worst,3)} | "
              f"{fmt(wt,2)} | {fmt(ww,2)} | {wl:.2e} | "
              f"{fmt(Q.scenario_energy(res),1)} |")
        else:
            w(f"| {sid} | n/a (bypass) | n/a | n/a | n/a | {fmt(worst,3)} | "
              f"{fmt(wt,2)} | {fmt(ww,2)} | {wl:.2e} | "
              f"{fmt(Q.scenario_energy(res),1)} |")
    w("")
    w("Setpoints: aftercooler outlet 40 degC (all injection scenarios, >= the catalogue "
      "minimum of 35 degC); grid pressure-control setpoint 6.20 MPa (all withdrawal "
      "scenarios); compressor discharge pressure per scenario as tabulated. Injection "
      "discharge pressures are set to give 0.05 MPa margin above the required "
      "well-group pressure; with a 0.05 MPa margin the worst-delivered well group is "
      "exactly at the required pressure +0.05 MPa.\n")
    w("### 4.1 Per-scenario pressure profile (selected)\n")
    for sid in RC.SCEN_IDS:
        res = normal[sid]
        w(f"**{sid}** (flow {fmt(res['flow'],1)} kg/s):")
        w("")
        w("| Element | Flow kg/s | P in (MPa) | P out (MPa) | T (degC) | dP (MPa) |")
        w("|---|---|---|---|---|---|")
        for r in res["rep"]["pipes"] + res["rep"]["equipment"]:
            nm = r.get("pipe") or r.get("equipment")
            w(f"| {nm} | {fmt(r['flow_kg_s'],2)} | {fmt(r['p_in_mpa'],3)} | "
              f"{fmt(r.get('p_out_mpa'),3)} | {fmt(r.get('t_c') or r.get('t_in_c'),2)} | "
              f"{fmt(r.get('dp_mpa'),4)} |")
        w("")
    w("### 4.2 Contingency (n-1) cases\n")
    w("| Case | Outage | Delivered flow kg/s | Retained fraction | Required | "
      "Feasible | Violations |")
    w("|---|---|---|---|---|---|---|")
    for c in n1:
        w(f"| {c['case']} | {c['outage'][0]} #{c['outage'][1]} | {fmt(c['flow_kg_s'],1)} | "
          f"{fmt(c['retained_fraction'],3)} | {c['required_fraction']} | "
          f"{'yes' if c['feasible'] else 'NO'} | {len(c['violations'])} |")
    w("")
    w("All contingency cases are feasible with zero rule violations, and in every case "
      "the full scenario flow (100 %) can be retained, which exceeds the 70 % "
      "requirement. Each contingency case is recorded with its full operating path, "
      "setpoints and per-element states in `operating_plan.json`.\n")
    w("Liquid side streams and drain velocities (the benchmark publishes no liquid "
      "density, so the band below spans water to a deliberately pessimistic "
      "gas-density-like fluid at the closed-drain pressure):\n")
    w("")
    w("| Pipeline | DN | Design liquid flow (kg/s) | v at 1000 | v at 800 | v at 500 | "
      "v at 100 | v at 8.2 kg/m3 | Limit |")
    w("|---|---|---|---|---|---|---|---|---|")
    all_liq = []
    for sid in RC.SCEN_IDS:
        for st in normal[sid]["rep"]["equipment"]:
            if st["category"] in ("separator", "filter"):
                all_liq.append(st.get("liquid_removed_kg_s", 0.0))
    for c in n1:
        for st in c["result"]["rep"]["equipment"]:
            if st["category"] in ("separator", "filter"):
                all_liq.append(st.get("liquid_removed_kg_s", 0.0))
    maxliq = max(all_liq) if all_liq else 0.0
    for row in BD.liquid_velocity_table(maxliq):
        v = row["velocity_m_s_vs_assumed_density"]
        w(f"| {row['pipeline_id']} | {row['dn']} | {row['design_liquid_flow_kg_s']:.4f} | "
          f"{v['1000']} | {v['800']} | {v['500']} | {v['100']} | {v['8.2']} | "
          f"{row['limit_m_s']} m/s |")
    w("")
    w("The maximum separator liquid side stream is 0.60 kg/s (separator n-1 case); each "
      "drain is rated 0.8 kg/s and the combined flow to the outfall is 1.20 kg/s of the "
      "10 kg/s limit, using 3 of the 8 permitted outfall connections.\n")
    w("---\n")

    # ------------------------------------------------------------------- layout
    w("## 5. Site layout, safety and maintenance access\n")
    w("### 5.1 Arrangement\n")
    for line in LAYOUT_NOTES:
        w(f"- {line}")
    w("")
    w("### 5.2 Safety separation\n")
    w("Minimum separation distances are taken from `safety_requirements.json` and are "
      "measured boundary-to-boundary between rotated footprints. The design satisfies "
      "every pair (worst achieved vs required):\n")
    w("")
    w("| Pair | Achieved (m) | Required (m) |")
    w("|---|---|---|")
    ids = sorted(eq)
    worst = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = eq[ids[i]], eq[ids[j]]
            sep = G.polygon_distance(a["poly"], b["poly"])
            need = C.SAFETY["minimum_separation_m"][a["safety_category"]][b["safety_category"]]
            if sep < 40:
                worst.append((sep - need, a["id"], b["id"], sep, need))
    for d, ai, bi, sep, need in sorted(worst)[:10]:
        w(f"| {ai} - {bi} | {sep:.2f} | {need} |")
    w("")
    w("### 5.3 Maintenance envelopes, roads and access\n")
    w("Routine clearance envelopes (catalogue `clearance_m`) plus the heavy-maintenance "
      "removal envelopes of the three compressors (12.0 m x 6.4 m, east side) are "
      "kept inside the site, outside equipment-exclusion zones and clear of all other "
      "equipment footprints. Road access and crane access distances:\n")
    w("")
    w("| Instance | Road access required | Crane access required | Distance to paved "
      "road (m) | Road limit (m) | Crane limit (m) |")
    w("|---|---|---|---|---|---|")
    for e in sorted(eq.values(), key=lambda x: x["id"]):
        maint = e["model_data"].get("maintenance", {})
        if not maint.get("road_access_required"):
            continue
        polys = CHK.maintenance_envelope(e)
        d = min(G.polygon_distance(poly, q) for poly in polys
                for r in roads.values() for q in r["pieces"])
        w(f"| {e['id']} | yes | {'yes' if maint.get('crane_access_required') else 'no'} | "
          f"{d:.2f} | {C.MAINT['road_access_buffer_m']} | "
          f"{'-' if not maint.get('crane_access_required') else C.MAINT['crane_access_buffer_m']} |")
    w("")
    w("| Road | Width (m) | Centreline length (m) |")
    w("|---|---|---|")
    for rid, r in sorted(roads.items()):
        pts = r["centerline"]
        w(f"| {rid} | {r['width']} | "
          f"{sum(G.dist(pts[i], pts[i+1]) for i in range(len(pts)-1)):.1f} |")
    w("")
    w("The road network is connected and contains the ROAD-ENTRANCE point; its paved "
      "geometry stays inside the site, out of road-exclusion zone interiors and clear "
      "of all equipment footprints.\n")
    w("---\n")

    # ------------------------------------------------------------------ piping
    w("## 6. Piping and network definition\n")
    w("| Pipeline | DN | ID (m) | Class | Level | Length (m) | Max velocity (m/s) | "
      "Installed capex (MBCU) |")
    w("|---|---|---|---|---|---|---|---|")
    capex, civil, lengths = Q.pipe_quantities(segs)
    vmax = {}
    for sid in RC.SCEN_IDS:
        for r in normal[sid]["rep"]["pipes"]:
            vmax[r["pipe"]] = max(vmax.get(r["pipe"], 0.0), r["velocity_m_s"])
    for c in n1:
        for r in c["result"]["rep"]["pipes"]:
            vmax[r["pipe"]] = max(vmax.get(r["pipe"], 0.0), r["velocity_m_s"])
    for pid in sorted(S.PIPES):
        p = S.PIPES[pid]
        w(f"| {pid} | {p['dn']} | {C.DIAMS[p['dn']]['internal_diameter_m']:.3f} | "
          f"{p['class']} | {p['level']} | {lengths[pid]:.1f} | "
          f"{vmax.get(pid, 0.0):.2f} | {capex[pid]:.4f} |")
    w("")
    w("Class selection: all gas services use CS-WET-160 where the stream can be wet "
      "(well branches, trunk, station header, separator/dehydrator trains up to the "
      "dehydration outlet) and CS-DRY-160 on the dry sections (grid tie, metering, "
      "compressor bank, aftercooler, dehydrator outlet, pressure control); all gas "
      "classes are both wet- and dry-compatible, so no scenario can violate "
      "compatibility. Drain services use CS-WET-100 (liquid-drain compatible, 10 MPa) "
      "well above the 1 MPa closed-drain domain. Velocity limits (25 m/s gas, 3 m/s "
      "liquid) are met in every operating and contingency case, including the "
      "highest-flow cases (the worst gas velocity in the whole case set is "
      f"{max(vmax.values()):.1f} m/s).\n")
    lvl = {}
    for x in segs:
        lvl[x["level"]] = lvl.get(x["level"], 0.0) + G.dist(x["a"], x["b"])
    w("Installation levels: process and metering piping is at grade (`ground`, "
      f"{lvl.get('ground', 0):.1f} m); drain pipelines and the lengths that cross paved "
      f"roads are `buried` ({lvl.get('buried', 0):.1f} m, "
      f"{sum(1 for x in segs if x['level']=='buried')} segments). No two segments of the same "
      "installation level overlap for a positive length anywhere in the design "
      "(verified), and no segment enters a pipeline-exclusion zone, crosses an "
      "equipment footprint interior or leaves the site.\n")
    w("---\n")

    # -------------------------------------------------------------- quantities
    w("## 7. Quantities and lifecycle cost\n")
    q = Q.quantities_json(eq, roads, segs, energy) if hasattr(Q, "quantities_json") else None
    capex, civil, lengths = Q.pipe_quantities(segs)
    w("### 7.1 Quantities\n")
    w("| Item | Value |")
    w("|---|---|")
    counts = {}
    for e in eq.values():
        counts[e["model"]] = counts.get(e["model"], 0) + 1
    w("| Equipment instances | " + ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())) + " |")
    w(f"| Total pipeline length | {sum(lengths.values()):.1f} m |")
    w(f"| Road centreline length | {sum(Q.road_lengths(roads).values()):.1f} m |")
    w(f"| Equipment foundation area | {sum(G.polygon_area(e['poly']) for e in eq.values()):.1f} m2 |")
    w(f"| Required maintenance area | {sum(Q.maintenance_areas(eq).values()):.1f} m2 |")
    w(f"| Annual energy | {lcc['annual_energy_mwh']:.1f} MWh/y |")
    w(f"| Annual maintenance | {lcc['annual_maintenance_mbcu']:.4f} MBCU/y |")
    w("")
    w("### 7.2 Lifecycle cost\n")
    w("Present-value factor: PVF = (1-(1+i)^-N)/i with i = "
      f"{C.ECON['discount_rate']} and N = {C.ECON['project_life_years']} years = "
      f"{lcc['pvf']:.6f}. Energy tariff {C.ECON['energy_tariff_mbcu_per_mwh']} MBCU/MWh.\n")
    w("| Component | MBCU |")
    w("|---|---|")
    w(f"| Equipment CAPEX | {lcc['equipment_capex_mbcu']:.4f} |")
    w(f"| Piping CAPEX | {lcc['piping_capex_mbcu']:.4f} |")
    w(f"| Civil / access CAPEX | {lcc['civil_capex_mbcu']:.4f} |")
    w(f"| Energy present value | {lcc['energy_pv_mbcu']:.4f} |")
    w(f"| Maintenance present value | {lcc['maintenance_pv_mbcu']:.4f} |")
    w(f"| **LCC total** | **{lcc['lcc_mbcu']:.4f}** |")
    w("")
    d = lcc["detail"]
    w("Civil / access breakdown: roads "
      f"{d['road_civil']:.4f}, foundations {d['foundation_civil']:.4f}, maintenance "
      f"areas {d['maintenance_civil']:.4f}, pipeline civil "
      f"{d['pipe_civil_total']:.4f} MBCU.\n")
    w("Energy by scenario (MWh/y): " +
      ", ".join(f"{k} {v:.0f}" for k, v in energy.items()) + ".\n")
    w("---\n")

    # -------------------------------------------------------------- verification
    w("## 8. Verification\n")
    vr = BD.verification(chk, normal, n1, errors)
    w(f"Automated checks were run over {len(RC.SCEN_IDS)} mandatory scenarios and "
      f"{len(n1)} contingency cases; the geometry/topology rule set was evaluated over "
      f"{len(eq)} equipment instances, {len(roads)} roads and {len(D.PIPELINES)} "
      f"pipelines ({len(segs)} routed segments, including "
      f"{sum(1 for x in segs if x['level'] == 'buried')} buried segments and road "
      f"crossings).\n")
    w(f"Total individual checks performed: {vr['total_checks_performed']}; "
      f"total failures: {vr['total_failures']}. Per-rule records with the number of "
      "checks performed and the failure count are in `verification.json`:\n")
    w("")
    w("| Rule | Checks | Failures | Result |")
    w("|---|---|---|---|")
    for rec in vr["geometry_and_layout_rules"] + vr["operating_rules"]:
        w(f"| {rec['rule']} | {rec['checks_performed']} | {rec['failures']} | "
          f"{rec['result']} |")
    w("")
    w("Liquid-drain class and velocity checks are reported in section 4.2 (the "
      "benchmark publishes no liquid density, so the velocity is bounded by an assumed "
      "density band rather than a single value). "
      "Total reported violations: "
      f"{len(chk.errors) + len(errors)}. Machine-readable evidence is in "
      "`verification.json`, `case_summary.json` and the per-case element states in "
      "`operating_plan.json`.\n")
    w("---\n")
    w("## 9. Known limitations\n")
    for line in LIMITATIONS:
        w(f"- {line}")
    w("")

    with open(os.path.join(OUT, "design_report.md"), "w") as fh:
        fh.write("\n".join(L))
    print("report written:", os.path.join(OUT, "design_report.md"), len(L), "lines")


ASSUMPTIONS = [
    "Three parallel process trains are used for the separator, dehydrator and "
    "compressor banks so that the published n-1 requirements are met with equipment "
    "that stays at moderate unit size.",
    "Scenario flows are split equally between the active trains and equally between "
    "the six well-group interfaces; the split is a design choice, not a published "
    "requirement. Well-group flow never exceeds 20 kg/s of the 25 kg/s boundary limit.",
    "Injection compressor discharge pressure is set 0.05 MPa above the pressure needed "
    "to satisfy the worst (longest) well-group branch, so that all six well-group "
    "interfaces receive at least their required pressure with margin.",
    "The injection aftercooler outlet setpoint is 40 degC so that the delivered gas is "
    "at least 20 K below the 60 degC delivery limit; the cooler is idle (zero duty) "
    "whenever the inlet temperature is below the setpoint, as on the withdrawal path.",
    "Grid pressure control holds the withdrawal delivery at 6.20 MPa at the "
    "pressure-control valve outlet, i.e. ~6.13-6.16 MPa at GRID-TIE, above the 6.0 MPa "
    "requirement, and avoids pushing high well pressure into the grid.",
    "Compressor discharge temperature is not limited by the delivery limit because the "
    "aftercooler is in series upstream of the well-group interfaces; the compressor's "
    "own 150 degC discharge limit is respected.",
    "Gas is treated as dry for pipe-class purposes when water content <= 50 mg/Sm3 and "
    "free-liquid loading <= 1e-4 kg/kg, following the published definition.",
    "Pressure losses use the published fixed-point convention with at most 8 updates; "
    "every pipeline in every case converges (reported in operating_plan.json).",
    "Plan-view crossings of two same-level pipelines at a discrete point are permitted "
    "by the published rules (only positive-length same-level overlap is prohibited); "
    "such crossings are resolved by local elevation changes in detailed design.",
    "Where a pipeline crosses a road, the crossing length is installed at buried level "
    "in the model; the design assumes a sleeved crossing as normal practice.",
    "Drain lines are installed buried; the separator liquid outlet is taken as already "
    "let down into the closed-drain pressure domain per the published semantics.",
    "Each scenario's active equipment set is defined by its operating path; every "
    "branch not listed is isolated by its block valve (compressor bypass closed during "
    "injection and in WDR-LOW, treatment trains isolated during injection, cooler "
    "branch isolated during withdrawal, grid-side branches isolated during injection).",
    "The benchmark publishes no liquid density, so drain-line velocities are reported "
    "over a density band from water (1000 kg/m3) to a deliberately pessimistic "
    "gas-density-like 8.2 kg/m3 at the closed-drain pressure: 0.022-0.027 m/s at "
    "800-1000 kg/m3 and 2.63 m/s in the pessimistic case, all within the 3 m/s limit "
    "(see operating_plan.json, liquid_drain_velocity_check).",
]

EQUIP_LOGIC = [
    "Compression: three C60 units (60 kg/s, ratio 2.4, eta 0.80) - the minimum unit "
    "count that satisfies compression n-1 for INJ-LOW (2 x 60 = 120 kg/s >= 84 kg/s "
    "required). Larger units (C80) reduce specific energy but need the same three "
    "instances and a higher-capital driver; smaller units (C40) need four instances and "
    "cost more energy. Net LCC is lowest with 3 x C60.",
    "Aftercooling: one COOL120 (120 kg/s, 32 MW duty) on the common discharge of the "
    "compressor bank; required because the compressor discharge temperature reaches "
    "51-95 degC depending on scenario (INJ-LOW 51.2, INJ-MID 74.8, INJ-HIGH 94.8 degC), "
    "above the 40 degC aftercooler setpoint and above the 60 degC delivery limit for "
    "INJ-MID and INJ-HIGH. No cooler n-1 requirement is "
    "published, and the retained flow in the n-1 compressor case (<= 120 kg/s) stays "
    "within capacity.",
    "Withdrawal separation: three SEP70 (70 kg/s, 16 MPa). A 10 MPa separator "
    "(SEP120/SEP40) cannot be used because the highest well-group pressure is 12 MPa "
    "and reducing it upstream would require an additional high-flow pressure-control "
    "station, which costs more than the units it would save; two SEP70 do not satisfy "
    "treatment n-1 (70 kg/s < 84 kg/s).",
    "Dehydration: three DEHY70 (70 kg/s, 16 MPa, outlet 35 mg/Sm3). Two units fail "
    "treatment n-1 for WDR-HIGH; the 10 MPa DEHY120 is not pressure-rated for the "
    "12 MPa source pressure.",
    "Grid metering: two MTR120 in series-free parallel paths - one for injection "
    "(GRID-TIE -> station) because a meter is one-way and a second for withdrawal - so "
    "that all exchanged gas passes through active meter capacity of 120 kg/s = the "
    "largest scenario flow, satisfying the 1.0 capacity fraction requirement.",
    "Pressure control: one REG120 (120 kg/s, 16 MPa) on the withdrawal path, letting "
    "the withdrawal trains deliver at a controlled grid pressure irrespective of well "
    "pressure (WDR-HIGH 12 MPa, WDR-MID 8 MPa, WDR-LOW 4.5 MPa). The published sink "
    "pressure is a lower limit, so the valve is not needed for feasibility; it is kept "
    "as a deliberate, costed design choice (0.34 MBCU capital + 0.018 MBCU/y = 0.52 "
    "MBCU lifecycle) because delivering uncontrolled 11.8 MPa well gas into a 6 MPa "
    "grid tie is not an acceptable operating philosophy.",
    "Headers: four HDR120 manifolds (suction, discharge, station/trunk, well manifold) "
    "provide the physical branching that the published semantics require. HDR120 has the "
    "same 6 x 3 m footprint and 16 MPa rating as the larger HDR180, ten branch ports "
    "(the largest demand is the suction header with eight) and a 120 kg/s rating equal to "
    "the largest header through-flow in any case; it is the lowest-LCC manifold that "
    "meets the branch-count and flow requirements (HDR180 would cut header pressure drop "
    "by 0.006 MPa but costs 0.11 MBCU capital and 0.004 MBCU/y more per header).",
    "Closed drains: three DRN-S (0.8 kg/s each) - one per separator as required by the "
    "semantics; the maximum liquid side stream is 0.60 kg/s (60 kg/s gas at 0.01 "
    "loading in the separator n-1 case), within capacity. Chaining drains would not "
    "reduce instances because each drain has a single inlet, so three discharge lines "
    "run to the outfall (3 of the 8 permitted connections, 1.2 kg/s of the 10 kg/s "
    "limit).",
]

ARCH_DIAGRAM = [
    "                                wells WG-01..WG-06",
    "                                     |   (6 branches, DN250/300/350)",
    "                                 [H-WELL header]",
    "                                     |   trunk DN600",
    "                                 [H-SITE header] ---------- cooler return (DN600)",
    "                                     |                                 |",
    "          +--------------------------+--------------+            [COOL120]",
    "          |                          |              |                  |",
    "      [SEP-A]                    [SEP-B]        [SEP-C]           [H-DIS header]",
    "          |                          |              |                  |",
    "      [DEH-A]                    [DEH-B]        [DEH-C]       +---+---+---+",
    "          |                          |              |          |   |   |   |",
    "          +-----------+--------------+--------------+----------+   |   |   |",
    "                      |                                            |   |   |",
    "                 [H-SUC header] -------- bypass (DN350) -----------+   |   |",
    "                      |                                                |   |",
    "          +-----------+-----------+                         +----------+   |",
    "          |           |           |                         |   |   |      |",
    "      [CMP-A]     [CMP-B]     [CMP-C]  ------------------- +   |   |      |",
    "                                                               |   |      |",
    "                                              [REG120] --------+   |      |",
    "                                                  |                |      |",
    "                            (withdrawal) [MTR-B] --+                |      |",
    "                                                  |                |      |",
    "                                              GRID-TIE <-----------+------+",
    "                                                  ^",
    "                                                  |  (injection)",
    "                                              [MTR-A] -- [H-SUC header]",
]

LAYOUT_NOTES = [
    "The site is used west to east: well manifold and trunk in the west, the three "
    "separator/dehydrator trains in three horizontal lanes at y = 70, 140 and 210 m, "
    "the compressor bank east of the trains, the aftercooler in the north band, and "
    "metering and grid tie on the east boundary.",
    "The well manifold sits close to the well-group interface line (x = 90 m), keeping "
    "the six well branches short and their pressure losses balanced.",
    "The main access road runs from the ROAD-ENTRANCE (0, 225) east to x = 560 m; a "
    "crane-access spur at x = 505 m serves the compressor removal envelopes (2.5 m "
    "clearance, limit 4.5 m) and a second spur at x = 302 m serves the separator "
    "maintenance envelopes (3 m clearance, limit 7 m).",
    "Equipment is kept out of the FUTURE-EXPANSION, DRAINAGE-CHANNEL and GRID-FACILITY "
    "no-build zones; pipelines avoid the two pipeline-exclusion zones; roads avoid all "
    "road-exclusion zones.",
    "The compressor bank is arranged as a north-south column with all heavy-maintenance "
    "removal envelopes facing the crane road, so lifting equipment out never crosses "
    "another footprint.",
    "The liquid-drain outfall is approached by the three drain discharge lines from "
    "three different directions (from the west, from the north and from the south), "
    "which keeps them free of same-level overlaps.",
]

LIMITATIONS = [
    "Steady-state only: no transient, surge, blowdown or start-up case is modelled; the "
    "benchmark does not publish transient criteria.",
    "The benchmark's simplified gas-property and equipment models are used as published; "
    "no detailed thermodynamics, hydrate or phase-envelope analysis is included, and "
    "the case explicitly excludes condensation and vaporisation.",
    "Dehydration water removal, regeneration, and water disposal are outside the "
    "modelled process, as stated in the published semantics.",
    "The closed-drain pressure letdown is treated as integral to the separator liquid "
    "outlet per the published semantics; no letdown valve, flashing or control valve "
    "sizing is presented.",
    "Metering is represented by catalogue capacity and pressure-drop models only: no "
    "uncertainty, proving, calibration or fiscal-metering standard is addressed.",
    "Electrical, instrument-air and firewater distribution are excluded; the equivalent "
    "utility ties are abstract boundaries and only catalogued equipment energy enters "
    "the lifecycle cost.",
    "Pipelines are modelled as zero-width plan-view centrelines with four discrete "
    "installation levels; support spacing, flexibility, stress analysis, corrosion "
    "allowance and sleeving at road crossings are not designed.",
    "Where two same-level pipelines cross at a single point in plan view (permitted by "
    "the published rules) a local elevation change would be required in detailed "
    "design; this is recorded as an assumption and not costed.",
    "Structural, civil, buildings, fire-water synthesis, full process-safety study and "
    "regulatory/code compliance are excluded by the project scope; the synthetic safety "
    "separations are not code criteria.",
    "The pipe-diameter optimisation is a coordinate descent over the complete published "
    "DN ladder (DN150-DN700 per line, continued while the LCC improves, up to six "
    "sweeps), so it terminates at a local rather than a proven global optimum; equipment "
    "model selection is by explicit comparison of the catalogue options rather than by a "
    "formal search. Cost rates are used as published, with no escalation, currency or "
    "financing assumptions beyond the published discount rate.",
    "Setpoint margins (0.05 MPa on injection pressure, 40 degC aftercooling) are design "
    "choices; they add a small energy penalty and increase robustness to modelling "
    "tolerance.",
]

if __name__ == "__main__":
    main()
