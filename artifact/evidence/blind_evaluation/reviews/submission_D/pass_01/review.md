# Anonymous engineering review: submission_D / pass_01

**Evaluation window:** 2026-09-27T13:47:12Z to 2026-09-27T13:58:54Z
**Evaluator process exit:** 0

Reviewed the frozen public brief and the supplied final submission only. The design is largely reconstructable and the sampled engineering calculations are internally coherent, but I found one confirmed LCC-objective issue: at least one installed HDR180 header is dominated by a cheaper HDR120 substitution that remains feasible under the published rules. I also recorded two public-semantics gaps for liquid density and unmodelled valve/isolation assumptions.

## Finding counts

- confirmed_violation: 1 (high 0, medium 1, low 0)
- unsupported_claim: 0
- suspected_risk: 0
- semantics_gap: 2
- observation: 0

## Areas checked

| Area | Coverage | Details |
|---|---|---|
| deliverable_completeness_reconstructability | full | Compared brief/final_delivery_contract.json with submission/DESIGN_REPORT.md, submission/README.md, submission/deliverables/design.json, diameters.json, layout.svg, verification.md, and checks.csv. Equipment tags/model IDs, port coordinates, routes, pipe classes/DNs, road geometry, scenario flows/setpoints/results, quantities, LCC, assumptions, and limitations are present and reconstructable from the final artifacts. |
| physical_topology_and_port_semantics | sampled | Checked all boundary connection counts from submission/checks.csv and sampled endpoint definitions in design.json for GRID-TIE, well groups, headers, compressors, meters, separator liquid drains, and outfall. Independently verified representative port direction semantics for injection meter/compressor/cooler, withdrawal meter/regulator, bidirectional headers/well groups, and drain_out/liquid_out routing. Did not independently re-enumerate every port-cardinality pair outside the sampled topology plus submitted check inventory. |
| operating_scenarios | sampled | Covered all six mandatory normal scenarios from design.json and verification.md. Independently checked scenario flow allocations, sink pressure/quality limits, metering sizing, and representative active paths for INJ-LOW, INJ-MID, INJ-HIGH, WDR-HIGH, WDR-MID, and WDR-LOW. Hydraulic marching and every per-pipe/equipment state were sampled, not exhaustively recomputed. |
| n_minus_1_reliability | sampled | Inspected the declared N-1 set: compressor outages for all compression-required scenarios including WDR-LOW, and separator/dehydration outages for all withdrawal scenarios. Independently checked representative retained-flow and remaining-capacity cases: INJ-LOW compressor outage and WDR-HIGH treatment outage. Exhaustive evidence relies partly on submitted scenario tables; symmetric units were not all independently recalculated. |
| equipment_limits | sampled | Independently checked selected compressor capacity/min-stable flow/ratio/temperature/power, cooler duty, separator/dehydrator capacity and feed quality, closed-drain capacity, meter capacity, regulator capacity, and header branch/capacity limits. Catalog pressure ratings and all equipment instances were inspected, but not every state point was independently recomputed. |
| hydraulic_calculations | sampled | Independently recomputed gas-property and pressure-loss samples for the high-flow long injection trunk P-113 and high-velocity small gas pipe P-103. Checked Z, viscosity, density, velocity, Reynolds number, friction factor, and fixed-point pressure loss against the submitted states. Did not recompute all pipelines or every eight-update convergence trace. |
| gas_quality_and_temperature | sampled | Checked all six normal scenario sink quality/temperature results against the public delivery limits and sampled N-1 delivery quality statements. Verified separator free-liquid reduction, dehydration outlet water, regulator JT cooling, compressor discharge temperature, and cooler outlet behavior for representative cases. Pipe dry/wet class eligibility was sampled. |
| liquid_drain | sampled | Checked separator removed-liquid formula, representative DRN-S capacity, outfall connection/flow count, DN150 liquid-drain class compatibility, and liquid velocity under the submission's stated 800 kg/m3 density assumption. Final velocity compliance is a semantics gap because the public brief does not publish liquid density. |
| geometry_layout_roads_maintenance | sampled | Sampled site containment, no-build zones, road widths/connectivity, road exclusion clearance, compressor heavy-maintenance/crane access geometry, separator road access, and close equipment separation pairs from the report and design coordinates. Did not perform a full computational polygon sweep independent of the submission checker. |
| pipeline_geometry | sampled | Sampled route endpoint matching and positive-length route geometry for injection, withdrawal, well-branch, boost, and drain lines. Checked representative site/exclusion interactions and same-level overlaps/crossings by inspection. Did not independently enumerate every segment pair or route-footprint intersection. |
| lifecycle_cost_arithmetic | sampled | Independently recomputed PVF, equipment CAPEX, annual maintenance, maintenance PV, annual energy cost/PV, civil/access subtotals from submitted quantities, and sampled piping CAPEX for representative pipes. Did not independently sum every individual pipe segment's piping CAPEX. |
| lcc_objective | sampled | Looked for obvious dominated equipment and route-cost choices. Found a confirmed lower-cost feasible alternative for at least HDR-DLV-01. Did not attempt or claim global optimality. |
| unsupported_assumptions | sampled | Reviewed submission assumptions and known limitations. Identified reliance on unmodelled isolation valves/path selection and liquid-density assumption; distinguished these from submission violations where the public brief is ambiguous or incomplete. |
| internal_consistency | sampled | Cross-checked report, README, design.json, verification.md, and checks.csv for equipment counts, scenario setpoints, N-1 claims, quantities, and LCC. Main numerical artifacts are consistent; noted the LCC-objective conflict where the report itself identifies cheaper HDR120 headers but rejects them for non-public margin/spare reasons. |

