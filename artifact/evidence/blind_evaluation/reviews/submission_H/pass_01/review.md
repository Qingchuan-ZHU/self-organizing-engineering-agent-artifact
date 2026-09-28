# Anonymous engineering review: submission_H / pass_01

**Evaluation window:** 2026-09-25T08:38:18Z to 2026-09-25T08:49:49Z
**Evaluator process exit:** 0

The submission is broadly reconstructable and many sampled scenario, hydraulic, quality, geometry, and LCC checks are internally consistent. The main issues are that the design is not LCC-minimal due exact lower-cost catalog substitutions, the N-1 evidence is representative rather than exhaustive for any-one-unit outages, liquid-drain velocity cannot be uniquely judged from the public brief because liquid density is absent, and the report misstates DRN-S capacity.

## Finding counts

- confirmed_violation: 1 (high 0, medium 1, low 0)
- unsupported_claim: 2
- suspected_risk: 0
- semantics_gap: 1
- observation: 0

## Areas checked

| Area | Coverage | Details |
|---|---|---|
| deliverable_completeness_reconstructability | full | Compared brief/final_delivery_contract.json with submission/deliverables. design_report.md and design.json include equipment instances and model IDs, boundary interfaces, ports/topology, positions/orientations, pipeline paths with DNs/classes/levels, all six scenario paths/flows/setpoints, quantities, LCC breakdown, assumptions, and limitations. One report capacity inconsistency is listed as a finding. |
| physical_topology_and_port_semantics | sampled | Checked the 40-pipeline schedule and sampled JSON endpoints against brief/network_semantics.md. Major gas paths respect one-way compressor/meter/regulator ports, bidirectional header/well/GRID ports, two GRID-TIE process connections, one connection to each well group, and three outfall drain connections within the limit of eight. I did not independently re-count every port in code. |
| operating_scenarios | sampled | Covered INJ-LOW, INJ-MID, INJ-HIGH, WDR-HIGH, WDR-MID, and WDR-LOW. Independently checked top-level allocation sums, delivered pressure margins, delivered temperature/water/free-liquid limits, metering model capacity, and active path selection. Hydraulic recomputation was sampled rather than repeated for every path element. |
| n_minus_1_reliability | full | Reviewed all reliability cases in submission/deliverables/design.json and submission/ugs_design.py. The artifacts simulate named representative outages, but not every installed compressor, separator, and dehydration unit for every applicable scenario; this is a finding. |
| equipment_limits | sampled | Compared installed compressor, separator, dehydration, cooler, meter, regulator, header, and closed-drain models with public catalog capacities/ratings. Sampled normal maxima: C60 compressors at 60 kg/s, treatment trains at 40 kg/s each in WDR-HIGH, MTR160 at 120 kg/s, REG180 at 120 kg/s, COOL120 at 120 kg/s. No sampled capacity/rating violation found. |
| hydraulic_calculations | sampled | Independently recomputed Z, viscosity, density, velocity, Reynolds number, Swamee-Jain friction factor, and pressure loss for PL-WM-1i in WDR-HIGH, PL-IR in INJ-LOW, and PL-WG-06 in INJ-LOW. These target the high-flow/high-velocity case, long pipe, and critical pressure-margin branch. Liquid DN200 velocity was checked only under the submission's stated gas-density proxy assumption. |
| gas_quality_and_temperature | sampled | Checked delivered limits in all six scenarios. Sampled state changes: separator free-liquid loading 0.01*(1-0.9995)=5e-6, dehydration outlet water 35 mg/Sm3, WDR-HIGH regulator cooling about 6.78 C, injection aftercooler outlet 40 C. Sampled values are consistent with public formulas and limits. |
| liquid_drain | sampled | Checked separator liquid side-stream formula, drain connectivity SEP-A/B/C to DRN-A/B/C to LIQUID-DRAIN-OUTFALL, outfall flow limit, DRN-S capacity against sampled side-streams, and liquid-compatible CS-WET-100 drain class. Liquid velocity is a semantics gap because the public brief gives no liquid density. |
| geometry_layout_roads_maintenance | sampled | Sampled site containment, equipment exclusion zones, obvious footprint separations, road widths and road network connectivity. Examples checked include COOL-1, injection compressors, withdrawal compressors, separator/drain separations, and road connections to RD-MAIN. I did not recompute all 276 pairwise polygon separations. |
| pipeline_geometry | sampled | Sampled route endpoint matching and containment for PL-IF, PL-IR, drain routes, well-group laterals, and meter/regulator lines. Route levels and crossings were inspected, but I did not independently recompute all same-level overlap and self-overlap cases. |
| lifecycle_cost_arithmetic | sampled | Independently recomputed PVF, equipment CAPEX, annual maintenance and PV, annual energy and PV, civil road/foundation/maintenance/pipeline-level costs, and sampled pipe cost formulas. Piping CAPEX was not fully summed segment-by-segment from raw JSON. |
| lcc_objective | sampled | Looked for dominated catalog choices. Found exact lower-cost substitutions for REG180 to REG120 and both MTR160 meters to MTR120 that preserve capacity, pressure rating, geometry, ports, and scenario feasibility. |
| unsupported_assumptions | sampled | Reviewed stated assumptions. The main unsupported or ambiguous items are representative N-1 cases presented as complete any-one-unit evidence and the liquid-drain velocity proxy used because no public liquid density is provided. |
| internal_consistency | sampled | Cross-checked report, JSON, validation report, and source for equipment models/capacities, N-1 cases, scenario summaries, validation claims, quantities, and LCC. Found a report-vs-catalog drain capacity inconsistency. |

