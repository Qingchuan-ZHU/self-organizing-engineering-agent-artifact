"""Generate the design report (DESIGN_REPORT.md) from the model and the design.

Usage:  python make_report.py [--brief DIR] [--out FILE]
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

TRAIN_TAG = {"SEP-WDR-01": "A", "SEP-WDR-02": "B", "SEP-WDR-03": "C"}


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default=str(here.parent.parent / "brief"))
    ap.add_argument("--out", default=str(here.parent / "DESIGN_REPORT.md"))
    args = ap.parse_args()
    case = B.CaseData(Path(args.brief))
    design = Design(case, D.EQUIPMENT, D.PIPES, D.ROADS)
    design.check_connections()
    design.check_equipment_geometry()
    design.check_maintenance_envelopes()
    design.check_roads()
    design.check_road_access()
    design.check_pipeline_geometry()
    plans = O.build_plans(design)
    results, normal, variants = [], [], []
    for plan in plans:
        p, m = O.run_plan(design, plan)
        results.append((p, m))
        (normal if plan["kind"] == "normal" else variants).append((p, m))
        for name, ok, detail in m.checks:
            design.add(f"[{plan['id']}] {name}", ok, detail)
    C.check_pipes_against_service(design, [m for _, m in results])
    lcc = C.compute_lcc(design, [m for _, m in normal])
    q = lcc["quantities"]
    fails = [r for r in design.results if not r.ok]

    L = []
    add = L.append

    # ------------------------------------------------------------------ header
    add("# UGS-SYNTH-D01 — surface facilities design report\n")
    add("**Case** UGS-SYNTH-D01 (UGS-SYNTH benchmark family), case version 1.1.0-development. "
        "All case data is synthetic benchmark data.\n")
    add("This report is the narrative deliverable; the machine-readable design definition is in "
        "`deliverables/design.json`, the rule-by-rule verification output in "
        "`deliverables/verification.md` and `deliverables/checks.csv`, the plan-view drawing in "
        "`deliverables/layout.svg`. Everything in this report is reproduced from those files by "
        "`tools/make_report.py`.\n")

    # ------------------------------------------------------------------ 1 scope
    add("## 1 Purpose, scope and basis\n")
    add("The project delivers an underground-gas-storage surface facility that connects the "
        "GRID-TIE boundary to six well groups and provides the six published operating scenarios "
        "(three injection, three withdrawal) at the published gas-quality, pressure and metering "
        "requirements. The design covers process architecture, equipment selection and count, "
        "train architecture, topology, operating philosophy, pipe sizing and classing, layout, "
        "routing, maintenance access and roads, as listed in the project scope. Reservoir "
        "behaviour, well completion, electrical/control systems, civil structures, procurement and "
        "code compliance are excluded by the case.\n")
    add("**Objective.** Among feasible designs, minimise the benchmark lifecycle cost (LCC). The "
        "LCC of the proposed design is **{:.3f} MBCU** (section 9).\n".format(lcc["lcc_mbcu"]))
    add("### 1.1 Published requirements used\n")
    pr = case.project_requirements
    add(f"* gas delivery limits: water content ≤ "
        f"{pr['gas_delivery_requirements']['maximum_water_content_mg_sm3']} mg/Sm3, free-liquid "
        f"mass fraction ≤ {pr['gas_delivery_requirements']['maximum_free_liquid_mass_fraction']} "
        f"kg/kg, temperature within "
        f"{pr['gas_delivery_requirements']['temperature_limits_c'][0]}…"
        f"{pr['gas_delivery_requirements']['temperature_limits_c'][1]} degC;")
    add("* GRID-TIE metering is mandatory, all exchanged gas must pass through active meter "
        "capacity ≥ the scenario flow;")
    add("* compression N-1: for every scenario whose sink pressure exceeds its source pressure, "
        "≥ 70 % of the scenario flow must remain deliverable with any one compressor unavailable;")
    add("* withdrawal treatment N-1: for every withdrawal scenario, ≥ 70 % of the scenario flow "
        "must remain deliverable with any one separator or dehydration unit unavailable;")
    add(f"* operating hours {pr['operating_hours_per_year']} h/a in total; well-group interface "
        f"limits 0…{pr['well_group_limits']['maximum_flow_per_interface_kg_s']} kg/s each; "
        f"GRID-TIE limit {case.interfaces['GRID-TIE']['maximum_flow_kg_s']} kg/s; liquid outfall "
        f"limit {case.interfaces['LIQUID-DRAIN-OUTFALL']['maximum_flow_kg_s']} kg/s.\n")

    # ------------------------------------------------------ 2 scenarios table
    add("## 2 Operating scenarios\n")
    add("| scenario | service | flow (kg/s) | source | p source (MPa) | T source (degC) | "
        "water (mg/Sm3) | free liquid (kg/kg) | p sink required (MPa) | hours (h/a) |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for sid, sc in case.scenarios.items():
        add(f"| {sid} | {sc['service']} | {sc['required_total_flow_kg_s']} | "
            f"{sc['source_interface']} | {sc['source_pressure_mpa']} | "
            f"{sc['source_temperature_c']} | {sc['source_water_mg_sm3']} | "
            f"{sc['source_free_liquid_mass_fraction']} | {sc['required_sink_pressure_mpa']} | "
            f"{sc['annual_hours']} |")
    add("")

    # ------------------------------------------------------- 3 architecture
    add("## 3 System architecture and process connections\n")
    add("The facility is a single station with two process chains that share the well-side "
        "manifold and the compressor set:\n")
    add("**Injection chain (GRID-TIE → wells).** GRID-TIE → injection custody meter `MTR-INJ-01` "
        "→ compressor suction header `HDR-INJ-SUC-01` → three parallel compressors "
        "(`CMP-INJ-01/02/03`, the station compressor set) → discharge header `HDR-INJ-DIS-01` → "
        "aftercooler `COOL-INJ-01` → injection trunk `P-113` → well manifold `WH-01` → six "
        "well-group branches `P-131…P-136`.\n")
    add("**Withdrawal chain (wells → GRID-TIE).** six well groups → well manifold `WH-01` → three "
        "withdrawal trunks `P-114/115/116` (one per train) → inlet separators "
        "`SEP-WDR-01/02/03` → dehydration units `DEHY-WDR-01/02/03` → treated-gas header "
        "`HDR-TRT-OUT-01` → delivery header `HDR-DLV-01` → pressure regulator `REG-WDR-01` → "
        "withdrawal custody meter `MTR-WDR-01` → GRID-TIE. In WDR-HIGH and WDR-MID the treated "
        "gas reaches the delivery header through the bypass `P-123`. In WDR-LOW it is boosted by "
        "the same station compressor set: the treated gas is routed to the compressor suction "
        "header through the boost feed line `P-143` (`HDR-TRT-OUT-01` → `HDR-INJ-SUC-01`), "
        "compressed, and returned to the delivery header through the boost discharge line `P-144` "
        "(`HDR-INJ-DIS-01` → `HDR-DLV-01`).\n")
    add("**Liquid system.** Each separator's `liquid_out` discharges through its own closed drain "
        "(`DRN-WDR-01/02/03`) and drain line to the public outfall `LIQUID-DRAIN-OUTFALL` "
        "(three separate discharge lines, `P-140/141/142`). The separators' liquid side streams "
        "are conveyed at the idealised closed-drain pressure domain (≤ 1 MPa), which the published "
        "model represents as an integral letdown at the separator `liquid_out`.\n")
    add("**Boundary interfaces used** (from `site.json`): GRID-TIE (2 connections: one injection "
        "meter inlet line, one withdrawal meter outlet line), the six well groups (one connection "
        "each, through `WH-01`), LIQUID-DRAIN-OUTFALL (3 of 8 available connections) and "
        "ROAD-ENTRANCE (road network). POWER-TIE, FIREWATER-TIE and INSTRUMENT-AIR-TIE are "
        "abstract utility boundaries; no distribution network is in scope and no process piping "
        "connects to them.\n")
    add("### 3.1 Architecture decisions and the rules behind them\n")
    add("* **Two custody meters.** Equipment ports are directional: a meter conveys gas only from "
        "`gas_in` to `gas_out`, and injection and withdrawal are opposite directions through the "
        "same boundary. Two catalogued meters are therefore installed in anti-parallel, one per "
        "flow direction, so that all exchanged gas passes through active meter capacity in every "
        "scenario (each MTR120 is rated exactly the 120 kg/s peak scenario flow, which the "
        "published tolerance convention treats as equal to the limit).\n")
    add("* **No treatment on the injection chain.** The injection gas arrives at 40 mg/Sm3 water "
        "and zero free liquid, i.e. inside both delivery limits, so separation/dehydration would "
        "add pressure loss and cost without changing the delivered quality.\n")
    add("* **One compressor set serves both services.** Compressor suction and discharge are "
        "one-way ports (`gas_in` / `gas_out`), so a machine can never be reversed; nothing in the "
        "published rules requires separate machinery for injection and for the low-pressure "
        "withdrawal boost, and the two services are seasonal and never simultaneous. The station "
        "set is therefore shared: in WDR-LOW the treated gas is routed to the compressor suction "
        "header (`P-143`) and the compressor discharge to the delivery header (`P-144`), and "
        "those lines are isolated while injection or a high-pressure withdrawal scenario runs. A "
        "dedicated two-machine boost set was costed as the alternative: 13.0 MBCU of equipment "
        "plus 3.1 MBCU of maintenance present value for no functional benefit. The well manifold "
        "`WH-01` is likewise a catalogued header shared by both directions, and the operating "
        "plan selects the active branches scenario by scenario; the published semantics "
        "explicitly allow cyclic physical networks and require only that every declared scenario "
        "satisfies the port, mass-balance, pressure, capacity, temperature and delivery rules.\n")
    add("* **Aftercooling is a delivery requirement, not a choice.** At the highest injection "
        "ratio the compressor discharge reaches ≈ 95 degC, above the 60 degC delivery limit; the "
        "aftercooler holds the injection gas at 50 degC, a 10 degC margin to the limit, at a duty "
        "of at most ≈ 13 MW against its 32 MW rating. The boost service runs at a ratio of ≈ 1.5 "
        "(discharge ≈ 55 degC) and does not pass through the aftercooler.\n")
    add("* **Delivery pressure control.** The regulator holds the GRID-TIE delivery pressure at "
        "the published requirement in every withdrawal scenario: the setpoints are chosen so that "
        "the delivered pressure equals 6.000 MPa. (The case's tolerance convention treats a value "
        "within 1e-5 MPa of a limit as equal to it, so delivering the requirement itself "
        "satisfies a minimum, an exact and an upper-bound reading of "
        "`required_sink_pressure_mpa`; the short well-group branches deliver marginally more than "
        "the worst branch.) In WDR-LOW the shared compressors raise the pressure to ≈ 6.39 MPa so "
        "that the regulator has a definite control drop (≈ 0.3 MPa) across it.\n")

    # -------------------------------------------------------- 4 equipment
    add("## 4 Equipment selection and stated capacities\n")
    add("| tag | model | category | x (m) | y (m) | orient. (deg) | rating | duty in the design |")
    add("|---|---|---|---|---|---|---|---|")
    for n in design.nodes.values():
        m = n.model
        if m["category"] == "compressor":
            rating = (f"{m['capacity_kg_s']:g} kg/s, ratio ≤ {m['maximum_pressure_ratio']:g}, "
                      f"≤ {m['maximum_power_mw']:g} MW, p_disch ≤ "
                      f"{m['maximum_discharge_pressure_mpa']:g} MPa")
        elif m["category"] == "header":
            rating = f"{m['capacity_kg_s']:g} kg/s, {m['maximum_branch_connections']} branches"
        elif m["category"] == "closed_drain":
            rating = f"{m['capacity_kg_s']:g} kg/s liquid, ≤ {m['maximum_pressure_mpa']:g} MPa"
        elif m["category"] == "cooler":
            rating = f"{m['capacity_kg_s']:g} kg/s, ≤ {m['maximum_duty_mw']:g} MW duty"
        elif m["category"] == "dehydration":
            rating = (f"{m['capacity_kg_s']:g} kg/s, outlet "
                      f"{m['normal_outlet_water_mg_sm3']:g} mg/Sm3, ≤ "
                      f"{m['maximum_pressure_mpa']:g} MPa")
        elif m["category"] == "separator":
            rating = (f"{m['capacity_kg_s']:g} kg/s, removal "
                      f"{m['liquid_removal_efficiency']:.4f}, ≤ "
                      f"{m['maximum_pressure_mpa']:g} MPa")
        else:
            rating = f"{m['capacity_kg_s']:g} kg/s, ≤ {m['maximum_pressure_mpa']:g} MPa"
        # duty
        flows = []
        for plan, mar in normal:
            if n.tag in mar.unit_flow and mar.unit_flow[n.tag] > 0:
                flows.append(mar.unit_flow[n.tag])
        duty = f"max {max(flows):.2f} kg/s" if flows else ("standby / N-1 only" if n.tag in
                                                           ("CMP-INJ-03",) else "-")
        add(f"| {n.tag} | {m['model_id']} | {m['category']} | {n.x:g} | {n.y:g} | {n.o} | "
            f"{rating} | {duty} |")
    add("")
    add(f"Installed equipment CAPEX {lcc['equipment_capex_mbcu']:.3f} MBCU, installed annual "
        f"maintenance {lcc['equipment_maintenance_mbcu_per_year']:.3f} MBCU/a. The duty column "
        "gives the maximum flow in **normal operation**; the higher flows of the "
        "single-unit-outage plans (which load the remaining units harder) are listed in tables "
        "7.1 and 7.3 and stay within every rating.\n")
    add("### 4.1 Sizing logic\n")
    add("**Station compressor set (`CMP-INJ-01/02/03`: 2 × C60 + 1 × C40).** The binding N-1 "
        "case is INJ-LOW: with one machine unavailable the station must still deliver 70 % of "
        "120 kg/s = 84 kg/s at the required pressure. Two installed machines cannot meet this "
        "(the largest catalogued machine is 80 kg/s), so at least three machines are required; the "
        "cheapest set whose total capacity minus the largest single unit is ≥ 84 kg/s is "
        "2 × C60 + 1 × C40 (160 − 60 = 100 kg/s). The same set serves the WDR-LOW boost duty "
        "through the boost feed and discharge lines (70 kg/s normal, 49 kg/s after one machine is "
        "out), and the largest required pressure ratio (≈ 2.11 at INJ-HIGH) stays inside the "
        "C60/C40 limit of 2.4. An independent enumeration of every catalogued C40/C60/C60H/C80 "
        "multiset of size 2-4 subject to capacity, ratio and N-1 limits confirms that this is the "
        "cheapest compliant set for both services.\n")
    add("**Load sharing.** Duty is loaded on the most efficient machines first and within an "
        "efficiency class in proportion to capacity, up to 95 % of rated capacity, so the two C60 "
        "carry the load and the C40 is only loaded when it is needed (the minimum-stable flow of "
        "every running machine is respected: in INJ-LOW the C40 runs at its 10 kg/s minimum; in "
        "INJ-MID, INJ-HIGH and WDR-LOW it is idle).\n")
    add("**Separators (3 × SEP70).** The withdrawal gas enters at up to 12 MPa, which rules out "
        "the 10 MPa-rated SEP40/SEP120 models. With one separator out the remaining two must "
        "carry the scenario flow (the design does so up to the full 120 kg/s, i.e. 60 kg/s per "
        "unit ≤ 70 kg/s); the 0.9995 removal efficiency of a single unit already brings the free "
        "liquid from 0.01 to 5 × 10⁻⁶ kg/kg, well inside the 10⁻⁴ limit, so no filter is required.\n")
    add("**Dehydration (3 × DEHY70).** Only the DEHY models change water content (220 → "
        "35 mg/Sm3). DEHY40 is limited to 10 MPa and DEHY120 is rated 10 MPa, both below the "
        "12 MPa withdrawal pressure, so DEHY70 (16 MPa) is the only usable model; three units are "
        "needed for the same N-1 reason as the separators.\n")
    add("**Aftercooler (1 × COOL120).** One aftercooler carries the full injection flow "
        "(120 kg/s = its rated flow, which the published tolerance convention treats as equal to "
        "the limit) at a duty of at most ≈ 13 MW against its 32 MW rating. Cooler redundancy is "
        "not a published N-1 requirement and the boost service needs no cooling, so a second unit "
        "and an outlet header would be pure cost.\n")
    add("**Headers (5 × HDR180).** Every fan-out/merge of more than two physical ports passes "
        "through a catalogued header: compressor suction header, compressor discharge header, "
        "well manifold, treated-gas header and delivery header. All are rated 180 kg/s, 16 MPa "
        "and 14 branches. This is the one place where margin is retained deliberately rather "
        "than sized at rating, and the choice is costed: replacing all five by HDR120 (rated "
        "exactly the 120 kg/s station throughput, so every declared flow equals its rating "
        "within the published tolerance) would lower the LCC by 0.59 MBCU - 0.55 MBCU of CAPEX "
        "and 0.20 MBCU of maintenance present value, less 0.16 MBCU of extra energy from the "
        "higher header pressure drop. It is not adopted because the well manifold needs 10 "
        "physical branch connections (6 well groups, 3 withdrawal trunks, 1 injection trunk), "
        "which is the complete HDR120 branch count with no spare port, and because the two "
        "compressor manifold headers and the two delivery-side headers carry the full station "
        "flow at the extreme of every scenario. The retained margin is therefore a conscious, "
        "costed robustness choice rather than an oversight; it is 0.7 % of the LCC.\n")
    add("**Metering and regulation.** Each custody meter is MTR120 (exactly the maximum "
        "scenario flow of 120 kg/s, which the published tolerance convention treats as equal to "
        "the limit) and the delivery regulator is REG120.\n")
    add("**Drains.** One DRN-S (0.8 kg/s liquid) per separator; the largest liquid production is "
        "0.60 kg/s (120 kg/s withdrawal through two trains), so each drain stays below 75 % of "
        "its rating and the three discharge lines stay far below the 10 kg/s outfall limit.\n")

    # -------------------------------------------------------- 5 layout
    add("## 5 Site layout, safety provisions and maintenance access\n")
    add("The site is the 700 m × 450 m boundary of `site.json`. The well manifold `WH-01` sits "
        "close to the well groups at (30, 225) with six L-shaped well branches; the two process "
        "chains are laid out in bands: the injection chain (meter, suction header, three "
        "compressors, discharge header, aftercooler) occupies the south band around "
        "y ≈ 90…196, and the withdrawal chain (three trains, treated-gas header, delivery header, "
        "regulator, meter) occupies the north band around y ≈ 210…280, ordered west to east so "
        "that the withdrawal chain runs in the direction of its flow. The two boost lines "
        "(`P-143` from the treated-gas header down to the compressor suction header, `P-144` from "
        "the compressor discharge header to the delivery header) close the boost path. The plan "
        "view is `deliverables/layout.svg`; coordinates are in `deliverables/design.json`.\n")
    add("All equipment footprints are inside the site and clear of the three no-build zones "
        "(FUTURE-EXPANSION, DRAINAGE-CHANNEL, GRID-FACILITY). Every category pair in the published "
        "separation matrix is checked on the *boundary-to-boundary* distance of the rotated "
        "footprints; the layout meets all of them (the closest pair is the compressor suction "
        "header against CMP-INJ-01 at 13.00 m against a 10 m requirement - see the table below). "
        "Routine clearance envelopes (2.0…3.1 m) and the heavy-"
        "maintenance removal envelopes of the compressors are inside the site, clear of the "
        "equipment-exclusion zones and clear of every other footprint.\n")
    # closest separations
    pairs = []
    tags = list(design.nodes)
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            a, b = design.nodes[tags[i]], design.nodes[tags[j]]
            d = B.polygons_distance(a.footprint, b.footprint)
            req = case.min_separation_m(a.safety_category, b.safety_category)
            pairs.append((d - req, a.tag, b.tag, a.safety_category, b.safety_category, d, req))
    pairs.sort()
    add("The tightest boundary-to-boundary separations in the layout are (all pairs at or "
        "below the sixth-smallest margin, so ties are included):\n")
    add("| pair | categories | achieved distance (m) | required (m) | margin (m) |")
    add("|---|---|---|---|---|")
    cutoff = pairs[5][0] + 1e-9
    shown = [x for x in pairs if x[0] <= cutoff]
    for margin, t1, t2, c1, c2, d, req in shown:
        add(f"| {t1} / {t2} | {c1} / {c2} | {d:.3f} | {req:g} | {margin:+.3f} |")
    add("")
    add("**Roads.** A public entrance road runs from ROAD-ENTRANCE along the south of the "
        "withdrawal band; three spurs serve the areas that require access at each side of the "
        "road:")
    for r in design.roads:
        add(f"* `{r['tag']}` (width {r['width_m']:g} m): {r['role']}")
    add("")
    add("Only the compressors require road and crane access and only the separators require road "
        "access (per the catalogued maintenance flags); the crane-access distances from the "
        "compressor removal envelopes to the paved road boundaries are within the published "
        "4.5 m buffer and the separator envelopes are within the 7 m road-access buffer. All "
        "paved geometry is inside the site, outside the road-exclusion zones and clear of every "
        "equipment footprint, and every road section is connected to the section carrying "
        "ROAD-ENTRANCE.\n")

    # -------------------------------------------------------- 6 piping
    add("## 6 Piping and network definition\n")
    add("Every connection is a physical pipeline with an explicit route, diameter, pipe class and "
        "installation level (`ground`, `buried`, `rack_low`, `rack_high`); level changes occur "
        "only at shared segment endpoints and add no modelled length, loss or cost. Table 6.1 "
        "lists the pipelines; the complete vertex lists are in `deliverables/design.json`.\n")
    add("| tag | from | to | DN | class | level(s) | length (m) | service / purpose |")
    add("|---|---|---|---|---|---|---|---|")
    for tag, pl in design.pipes.items():
        levels = sorted({lvl for (_, _, lvl, _) in pl.segments()})
        a = f"{pl.a[0]}.{pl.a[1]}" if pl.a[0] in design.nodes else pl.a[0]
        b = f"{pl.b[0]}.{pl.b[1]}" if pl.b[0] in design.nodes else pl.b[0]
        add(f"| {tag} | {a} | {b} | {pl.dn.replace('DN','')} | {pl.cls} | {', '.join(levels)} | "
            f"{pl.length_m:.1f} | {pl.role} |")
    add("")
    add("**Class selection.** All pipelines that can convey wet gas (water > 50 mg/Sm3 or free "
        "liquid > 10⁻⁴ kg/kg) are classed CS-WET-160: the six well branches and the three "
        "withdrawal trunks (wet at up to 12 MPa) and the separator-to-dehydration runs. From the "
        "dehydration outlet to the GRID-TIE the gas is dry, so CS-DRY-160 is used; it has both a "
        "lower roughness (1.5 × 10⁻⁵ m versus 4.5 × 10⁻⁵ m) and a lower cost multiplier than the "
        "wet class. The injection chain is dry gas throughout and uses CS-DRY-160. All gas "
        "pipelines are rated 16 MPa, above the highest pressure anywhere in the design, and their "
        "temperature range covers the service temperatures. Liquid-drain lines use CS-WET-100, "
        "the only class that is both liquid-drain compatible and rated above the 1 MPa drain "
        "domain.\n")
    add("**Sizing.** Diameters were optimised against the LCC: every pipeline was sized between "
        "the diameter that satisfies the 25 m/s gas velocity limit and the diameter at which the "
        "capital cost of further upsizing exceeds the present value of the compressor energy it "
        "saves. Because the compressor energy is the dominant cost, the main lines are "
        "deliberately larger than the velocity minimum (for example the 620 m injection trunk is "
        "DN600, the GRID-TIE suction line DN700). Liquid-drain lines are DN150; at the maximum "
        "liquid flow of 0.6 kg/s they run far below the 3 m/s liquid-drain limit.\n")
    add("**Routing rules applied.** Every segment stays inside the site, avoids the interior of "
        "the FUTURE-EXPANSION and DRAINAGE-CHANNEL pipeline-exclusion zones, and never crosses an "
        "equipment footprint interior (the only footprint contact is at the port itself). No two "
        "same-level segments overlap by a positive length, so no co-routing corridor declaration "
        "is needed; pipelines that would otherwise cross at the same level are separated by level "
        "(for example the compressor discharge manifolds sit on ground, rack_low and rack_high "
        "risers where they cross the unit access road). The long trunk lines and all drain lines "
        "are buried, which also keeps them clear of road construction.\n")

    # -------------------------------------------------------- 7 operation
    add("## 7 Operating philosophy and scenario plans\n")
    add("Each published scenario is operated along the physical path described in section 3, with "
        "the flows, splits and setpoints listed in table 7.1. The plan is a steady-state plan: "
        "boundary flows, per-unit flows, compressor discharge pressures, aftercooler outlet "
        "temperatures and the delivery regulator setpoint.\n")
    add("| scenario | setpoints | well-group flows (kg/s) | unit flows (kg/s) |")
    add("|---|---|---|---|")
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
                sp.append(f"aftercooler {v:.0f} degC")
        wf = ", ".join(f"{w[:6]}:{plan['well_alloc'][w]:.2f}" for w in O.WELLS)
        uf = ", ".join(f"{k}:{v:.2f}" for k, v in sorted(m.unit_flow.items()) if v > 0)
        add(f"| {plan['id']} | {'; '.join(sp)} | {wf} | {uf} |")
    add("")
    add("### 7.1 Scenario results\n")
    add("| scenario | sink pressure (MPa) | required (MPa) | delivery temperature (degC) | "
        "water (mg/Sm3) | free liquid (kg/kg) | energy (MWh) |")
    add("|---|---|---|---|---|---|---|")
    for plan, m in results:
        if plan["kind"] != "normal":
            continue
        if plan["service"] == "injection":
            p = min(m.state[w]["p"] for w in O.WELLS)
            t = m.state[O.WELLS[0]]["t"]
            w = m.state[O.WELLS[0]]["water"]
            liq = m.state[O.WELLS[0]]["liquid"]
        else:
            st = m.state["GRID-TIE"]
            p, t, w, liq = st["p"], st["t"], st["water"], st["liquid"]
        add(f"| {plan['id']} | {p:.4f} | {plan['sink_required_mpa']:g} | {t:.2f} | {w:.1f} | "
            f"{liq:.2e} | {m.energy_mwh:.1f} |")
    add("")
    add("### 7.2 Pressure and temperature profile of two representative scenarios\n")
    for sid, nodes in (("INJ-LOW", ["GRID-TIE", "MTR-INJ-01", "HDR-INJ-SUC-01", "CMP-INJ-01",
                                    "HDR-INJ-DIS-01", "COOL-INJ-01", "HDR-INJ-OUT-01", "WH-01",
                                    "WG-01", "WG-06"]),
                       ("WDR-HIGH", ["WG-01", "WH-01", "SEP-WDR-01", "DEHY-WDR-01",
                                     "HDR-TRT-OUT-01", "HDR-DLV-01", "REG-WDR-01", "MTR-WDR-01",
                                     "GRID-TIE"])):
        plan, mar = [x for x in results if x[0]["id"] == sid][0]
        add(f"**{sid}** ({plan['source']['flow']:.2f} kg/s from {plan['source']['iface']} at "
            f"{plan['source']['p']:.2f} MPa)\n")
        add("| node | inlet p (MPa) | outlet p (MPa) | temperature (degC) | flow (kg/s) |")
        add("|---|---|---|---|---|")
        for nid in nodes:
            st = mar.state.get(nid)
            if st is None:
                continue
            pin = st.get("p_in", st.get("p"))
            pout = st.get("p_out", st.get("p"))
            tt = st.get("t_out", st.get("t"))
            add(f"| {nid} | {pin:.4f} | {pout:.4f} | {tt:.2f} | {st.get('flow', float('nan')):.2f} |")
        add("")
    add("### 7.3 Reliability: single-unit-outage plans\n")
    add("| case | failed unit | retained flow (kg/s) | retained fraction | delivery requirement met |")
    add("|---|---|---|---|---|")
    for plan, m in variants:
        sid = plan["id"].split("/")[0]
        scen_flow = case.scenarios[sid]["required_total_flow_kg_s"]
        if plan["service"] == "injection":
            detail = f"{min(m.state[w]['p'] for w in O.WELLS):.3f} MPa min well-group"
        else:
            detail = f"{m.state['GRID-TIE']['p']:.3f} MPa at GRID-TIE, T " \
                     f"{m.state['GRID-TIE']['t']:.1f} degC, water " \
                     f"{m.state['GRID-TIE']['water']:.1f} mg/Sm3"
        add(f"| {sid} | {plan['outage']} | {plan['source']['flow']:.2f} | "
            f"{plan['source']['flow'] / scen_flow:.3f} | {detail} |")
    add("")
    add("All compressor-outage cases retain at least the required 70 % of the scenario flow "
        "(INJ-LOW 84 kg/s, INJ-MID 70, INJ-HIGH 52.5, WDR-LOW 49) at the required delivery "
        "pressure and quality; the two withdrawal trains that remain in a separator or "
        "dehydration outage carry the **full** scenario flow, i.e. more than the 70 % required. "
        "The delivery limits are re-checked in every outage case.\n")

    # -------------------------------------------------------- 8 quantities
    add("## 8 Quantities\n")
    add(f"* equipment: {q['equipment']}")
    add(f"* gas and liquid pipelines: {q['pipe_length_total_m']:.0f} m total; by level: "
        + ", ".join(f"{k} {v:.0f} m" for k, v in sorted(q['pipe_length_by_level'].items())))
    add(f"* pipeline length by diameter: "
        + ", ".join(f"{k} {v:.0f} m" for k, v in sorted(q['pipe_length_by_dn'].items())))
    add(f"* road centreline length: {q['road_length_m']:.1f} m")
    add(f"* equipment footprint area: {q['footprint_area_m2']:.0f} m2")
    add(f"* required maintenance-envelope area (envelope area minus footprint area): "
        f"{q['maintenance_area_m2']:.0f} m2\n")

    # -------------------------------------------------------- 9 LCC
    add("## 9 Lifecycle cost\n")
    add("The LCC follows the published basis exactly: equipment CAPEX (sum over installed "
        "instances), piping CAPEX (segment length × diameter installed cost × pipe-class "
        "multiplier × routing-level multiplier), civil/access CAPEX (road centreline × rate, "
        "footprint area × foundation rate, maintenance-envelope area × rate, and pipeline length "
        "× routing-level civil rate), the present value of the annual energy cost and the present "
        "value of the annual maintenance cost, with PVF = "
        f"{lcc['pvf']:.6f} (8 %, 20 years).\n")
    add("| component | MBCU |")
    add("|---|---|")
    add(f"| equipment CAPEX | {lcc['equipment_capex_mbcu']:.4f} |")
    add(f"| piping CAPEX | {lcc['piping_capex_mbcu']:.4f} |")
    add(f"| civil / access CAPEX | {lcc['civil_capex_mbcu']:.4f} |")
    add(f"| energy, present value ({lcc['annual_energy_mwh']:.0f} MWh/a) | "
        f"{lcc['energy_pv_mbcu']:.4f} |")
    add(f"| maintenance, present value ({lcc['equipment_maintenance_mbcu_per_year']:.3f} MBCU/a) | "
        f"{lcc['maintenance_pv_mbcu']:.4f} |")
    add(f"| **LCC** | **{lcc['lcc_mbcu']:.4f}** |")
    add("")
    add("Civil/access breaks down as roads "
        f"{lcc['civil_breakdown']['roads']:.4f}, foundations "
        f"{lcc['civil_breakdown']['foundations']:.4f}, maintenance envelopes "
        f"{lcc['civil_breakdown']['maintenance_area']:.4f}, pipeline civil "
        f"{lcc['civil_breakdown']['pipeline_civil']:.4f} MBCU.\n")
    inj_e = sum(m.energy_mwh for p, m in normal if p["service"] == "injection")
    boost_e = 0.0
    for p, m in normal:
        if p["id"] == "WDR-LOW":
            boost_e = sum(m.state[c]["power_mw"] * p["hours"] for c in p["compressors"]
                          if m.state[c].get("running"))
    dehyd_e = sum(0.018 * p["source"]["flow"] * p["hours"] for p, m in normal
                  if p["service"] == "withdrawal")
    cooler_e = sum(m.state[c]["power_mw"] * p["hours"] for p, m in normal
                   for c in p.get("coolers", []) if c in m.state)
    add(f"Annual energy is dominated by the shared compressor set: {inj_e:.0f} MWh/a over the "
        f"three injection scenarios (including the aftercooler power), {boost_e:.0f} MWh/a on "
        f"the WDR-LOW boost duty, plus {dehyd_e:.0f} MWh/a of dehydration energy (0.018 MW per "
        f"kg/s of withdrawal gas). The rejected dedicated-boost alternative would have added "
        f"roughly the same boost duty at a slightly higher ratio, on top of its 13.0 MBCU of "
        "additional equipment.\n")
    add("Because the present value of energy is more than half of the LCC, the design was "
        "optimised on two levels: (i) equipment selection and count, solved as the cheapest "
        "compliant set subject to the N-1 rules and the equipment pressure/ratio limits; and "
        "(ii) pipe diameters, solved by coordinate descent over groups of parallel branches and "
        "then over every individual pipeline against the full LCC (piping CAPEX + pipeline civil "
        "+ energy present value), with the velocity limit enforced in the single-unit-outage cases "
        "as well as in normal operation (`tools/optimize.py`). The diameter optimisation is worth "
        "**2.79 MBCU**: relative to the smallest diameters that merely satisfy the velocity and "
        "delivery limits, the chosen (larger) diameters add 0.56 MBCU of piping CAPEX but remove "
        "2 840 MWh/a of compressor energy, worth 3.34 MBCU of present value. Changing to "
        "higher-efficiency but larger machines (for example 2 × C80 + 1 × C40 instead of "
        "2 × C60 + 1 × C40) was evaluated and rejected: the extra capital and maintenance exceed "
        "the energy saving at these duty points.\n")

    # -------------------------------------------------------- 10 verification
    add("## 10 Verification\n")
    add(f"`tools/build.py` re-derives every rule in the v1.1 basis from the brief data and the "
        f"design definition: {len(design.results)} individual checks were evaluated, of which "
        f"**{len(fails)} failed**. The checks cover port compatibility and connection "
        "cardinality, footprint containment and exclusion zones, the full separation matrix, "
        "clearance and removal envelopes, road geometry, connectivity and access buffers, every "
        "pipeline route against site/exclusion/footprint/overlap rules, and for every scenario "
        "(normal and outage) the mass balance, hydraulic march with the published fixed-point "
        "convention, equipment limits, velocity limits, pipe-class rating and compatibility, "
        "metering capacity, drain capacity and the delivery limits at the sink interfaces. "
        "The full list is `deliverables/checks.csv`.\n")
    add("Reproduce with:\n")
    add("```\npython tools/build.py          # writes deliverables/design.json, verification.md, "
        "checks.csv, layout.svg\npython tools/optimize.py       # re-runs the diameter optimisation\n"
        "python tools/make_report.py    # regenerates this report\n```\n")

    # -------------------------------------------------------- 11 assumptions
    add("## 11 Assumptions and known limitations\n")
    add("1. **Valve isolation is not modelled.** The catalogued world contains no valves, so the "
        "physical network of section 6 is fixed and the scenario plans assume that isolating "
        "valves (outside the catalogued scope, as in any real station) select the path of each "
        "scenario. For this design those valves are: the injection custody meter and the "
        "`P-143` boost feed line are closed during withdrawal (otherwise the discharge header "
        "would be connected back to the wells through `P-109`/`COOL-INJ-01`/`P-113` and to the "
        "grid through the injection meter); the `P-144` boost discharge line and the compressor "
        "branch are closed during injection and during the two high-pressure withdrawal "
        "scenarios (which use the `P-123` bypass); and the well manifold `WH-01` is manifolded "
        "between the injection chain and the three withdrawal trains, with the active branch set "
        "selected per scenario. The published semantics explicitly allow cyclic physical "
        "networks and require only that every declared scenario satisfies the port, "
        "mass-balance, pressure, capacity, temperature and delivery rules.\n")
    add("2. **Delivery pressure setpoints equal the requirement.** `required_sink_pressure_mpa` "
        "is read as the pressure at which the sink accepts gas; the case makes compression "
        "necessary exactly when the sink pressure requirement exceeds the source pressure, so it "
        "cannot be an upper bound. The design delivers exactly the requirement (the published "
        "tolerance convention treats a value within 1e-5 MPa of a limit as equal to it), which "
        "satisfies a minimum, an exact and an upper-bound reading simultaneously.\n")
    add("3. **Liquid density.** No liquid density is published; the drain-velocity check assumes "
        "800 kg/m³. The largest drain flow gives ≈ 0.04 m/s in DN150, so the conclusion is "
        "insensitive to this assumption.\n")
    add("4. **No heat transfer in pipelines.** The basis models no heat loss, so delivered "
        "temperatures equal the last machine setpoint: 50.0 degC for injection after the "
        "aftercooler (limit 60 degC), 13.1/17.9 degC for the high- and mid-pressure withdrawal "
        "scenarios after the regulator's JT cooling, and 53.4 degC for WDR-LOW, where the gas "
        "leaves the shared compressors at ≈ 54 degC and the regulator - the only cooling device "
        "in that path - removes only ≈ 0.4 K.\n")
    add("5. **Aftercooler and cooler loads** are computed at the mixed compressor-discharge "
        "temperature; the cooler duty/power and the dehydration energy are included in the LCC.\n")
    add("6. **Simplified operating plans.** Steady-state plans only: no start-up, shutdown, "
        "transients, blowdown or pressure-equalisation sequences are modelled, and no scenario "
        "is required to operate two simultaneous unrelated outages.\n")
    add("7. **Safety provisions** are those the case publishes: the separation matrix, the "
        "maintenance envelopes, road/crane access and the GRID-TIE/LIQUID-DRAIN-OUTFALL flow and "
        "connection limits. No code compliance, fire protection, ESD or hazardous-area design is "
        "in scope.\n")
    add("8. **Excluded scope** (from the project requirements): reservoir model, well completion, "
        "full electrical and control systems, firewater synthesis, structural and civil detail, "
        "process safety study, regulatory compliance and vendor procurement. Equipment costs and "
        "ratings are the synthetic catalogue values, not vendor data.\n")

    Path(args.out).write_text("\n".join(L) + "\n")
    print("wrote", args.out, f"({len('\n'.join(L))} chars)")


if __name__ == "__main__":
    main()
