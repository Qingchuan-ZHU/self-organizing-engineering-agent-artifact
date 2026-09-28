# Anonymous engineering review: submission_G / pass_02

**Evaluation window:** 2026-09-25T06:18:04Z to 2026-09-25T06:28:35Z
**Evaluator process exit:** 0

The submission is mostly reconstructable and the sampled normal-scenario, hydraulic, equipment-limit, and LCC arithmetic checks are broadly consistent with the public basis. I found one confirmed physical endpoint-reference violation for the drain outfall, one material unsupported reliance on free/unpriced isolation and bypass valves, one public semantics gap for liquid-drain velocity density, and one low-impact internal inconsistency in claimed meter capacity.

## Finding counts

- confirmed_violation: 1 (high 0, medium 1, low 0)
- unsupported_claim: 2
- suspected_risk: 0
- semantics_gap: 1
- observation: 0

## Areas checked

| Area | Coverage | Details |
|---|---|---|
| deliverable_completeness_reconstructability | full | Compared brief/final_delivery_contract.json with submission deliverables. The submission includes a report, equipment register, topology, pipeline schedule, scenario operations, allocations, reliability cases, quantities, LCC, validation report, and layout. Equipment, catalog model IDs, positions, ports, routes, pipe classes, scenario flows/setpoints, costs, assumptions, and limitations are generally reconstructable. Exceptions are captured in findings for the drain outfall endpoint name and unmodelled isolation assumptions. |
| physical_topology_and_port_semantics | sampled | Checked declared external interfaces, catalog port types, branch/header usage, GRID-TIE and well-group connection counts, drain routes, and one-way port use in the active paths. Header branch counts and boundary connection counts are within limits in the sampled reconstruction. P39-P41 reference LIQUID-DRAIN-OUTFALL.gas even though the public and submitted interface port_id is drain. |
| operating_scenarios | sampled | Covered all six mandatory scenarios from scenario_operations.json and well_group_allocations.csv. Checked allocation sums, per-well maximum 25 kg/s limits, delivered pressure/temperature/water/free-liquid values, active meter capacity, and representative active paths. Flow and hydraulic details were independently recomputed only for selected representative pipes, not every pipe in every scenario. |
| n_minus_1_reliability | sampled | Checked the case inventory against the public N-1 selectors: 12 compressor-outage cases and 18 withdrawal treatment-outage cases are reported. Retained flow fractions are 0.7 and surviving nameplate capacities meet or exceed retained flow. I did not fully reconstruct every contingency active path because reliability_cases.json provides delivered summaries but not per-contingency pipeline-flow/path tables; the claimed isolation also depends on unmodelled valves. |
| equipment_limits | sampled | Sampled worst or representative limits: MTR120 at 120 kg/s, C60 injection high-pressure ratio and discharge temperature, C60 WDR-LOW compression, separator/dehydration train WDR-HIGH flow and liquid removal, regulator/cooler duty, header capacity, and closed-drain capacity. No sampled numerical exceedance was found. |
| hydraulic_calculations | sampled | Independently recomputed gas properties, velocity, Reynolds number, friction factor, and fixed-point pressure loss for P01 INJ-LOW, P32 WDR-HIGH, P11 INJ-LOW, and the limiting drain velocity assumption for P37 WDR-HIGH. These cover highest flow, high velocity, long/small-DN, and critical pressure-margin examples, but not all pipelines. |
| gas_quality_and_temperature | sampled | Checked delivered sink values for all six scenarios. Injection remains water 40 mg/Sm3 and free liquid 0; withdrawal after separation/dehydration is reported at water 35 mg/Sm3 and free liquid 5e-6. Temperatures at delivery are within -10 to 60 C. Wet/dry pipe-class eligibility was sampled along injection dry and withdrawal wet/dry paths. |
| liquid_drain | sampled | Checked all three separator-to-drain-to-outfall routes at the worst normal withdrawal case reported. Separator liquid rates, DRN-S capacities, total outfall flow, outfall connection count, and DN200 CS-WET-100 class were reviewed. Definitive liquid velocity compliance is a public semantics gap because no liquid density is published; the submission uses a gas-density proxy. |
| geometry_layout_roads_maintenance | sampled | Sampled site containment, exclusion avoidance, safety separation, road widths/connectivity, and access distances from equipment_register.json, design_report.md, validation_results.json, and road geometry in submission/tools/design.py. Examples checked include drain-drain separation, compressor road/crane access, future-expansion avoidance, and road length. I did not independently reimplement a full polygon overlap engine. |
| pipeline_geometry | sampled | Checked route endpoint coordinates and selected route/exclusion cases from process_topology.json and pipeline_schedule.csv. All routes are ground level and no corridor is declared. The main exact endpoint issue is P39-P41 using an undeclared LIQUID-DRAIN-OUTFALL.gas port. Same-level overlap and all footprint crossings were not exhaustively recomputed. |
| lifecycle_cost_arithmetic | sampled | Independently recomputed installed equipment CAPEX, annual maintenance, PV factor, energy present value, maintenance present value, road/foundation/maintenance-area civil cost, and sample piping CAPEX lines. The total LCC arithmetic matches the reported 87.961988 MBCU within rounding. I did not manually sum every pipeline segment line-by-line. |
| lcc_objective | sampled | Reviewed the major sizing choices for obvious dominated equipment: three compressors, three SEP70/DEHY70 trains, MTR120 meters, HDR120 headers, and DN choices. I did not establish global optimality and found no fully specified lower-cost feasible alternative with a defensible delta-LCC. |
| unsupported_assumptions | full | Reviewed the assumptions and known limitations in design_report.md. The material unsupported assumptions are free/unpriced isolation valves/check valves/bypass line-up, passive compressor pass-through in WDR-HIGH/WDR-MID, and the liquid-drain density basis. These are distinguished from confirmed numerical violations. |
| internal_consistency | sampled | Cross-checked report, JSON, CSV, validation, and LCC values. LCC and equipment quantities are internally consistent in sampled checks. Inconsistencies found: drain outfall endpoint name mismatch and report claims of 160 kg/s meter capacity despite MTR120 equipment rated at 120 kg/s. |