## Independent calculations

### PVF and LCC component arithmetic

**Method:** Computed PVF = (1-(1+0.08)^-20)/0.08 = 9.818147. Summed equipment model counts from the report: C40 1, C60 4, COOL120 1, DEHY70 3, DRN-S 3, HDR120 6, MTR160 2, REG180 1, SEP70 3. Recomputed annual energy from scenario powers and hours.

**Result:** Equipment CAPEX = 42.370 MBCU and annual maintenance = 1.391 MBCU/y, giving maintenance PV = 13.657 MBCU. Scenario energy = 40452.28 MWh/y, annual energy cost = 4.8543 MBCU/y, energy PV = 47.660 MBCU. Civil sampled components match: roads 1065*0.00015=0.15975, foundations 1033*4e-6=0.00413, maintenance area 2079.96*1e-6=0.00208, routing civil about 0.08707 MBCU. These match the submitted LCC components to displayed precision.

**Public inputs:** brief/economic_assumptions.json: discount_rate 0.08, project_life_years 20, energy tariff 0.00012 MBCU/MWh, civil rates, brief/equipment_catalog/*.json: installed model CAPEX and annual maintenance, brief/engineering_calculation_basis.md: LCC formula
**Submission inputs:** submission/deliverables/design.json:lcc, submission/deliverables/design_report.md section 8 and appendix 10.3
**Scratch files:** None listed

### Dominated meter and regulator substitutions

**Method:** Compared catalog ratings, geometry, ports, pressure drops, CAPEX, and annual maintenance. Maximum normal meter/regulator scenario flow is 120 kg/s. N-1 retained flows are lower. REG120 and MTR120 have adequate 120 kg/s capacity, same pressure rating needed here, same port offsets/footprints as the installed larger models; MTR120 also has lower pressure drop than MTR160.

**Result:** Replacing REG180 with REG120 reduces LCC by (0.46-0.34)+(0.022-0.018)*9.818147 = 0.159273 MBCU. Replacing both MTR160 meters with MTR120 reduces LCC by 2*((0.38-0.30)+(0.020-0.016)*9.818147)=0.238545 MBCU. Combined reduction is 0.397819 MBCU before any favorable meter pressure-drop energy benefit, with no identified public requirement broken.

**Public inputs:** brief/project_requirements.json: primary objective is to minimize LCC; metering capacity fraction is 1.0 of scenario flow, brief/network_semantics.md: active meter capacity must be at least scenario required flow, brief/equipment_catalog/metering_regulation.json: MTR120, MTR160, REG120, REG180 ratings and costs
**Submission inputs:** submission/deliverables/design.json: REG-1 model REG180; IMTR-1 and WMTR-1 model MTR160; LCC 106.0706 MBCU, submission/deliverables/design_report.md: REG180 retained instead of REG120 to avoid exact duty matching
**Scratch files:** None listed

### All-scenario allocation and delivery limit check

**Method:** For each mandatory scenario, summed well-group allocations and compared each per-well flow with 25 kg/s. Compared delivered pressure with required sink pressure, delivered temperature with -10 to 60 C, water with 50 mg/Sm3, free liquid with 1e-4, and active MTR160 meter capacity with scenario flow.

**Result:** All six scenario allocation sums match required flow within displayed rounding: 120, about 100, 75, 120, about 100, about 70 kg/s. Delivered pressures are requirement + 0.05 MPa in each scenario. Delivered temperatures are 40.0 C for injection, 13.215/17.971/49.94 C for withdrawal. Water is 40 mg/Sm3 injection and 35 mg/Sm3 withdrawal; free liquid is 0 injection and 5e-6 withdrawal. MTR160 capacity 160 kg/s exceeds every scenario flow. This check did not independently recompute every path pressure.

**Public inputs:** brief/operating_scenarios.json: required flows, hours, source/sink pressures, brief/project_requirements.json: well-group limit 25 kg/s, delivery water/free-liquid/temperature limits, metering requirement
**Submission inputs:** submission/deliverables/design.json: scenarios[].well_group_flows_kg_s, delivered values, operating_path, meter models
**Scratch files:** None listed

### Hydraulic sample: PL-WM-1i in WDR-HIGH

**Method:** Used mean pressure 6.120915 MPa and T=286.365 K. Computed Z=0.92936, viscosity about 1.046e-5 Pa*s, density about 50.35 kg/m3, area 0.11104 m2, velocity 21.47 m/s, Re about 3.89e7, Swamee-Jain f about 0.01246, and deltaP = f*(L/D)*rho*v^2/2.

**Result:** Calculated velocity 21.47 m/s matches submission and is below 25 m/s. Calculated pressure loss is about 0.02154 MPa, matching the submitted 0.02153 MPa to rounding. This supports the highest-velocity sampled gas pipe result.

**Public inputs:** brief/engineering_calculation_basis.md: gas property and Darcy-Weisbach fixed-point formulas, brief/gas_properties.json: MW 0.0182 kg/mol, gas property clamps, brief/piping_catalog.json: DN400 ID 0.376 m, CS-WET-100 roughness 4.5e-5 m, max gas velocity 25 m/s
**Submission inputs:** submission/deliverables/design.json: WDR-HIGH PL-WM-1i flow 120 kg/s, T 13.215 C, P_in 6.13168 MPa, P_out 6.11015 MPa, length 56.0 m, velocity 21.467 m/s
**Scratch files:** None listed

### Hydraulic samples: long injection return and critical well lateral

**Method:** For PL-IR, used DN700 ID 0.658 m, CS-DRY-160 roughness 1.5e-5 m, length 657 m, flow 120 kg/s, T 40 C, mean pressure about 8.5747 MPa. For PL-WG-06, used DN300 ID 0.282 m, CS-WET-160 roughness 4.5e-5 m, length 263.5 m, flow 20 kg/s, T 40 C, mean pressure about 8.555 MPa.

**Result:** PL-IR recomputation gives velocity about 5.53 m/s and pressure loss about 0.00931 MPa, matching submission 5.534 m/s and 0.009312 MPa. PL-WG-06 recomputation gives velocity about 5.03 m/s and pressure loss about 0.01004 MPa, matching submission 0.010033 MPa and confirming the critical INJ-LOW branch delivers about 8.55 MPa against the 8.5 MPa requirement.

**Public inputs:** brief/engineering_calculation_basis.md: gas hydraulic formulas, brief/piping_catalog.json: DN700/DN300 dimensions and class roughness values
**Submission inputs:** submission/deliverables/design.json: INJ-LOW PL-IR and PL-WG-06 operating path values
**Scratch files:** None listed

### Liquid drain rate and velocity under explicit proxy assumption

**Method:** For WDR-HIGH, each train gas flow is 40 kg/s and inlet liquid loading is 0.01 kg/kg, so removed liquid per separator is 40*0.01*0.9995=0.3998 kg/s. Under the submission's conservative displayed 0.4198 kg/s proxy and 1 MPa gas density near 8.27 kg/m3, DN200 area is pi*0.188^2/4=0.02776 m2, so velocity is 0.4198/(8.27*0.02776).

**Result:** Separator liquid flow is below SEP70 2.0 kg/s and DRN-S 0.8 kg/s capacities, and total WDR-HIGH liquid flow is about 1.1994 kg/s below the 10 kg/s outfall limit. Under the gas-density proxy assumption, DN200 drain velocity is about 1.83 m/s, consistent with submission's 1.837 m/s and below 3.0 m/s. Because the public brief gives no liquid density, this is not a decisive public-basis velocity pass.

**Public inputs:** brief/engineering_calculation_basis.md: separator liquid removal formula and liquid-drain velocity requirement, brief/piping_catalog.json: DN200 ID 0.188 m, maximum_liquid_drain_velocity_m_s 3.0, brief/equipment_catalog/separators.json: SEP70 removal efficiency 0.9995 and max liquid rate 2.0 kg/s, brief/equipment_catalog/drains.json: DRN-S capacity 0.8 kg/s
**Submission inputs:** submission/deliverables/design.json: liquid validation checks use 0.4198 kg/s and gas-density proxy at 1 MPa, submission/deliverables/validation_report.md: no liquid density is published; gas-density proxy used
**Scratch files:** None listed

## Findings

### F-001 — confirmed_violation / medium / confidence high

**Public basis:** brief/project_requirements.json states the primary objective is to minimize benchmark LCC among feasible designs. brief/network_semantics.md requires GRID-TIE active metering capacity at least equal to scenario required flow, and brief/equipment_catalog/metering_regulation.json publishes MTR120/MTR160 and REG120/REG180 capacities, ratings, ports, geometry, and costs.

**Claim or requirement:** The selected feasible design should not contain exact dominated catalog choices that increase LCC without satisfying any additional public requirement.

**Submission evidence:** submission/deliverables/design.json installs REG-1 as REG180 and IMTR-1/WMTR-1 as MTR160. submission/deliverables/design_report.md explicitly states REG180 was retained over REG120 so the regulator is not exactly duty-matched; it also uses MTR160 meters rated 160 kg/s for maximum scenario flow 120 kg/s.

**Independent check:** REG120 has 120 kg/s capacity, 16 MPa rating, same footprint, same port offsets, same JT coefficient, and lower CAPEX/maintenance than REG180. MTR120 has 120 kg/s capacity, 16 MPa rating, same footprint/ports, lower pressure drop, and lower CAPEX/maintenance than MTR160. The maximum mandatory scenario flow through either regulator or meter is 120 kg/s; N-1 retained flows are lower, and equality to a limit is allowed by the public numerical convention.

**Result:** Replacing REG180 with REG120 reduces LCC by 0.159273 MBCU. Replacing both MTR160 units with MTR120 reduces LCC by 0.238545 MBCU. The combined exact catalog substitution reduces LCC by about 0.397819 MBCU before any favorable meter pressure-drop energy effect, while preserving topology, geometry, ports, pressure rating, capacity against all mandatory scenarios, and metering compliance.

**Why it matters:** This is an exact lower-cost feasible alternative, so the submitted design is not minimal under the public LCC objective even without proving a global optimum.

### F-002 — unsupported_claim / medium / confidence high

**Public basis:** brief/project_requirements.json requires compression n-minus-one for applicable pressure-boost scenarios and withdrawal treatment n-minus-one for separator and dehydration categories, with one unit unavailable at a time and at least 70 percent retained flow. Delivery requirements remain applicable after outage.

**Claim or requirement:** The submission claims each required N-1 case is re-solved with one unit out and presents the reliability demonstration as satisfying any-one-unit outage requirements.

**Submission evidence:** submission/deliverables/validation_report.md says reliability checks re-solve each required N-1 case with one unit out. submission/deliverables/design.json lists 12 reliability rows. submission/ugs_design.py N1_CASES selects ICOMP-2 only for INJ-MID and INJ-HIGH, WCOMP-1 only for WDR-LOW, separator train A only for all withdrawal separator outages, and dehydration train B only for all withdrawal dehydration outages.

**Independent check:** Compared installed relevant units with listed failed units. Injection compression has ICOMP-1, ICOMP-2, and ICOMP-3; withdrawal compression has WCOMP-1 and WCOMP-2; treatment has SEP-A/B/C and DEH-A/B/C. The N1 list is exhaustive only for INJ-LOW compression. It omits other individual failed units for INJ-MID, INJ-HIGH, WDR-LOW, separator outage scenarios, and dehydration outage scenarios.

**Result:** The artifacts support representative outage simulations, not exhaustive any-one compressor/separator/dehydration-unit simulations. This does not by itself prove those omitted outage cases fail, but it does not support the claimed complete N-1 evidence.

**Why it matters:** The omitted cases are not purely identical in routing: branch lengths and diameters differ between trains and compressor branches. N-1 feasibility can depend on the failed unit's remaining active path, pressure losses, and minimum stable flow.

### F-003 — semantics_gap / low / confidence high

**Public basis:** brief/piping_catalog.json gives maximum_liquid_drain_velocity_m_s = 3.0 and brief/engineering_calculation_basis.md requires liquid-drain pipelines to remain within the velocity limit, but the public brief does not publish a liquid density or volumetric conversion basis for separated liquid.

**Claim or requirement:** Liquid-drain velocity compliance should be determined from public inputs.

**Submission evidence:** submission/deliverables/validation_report.md and design_report.md state that no liquid density is published and use a gas-density proxy at the 1 MPa drain-domain limit. design.json validation checks report DN200 drain velocity 1.837 m/s at 0.4198 kg/s under that proxy.

**Independent check:** Under the submission's explicit proxy, 0.4198 kg/s in DN200 with density about 8.27 kg/m3 gives about 1.83 m/s, consistent with the submitted 1.837 m/s and below 3.0 m/s. Separator mass rates, drain drum capacities, outfall capacity, and drain connectivity are independently checkable and pass in sampled checks.

**Result:** Drain velocity is unresolvable as a definitive public-basis PASS because the decisive liquid density input is absent. The proxy calculation is internally conservative-looking, but it is still an assumption rather than a published rule.

**Why it matters:** The benchmark asks for liquid drain velocity compliance; without density or an explicit proxy rule, independent evaluators cannot uniquely reproduce that part of the pass/fail decision.

### F-004 — unsupported_claim / low / confidence high

**Public basis:** brief/equipment_catalog/drains.json defines DRN-S capacity_kg_s = 0.8, and brief/engineering_calculation_basis.md states closed-drain capacity_kg_s is rated liquid flow.

**Claim or requirement:** Stated equipment capacities in the report should match the public catalog and machine-readable design.

**Submission evidence:** submission/deliverables/design_report.md equipment table states DRN-A, DRN-B, and DRN-C are DRN-S closed drain drums with 2.0 kg/s capacity. submission/deliverables/design.json lists the same DRN-S instances with capacity_kg_s = 0.8.

**Independent check:** Compared the report table with the public drains catalog and design.json. The 2.0 kg/s value corresponds to SEP70 maximum_liquid_rate_kg_s, not DRN-S capacity. The sampled maximum per-train separated liquid flow is about 0.3998 kg/s, so the correct 0.8 kg/s drain capacity is still adequate.

**Result:** The report's stated DRN-S capacity is unsupported and internally inconsistent with both the public catalog and design.json. This is a documentation consistency issue, not a demonstrated feasibility failure.

**Why it matters:** Closed-drain capacity is a required equipment limit; overstating it in the human-readable report can mislead reconstruction even though the machine-readable design and sampled calculation remain within the true limit.

## Limitations

- The environment was read-only. An attempted write to scratch/evaluator_calculations.md was rejected, so no evaluator-authored scratch files could be created; scratch_files arrays are therefore empty and calculations are reported inline.
- External interpreter execution such as python was blocked by local policy, so I did not run submission/ugs_validate.py or create independent executable scripts. The submission's automated PASS was inspected but not treated as independent evidence.
- Geometry, safety separation, maintenance envelopes, road exclusions, all same-level pipeline overlaps, and all pipeline hydraulic losses were sampled rather than exhaustively recomputed.
- Piping CAPEX was sampled through public cost formulas and submitted totals, but I did not independently sum every pipeline segment from raw JSON due the no-write/no-parser constraints.

Codex post-hoc findings are independent model-based engineering review findings, not formal ground truth.
