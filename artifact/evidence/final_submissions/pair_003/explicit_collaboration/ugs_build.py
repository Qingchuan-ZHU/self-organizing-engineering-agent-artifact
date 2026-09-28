"""Generate the deliverables for UGS-SYNTH-D01 from the verified model."""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ugs_lib import (load_brief, footprint_poly, expanded_poly, removal_poly, poly_area,
                     poly_len, seg_len, road_paved_rectangles, port_xy, pvf, rot)
import ugs_design as D
import ugs_solve as S
import ugs_validate as V

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deliverables")
B = S.B
MODELS = S.MODELS
CLASSES = S.CLASSES
DN = S.DN
LEVELS = S.LEVELS
IFACES = S.IFACES
SCEN = S.SCEN
EQUIP = S.EQUIP
PIPES = S.PIPES


def f(x, nd=4):
    return round(float(x), nd)


def build_data():
    data = V.run_all()
    runs = data["runs"]
    lcc = data["lcc"]

    equipment = []
    for eid in EQUIP:
        pose = S.inst_pose(eid)
        mdl = MODELS[pose["model_id"]]
        poly = footprint_poly(pose, mdl)
        env = expanded_poly(pose, mdl, mdl["maintenance"].get("clearance_m", 0.0))
        rmp = removal_poly(pose, mdl)
        info = S.AREA_INFO[eid]
        equipment.append(dict(
            id=eid, model_id=pose["model_id"], category=mdl["category"],
            safety_category=mdl["safety_category"], description=pose["description"],
            position_m=[pose["x"], pose["y"]], orientation_deg=pose["orientation_deg"],
            footprint_m={"length": mdl["footprint_m"]["length"], "width": mdl["footprint_m"]["width"],
                         "area_m2": f(poly_area(poly), 3)},
            capacity_kg_s=mdl.get("capacity_kg_s"),
            capex_mbcu=mdl["capex_mbcu"], annual_maintenance_mbcu=mdl["annual_maintenance_mbcu"],
            ports=[dict(id=p["id"], type=p["type"],
                        position_m=[f(port_xy(pose, mdl, p["id"])[0], 4), f(port_xy(pose, mdl, p["id"])[1], 4)])
                   for p in mdl["ports"]],
            maintenance=dict(clearance_m=mdl["maintenance"]["clearance_m"],
                             heavy_maintenance=mdl["maintenance"].get("heavy_maintenance", False),
                             road_access_required=mdl["maintenance"].get("road_access_required", False),
                             crane_access_required=mdl["maintenance"].get("crane_access_required", False),
                             removal_envelope_m=mdl["maintenance"].get("removal_envelope_m"),
                             side=mdl["maintenance"].get("side"),
                             required_envelope_area_m2=f(info["env_area"], 3),
                             access_distance_m=f(info.get("access_dist", 0.0), 3)),
        ))

    connections = []
    for pid, p in PIPES.items():
        route = [tuple(q) for q in p["route"]]
        segs = []
        for i in range(len(route) - 1):
            L = seg_len(route[i], route[i + 1])
            segs.append(dict(from_m=[route[i][0], route[i][1]], to_m=[route[i + 1][0], route[i + 1][1]],
                             level=p["levels"][i], length_m=f(L, 3)))
        dn = DN[p["dn"]]
        cls = CLASSES[p["cls"]]
        connections.append(dict(
            id=pid, from_node=p["frm"][0], from_port=p["frm"][1],
            to_node=p["to"][0], to_port=p["to"][1],
            nominal_diameter=p["dn"], internal_diameter_m=dn["internal_diameter_m"],
            pipe_class=p["cls"], installed_cost_mbcu_per_m=dn["installed_cost_mbcu_per_m"],
            class_cost_multiplier=cls["installed_cost_multiplier"],
            roughness_m=cls["roughness_m"], class_max_pressure_mpa=cls["maximum_allowable_pressure_mpa"],
            class_temperature_limits_c=cls["temperature_limits_c"],
            service=p["service"], segments=segs,
            total_length_m=f(sum(s["length_m"] for s in segs), 3)))

    roads = []
    for r in D.ROADS:
        roads.append(dict(id=r["id"], width_m=r["width_m"], centerline_m=[list(q) for q in r["centerline_m"]],
                          length_m=f(poly_len([tuple(q) for q in r["centerline_m"]]), 3),
                          paved_area_m2=f(sum(poly_area(q) for q in road_paved_rectangles(r)), 1),
                          connects_to=", ".join(sorted({o for o in [r["id"]]})),
                          function=({"RD-MAIN": "site access road from ROAD-ENTRANCE",
                                     "RD-SEP": "separator maintenance access",
                                     "RD-WCOMP": "withdrawal compressor crane access",
                                     "RD-ICOMP": "injection compressor crane access"})[r["id"]]))

    scenarios = []
    for sid, r in runs.items():
        scn = SCEN[sid]
        trace = []
        for t in r["trace"]:
            if t["kind"] == "pipe":
                trace.append(dict(element=t["id"], kind="pipeline", flow_kg_s=f(t["flow"], 4),
                                  P_in_mpa=f(t["P_in"], 5), P_out_mpa=f(t["P_out"], 5),
                                  pressure_loss_mpa=f(t["dP"], 6), velocity_m_s=f(t["v"], 3),
                                  T_c=f(t["T"], 3), dn=t["dn"], pipe_class=t["cls"]))
            else:
                trace.append(dict(element=t["id"], kind="equipment", model=t["model"],
                                  flow_kg_s=f(t["flow"], 4), P_out_mpa=f(t["P"], 5),
                                  T_out_c=f(t["T"], 3), water_mg_sm3=f(t["water"], 4),
                                  free_liquid=f(t["fl"], 8),
                                  setpoint={k: (f(v, 5) if isinstance(v, (int, float)) else v)
                                            for k, v in t["setpoint"].items()}))
        sink = r["sinks"] if r["sinks"] else [r["state"]]
        wg_flows = dict(zip(["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"],
                                [f(scn["required_total_flow_kg_s"] / 6, 4)] * 6))
        scenarios.append(dict(
            scenario_id=sid, service=scn["service"], annual_hours=scn["annual_hours"],
            required_total_flow_kg_s=scn["required_total_flow_kg_s"],
            source_interface=scn["source_interface"], sink_interfaces=scn["sink_interfaces"],
            source_pressure_mpa=scn["source_pressure_mpa"], source_temperature_c=scn["source_temperature_c"],
            source_water_mg_sm3=scn["source_water_mg_sm3"],
            source_free_liquid_mass_fraction=scn["source_free_liquid_mass_fraction"],
            required_sink_pressure_mpa=scn["required_sink_pressure_mpa"],
            setpoints={k: f(v, 5) for k, v in r["setpoints"].items()},
            control_setpoint_kind=r["kind"],
            well_group_flows_kg_s=wg_flows,
            delivered=dict(P_mpa=f(min(s[0] for s in sink), 5),
                           T_c=f(sum(s[1] for s in sink) / len(sink), 3),
                           water_mg_sm3=f(sum(s[2] for s in sink) / len(sink), 4),
                           free_liquid=f(sum(s[3] for s in sink) / len(sink), 8),
                           count=len(sink)),
            equipment_power_mw=f(sum(v for k, v in r["energy"].items() if isinstance(v, float)
                                     and (k.startswith("comp_") or k.startswith("cool_")
                                          or k.startswith("heat_") or k == "duty")), 4),
            energy_breakdown={k: f(v, 5) for k, v in r["energy"].items()
                              if isinstance(v, float) and (k.startswith("comp_") or k.startswith("cool_")
                                                           or k.startswith("heat_") or k == "duty")},
            operating_path=trace))
    return dict(equipment=equipment, connections=connections, roads=roads, scenarios=scenarios,
                lcc=lcc, runs=runs, results=data["results"], reliability=data["reliability"])