## Independent calculations

### Equipment CAPEX and Annual Maintenance Recalculation

**Method:** Summed public catalog CAPEX and annual maintenance for each installed model in the equipment register: COOL120; 3 x DEHY70; 3 x DRN-S; 5 x HDR120; 2 x C60; 1 x C40; 2 x MTR120; 1 x REG120; 3 x SEP70.

**Result:** Equipment CAPEX = 28.84 MBCU and annual maintenance = 1.047 MBCU/yr, matching lcc.json. Example subtotal: compressors = 6.5 + 6.5 + 4.6 = 17.6 MBCU; treatment trains = 3 x (0.78 + 1.85) = 7.89 MBCU.

**Public inputs:** brief/equipment_catalog/*.json catalog capex_mbcu and annual_maintenance_mbcu values
**Submission inputs:** submission/deliverables/equipment_register.json, submission/deliverables/lcc.json
**Scratch files:** None listed

### Lifecycle Cost Arithmetic Recalculation

**Method:** Recomputed PVF = (1 - (1 + 0.08)^-20) / 0.08, annual energy cost, maintenance PV, civil cost from road/foundation/maintenance areas, and sampled pipe line costs using length x DN rate x class multiplier x level multiplier.

**Result:** PVF = 9.818147407. Civil/access = 1406 x 0.00015 + 775 x 4e-6 + 1589.88 x 1e-6 = 0.21558988 MBCU. Energy PV = 39713.371419 x 0.00012 x PVF = 46.789408 MBCU. Maintenance PV = 1.047 x PVF = 10.279600 MBCU. Total = 28.84 + 1.837390 + 0.215590 + 46.789408 + 10.279600 = 87.961988 MBCU, matching lcc.json. Sample pipe P01 = 133 x 0.00066 x 1.15 = 0.100947 MBCU.

**Public inputs:** brief/economic_assumptions.json, brief/piping_catalog.json, brief/engineering_calculation_basis.md lifecycle-cost formula
**Submission inputs:** submission/deliverables/lcc.json, submission/deliverables/quantities.json, submission/deliverables/process_topology.json, submission/deliverables/scenario_operations.json
**Scratch files:** None listed

### Scenario Delivery and Allocation Checks

**Method:** For each of the six scenarios, compared allocation totals with required_total_flow_kg_s, checked each well-group flow against 25 kg/s, checked delivered pressure/temperature/water/free-liquid at gas sinks, and compared active meter model capacity with scenario flow.

**Result:** All six allocation totals equal the required scenario flows: 120, 100, 75, 120, 100, and 70 kg/s. Largest well allocation is about 20.683 kg/s, below 25 kg/s. Delivered gas sinks meet pressure and quality limits in the submitted results. MTR-INJ and MTR-WDR are MTR120 units; actual active meter capacity is 120 kg/s, which equals the maximum scenario flow and meets the public minimum fraction of 1.0 at equality.

**Public inputs:** brief/operating_scenarios.json, brief/project_requirements.json, brief/well_group_interfaces.json
**Submission inputs:** submission/deliverables/scenario_operations.json, submission/deliverables/well_group_allocations.csv, submission/deliverables/equipment_register.json
**Scratch files:** None listed

### Hydraulic Fixed-Point Samples

**Method:** Manually recomputed representative mean-pressure gas properties, velocity, Reynolds number, Swamee-Jain friction factor, and pressure loss for selected reported pipes using the published formulas.

**Result:** P01 INJ-LOW at 120 kg/s, DN700, L=133 m, Pmean about 6.499 MPa, T=25 C gives Z about 0.9323, mu about 1.08e-5 Pa*s, rho about 51.2 kg/m3, v about 6.89 m/s, Re about 2.16e7, f about 0.0095, dP about 0.00234 MPa versus reported 0.002346. P32 WDR-HIGH at 120 kg/s, DN500, L=82 m, T about 13.1 C gives v about 14.0 m/s and dP about 0.0101 MPa, matching the reported high-velocity case and below the 25 m/s limit. P11 INJ-LOW, DN300, L=382.105 m gives dP about 0.01378 MPa, matching the critical delivery margin. P37 WDR-HIGH under the submission's 1 MPa gas-density drain assumption gives v about 2.06 m/s, below 3 m/s.

**Public inputs:** brief/engineering_calculation_basis.md gas-property and pipe-loss formulas, brief/gas_properties.json, brief/piping_catalog.json
**Submission inputs:** submission/deliverables/scenario_operations.json, submission/deliverables/process_topology.json, submission/deliverables/design_report.md
**Scratch files:** None listed

### N-1 Reliability Inventory Check

**Method:** Derived expected N-1 cases from public selectors: all installed compressors for scenarios with required_sink_pressure_mpa > source_pressure_mpa, plus all separators and dehydration units for each withdrawal scenario. Compared retained flow and surviving capacity fields with the 0.7 fraction requirement.

**Result:** Expected cases = 3 compressors x 4 compression scenarios = 12 plus 6 treatment units x 3 withdrawal scenarios = 18, total 30. reliability_cases.json reports 30 cases. Retained flows are 84, 70, 52.5, or 49 kg/s as applicable, exactly 0.7 of scenario flow. Reported surviving capacities exceed the retained-flow requirement in all cases. Per-contingency active paths were not fully independently reconstructed because reliability_cases.json lacks pipeline-flow tables.

**Public inputs:** brief/project_requirements.json reliability requirements, brief/operating_scenarios.json
**Submission inputs:** submission/deliverables/reliability_cases.json, submission/deliverables/equipment_register.json
**Scratch files:** None listed

### Liquid Removal and Drain Capacity Check

**Method:** Checked the worst normal withdrawal separator branch from WDR-HIGH and compared removed liquid with separator, closed-drain, and outfall limits.

**Result:** For WDR-HIGH train 2, m_dot about 47.16 kg/s and source free-liquid loading 0.01 with SEP70 efficiency 0.9995 gives removed liquid about 0.4716 kg/s. This is below SEP70 maximum_liquid_rate 2.0 kg/s and DRN-S capacity 0.8 kg/s. Total normal outfall liquid is about 1.199 kg/s, below the 10 kg/s outfall limit, and three outfall connections are below the maximum of eight. The endpoint naming defect for P39-P41 is listed separately.

**Public inputs:** brief/engineering_calculation_basis.md separator liquid formula, brief/equipment_catalog/separators.json, brief/equipment_catalog/drains.json, brief/site.json
**Submission inputs:** submission/deliverables/scenario_operations.json, submission/deliverables/process_topology.json
**Scratch files:** None listed

### Geometry and Access Spot Checks

**Method:** Checked selected footprint positions against the site and exclusion zones, sampled separations and maintenance access, and recomputed road length from the stated road centrelines.

**Result:** Sampled equipment centres and footprints are within the 700 m x 450 m site and outside the future-expansion and grid-facility exclusions. DRN-1/DRN-2 boundary gap is 8 m versus 4 m required. C60 removal envelope east edge is about 0.5 m from the paved road boundary at x=421 m, within the 4.5 m crane buffer. Road length from centrelines is (660-3) + (440-100) + (665-421) + (275-110) = 1406 m, matching quantities.json.

**Public inputs:** brief/site.json, brief/safety_requirements.json, brief/engineering_geometry_basis.md, brief/maintenance_requirements.json
**Submission inputs:** submission/deliverables/equipment_register.json, submission/deliverables/design_report.md, submission/tools/design.py, submission/deliverables/validation_results.json
**Scratch files:** None listed

## Findings

### F-001 — confirmed_violation / medium / confidence high

**Public basis:** brief/site.json declares LIQUID-DRAIN-OUTFALL with port_id drain and port_type drain_in. brief/network_semantics.md requires physical connections between compatible ports; drain_out is compatible with drain_in.

**Claim or requirement:** Liquid drain pipelines must terminate on the declared drain_in physical outfall port, and endpoint references must identify physical ports for reconstructability and port compatibility.

**Submission evidence:** submission/deliverables/process_topology.json lists P39, P40, and P41 with to_port LIQUID-DRAIN-OUTFALL.gas. submission/deliverables/pipeline_schedule.csv and submission/deliverables/design_report.md repeat the same endpoint. The interface entry in process_topology.json itself lists port_id drain, not gas.

**Independent check:** Compared the three outfall pipeline endpoint names with the public and submitted external-interface port_id fields. GRID-TIE and well groups use gas ports, but LIQUID-DRAIN-OUTFALL uses drain.

**Result:** P39-P41 reference an undeclared endpoint. The route geometry still ends at the outfall coordinates, so the likely intended endpoint is LIQUID-DRAIN-OUTFALL.drain, but strict port reconstruction and compatibility checking fail without that inference.

**Why it matters:** Closed-drain compliance depends on proving separator liquid reaches a compatible drain_in boundary port within connection limits. The submission's own validation reports port compatibility PASS despite this exact endpoint mismatch.

### F-002 — unsupported_claim / medium / confidence high

**Public basis:** brief/final_delivery_contract.json requires the physical system and operating scenarios to be reconstructable. brief/engineering_calculation_basis.md prices installed catalog equipment in LCC. brief/network_semantics.md defines physical components and ports; no valve or check-valve catalog component is published.

**Claim or requirement:** The submission claims inactive paths and failed units are isolated, including scenario valve line-ups, compressor unit valves, discharge checks, and bypass/pass-through line-ups.

**Submission evidence:** submission/deliverables/design_report.md section 5.3 states that isolation and check valves are not catalogue components and provides a valve schedule V-01 through V-08 plus unit valves. Section 11 assumption 2 says valves are not modelled as physical items. reliability_cases.json states failed units have no exceptions, but does not include per-contingency valve states or pipeline flows. lcc.json equipment_lines contain no valves or bypass components.

**Independent check:** Reviewed the physical topology and LCC artifacts for valve/check/bypass instances and costs; only catalog equipment and pipelines are installed. The operating and N-1 claims rely on active-path declarations that remove flow from connected inactive branches or failed units without a priced physical isolation element.

**Result:** The claimed isolation is an operating assumption, not a reconstructable or priced physical artifact. This does not prove infeasibility because the public catalog has no valve model, but the submission's N-1 and active-path evidence depends materially on free isolation/bypass semantics.

**Why it matters:** N-1 reliability and seasonal operation require the failed unit to leave the active path and inactive meter/cooler/treatment paths not to carry unintended flow. If isolation is in scope or must be costed, the reported topology and LCC are incomplete.

### F-003 — semantics_gap / low / confidence high

**Public basis:** brief/engineering_calculation_basis.md imposes a maximum_liquid_drain_velocity_m_s but does not publish a liquid density. The gas density formula is explicit for gas properties; the brief does not state a unique density for separated liquid.

**Claim or requirement:** The submission claims DN200 drain lines satisfy the liquid-drain velocity limit, using the gas-property density proxy at 1.0 MPa as a conservative assumption.

**Submission evidence:** submission/deliverables/design_report.md assumption 6 says liquid-drain lines are checked with the gas property proxy in the 1.0 MPa drain domain. scenario_operations.json and design_report.md report WDR-HIGH P37 velocity about 2.064 m/s for the limiting normal drain line.

**Independent check:** For WDR-HIGH P37, m_dot about 0.4716 kg/s and DN200 internal diameter 0.188 m give area about 0.02776 m2. Using the gas proxy at 1.0 MPa and 20 C gives rho about 8.23 kg/m3 and velocity about 2.06 m/s; using an assumed condensate density of 1000 kg/m3 would give about 0.017 m/s.

**Result:** Under the submission's gas-proxy assumption, the drain velocity is below the 3 m/s limit. Because the public brief does not define liquid density or explicitly mandate the gas proxy for liquid velocity, there is no unique public calculation for a definitive PASS/FAIL on liquid velocity.

**Why it matters:** The drain pipe size and cost are affected by the velocity basis. This is a public-semantics gap, not a confirmed submission violation.

### F-004 — unsupported_claim / low / confidence high

**Public basis:** brief/project_requirements.json requires active GRID-TIE metering capacity at least 1.0 times scenario flow. brief/equipment_catalog/metering_regulation.json defines MTR120 with capacity_kg_s 120 and MTR160 with capacity_kg_s 160.

**Claim or requirement:** The design report claims the active meter rated capacity is 160 kg/s and larger than the largest scenario flow.

**Submission evidence:** submission/deliverables/design_report.md states the inlet and outlet metering lines are MTR-INJ and MTR-WDR at 160 kg/s and later says active meter rated capacity (160 kg/s) is at least the scenario flow. submission/deliverables/equipment_register.json lists both meters as model_id MTR120 with rated_capacity_kg_s 120.

**Independent check:** Compared the installed meter model IDs against the public metering catalog and maximum scenario flow. MTR120 is 120 kg/s; the maximum scenario flow is 120 kg/s.

**Result:** The design meets the public metering requirement at equality, but the report's 160 kg/s and 'larger than largest scenario flow' statements are unsupported and internally inconsistent with the register, LCC, and catalog model selection.

**Why it matters:** This does not invalidate metering compliance, but it is a documentation and internal-consistency defect in a mandatory boundary requirement.

## Limitations

- No evaluator-authored scratch files were created because the active execution environment exposed the workspace as read-only and blocked interpreter-based scratch calculations. Independent arithmetic is documented directly in this JSON object.
- I did not inspect any parent directories, hidden production data, prior evaluations, or external answers.
- I did not rely on the submission validator PASS status as independent evidence. Submission code was inspected only for context such as road definitions and stated assumptions.
- Hydraulic checks were representative samples, not a full recomputation of every pipe in every scenario.
- Geometry, overlap, road exclusion, and maintenance access checks were sampled manually rather than exhaustively recomputed with an independent polygon engine.
- Reliability case inventory and retained-flow arithmetic were checked, but per-contingency active-path hydraulics were not fully reconstructed because reliability_cases.json does not include full contingency pipeline-flow tables.

Codex post-hoc findings are independent model-based engineering review findings, not formal ground truth.