## Independent calculations

### Lifecycle-cost arithmetic from submitted quantities

**Method:** Recomputed PVF=(1-(1+0.08)^-20)/0.08, equipment capex and annual maintenance from catalog counts, civil subtotals from submitted quantities and public rates, then summed submitted piping CAPEX and independently recomputed energy/maintenance PV terms.

**Result:** PVF=9.818147407. Equipment CAPEX=29.39 MBCU. Annual maintenance=1.067 MBCU/a and PV=10.475963 MBCU. Civil/access=0.178425+0.003100+0.00158988+0.071006125=0.254121005 MBCU. Energy annual cost=40121.58632894494*0.00012=4.814590359 MBCU/a and PV=47.270357856 MBCU. Total=89.284594 MBCU, matching the submitted LCC when using the submitted piping CAPEX.

**Public inputs:** brief/economic_assumptions.json: discount_rate 0.08, project_life_years 20, energy_tariff 0.00012 MBCU/MWh, road/foundation/maintenance-area rates., brief/equipment_catalog/*.json: model capex and annual maintenance values., brief/piping_catalog.json: routing-level civil rates.
**Submission inputs:** submission/deliverables/design.json lifecycle_cost.quantities: equipment counts, road length 1189.5 m, footprint area 775.0 m2, maintenance area 1589.88 m2, level lengths ground 2012.375 m, rack_low 89.375 m, rack_high 131.5 m, buried 3586.875 m., submission/deliverables/design.json lifecycle_cost: annual_energy_mwh 40121.58632894494, piping_capex_mbcu 1.8941519125.
**Scratch files:** None listed

### High-flow long-pipe hydraulic sample: P-113 in INJ-LOW

**Method:** Used mean pressure about 8.52236 MPa and T=323.15 K. Recomputed Z, viscosity, density, area, velocity, Reynolds number, friction factor, and pressure drop for the fixed-point solution implied by the submitted endpoints.

**Result:** Z≈0.9413, mu≈1.143e-5 Pa*s, rho≈61.3 kg/m3, velocity≈7.83 m/s, Re≈2.37e7, Darcy f≈0.00973, deltaP≈0.02011 MPa. Submitted P-113 drop from 8.532415 to 8.512304 MPa is 0.020111 MPa, matching the independent sample.

**Public inputs:** brief/engineering_calculation_basis.md gas-property, Reynolds, Swamee-Jain, and fixed-point pressure-loss formulas., brief/gas_properties.json MW=0.0182 kg/mol, cp not used, Z and viscosity bounds., brief/piping_catalog.json DN600 internal diameter 0.564 m, CS-DRY-160 roughness 1.5e-5 m.
**Submission inputs:** submission/deliverables/design.json P-113 length 620.0 m, flow 120 kg/s in INJ-LOW, COOL-INJ-01 outlet pressure 8.532415 MPa, WH-01 inlet pressure 8.512304 MPa, T=50 C.
**Scratch files:** None listed

### Highest-velocity sampled gas pipe: P-103 in INJ-LOW compressor N-1

**Method:** Recomputed properties at mean pressure about 6.44368 MPa and T=298.15 K, then applied the published pipe pressure-loss equations.

**Result:** Z≈0.9321, mu≈1.076e-5 Pa*s, rho≈50.8 kg/m3, velocity≈19.2 m/s, Re≈1.70e7, Darcy f≈0.0117, deltaP≈0.0643 MPa. This matches the submitted drop of about 0.06427 MPa and remains below 25 m/s.

**Public inputs:** brief/engineering_calculation_basis.md gas hydraulic formulas., brief/piping_catalog.json DN200 internal diameter 0.188 m, CS-DRY-160 roughness 1.5e-5 m, max gas velocity 25 m/s.
**Submission inputs:** submission/deliverables/design.json INJ-LOW/N-1 CMP-INJ-01 out: P-103 flow 27 kg/s, upstream HDR-INJ-SUC-01 6.475818 MPa, CMP-INJ-03 suction 6.411547 MPa, length 111.25 m, T=25 C.
**Scratch files:** None listed

### Compressor and cooler thermal sample: INJ-HIGH normal

**Method:** Applied T_out=T_in*(1+(r^((k-1)/k)-1)/eta) and W=m cp T_in (r^a-1)/(eta*eta_driver), then cooler duty m cp |deltaT|.

**Result:** For the C60 sample, T_out≈94.1 C and power≈6.62 MW, matching submission values and below catalog limits. Cooler duty≈75*2450*(94.19-50)/1e6=8.12 MW and electric power≈0.284 MW, matching submission values and below COOL120's 32 MW duty limit.

**Public inputs:** brief/engineering_calculation_basis.md compressor temperature/power and cooler duty formulas., brief/gas_properties.json cp=2450 J/kg/K, k=1.3., brief/equipment_catalog/compressors.json C60 efficiency_proxy 0.80, driver_efficiency 0.96, max ratio 2.4, max discharge temperature 150 C, max power 32 MW., brief/equipment_catalog/thermal_equipment.json COOL120 maximum duty 32 MW, electric fraction 0.035.
**Submission inputs:** submission/deliverables/design.json INJ-HIGH: CMP-INJ-01 flow 37.5 kg/s, p_in about 6.476 MPa, p_out 13.546606 MPa, ratio 2.091649, T_in 25 C; COOL-INJ-01 flow 75 kg/s, t_in about 94.19 C, t_out 50 C.
**Scratch files:** None listed

### Liquid-drain capacity and velocity under explicit density assumption

**Method:** Computed removed liquid m_dot_liq=60*0.01*0.9995 and velocity v=m_dot_liq/(rho*pi*D^2/4) under the stated 800 kg/m3 assumption.

**Result:** Removed liquid per active train≈0.5997 kg/s, below SEP70 2.0 kg/s and DRN-S 0.8 kg/s. With rho=800 kg/m3 and D=0.141 m, velocity≈0.048 m/s, below 3 m/s. Because the public brief gives no liquid density, this supports only an assumption-bound result, not a definitive public PASS.

**Public inputs:** brief/engineering_calculation_basis.md separator removed-liquid formula and liquid velocity requirement., brief/equipment_catalog/separators.json SEP70 liquid_removal_efficiency 0.9995 and max liquid rate 2.0 kg/s., brief/equipment_catalog/drains.json DRN-S capacity 0.8 kg/s., brief/piping_catalog.json DN150 internal diameter 0.141 m and max liquid-drain velocity 3 m/s.
**Submission inputs:** submission/DESIGN_REPORT.md assumption: liquid density 800 kg/m3., submission/deliverables/design.json WDR-HIGH treatment N-1 train flow 60 kg/s per remaining separator/drain, source free liquid 0.01 kg/kg.
**Scratch files:** None listed

### Representative N-1 retained-flow and capacity checks

**Method:** Compared retained flow to required fractions and active unit flows to catalog capacity/min-stable limits.

**Result:** INJ-LOW compressor outage retained flow is 84/120=0.70; C60 at 57 kg/s is within 15-60 and C40 at 27 kg/s is within 10-40. WDR-HIGH treatment outage retains 120/120=1.0; each remaining SEP70/DEHY70 train at 60 kg/s is below 70 kg/s. Representative N-1 capacity checks are coherent.

**Public inputs:** brief/project_requirements.json requires at least 70% retained flow for compressor N-1 when sink pressure exceeds source pressure and for withdrawal separator/dehydration N-1., brief/equipment_catalog/compressors.json C60 capacity/min-stable 60/15 kg/s and C40 capacity/min-stable 40/10 kg/s., brief/equipment_catalog/separators.json and dehydration.json SEP70/DEHY70 capacity 70 kg/s.
**Submission inputs:** submission/deliverables/design.json INJ-LOW/N-1 CMP-INJ-01 out unit flows CMP-INJ-02 57 kg/s, CMP-INJ-03 27 kg/s, total 84 kg/s., submission/DESIGN_REPORT.md N-1 tables: WDR-HIGH treatment outage uses two remaining SEP70/DEHY70 trains at 60 kg/s each, total 120 kg/s.
**Scratch files:** None listed

## Findings

### F-001 — confirmed_violation / medium / confidence high

**Public basis:** brief/project_requirements.json states the primary objective is to minimize benchmark LCC among feasible designs. brief/equipment_catalog/headers.json defines HDR120 as 120 kg/s, 16 MPa, 10 branches, capex 0.25 MBCU, annual maintenance 0.012 MBCU/a; HDR180 is 180 kg/s, 16 MPa, 14 branches, capex 0.36 MBCU, annual maintenance 0.016 MBCU/a. brief/engineering_calculation_basis.md treats values at limits as acceptable within tolerance.

**Claim or requirement:** The submitted design installs five HDR180 headers and reports LCC 89.284594 MBCU, while also stating that smaller HDR120 headers were not adopted for spare-port/margin reasons.

**Submission evidence:** submission/deliverables/design.json lists HDR-DLV-01 as model_id HDR180 and lifecycle_cost.quantities counts HDR180: 5. submission/DESIGN_REPORT.md section 4.1 states replacing all five headers by HDR120 would lower LCC by about 0.59 MBCU but is rejected because WH-01 would have no spare port and headers would carry full station flow at the scenario extreme.

**Independent check:** A narrower exact alternative is to replace only HDR-DLV-01 with HDR120 at the same position/orientation. It has only three physical connections and max declared flow 120 kg/s, so HDR120's 10 branches and 120 kg/s capacity are sufficient; its pressure rating and footprint category are unchanged. Existing connected routes can be remapped to HDR120 gas_bidirectional ports with sub-metre endpoint adjustments and no new exclusion or separation issue. CAPEX saves 0.11 MBCU and maintenance PV saves (0.016-0.012)*9.818147=0.0393 MBCU. The worst additional header pressure drop is 0.00556 MPa at 120 kg/s upstream of a regulator in high/mid withdrawal, and about 0.0019 MPa at 70 kg/s in WDR-LOW, causing negligible compressor-energy penalty relative to the savings.

**Result:** The HDR-DLV-01 substitution remains feasible under the public capacity, pressure, branch-count, geometry, and delivery requirements and reduces LCC by roughly 0.14-0.15 MBCU. Therefore the submitted design is not minimized even by an obvious local catalog substitution; the larger header margin is not a published requirement or priced objective benefit.

**Why it matters:** The benchmark objective is LCC minimization, not robustness margin. Keeping a dominated higher-cost header materially invalidates an optimality claim even though it does not make the design infeasible.

### F-002 — semantics_gap / low / confidence high

**Public basis:** brief/engineering_calculation_basis.md requires liquid-drain pipelines to satisfy the published liquid velocity limit, and brief/piping_catalog.json gives the 3 m/s limit and DN150 internal diameter. The public brief does not publish a liquid density needed to convert kg/s to m/s.

**Claim or requirement:** The submission reports liquid-drain velocity compliance and states an assumed liquid density of 800 kg/m3.

**Submission evidence:** submission/DESIGN_REPORT.md section 11 lists 'Liquid density. No liquid density is published; the drain-velocity check assumes 800 kg/m3.' submission/deliverables/checks.csv reports DN150 drain velocity about 0.0480 m/s at 0.5997 kg/s under that assumption.

**Independent check:** Using the submission assumption, area=pi*0.141^2/4≈0.0156 m2 and v=0.5997/(800*area)≈0.048 m/s, well below 3 m/s. But without a public density, the benchmark has no unique mass-flow-to-velocity conversion.

**Result:** Drain capacity and liquid mass flow can be checked, but definitive liquid velocity PASS/FAIL is not uniquely determined from the public brief. Under the submission's explicit density assumption the drain velocity is comfortably below the limit.

**Why it matters:** This affects the evidentiary status of drain-velocity compliance, not the general reconstructability of the liquid-drain design.

### F-003 — semantics_gap / medium / confidence high

**Public basis:** brief/network_semantics.md allows cyclic physical networks and requires scenarios to satisfy port, mass-balance, pressure, capacity, temperature, and delivery rules, but the public catalog contains no valve models or valve costs. brief/project_requirements.json excludes the full control system but does not explicitly define whether process isolation/path selection is free.

**Claim or requirement:** The operating philosophy assumes inactive paths are isolated by valves that are outside the catalogued model.

**Submission evidence:** submission/DESIGN_REPORT.md section 11 states valve isolation is not modelled and names valves needed to close the injection custody meter, P-143, P-144, compressor branches, and selected WH-01 manifold branches in different scenarios.

**Independent check:** The active scenario paths sampled in design.json avoid reverse use of one-way ports and satisfy mass-flow logic when inactive branches are treated as isolated. However, no installed valve equipment, valve CAPEX, or valve pressure-loss model appears in design.json or the public catalog.

**Result:** If the public semantics allow free scenario path selection, the assumption is acceptable; if physical isolation must be represented or costed, the submitted topology and LCC omit required components. The brief is not decisive, so this is a semantics gap rather than a confirmed submission violation.

**Why it matters:** The design uses a shared cyclic network and shared compressor set; whether isolation is free directly affects reconstructability of active paths and potentially LCC.

## Limitations

- No evaluator-authored scratch files were created because the active filesystem sandbox was read-only; all independent reproductions were performed in-session from public brief values and final submission data, with scratch_files recorded as empty.
- I did not modify, regenerate, or write into submission/. I also did not inspect parent directories or external/non-public sources.
- Submission-authored checks and reports were read as context, but PASS judgments above rely on independent spot calculations where stated; the 6678-check PASS was not treated as independent evidence.
- Geometry, pipeline-overlap, and all-scenario hydraulic checks were sampled rather than exhaustively recomputed with an independent geometry engine.
- I did not prove a global optimum; the LCC-objective finding identifies one feasible lower-cost local alternative only.

Codex post-hoc findings are independent model-based engineering review findings, not formal ground truth.