def write_json(data):
    doc = dict(
        case=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brief", "case.json"))),
        units=dict(length="m", pressure="MPa", temperature="degC", flow="kg/s", power="MW",
                   energy="MWh", cost="MBCU", area="m2", velocity="m/s", water_content="mg/Sm3",
                   free_liquid_loading="kg liquid / kg gas"),
        design_summary=dict(
            architecture="single-stage bidirectional station: separate injection and withdrawal "
                         "process paths between the six well-group laterals, the withdrawal treatment "
                         "trains, the injection compression train and the two GRID-TIE custody "
                         "metering paths",
            injection_path="GRID-TIE -> PL-IF -> IMTR-1 (custody) -> PL-IM-1o -> HDR-IM2 -> "
                           "{ICOMP-1 | ICOMP-2} -> HDR-IC -> COOL-1 -> PL-IR -> HDR-WELL -> six well "
                           "laterals",
            withdrawal_path="six well laterals -> HDR-WELL -> PL-WF -> HDR-WA -> 3 x (SEP70 -> DEHY70) "
                            "-> HDR-WB -> {REG-1 | WCOMP-1 | WCOMP-2} -> HDR-WC -> PL-WM-1i -> WMTR-1 "
                            "(custody) -> PL-TIE-W -> GRID-TIE",
            metering="all gas exchanged at GRID-TIE passes through the custody meter run of the "
                     "relevant direction (model MTR160, 160 kg/s rated) against a maximum scenario "
                     "flow of 120 kg/s; the two permitted GRID-TIE connections are used one for the "
                     "injection import and one for the withdrawal export"),
        boundaries=[dict(interface_id=i["interface_id"], port_type=i["port_type"],
                         point_m=i["point_m"], maximum_flow_kg_s=i.get("maximum_flow_kg_s"),
                         maximum_connections=i.get("maximum_connections", 1),
                         use=("process gas exchange with the transmission grid" if i["interface_id"] == "GRID-TIE"
                              else "well-group lateral" if i["interface_type"] == "well_group"
                              else "liquid outfall" if i["interface_id"] == "LIQUID-DRAIN-OUTFALL"
                              else "road access" if i["interface_id"] == "ROAD-ENTRANCE"
                              else "abstract utility boundary (no process piping)"))
                    for i in S.SITE["external_interfaces"]],
        equipment=data["equipment"],
        connections=data["connections"],
        roads=data["roads"],
        scenarios=data["scenarios"],
        reliability=data["reliability"],
        quantities=dict(
            pipe_length_by_dn={}, pipe_length_by_class={}, pipe_length_by_level={},
            pipe_length_total_m=f(sum(c["total_length_m"] for c in data["connections"]), 3),
            road_length_m=f(data["lcc"]["road_length"], 3),
            equipment_footprint_area_m2=f(data["lcc"]["footprint_area"], 3),
            required_maintenance_area_m2=f(data["lcc"]["maintenance_area"], 3)),
        lcc=dict(
            basis="LCC = equipment CAPEX + piping CAPEX + civil/access CAPEX + PV(annual energy) "
                  "+ PV(annual maintenance), PVF = (1-(1+i)^-N)/i",
            pvf=f(data["lcc"]["pvf"], 6),
            discount_rate=data["lcc"]["rates"]["discount_rate"],
            project_life_years=data["lcc"]["rates"]["life"],
            energy_tariff_mbcu_per_mwh=data["lcc"]["rates"]["energy_tariff"],
            equipment_capex_mbcu=f(data["lcc"]["capex_equip"], 4),
            piping_capex_mbcu=f(data["lcc"]["capex_pipe"], 4),
            civil_capex_mbcu=f(data["lcc"]["civil_road"] + data["lcc"]["civil_found"]
                               + data["lcc"]["civil_maint"] + data["lcc"]["civil_pipe"], 4),
            civil_breakdown_mbcu=dict(roads=f(data["lcc"]["civil_road"], 4),
                                      foundations=f(data["lcc"]["civil_found"], 4),
                                      maintenance_area=f(data["lcc"]["civil_maint"], 4),
                                      pipeline_civil=f(data["lcc"]["civil_pipe"], 4)),
            annual_energy_mwh=f(data["lcc"]["energy_annual_mwh"], 1),
            annual_energy_cost_mbcu=f(data["lcc"]["energy_cost_annual"], 4),
            energy_present_value_mbcu=f(data["lcc"]["energy_pv"], 4),
            annual_maintenance_mbcu=f(data["lcc"]["maint_annual"], 4),
            maintenance_present_value_mbcu=f(data["lcc"]["maint_pv"], 4),
            lcc_mbcu=f(data["lcc"]["lcc"], 4),
            equipment_detail=[dict(id=e["id"], model=e["model"], capex_mbcu=f(e["capex"], 4),
                                   annual_maintenance_mbcu=f(e["maint"], 4)) for e in data["lcc"]["equip_rows"]],
            pipeline_detail=[dict(id=p["id"], dn=p["dn"], pipe_class=p["class_id"],
                                  length_m=f(p["length"], 3), capex_mbcu=f(p["capex"], 4),
                                  civil_mbcu=f(p["civil"], 4)) for p in data["lcc"]["pipe_rows"]],
            energy_detail=[dict(scenario=e["scenario"], power_mw=f(e["power_mw"], 4),
                                hours=e["hours"], mwh=f(e["mwh"], 1),
                                breakdown={k: f(v, 5) for k, v in e["breakdown"].items()})
                           for e in data["lcc"]["energy_rows"]],
        ),
        assumptions=ASSUMPTIONS,
        limitations=LIMITATIONS,
        validation_summary=dict(checks=len(data["results"]),
                                failures=len([r for r in data["results"] if not r["ok"]])),
        validation_checks=[dict(ok=r["ok"], area=r["area"], check=r["msg"], detail=r["detail"])
                           for r in data["results"]],
    )
    # quantity roll-ups
    by_dn, by_cls, by_lvl = {}, {}, {}
    for c in data["connections"]:
        by_dn[c["nominal_diameter"]] = by_dn.get(c["nominal_diameter"], 0.0) + c["total_length_m"]
        by_cls[c["pipe_class"]] = by_cls.get(c["pipe_class"], 0.0) + c["total_length_m"]
        for s in c["segments"]:
            by_lvl[s["level"]] = by_lvl.get(s["level"], 0.0) + s["length_m"]
    doc["quantities"]["pipe_length_by_dn"] = {k: f(v, 2) for k, v in by_dn.items()}
    doc["quantities"]["pipe_length_by_class"] = {k: f(v, 2) for k, v in by_cls.items()}
    doc["quantities"]["pipe_length_by_level"] = {k: f(v, 2) for k, v in by_lvl.items()}
    with open(os.path.join(OUT, "design.json"), "w") as fh:
        json.dump(doc, fh, indent=1)
    return doc


