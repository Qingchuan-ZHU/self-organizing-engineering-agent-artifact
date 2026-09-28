# Anonymous engineering review: submission_A / pass_01

**Evaluation window:** 2026-09-28T02:02:20Z to 2026-09-28T02:14:12Z
**Evaluator process exit:** 0

Submission is broadly reconstructable and most sampled calculations are internally consistent, but I found one confirmed LCC-objective issue: the submitted REG120 pressure-control station is explicitly nonessential for public feasibility and can be removed with an estimated LCC reduction of about 0.52 MBCU. Liquid-drain velocity cannot be definitively judged because the public brief does not specify liquid density.

## Finding counts

- confirmed_violation: 1 (high 0, medium 1, low 0)
- unsupported_claim: 1
- suspected_risk: 0
- semantics_gap: 1
- observation: 0

## Areas checked

| Area | Coverage | Details |
|---|---|---|
| deliverable_completeness_reconstructability | sampled | Checked final contract against README and deliverables: equipment, topology, pipelines, site/roads, operating_plan, quantities, lifecycle_cost, verification, and report are present and mostly reconstructable. Did not manually enumerate every route segment or every operating element. |
| physical_topology_and_port_semantics | sampled | Checked topology and representative equipment ports. GRID-TIE has 2/2 gas connections, each well group has one connection, outfall has 3/8 drain connections, separator liquid outlets route to closed drains, and sampled gas/liquid port directions are compatible. Full 105-port checker result was inspected but not treated as independent proof. |
| operating_scenarios | sampled | Covered all six mandatory scenarios at sink-summary level for flow allocation, sink pressure, temperature, water, free liquid, and metering path. Independently checked selected active paths and flow splits, not every element-state balance. |
| n_minus_1_reliability | sampled | Confirmed the submission includes 30 outage cases. Sampled INJ-LOW-N1-CMP-A, WDR-HIGH-N1-SEP-A, and WDR-LOW-N1-CMP-A; failed units are absent from active paths and retained flow is 100% in those samples. Did not exhaustively re-simulate all symmetric outages. |
| equipment_limits | sampled | Sampled compressor capacity/minimum flow/ratio/temperature/power, separator/dehydrator/drain capacity, meter capacity, cooler duty, and pipe pressure/velocity margins using operating_plan values and public catalogues. |
| hydraulic_calculations | sampled | Independently recomputed P01 as a high-flow dry gas line and P20 as the highest-velocity/small-DN sampled wet gas line. Checked Z, viscosity, density, velocity, Reynolds/friction factor, pressure loss, and convergence count for those samples. Did not recompute all 656 pipe-case checks. |
| gas_quality_and_temperature | sampled | Checked all six mandatory scenario sink water/free-liquid/temperature summaries against public limits. Sampled dry/wet class eligibility around dehydration outlet and wet withdrawal feeds. Did not verify every pipe in every outage. |
| liquid_drain | sampled | Recomputed separator liquid removal for WDR-HIGH N-1 and checked SEP70, DRN-S, and outfall capacity. Drain velocity remains a semantics gap because public liquid density is absent. |
| geometry_layout_roads_maintenance | sampled | Inspected site boundary, no-build zones, roads, footprints, maintenance envelopes, and reported road/crane access. Sampled road connectivity and clearances; did not independently recompute all footprint separations. |
| pipeline_geometry | sampled | Inspected pipeline endpoint matching, positive segment lengths, installation levels, and representative road-crossing buried segments. Did not exhaustively recompute site containment, exclusions, or 6684 same-level overlap pairs. |
| lifecycle_cost_arithmetic | sampled | Independently recomputed PVF, equipment CAPEX, annual maintenance/PV, civil/access components, selected piping CAPEX and civil costs, annual energy PV, and total LCC. Did not recalc every pipe item independently. |
| lcc_objective | sampled | Did not prove global optimum. Identified one specific lower-cost feasible alternative: remove the nonessential REG120 and replace P31/P32 with one direct dry-gas pipe to MTR-B. |
| unsupported_assumptions | sampled | Found reliance on an extra pressure-control philosophy not required by the public brief, and an unavoidable liquid-density assumption for drain velocity. |
| internal_consistency | sampled | README, case_summary, verification, quantities, operating_plan, and lifecycle_cost agree on 20 equipment items, 36 pipelines, 30 N-1 cases, 12158 checks, annual energy, and LCC. Found one report wording inconsistency about pipe-class wet compatibility. |

## Independent calculations

### Lifecycle-cost arithmetic sample

**Method:** PVF=(1-(1.08)^-20)/0.08. Summed selected model costs and maintenance; sampled P01/P02/P34/P37 pipe and civil costs; recomputed energy PV and total LCC.