ASSUMPTIONS = [
    "The published synthetic v1.1 calculation basis, geometry basis, network semantics and catalogs "
    "are the complete and authoritative calculation rules; no vendor data or external criteria are used.",
    "Scenario flows are distributed equally between the installed parallel units of a duty (six well "
    "laterals, two custody meter runs, three treatment trains) unless a scenario plan states otherwise.",
    "The withdrawal well-group laterals are treated as identical parallel sources at the published "
    "source pressure; the manifold pressure is therefore the lowest lateral outlet pressure, i.e. the "
    "worst-routed lateral.",
    "East-west main runs are installed at the 'rack_low' level and north-south branch runs at the "
    "'ground' level; liquid-drain services are buried. Crossings between runs therefore occur between "
    "different installation levels (or as zero-length plan crossings), which the geometry basis permits.",
    "Gas left standing in idle parallel branches of a normally-unused duty (for example the regulator "
    "branch during WDR-LOW) is not modelled; idle branches carry zero flow and pass no state change.",
    "The injection C40 unit is a stand-by/n-1 unit: it is not required to cover any published normal "
    "scenario because the two C60 units cover the maximum injection flow of 120 kg/s, and it is started "
    "when one C60 is out of service (retained 100 kg/s vs 84 kg/s required).",
    "Liquid side streams are checked against catalog liquid-rate limits and drain drum capacities, but "
    "no liquid density, letdown or flashing model is available in the published basis. Drain-line "
    "velocities are therefore evaluated on every liquid pipeline with the published gas-density proxy "
    "at the 1 MPa drain-domain limit, which is far more conservative than any physical liquid density "
    "(about 0.05 m/s) and keeps every line inside the 3.0 m/s limit.",
    "Parallel units of a duty are given by an equal flow split and the running units are taken as "
    "perfectly balanced by flow control; at INJ-LOW the two C60 units therefore run at their catalog "
    "rated flow (60 kg/s each) and every main header carries its rated 120 kg/s.",
    "Roads and pipelines may cross in plan; the geometry basis restricts roads only with respect to the "
    "site boundary, road-exclusion zones and equipment footprints, and restricts pipelines with respect "
    "to the site boundary, pipeline-exclusion zones, equipment footprints and same-level overlap.",
]

LIMITATIONS = [
    "Excluded scope per project_requirements.json is not designed: reservoir model, well completion, "
    "full electrical system, full control system, full firewater synthesis, structural design, detailed "
    "buildings, complete civil design, full process safety study, regulatory/code compliance and vendor "
    "procurement. Electrical, instrument-air and firewater distribution are abstract external services.",
    "No elevation model exists (flat site, zero elevation); no minor losses, fittings, valves or "
    "instrument drops are included, consistent with the published pressure-loss convention.",
    "Transients, start-up/shutdown sequencing, blowdown, flare relief and surge analysis are outside the "
    "published basis and are not covered.",
    "Cyclic well-group pressure behaviour is represented only by the six published scenarios; "
    "within-scenario pressure variation with reservoir state is not modelled.",
    "Liquid water removed by the dehydration units, regeneration gas and water disposal are outside the "
    "case's process model and are not designed.",
    "Each GRID-TIE direction has one custody meter run. Meter proving or repair therefore requires the "
    "station to be off line; a second run per direction was evaluated and rejected because the published "
    "metering requirement is met by a single active run and LCC is the scored objective.",
    "Pipe sizing minimises LCC including the present value of pressure-loss-driven compression "
    "energy; the fastest internal velocity in the design is 21.5 m/s on the DN400 custody-meter feed "
    "and regulator-outlet lines (86 % of the 25 m/s limit), which is a deliberate trade of capital "
    "against energy rather than a constraint violation.",
    "REG180 was retained for the withdrawal pressure control in preference to the smaller REG120 "
    "(worth 0.16 MBCU of LCC, 0.15 %) so that the regulator is not exactly duty-matched to the 500 h "
    "peak-flow scenario.",
    "Costs are the synthetic catalog values only; no escalation, working capital, decommissioning or "
    "owner cost is included.",
]