**Result:** PVF 9.818147; equipment CAPEX 30.49 MBCU; annual maintenance 1.075 MBCU/y and PV 10.5545; civil/access 0.170986; energy PV 40832.644384*0.00012*9.818147=48.1081; total 91.17408 MBCU, matching submission.

**Public inputs:** brief/economic_assumptions.json: discount_rate 0.08, project_life_years 20, energy_tariff 0.00012, road/foundation/maintenance rates, brief/piping_catalog.json: DN and class/routing cost multipliers, brief/equipment_catalog/*.json: selected model capex and annual maintenance
**Submission inputs:** submission/deliverables/lifecycle_cost.json, submission/deliverables/quantities.json, submission/deliverables/equipment.json
**Scratch files:** None listed

### P01 high-flow dry-gas hydraulic sample

**Method:** Used Pmean about 6.498 MPa and T=298.15 K to compute Z, mu, rho, velocity, Re, Swamee-Jain f, and Darcy pressure loss.

**Result:** Z about 0.9323, mu about 1.076e-5 Pa s, rho about 51.2 kg/m3, velocity about 9.39 m/s, Re about 2.5e7, f about 0.0097, dp about 0.00392 MPa. This matches submission P01 dp 0.0039216 MPa and velocity 9.3889 m/s with 2 updates.

**Public inputs:** brief/engineering_calculation_basis.md gas-property and Darcy/Swamee-Jain formulas, brief/gas_properties.json MW 0.0182, Z/mu bounds, brief/piping_catalog.json DN600 ID 0.564 m, CS-DRY-160 roughness 1.5e-5 m
**Submission inputs:** submission/deliverables/operating_plan.json INJ-LOW P01: 120 kg/s, 6.5 MPa, 25 C, length 101.027756 m, submission/deliverables/pipelines.json P01 DN600 CS-DRY-160
**Scratch files:** None listed

### P20 highest-velocity small-DN hydraulic sample

**Method:** Computed wet-gas properties at Pmean about 4.475 MPa and 293.15 K, then velocity and Darcy pressure loss.

**Result:** Z about 0.9247, mu about 1.059e-5 Pa s, rho about 36.1 kg/m3, velocity about 22.34 m/s, f about 0.0137, dp about 0.01736 MPa. This agrees with submission velocity 22.3747 m/s and dp 0.01733 MPa, below 25 m/s.

**Public inputs:** brief/engineering_calculation_basis.md gas-property and pipe-loss formulas, brief/piping_catalog.json DN250 ID 0.235 m, CS-WET-160 roughness 4.5e-5 m
**Submission inputs:** submission/deliverables/operating_plan.json WDR-LOW N-1 sample P20: 35 kg/s, p_in 4.483531 MPa, p_out 4.466198 MPa, 20 C, length 33 m
**Scratch files:** None listed

### WDR-HIGH N-1 liquid drain load

**Method:** Removed liquid per active separator = 60*0.01*0.9995; total active liquid flow = 2 times that in the sampled N-1 case.

**Result:** 0.5997 kg/s per active separator/drain, below SEP70 2.0 and DRN-S 0.8; total 1.1994 kg/s below outfall 10 kg/s.

**Public inputs:** brief/operating_scenarios.json: WDR-HIGH flow 120 kg/s and free-liquid loading 0.01, brief/equipment_catalog/separators.json: SEP70 removal efficiency 0.9995 and liquid limit 2.0 kg/s, brief/equipment_catalog/drains.json: DRN-S capacity 0.8 kg/s, brief/site.json: outfall limit 10 kg/s
**Submission inputs:** submission/deliverables/operating_plan.json WDR-HIGH-N1-SEP-A uses two remaining treatment trains at 60 kg/s each, submission/deliverables/topology.json separator drains P34-P39 to outfall
**Scratch files:** None listed

### Lower-cost regulator-removal alternative

**Method:** Remove REG and P31/P32; add one direct DN350 CS-DRY-160 ground pipe from H-DIS.branch_05 to MTR-B.gas_in following the existing path through the removed regulator location, length about 201.5 m. Estimated WDR-LOW pressure by scaling current P31 loss over the longer DN350 line.

**Result:** Regulator removal saves 0.34+0.018*9.818147=0.5167 MBCU. Direct DN350 pipe costs about 201.5*0.00026*1.15=0.06025 MBCU versus existing P31+P32 0.06511, adding about 0.00486 MBCU further savings. WDR-LOW GRID-TIE pressure remains about 6.20 MPa after scaled pipe, meter, and P33 losses, above 6.0 MPa; WDR-MID/HIGH remain higher pressure and below 16 MPa. Estimated net LCC reduction about 0.522 MBCU.

**Public inputs:** brief/project_requirements.json primary objective minimizes LCC among feasible designs, brief/network_semantics.md gas_bidirectional may feed gas_in, brief/piping_catalog.json DN350 dry-gas cost and 16 MPa class rating, brief/economic_assumptions.json PVF inputs
**Submission inputs:** submission/deliverables/design_report.md states REG is not needed for public feasibility and is kept as operating philosophy, submission/deliverables/lifecycle_cost.json REG capex 0.34, annual maintenance 0.018, P31/P32 capex 0.065110125, submission/deliverables/operating_plan.json WDR-LOW H-DIS/P31/P32/P33 pressures
**Scratch files:** None listed

## Findings

### LCC-REG-001 — confirmed_violation / medium / confidence high

**Public basis:** brief/project_requirements.json states the primary objective is to minimize benchmark LCC among feasible designs. brief/economic_assumptions.json and brief/engineering_calculation_basis.md define the LCC arithmetic. Full pressure-control philosophy beyond published limits is not a scored requirement.

**Claim or requirement:** The final design should not retain non-required equipment that increases LCC while preserving all public feasibility requirements.

**Submission evidence:** submission/deliverables/design_report.md says the REG120 is not needed for feasibility and is kept as a deliberate operating-philosophy choice. submission/deliverables/equipment.json installs REG; submission/deliverables/lifecycle_cost.json includes REG capex 0.34 MBCU and annual maintenance 0.018 MBCU/y.

**Independent check:** A direct H-DIS.branch_05 to MTR-B.gas_in connection is port-compatible. Replacing REG plus P31/P32 with one DN350 CS-DRY-160 ground pipe about 201.5 m long preserves metering, dry gas quality, 16 MPa pressure rating, and WDR-LOW sink pressure margin by scaled pressure-loss check. Removing REG also removes its footprint and maintenance burden.

**Result:** Estimated LCC decreases by about 0.522 MBCU: 0.5167 MBCU from removed REG capex/maintenance PV plus about 0.0049 MBCU lower pipe capex. This is a specific lower-cost feasible alternative, so the submitted design is not LCC-minimal under the public objective.

**Why it matters:** The benchmark objective is LCC minimization among feasible designs; retaining a non-required pressure-control station materially inflates the reported objective value.

### LIQ-DENS-001 — semantics_gap / low / confidence high

**Public basis:** brief/engineering_calculation_basis.md imposes a maximum liquid-drain velocity, but the public brief does not publish a liquid density or a liquid volumetric-flow convention for converting kg/s to m/s.

**Claim or requirement:** Liquid-drain pipelines must remain within the published liquid velocity limit.

**Submission evidence:** submission/deliverables/design_report.md reports drain velocities over an assumed density band and notes the benchmark publishes no liquid density. submission/deliverables/operating_plan.json reports design_liquid_flow_kg_s 0.5997 for drain checks.

**Independent check:** For DN200 ID 0.188 m, area is about 0.0278 m2. At 0.5997 kg/s, velocity is 0.5997/(rho*0.0278). It is about 0.0216 m/s at rho=1000 kg/m3 and about 2.63 m/s at rho=8.2 kg/m3; the 3 m/s threshold corresponds to rho about 7.2 kg/m3.

**Result:** Drain velocity compliance cannot be uniquely determined from public inputs. Capacity and outfall-flow checks pass, but velocity PASS depends on an assumed liquid density.

**Why it matters:** This prevents a definitive independent PASS/FAIL judgment for the liquid-drain velocity requirement and should not be treated as a submission violation.

### DOC-PIPECLASS-001 — unsupported_claim / low / confidence high

**Public basis:** brief/piping_catalog.json marks CS-DRY-160 as dry_gas_compatible true and wet_gas_compatible false.

**Claim or requirement:** Report statements about pipe-class compatibility should match the public catalogue and the delivered pipeline data.

**Submission evidence:** submission/deliverables/design_report.md section 6 states that all gas classes are both wet- and dry-compatible, while submission/deliverables/pipelines.json correctly records CS-DRY-160 wet_gas_compatible=false on dry gas lines.

**Independent check:** Compared the report text, pipelines.json class flags, and public piping catalog. The installed dry-gas lines appear to be used only after the stream is dry in sampled cases, so this is a documentation inconsistency rather than a confirmed feasibility defect.

**Result:** The broad report claim is unsupported by the catalogue; the machine-readable pipeline fields are more accurate.

**Why it matters:** It can mislead reconstruction of wet/dry pipe-class eligibility even though sampled operating cases did not show an actual class misuse.

## Limitations

- The environment was read-only and rejected creating scratch/evaluator_notes.txt, so no evaluator-authored scratch files could be produced; independent calculations are documented inline above.
- I did not execute submission scripts because reproduction would write deliverables and scratch/ was not writable in this environment.
- Geometry, overlap, and all operating-case checks were not exhaustively recomputed; several conclusions rely on targeted independent samples plus inspection of final artifacts.
- The LCC objective review does not prove a global optimum; it identifies one specific lower-cost feasible alternative.

Codex post-hoc findings are independent model-based engineering review findings, not formal ground truth.