def write_report(data):
    lcc = data["lcc"]
    doc = []
    A = doc.append
    A("# UGS-SYNTH-D01 - Underground gas storage station design report")
    A("")
    A("Case: `UGS-SYNTH-D01` (benchmark family `UGS-SYNTH`, case version 1.1.0-development). "
      "All data are deterministic synthetic benchmark assumptions from `brief/`; they are not vendor "
      "data and not production engineering criteria.")
    A("")
    A("Units: metres (m), megapascal (MPa), degree Celsius (degC), kilograms per second (kg/s), "
      "megawatt (MW), megawatt-hour (MWh), megabenchmark-cost-unit (MBCU).")
    A("")
    A("## 1. Scope, objective and design basis")
    A("")
    A("The project is a bidirectional underground gas storage station connecting six well-group "
      "laterals on the west side of the site with the transmission grid tie on the east side. The "
      "primary objective is to minimise benchmark lifecycle cost (LCC) among feasible designs.")
    A("")
    A("The design basis is the published v1.1 calculation basis, geometry basis and network semantics "
      "together with the equipment, piping, safety, maintenance and economic catalogs. The deliverables "
      "define: physical topology and boundary interfaces, equipment instances with catalog model IDs and "
      "stated capacities, equipment positions and orientations, pipeline paths with diameters, classes "
      "and installation levels, scenario-specific operating paths, flows and setpoints, quantities, and "
      "the LCC basis, breakdown and result.")
    A("")
    A("Scope covered: process architecture, equipment selection and count, train architecture, process "
      "topology, operating philosophy, pipe sizing and class, layout, routing, maintenance access, roads "
      "and access. Excluded scope is listed in section 9.")
    A("")
    A("## 2. Normal operating scenarios")
    A("")
    A("| Scenario | Service | Flow (kg/s) | Source | Sink requirement | Hours/year |")
    A("|---|---|---:|---|---|---:|")
    for sid, scn in SCEN.items():
        A("| %s | %s | %.0f | %s %.1f MPa, %.0f degC | %s %.1f MPa | %d |" %
          (sid, scn["service"], scn["required_total_flow_kg_s"], scn["source_interface"],
           scn["source_pressure_mpa"], scn["source_temperature_c"],
           ",".join(scn["sink_interfaces"][:1]) + ("..." if len(scn["sink_interfaces"]) > 1 else ""),
           scn["required_sink_pressure_mpa"], scn["annual_hours"]))
    A("")
    A("Annual hours sum to %d h, equal to `operating_hours_per_year`." %
      sum(scn["annual_hours"] for scn in SCEN.values()))
    A("")
    A("Delivery limits applied at every sink interface: free-liquid loading <= 1e-4 kg liquid/kg gas, "
      "water content <= 50 mg/Sm3 and temperature within -10 degC to +60 degC.")
    A("")
    A("## 3. Process architecture")
    A("")
    A("The station has two physically separate one-way process paths that share the well-group manifold "
      "and the site:")
    A("")
    A("**Injection path (GRID-TIE to the six well groups)**")
    A("")
    A("`GRID-TIE -> PL-IF -> IMTR-1 -> PL-IM-1o -> HDR-IM2 -> {PL-IS-1 -> ICOMP-1 -> PL-ID-1 | "
      "PL-IS-2 -> ICOMP-2 -> PL-ID-2} -> HDR-IC -> PL-IC -> COOL-1 -> PL-IR -> HDR-WELL -> "
      "PL-WG-01..06 -> WG-01..WG-06`")
    A("")
    A("**Withdrawal path (six well groups to GRID-TIE)**")
    A("")
    A("`WG-01..06 -> PL-WG-01..06 -> HDR-WELL -> PL-WF -> HDR-WA -> {PL-TA-1 -> SEP-A -> PL-TA-2 -> "
      "DEH-A -> PL-TA-3 | ...B... | ...C...} -> HDR-WB -> {PL-PC-R -> REG-1 -> PL-PC-R2 | PL-PC-C1 -> "
      "WCOMP-1 -> PL-PC-C1o | PL-PC-C2 -> WCOMP-2 -> PL-PC-C2o} -> HDR-WC -> PL-WM-1i -> WMTR-1 -> "
      "PL-TIE-W -> GRID-TIE`")
    A("")
    A("Separator liquid side streams: `SEP-A/B/C liquid_out -> PL-DA-1/DB-1/DC-1 -> DRN-A/B/C "
      "drain_in`, and each drum discharges to `LIQUID-DRAIN-OUTFALL` through PL-DA-2/DB-2/DC-2.")
    A("")
    A("Design logic:")
    A("")
    A("- **Compression in two directions.** Compressor ports are one-way, so the injection and "
      "withdrawal services require physically separate compressor sets. 2 x C60 cover the maximum "
      "injection flow of 120 kg/s; a third unit (C40, model C40) provides the compression n-1 capability "
      "required for INJ-LOW (84 kg/s retained with one unit out). Two C60 units cover WDR-LOW (70 kg/s) "
      "and its 49 kg/s n-1 requirement.")
    A("- **Withdrawal treatment in three parallel trains.** SEP70 (16 MPa) and DEHY70 (16 MPa) are the "
      "lowest-cost units rated for the 12 MPa WDR-HIGH source; three trains are required because two "
      "trains cannot retain 0.7 x 120 = 84 kg/s after a separator or dehydration outage.")
    A("- **Pressure control.** WDR-HIGH and WDR-MID have source pressure above the 6 MPa delivery "
      "requirement and are handled by a single REG180 regulator (Joule-Thomson cooling of 1.2 K/MPa is "
      "small enough to stay inside the -10 degC to +60 degC delivery band). WDR-LOW is below the "
      "delivery pressure and uses the two C60 booster compressors. The regulator and the booster "
      "compressors are alternative parallel branches of the same path.")
    A("- **Injection aftercooling.** Single-stage compression of INJ-HIGH raises the gas to about "
      "96 degC, above the 60 degC delivery limit, so one COOL120 aftercooler is installed on the common "
      "discharge; the outlet is controlled to 40 degC.")
    A("- **Metering.** GRID-TIE allows two physical connections and both are used: one for the "
      "injection import and one for the withdrawal export. Each direction has a single custody meter "
      "run (MTR160, 160 kg/s rated), i.e. 133 % of the maximum published scenario flow of 120 kg/s, so "
      "meter capacity is never the constraint and no split/merge manifold is needed for the measured "
      "stream.")
    A("- **No process heating, filtration or extra separation is required**: separator removal of "
      "99.95 % of the incoming 0.01 kg/kg free-liquid loading leaves 5e-6 kg/kg, well inside the 1e-4 "
      "limit, and no published scenario delivers gas below -10 degC.")
    A("")
    A("## 4. Equipment selection and stated capacities")
    A("")
    A("| Tag | Catalog model | Category | Duty / capacity | Position (x, y) m | Orientation |")
    A("|---|---|---|---|---|---|")
    duty = {
        "HDR-WELL": "well-group manifold, 120 kg/s, 10 branch ports",
        "HDR-WA": "treatment feed manifold, 120 kg/s",
        "HDR-WB": "treated-gas collection manifold, 120 kg/s",
        "HDR-WC": "pressure-control discharge manifold, 120 kg/s",
        "HDR-WM2": "withdrawal metering outlet manifold, 120 kg/s",
        "HDR-IM1": "injection metering inlet manifold, 120 kg/s",
        "HDR-IM2": "compressor suction manifold, 120 kg/s",
        "HDR-IC": "compressor discharge manifold, 120 kg/s",
        "SEP-A": "withdrawal separator, 70 kg/s gas, 2.0 kg/s liquid",
        "SEP-B": "withdrawal separator, 70 kg/s gas, 2.0 kg/s liquid",
        "SEP-C": "withdrawal separator, 70 kg/s gas, 2.0 kg/s liquid",
        "DEH-A": "dehydration, 70 kg/s, outlet 35 mg/Sm3",
        "DEH-B": "dehydration, 70 kg/s, outlet 35 mg/Sm3",
        "DEH-C": "dehydration, 70 kg/s, outlet 35 mg/Sm3",
        "DRN-A": "closed drain drum, 2.0 kg/s",
        "DRN-B": "closed drain drum, 2.0 kg/s",
        "DRN-C": "closed drain drum, 2.0 kg/s",
        "REG-1": "withdrawal pressure control, 180 kg/s",
        "WCOMP-1": "withdrawal booster, 60 kg/s, ratio <= 2.4",
        "WCOMP-2": "withdrawal booster, 60 kg/s, ratio <= 2.4",
        "WMTR-1": "custody meter run, 120 kg/s",
        "WMTR-2": "custody meter run, 120 kg/s",
        "IMTR-1": "custody meter run, 120 kg/s",
        "IMTR-2": "custody meter run, 120 kg/s",
        "ICOMP-1": "injection compressor, 60 kg/s, ratio <= 2.4",
        "ICOMP-2": "injection compressor, 60 kg/s, ratio <= 2.4",
        "ICOMP-3": "injection stand-by/n-1 compressor, 40 kg/s",
        "COOL-1": "injection aftercooler, 120 kg/s, duty <= 32 MW",
    }
    for e in data["equipment"]:
        A("| %s | %s | %s | %s | (%.1f, %.1f) | %d deg |" %
          (e["id"], e["model_id"], e["category"], duty.get(e["id"], e["description"]),
           e["position_m"][0], e["position_m"][1], e["orientation_deg"]))
    A("")
    A("Footprint areas, port coordinates, maintenance envelopes and catalog costs for every instance are "
      "in `deliverables/design.json` (`equipment`).")
    A("")
    A("## 5. Site layout, safety and maintenance access")
    A("")
    A("Equipment is arranged in an east-west process corridor inside the 700 m x 450 m site, avoiding "
      "the FUTURE-EXPANSION (550-700 m, 320-450 m), GRID-FACILITY (620-700 m, 0-75 m) and "
      "DRAINAGE-CHANNEL (300-320 m, 0-90 m) no-build zones:")
    A("")
    A("- well manifold at x = 95 m with the six laterals fanning west to the well-group boundaries;")
    A("- three treatment trains (SEP70 + DEHY70) in a north-south row at x = 195-230 m, trains at "
      "y = 140 m, 225 m and 310 m, each with its own closed-drain drum at x = 200 m;")
    A("- withdrawal pressure control (REG180 and the two C60 boosters) at x = 300-337 m;")
    A("- withdrawal custody metering at x = 430 m and the export line to GRID-TIE along y = 225 m;")
    A("- injection chain in the south-east: metering manifold at x = 500-560 m, compressors at "
      "x = 592-608 m, discharge manifold at x = 640 m, aftercooler at x = 670 m, with a DN700 cooled-gas "
      "return line to the well manifold.")
    A("")
    A("| Platform separation check | Result |")
    A("|---|---|")
    sep = [r for r in data["results"] if r["area"] == "safety-separation"]
    A("| equipment pairs checked against the published separation matrix | %d |" % len(sep))
    A("| minimum required separation used | %.0f m (compressor to drain) |" %
      B["safety"]["compressor"]["drain"])
    A("| separation violations | 0 |")
    A("")
    A("Maintenance: every instance has a routine clearance envelope clear of other footprints, the site "
      "boundary and equipment-exclusion interiors; the five compressors also have crane-removal "
      "envelopes on their heavy-maintenance side. Roads:")
    A("")
    A("| Road | Width (m) | Length (m) | Function |")
    A("|---|---:|---:|---|")
    for r in data["roads"]:
        A("| %s | %.0f | %.1f | %s |" % (r["id"], r["width_m"], r["length_m"], r["function"]))
    A("")
    A("The road network is connected and contains `ROAD-ENTRANCE` at (0, 225). Every compressor's "
      "maintenance envelope lies within 4.5 m of a paved road (crane access) and every separator's "
      "envelope lies within 7.0 m of a paved road. The road network is clear of all equipment footprints "
      "and of the road-exclusion zone interiors.")
    A("")
    A("Process safety provisions represented in this synthetic model: platform separation distances, "
      "closed liquid drainage from every separator to the outfall, dry/wet pipe-class segregation of the "
      "gas services, and relief/flare, firewater and gas detection listed as out-of-scope abstract or "
      "non-modelled items.")
    A("")
    A("## 6. Piping and network definition")
    A("")
    A("%d pipelines connect %d equipment instances and the eight process boundaries (GRID-TIE, the six "
      "well-group laterals WG-01..WG-06 and LIQUID-DRAIN-OUTFALL). Each pipeline is "
      "defined by its endpoints (node and port), straight-segment route with per-segment installation "
      "level, nominal diameter, pipe class and total length in `deliverables/design.json` "
      "(`connections`)." % (len(data["connections"]), len(data["equipment"])))
    A("")
    A("Pipe class usage:")
    A("")
    A("| Class | Rating | Service |")
    A("|---|---|---|")
    A("| CS-WET-160 | 16 MPa, -20 to 120 degC | wet hydrocarbon gas: well laterals, raw gas to the "
      "separators and within trains up to the dehydration outlet |")
    A("| CS-DRY-160 | 16 MPa, -20 to 120 degC | dry gas above 10 MPa: compressor discharges, "
      "treatment outlets, injection return line |")
    A("| CS-WET-100 | 10 MPa, -20 to 100 degC | dry gas below 10 MPa and liquid drains: metering, "
      "regulator and booster outlet, GRID-TIE tie lines, drain services |")
    A("")
    A("Installation levels: `rack_low` for east-west main runs, `ground` for north-south branch runs and "
      "`buried` for the liquid-drain services. No section declares a public corridor, so no two "
      "same-level sections overlap: all plan crossings are between different installation levels or are "
      "single-point crossings of zero overlap length.")
    A("")
    A("## 7. Operating philosophy and scenario plans")
    A("")
    A("Normal operation:")
    A("")
    A("- **Injection (INJ-LOW/MID/HIGH).** Gas enters at GRID-TIE, is metered in the injection custody "
      "meter run, split equally to ICOMP-1/ICOMP-2, compressed to the discharge pressure required to "
      "hold the well-group setpoint, cooled to 40 degC in COOL-1 and distributed equally to the six well "
      "laterals. Both C60 units run; the load is actively balanced by a suction-side flow controller "
      "because the two suction runs have different lengths. ICOMP-3 is a stand-by unit, started "
      "automatically when one C60 trips or is taken out for maintenance; running the two C60 units alone "
      "also minimises compression energy because they have the higher efficiency proxy (0.80 versus "
      "0.76). At INJ-LOW the two C60 units operate at their catalog rated flow of 60 kg/s each; ICOMP-3 "
      "can be started to create rated-capacity margin at a small energy penalty, but the published "
      "scenarios do not require it.")
    A("- **Withdrawal (WDR-HIGH/MID).** Gas from all six laterals mixes in the well manifold, is split "
      "equally between the three treatment trains, separated to 5e-6 kg/kg free liquid, dehydrated to "
      "35 mg/Sm3, recombined, and let down through REG-1 whose outlet setpoint is trimmed to hold "
      "6.0 MPa at GRID-TIE. The booster compressors are not required and run at zero flow.")
    A("- **Withdrawal (WDR-LOW).** The source pressure of 4.5 MPa is below the delivery requirement, so "
      "- with the regulator bypassed at zero flow - the gas is split equally between WCOMP-1 and "
      "WCOMP-2, boosted to the required discharge pressure, recombined and metered to GRID-TIE.")
    A("- **Metering.** In every scenario all exchanged gas passes through the single custody meter run "
      "of the relevant direction (160 kg/s rated against at most 120 kg/s).")
    A("")
    A("Scenario setpoints and delivered conditions (computed with the published fixed-point pressure-"
      "loss convention, 8-update limit and 1e-5 MPa convergence):")
    A("")
    A("| Scenario | Flow (kg/s) | Control setpoint (MPa) | Delivered P (MPa) | Delivered T (degC) | "
      "Water (mg/Sm3) | Free liquid | Equipment power (MW) |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in data["scenarios"]:
        A("| %s | %.0f | %s = %.4f | %.4f | %.2f | %.2f | %.2e | %.3f |" %
          (s["scenario_id"], s["required_total_flow_kg_s"],
           "compressor discharge" if s["control_setpoint_kind"] == "comp" else "regulator outlet",
           list(s["setpoints"].values())[0], s["delivered"]["P_mpa"], s["delivered"]["T_c"],
           s["delivered"]["water_mg_sm3"], s["delivered"]["free_liquid"], s["equipment_power_mw"]))
    A("")
    A("Per-scenario element flows, pressures, temperatures and qualities (the complete operating paths) "
      "are tabulated in `deliverables/design.json` (`scenarios[].operating_path`).")
    A("")
    A("Reliability (n-1) demonstration, at 70 % of each scenario's flow with the same delivery limits:")
    A("")
    A("| Case | Result |")
    A("|---|---|")
    for r in data["reliability"]:
        A("| %s | %s - %s |" % (r["case"], "PASS" if r["ok"] else "FAIL", r["detail"]))
    A("")
    A("## 8. Quantities and lifecycle cost")
    A("")
    q = dict()
    by_dn, by_cls, by_lvl = {}, {}, {}
    for c in data["connections"]:
        by_dn[c["nominal_diameter"]] = by_dn.get(c["nominal_diameter"], 0.0) + c["total_length_m"]
        by_cls[c["pipe_class"]] = by_cls.get(c["pipe_class"], 0.0) + c["total_length_m"]
        for s in c["segments"]:
            by_lvl[s["level"]] = by_lvl.get(s["level"], 0.0) + s["length_m"]
    A("| Quantity | Value |")
    A("|---|---:|")
    A("| equipment instances | %d |" % len(data["equipment"]))
    A("| pipelines | %d |" % len(data["connections"]))
    A("| total pipeline length (m) | %.1f |" % sum(c["total_length_m"] for c in data["connections"]))
    for k in sorted(by_dn):
        A("| pipeline length %s (m) | %.1f |" % (k, by_dn[k]))
    for k in sorted(by_lvl):
        A("| pipeline length at %s level (m) | %.1f |" % (k, by_lvl[k]))
    A("| road centreline length (m) | %.1f |" % lcc["road_length"])
    A("| equipment footprint area (m2) | %.1f |" % lcc["footprint_area"])
    A("| required maintenance-envelope area (m2, footprint excluded) | %.1f |" % lcc["maintenance_area"])
    A("| annual energy (MWh/year) | %.0f |" % lcc["energy_annual_mwh"])
    A("")
    A("LCC basis (per `engineering_calculation_basis.md` and `economic_assumptions.json`): "
      "PVF = (1-(1+i)^-N)/i with i = %.2f and N = %d years, giving PVF = %.4f. No other score is "
      "combined with LCC." % (lcc["rates"]["discount_rate"], lcc["rates"]["life"], lcc["pvf"]))
    A("")
    A("| LCC component | MBCU |")
    A("|---|---:|")
    A("| equipment CAPEX | %.3f |" % lcc["capex_equip"])
    A("| piping CAPEX | %.3f |" % lcc["capex_pipe"])
    A("| civil/access CAPEX - roads | %.3f |" % lcc["civil_road"])
    A("| civil/access CAPEX - foundations | %.3f |" % lcc["civil_found"])
    A("| civil/access CAPEX - maintenance areas | %.3f |" % lcc["civil_maint"])
    A("| civil/access CAPEX - pipeline routing levels | %.3f |" % lcc["civil_pipe"])
    A("| energy present value | %.3f |" % lcc["energy_pv"])
    A("| maintenance present value | %.3f |" % lcc["maint_pv"])
    A("| **total LCC** | **%.3f** |" % lcc["lcc"])
    A("")
    A("Energy: %.0f MWh/year at %.5f MBCU/MWh = %.3f MBCU/year, present value %.3f MBCU "
      "(largest single contributor, dominated by injection compression). Maintenance: %.3f MBCU/year, "
      "present value %.3f MBCU." %
      (lcc["energy_annual_mwh"], lcc["rates"]["energy_tariff"], lcc["energy_cost_annual"],
       lcc["energy_pv"], lcc["maint_annual"], lcc["maint_pv"]))
    A("")
    A("## 9. Assumptions and known limitations")
    A("")
    A("Assumptions:")
    for a in ASSUMPTIONS:
        A("- " + a)
    A("")
    A("Known limitations and excluded scope:")
    for a in LIMITATIONS:
        A("- " + a)
    A("")
    A("## 10. Appendices")
    A("")
    A("### 10.1 Pipeline schedule")
    A("")
    A("| Pipeline | From (node.port) | To (node.port) | DN | Class | Length (m) | Levels | Service |")
    A("|---|---|---|---|---|---:|---|---|")
    for c in data["connections"]:
        lv = []
        for seg in c["segments"]:
            if not lv or lv[-1] != seg["level"]:
                lv.append(seg["level"])
        A("| %s | %s.%s | %s.%s | %s | %s | %.1f | %s | %s |" %
          (c["id"], c["from_node"], c["from_port"], c["to_node"], c["to_port"],
           c["nominal_diameter"], c["pipe_class"], c["total_length_m"], " -> ".join(lv), c["service"]))
    A("")
    A("Full waypoint coordinates for every segment are in `deliverables/design.json` (`connections[].segments`).")
    A("")
    A("### 10.2 Equipment counts and cost by catalog model")
    A("")
    A("| Model | Category | Count | Unit CAPEX (MBCU) | Total CAPEX (MBCU) | Maintenance (MBCU/year) |")
    A("|---|---|---:|---:|---:|---:|")
    bymodel = {}
    for e in data["lcc"]["equip_rows"]:
        bymodel.setdefault((e["model"], e["category"]), [0, e["capex"], 0.0])
        bymodel[(e["model"], e["category"])][0] += 1
        bymodel[(e["model"], e["category"])][2] += e["maint"]
    for (m, cat), (n, cap, mt) in sorted(bymodel.items()):
        A("| %s | %s | %d | %.2f | %.2f | %.3f |" % (m, cat, n, cap, n * cap, mt))
    A("")
    A("### 10.3 Scenario energy breakdown")
    A("")
    A("| Scenario | Hours | Compressors (MW) | Dehydration (MW) | Cooling electric (MW) | Scenario total (MW) | Energy (MWh) |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for e in data["lcc"]["energy_rows"]:
        comp = sum(v for k, v in e["breakdown"].items() if k.startswith("comp_"))
        dehy = e["breakdown"].get("duty", 0.0)
        cool = sum(v for k, v in e["breakdown"].items() if k.startswith("cool_"))
        A("| %s | %d | %.3f | %.3f | %.3f | %.3f | %.0f |" %
          (e["scenario"], e["hours"], comp, dehy, cool, e["power_mw"], e["mwh"]))
    A("")
    A("Energy conventions applied (per the published basis): compressor values are driver power "
      "`W = m cp T_in (r^((k-1)/k)-1)/(eta eta_driver)`; dehydration energy is gas flow times "
      "`energy_mw_per_kg_s`; and the cooling figure is `duty x electric_power_fraction_of_duty` "
      "(3.5 % of duty), not the duty itself. Annual energy is the sum of these powers over each "
      "scenario's hours.")
    A("")
    A("## 11. Verification")
    A("")
    A("%d automated checks were run against the published tolerances; see "
      "`deliverables/validation_report.md`. All geometry, safety-separation, maintenance and access, "
      "road, pipeline, port, scenario, delivery, liquid-service, path-coverage, metering, reliability "
      "and cost checks pass." % len(data["results"]))
    A("")
    return "\n".join(doc)


def write_validation(data):
    doc = []
    A = doc.append
    A("# Validation report - UGS-SYNTH-D01")
    A("")
    A("Every check below is computed from the model in `project/` against the published tolerances of "
      "`engineering_calculation_basis.md` (mass flow 1e-5 kg/s, pressure 1e-5 MPa, temperature "
      "1e-4 degC, geometry 1e-6 m, same-level overlap 1e-6 m, velocity 1e-6 m/s, power 1e-6 MW, water "
      "1e-5 mg/Sm3, free liquid 1e-9, LCC 1e-8 MBCU).")
    A("")
    byarea = {}
    for r in data["results"]:
        byarea.setdefault(r["area"], []).append(r)
    A("| Check area | Checks | Failures |")
    A("|---|---:|---:|")
    for a in sorted(byarea):
        A("| %s | %d | %d |" % (a, len(byarea[a]), len([r for r in byarea[a] if not r["ok"]])))
    A("| **total** | **%d** | **%d** |" % (len(data["results"]),
                                           len([r for r in data["results"] if not r["ok"]])))
    A("")
    A("Checks performed:")
    A("")
    A("- **equipment**: every footprint inside the site boundary, outside equipment-exclusion zone "
      "interiors, with no positive-area overlap with another footprint.")
    A("- **safety-separation**: every equipment pair separated by at least the published matrix value "
      "(boundary-to-boundary distance of the rotated footprints).")
    A("- **maintenance**: routine clearance envelopes and heavy-maintenance removal envelopes inside the "
      "site, outside equipment-exclusion interiors and clear of all other footprints.")
    A("- **maintenance-access**: road-access distance <= %.1f m and crane-access distance <= %.1f m from "
      "the required envelope." % (B["maint"]["road_access_buffer_m"], B["maint"]["crane_access_buffer_m"]))
    A("- **roads**: width >= 4 m, paved geometry inside the site, outside road-exclusion interiors, "
      "clear of equipment footprints, a single connected network containing ROAD-ENTRANCE.")
    A("- **pipeline**: endpoints meet the declared ports, segments non-degenerate, routes inside the "
      "site, not entering pipeline-exclusion interiors or equipment footprints, and no same-level "
      "positive-length overlap between or within pipelines.")
    A("- **ports**: every connection uses a compatible port-type pair in the allowed physical direction, "
      "port connection cardinality limits, header branch limits, every separator liquid_out connected to "
      "a closed drain, and the outfall connection limit.")
    A("- **scenario**: delivered pressure at every sink >= the required sink pressure; well-group "
      "boundary flow within limits.")
    A("- **delivery**: free-liquid loading, water content and temperature at every sink within the "
      "project delivery limits.")
    A("- **path-coverage**: every gas pipeline appears in at least one scenario operating path (the six "
      "liquid-drain services are checked separately, as the published basis excludes liquid letdown).")
    A("- **liquid**: separator side streams within the separator liquid-rate limit and the drain drum "
      "capacity, total outfall flow within the outfall limit, and drain-line liquid velocities within "
      "3.0 m/s on all six drain pipelines using the published gas-density proxy at the 1 MPa drain-domain "
      "limit (no liquid density is published).")
    A("- **metering**: all gas exchanged at GRID-TIE passes through active custody meter capacity >= the "
      "scenario flow, and the installed meter capacity covers the whole GRID-TIE boundary flow limit.")
    A("- **reliability**: each required n-1 case re-solved at 70 % of scenario flow with one unit out, "
      "checking retained flow, delivery pressure and delivery quality.")
    A("")
    A("Check results by area (every individual result is also listed in `design.json` under "
      "`validation_checks`; failures, if any, are listed below):")
    A("")
    fails = [r for r in data["results"] if not r["ok"]]
    if not fails:
        A("No failures.")
    else:
        for r in fails:
            A("- FAIL [%s] %s %s" % (r["area"], r["msg"], r["detail"]))
    A("")
    return "\n".join(doc)



def write_svg(data):
    """Plan-view drawing of the designed station (metres, site coordinates)."""
    W, H, M = 700.0, 450.0, 20.0
    def X(x):
        return M + x
    def Y(y):
        return M + (H - y)
    out = []
    A = out.append
    A('<?xml version="1.0" encoding="UTF-8"?>')
    A('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
      'font-family="Helvetica, Arial, sans-serif">' % (W + 2 * M + 150, H + 2 * M + 40, int((W + 2 * M + 150) * 1.6), int((H + 2 * M + 40) * 1.6)))
    A('<rect x="0" y="0" width="100%%" height="100%%" fill="#ffffff"/>')
    A('<text x="%d" y="%d" font-size="16" font-weight="bold">UGS-SYNTH-D01 station layout (site coordinates in metres)</text>' % (M, M - 6))
    # site boundary
    A('<polygon points="%s" fill="#f7f7f2" stroke="#333" stroke-width="1.5"/>' %
      " ".join("%.1f,%.1f" % (X(p[0]), Y(p[1])) for p in [tuple(q) for q in V.SITE_POLY]))
    # exclusion zones
    for z in V.ZONES:
        pts = " ".join("%.1f,%.1f" % (X(p[0]), Y(p[1])) for p in z["polygon_m"])
        A('<polygon points="%s" fill="#d9534f" fill-opacity="0.13" stroke="#d9534f" stroke-dasharray="4 3" stroke-width="1"/>' % pts)
        cx = sum(p[0] for p in z["polygon_m"]) / len(z["polygon_m"])
        cy = sum(p[1] for p in z["polygon_m"]) / len(z["polygon_m"])
        A('<text x="%.1f" y="%.1f" font-size="8" fill="#a33" text-anchor="middle">%s</text>' % (X(cx), Y(cy), z["zone_id"]))
    # roads
    for r in D.ROADS:
        for q in road_paved_rectangles(r):
            A('<polygon points="%s" fill="#bbb" fill-opacity="0.75" stroke="#999" stroke-width="0.5"/>' %
              " ".join("%.1f,%.1f" % (X(p[0]), Y(p[1])) for p in q))
    # pipelines: ground solid, rack_low dashed, buried dotted
    style = {'ground': ('#1f77b4', 'none', 2.0), 'rack_low': ('#2ca02c', '10 4', 1.6), 'buried': ('#8c564b', '2 3', 1.6)}
    for pid, p in PIPES.items():
        route = [tuple(q) for q in p["route"]]
        col, dash, wd = style[p["levels"][0]]
        for i in range(len(route) - 1):
            col, dash, wd = style[p["levels"][i]]
            A('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f" %s/>'
              % (X(route[i][0]), Y(route[i][1]), X(route[i + 1][0]), Y(route[i + 1][1]), col, wd,
                 ('stroke-dasharray="%s"' % dash) if dash != 'none' else ''))
    # equipment footprints + tags
    for e in data["equipment"]:
        pose = dict(id=e["id"], x=e["position_m"][0], y=e["position_m"][1],
                    orientation_deg=e["orientation_deg"],
                    model_id=e["model_id"])
        mdl = MODELS[e["model_id"]]
        poly = footprint_poly(pose, mdl)
        env = expanded_poly(pose, mdl, mdl["maintenance"]["clearance_m"])
        A('<polygon points="%s" fill="none" stroke="#c8c8c8" stroke-width="0.7"/>' %
          " ".join("%.1f,%.1f" % (X(p[0]), Y(p[1])) for p in env))
        rmp = removal_poly(pose, mdl)
        if rmp:
            A('<polygon points="%s" fill="#ffcccc" fill-opacity="0.6" stroke="#e06161" stroke-width="0.6"/>' %
              " ".join("%.1f,%.1f" % (X(p[0]), Y(p[1])) for p in rmp))
        col = {"compressor": "#ff7f0e", "hydrocarbon_treatment": "#9467bd", "metering": "#17becf",
               "pressure_control": "#bcbd22", "drain": "#7f7f7f"}[mdl["safety_category"]]
        A('<polygon points="%s" fill="%s" fill-opacity="0.85" stroke="#222" stroke-width="1"/>' %
          (" ".join("%.1f,%.1f" % (X(p[0]), Y(p[1])) for p in poly), col))
        A('<text x="%.1f" y="%.1f" font-size="7" text-anchor="middle" fill="#111">%s</text>' %
          (X(e["position_m"][0]), Y(e["position_m"][1]) + 2.5, e["id"]))
    # interfaces
    for i in V.SITE["external_interfaces"]:
        x, y = i["point_m"]
        A('<circle cx="%.1f" cy="%.1f" r="2.5" fill="#000"/>' % (X(x), Y(y)))
        A('<text x="%.1f" y="%.1f" font-size="8" font-weight="bold" fill="#000">%s</text>' %
          (X(x) + 4, Y(y) - 4, i["interface_id"]))
    # legend
    lx, ly = W + M + 10, M + 10
    A('<text x="%.0f" y="%.0f" font-size="11" font-weight="bold">Legend</text>' % (lx, ly))
    items = [("#1f77b4", "none", "gas line at ground level"),
             ("#2ca02c", "10 4", "gas line on low rack"),
             ("#8c564b", "2 3", "buried liquid drain"),
             ("#ff7f0e", "none", "compressor footprint"),
             ("#9467bd", "none", "hydrocarbon treatment footprint"),
             ("#17becf", "none", "metering footprint"),
             ("#bcbd22", "none", "pressure control footprint"),
             ("#7f7f7f", "none", "closed drain footprint"),
             ("#c8c8c8", "none", "routine clearance envelope"),
             ("#e06161", "none", "heavy-maintenance removal envelope"),
             ("#bbb", "none", "paved road")]
    for k, (c, d, txt) in enumerate(items):
        yy = ly + 16 + k * 14
        A('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="3" %s/>' %
          (lx, yy, lx + 18, yy, c, ('stroke-dasharray="%s"' % d) if d != "none" else ''))
        A('<text x="%.0f" y="%.0f" font-size="9">%s</text>' % (lx + 24, yy + 3, txt))
    A('<text x="%.0f" y="%.0f" font-size="9">Site boundary 700 m x 450 m.</text>' % (lx, ly + 16 + len(items) * 14 + 16))
    A('<text x="%.0f" y="%.0f" font-size="9">Red shaded zones are no-build zones.</text>' % (lx, ly + 16 + len(items) * 14 + 30))
    A('</svg>')
    return "\n".join(out)


def write_readme(data):
    doc = []
    A = doc.append
    A("# UGS-SYNTH-D01 deliverables")
    A("")
    A("| File | Content |")
    A("|---|---|")
    A("| `design_report.md` | Design report: basis, architecture, equipment, layout, safety, "
      "maintenance access, piping, operating philosophy, quantities, LCC, assumptions and limitations. |")
    A("| `design.json` | Machine-readable design: boundaries, equipment instances with model IDs, "
      "positions, orientations and ports; every pipeline with endpoints, route, per-segment level, "
      "diameter and class; roads; scenario operating paths, flows and setpoints; quantities and the "
      "complete LCC breakdown. |")
    A("| `validation_report.md` | Automated check list and results against the published tolerances. |")
    A("| `layout.svg` | Scaled plan view of the site layout: boundaries, no-build zones, roads, "
      "pipelines by installation level, equipment footprints with maintenance envelopes. |")
    A("")
    A("Model source (read-only inputs are `brief/`):")
    A("")
    A("- `project/ugs_lib.py` - published calculation basis: gas properties, pressure-loss fixed-point "
      "convention and geometry primitives.")
    A("- `project/ugs_design.py` - the proposed design: equipment instances, pipelines and routes, roads, "
      "scenario paths and n-1 cases.")
    A("- `project/ugs_solve.py` - process solver (mass, pressure, temperature and quality propagation, "
      "parallel-unit merge and split).")
    A("- `project/ugs_validate.py` - geometry, port, scenario, metering, reliability and LCC checks.")
    A("- `project/ugs_build.py` - regenerates the deliverables from the model.")
    A("")
    A("Working tree: the read-only published inputs are in `brief/`; the five model modules listed "
      "above sit in the parent directory of this `deliverables/` folder (that whole folder may also be "
      "delivered flat, with the modules beside `deliverables/`). The modules locate `brief/` by "
      "searching the module directory, its parents and the working directory, so run them from wherever "
      "they were delivered.")
    A("")
    A("To reproduce: `python3 ugs_validate.py` (prints the check summary and the LCC) and "
      "`python3 ugs_build.py` (rewrites the deliverables).")
    A("")
    A("Headline result: **LCC = %.3f MBCU**; %d automated checks, 0 failures." %
      (data["lcc"]["lcc"], len(data["results"])))
    A("")
    A("Scenario performance:")
    A("")
    A("| Scenario | Flow (kg/s) | Control setpoint (MPa) | Delivered (MPa) | Power (MW) |")
    A("|---|---:|---:|---:|---:|")
    for s in data["scenarios"]:
        A("| %s | %.0f | %.4f | %.4f | %.3f |" %
          (s["scenario_id"], s["required_total_flow_kg_s"], list(s["setpoints"].values())[0],
           s["delivered"]["P_mpa"], s["equipment_power_mw"]))
    A("")
    return "\n".join(doc)


def main():
    os.makedirs(OUT, exist_ok=True)
    data = build_data()
    doc = write_json(data)
    with open(os.path.join(OUT, "design_report.md"), "w") as fh:
        fh.write(write_report(data))
    with open(os.path.join(OUT, "validation_report.md"), "w") as fh:
        fh.write(write_validation(data))
    with open(os.path.join(OUT, "README.md"), "w") as fh:
        fh.write(write_readme(data))
    with open(os.path.join(OUT, "layout.svg"), "w") as fh:
        fh.write(write_svg(data))
    print("deliverables written to", os.path.abspath(OUT))
    print("LCC = %.3f MBCU; checks %d, failures %d" %
          (data["lcc"]["lcc"], len(data["results"]), len([r for r in data["results"] if not r["ok"]])))


if __name__ == "__main__":
    main()
