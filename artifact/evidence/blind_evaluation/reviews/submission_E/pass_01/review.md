# Anonymous engineering review: submission_E / pass_01

**Evaluation window:** 2026-09-27T15:02:15Z to 2026-09-27T15:17:27Z
**Evaluator process exit:** 0

The design is mostly reconstructable and the six normal operating scenarios are internally coherent under sampled independent checks. Main exceptions: the submitted N-1 evidence is capacity-only rather than actual outage simulation, and a specific lower-cost feasible header substitution shows the submitted LCC is not minimal. Liquid-drain velocity also depends on an unpublished density assumption.

## Finding counts

- confirmed_violation: 1 (high 0, medium 1, low 0)
- unsupported_claim: 2
- suspected_risk: 0
- semantics_gap: 1
- observation: 0

## Areas checked

| Area | Coverage | Details |
|---|---|---|
| deliverable_completeness_reconstructability | full | Compared final_delivery_contract.json against submission artifacts. Equipment instances, catalog IDs, ports, positions, orientations, pipelines, diameters/classes, route levels, scenario flows/setpoints, quantities, LCC, assumptions, and limitations are present. N-1 outage operating cases are not reconstructable beyond aggregate capacity statements. |
| physical_topology_and_port_semantics | full | Reviewed declared endpoints for all pipelines, port types, header branch use, external interface counts, well-group and GRID-TIE counts, drain routes, and one-way gas_out usage. Declared normal topology is compatible; GRID-TIE has 2 connections, each well group has 1, outfall has 3, and separator liquid_out ports are drained. |
| operating_scenarios | full | Checked all six mandatory scenarios in scenarios_operating.json for allocation sums, well-group limits, meter capacity, active path consistency, delivery pressure, delivery temperature, water, and free liquid. Hydraulic details were independently sampled rather than fully recomputed for every active pipe. |
| n_minus_1_reliability | sampled | Inspected report, check_summary, scenarios, pipelines, and source implementation. Aggregate installed capacities meet retained-flow thresholds, but the submitted N-1 checker does not simulate each failed compressor/separator/dehydration unit and no outage scenario records are supplied. |
| equipment_limits | sampled | Checked normal-scenario compressor flow, minimum stable flow, ratio, discharge temperature, power, and selected separator/dehydrator/meter/regulator/cooler/drain capacities. No normal-case limit violation found in the sampled checks. |
| hydraulic_calculations | sampled | Recomputed representative gas-property and pipe-loss cases for the highest-flow pipe, highest-velocity/small-DN pipe, a long pipe, a critical grid-delivery pipe, and a well lateral using the public fixed-point formula. Did not recompute every pipe in every scenario. |
| gas_quality_and_temperature | sampled | Checked all six delivered water/free-liquid/temperature values against public limits and sampled state changes through separator, dehydration, cooler, and regulator. Wet/dry class eligibility was reviewed from active paths and pipe classes. |
| liquid_drain | sampled | Checked separator liquid mass flow, DRN-S capacity, outfall flow/counts, and liquid-compatible pipe class. Drain velocity cannot be definitively judged because the public brief gives a velocity limit but no liquid density. |
| geometry_layout_roads_maintenance | sampled | Sampled site containment, exclusion-zone avoidance, separations, road widths/connectivity, and road/crane access distances from coordinates. Did not independently compute every polygon/envelope intersection. |
| pipeline_geometry | sampled | Sampled endpoint matching, route lengths, positive lengths, containment, no-build-zone avoidance, and same-level overlap risk. Did not perform exhaustive segment intersection enumeration because execution/scratch writing was blocked. |
| lifecycle_cost_arithmetic | sampled | Independently recomputed PVF, equipment CAPEX, road/foundation/maintenance/pipeline civil components, annual maintenance, energy PV from scenario energy detail, and total LCC. Piping CAPEX was formula-checked and accepted against submitted aggregate rather than independently summing every line by script. |
| lcc_objective | sampled | Did not attempt global optimization. Checked for obvious dominated equipment and found one exact lower-cost feasible substitution for header Y. |
| unsupported_assumptions | sampled | Identified reliance on an assumed liquid density for drain velocity and active-path selection in a looped network without catalogued valves. The liquid density issue is a public semantics gap; active-path selection is noted but not judged a violation because the public model permits loops and does not catalog valves. |
| internal_consistency | sampled | Cross-checked report, JSON, and source. Found consistency gaps in N-1 evidence and reproduction command wording; normal scenario report values generally match JSON quantities. |

## Independent calculations

### Normal-scenario flow, metering, and delivery checks

**Method:** For each mandatory scenario, summed well allocations, compared each allocation with 25 kg/s well limit, checked active meter model MTR120 against scenario flow, and compared delivered pressure, temperature, water, and free-liquid values with public limits.

**Result:** All six scenarios were present. Allocation sums matched required flow within rounding: 120, about 100.000002, 75, 120, about 100.000002, and about 70.000002 kg/s. Maximum well allocation was 20 kg/s. Delivered pressures met required sink pressures, temperatures were 13.3 to 55.0 C, water was 35 or 40 mg/Sm3, and free liquid was 0 or 5e-6, all within public delivery limits. MTR120 capacity equals or exceeds each scenario flow up to 120 kg/s.

**Public inputs:** brief/operating_scenarios.json required flows, pressures, hours, and well limits, brief/project_requirements.json delivery water/free-liquid/temperature and metering requirements, brief/site.json external interface limits
**Submission inputs:** submission/design/scenarios_operating.json, submission/design/equipment_instances.json
**Scratch files:** None listed

### Topology, port semantics, and connection counts

**Method:** Manually traced all declared pipeline endpoints against catalog/interface port types and counted connections on GRID-TIE, well groups, outfall, header branches, ordinary equipment ports, and separator drain ports.

**Result:** No incompatible declared endpoint pair was found. GRID-TIE uses 2 of 2 allowed connections; each well group uses 1 connection; LIQUID-DRAIN-OUTFALL uses 3 of 8; WH/WP/X/DH/Y use 7/5/8/5/3 HDR180 branch connections respectively, all below 14. Each separator liquid_out connects to a DRN-S drain_in and each drain_out connects to the outfall.

**Public inputs:** brief/network_semantics.md port compatibility and cardinality rules, brief/site.json external interface connection limits, brief/equipment_catalog/*.json header branch counts and port types
**Submission inputs:** submission/design/equipment_instances.json, submission/design/pipelines.json
**Scratch files:** None listed

### N-1 aggregate capacity and evidence check

**Method:** Computed installed capacity after loss of the largest unit and inspected whether the submission provided or executed per-failed-unit outage scenarios.

**Result:** Compression capacity is 60+60+40 = 160 kg/s; worst one-compressor outage leaves 100 kg/s, above the largest retained-flow threshold of 84 kg/s. Separator and dehydration capacity are each 3*70 = 210 kg/s; worst one-unit outage leaves 140 kg/s, also above 84 kg/s. However, submission/src/ugssynth/engine.py check_n_minus_one only compares aggregate capacities, and submission/design/pipelines.json reports PX-CMP3 and PCMP-DH3 max velocity and pressure as 0.0, showing the standby C40 path is not represented in normal scenario hydraulic results.

**Public inputs:** brief/project_requirements.json retained fraction 0.7 for compression and withdrawal treatment, brief/equipment_catalog/compressors.json capacities and minimum stable flows, brief/equipment_catalog/separators.json and dehydration.json capacities
**Submission inputs:** submission/design/check_summary.json, submission/design/scenarios_operating.json, submission/design/pipelines.json, submission/src/ugssynth/engine.py
**Scratch files:** None listed

### Sampled gas-pipeline hydraulic recomputations

**Method:** Recomputed Z, viscosity, density, velocity, Reynolds number, Swamee-Jain friction factor, and pressure drop for selected representative pipes using final route lengths and scenario flows.

**Result:** Samples were consistent with submitted magnitudes and public limits: PGRID-INJ in INJ-LOW at 120 kg/s gave Z about 0.932, rho about 51.2 kg/m3, v about 6.90 m/s, Re about 2.16e7, f about 0.0113, dp about 0.0023 MPa. PWP-CLR long pipe gave v about 7.8 m/s and dp about 0.010 MPa. PSEP-DHY3 in WDR-LOW, the highest-velocity DN200 sample, gave v about 23.9 m/s, Re about 1.5e7, f about 0.0143, dp about 0.085 MPa, below the 25 m/s gas limit. PMTR-GRID in WDR-LOW gave v about 11.54 m/s and dp about 0.0043 MPa. PWG6 in INJ-LOW gave v about 11.8 m/s and dp about 0.080 MPa.

**Public inputs:** brief/engineering_calculation_basis.md gas-property, Darcy friction, and eight-update fixed-point pressure-loss formulas, brief/gas_properties.json, brief/piping_catalog.json
**Submission inputs:** submission/design/pipelines.json lengths, diameters, classes, submission/design/scenarios_operating.json pipe flows and relevant pressures/temperatures
**Scratch files:** None listed

### Equipment-limit spot checks

**Method:** Recomputed compressor ratios, discharge temperatures, and powers from public formulas for critical normal cases and compared selected equipment flows against catalog capacities.

**Result:** INJ-HIGH C60 compressors run at 37.5 kg/s each, ratio about 2.096, outlet temperature about 94.4 C, and power about 6.64 MW, within C60 limits of 60 kg/s, ratio 2.4, 150 C, and 32 MW. WDR-LOW C60 compressors run at 35 kg/s, ratio about 1.445, outlet temperature about 52.5 C, and power about 2.90 MW. WDR-HIGH treatment trains carry 40 kg/s each, below SEP70/DEHY70 70 kg/s capacity; per-separator liquid removal is about 0.3998 kg/s, below the 2.0 kg/s separator liquid limit and 0.8 kg/s DRN-S capacity.

**Public inputs:** brief/equipment_catalog/compressors.json compressor capacity, min flow, ratio, pressure, temperature, and power limits, brief/equipment_catalog/separators.json, dehydration.json, thermal_equipment.json, metering_regulation.json, drains.json
**Submission inputs:** submission/design/scenarios_operating.json, submission/design/equipment_instances.json
**Scratch files:** None listed

### Liquid-drain mass and assumed-density velocity

**Method:** Computed removed liquid as gas flow times 0.01 loading times 0.9995 removal efficiency, split equally over three separators. Converted mass flow to velocity only under the submission's explicit 1000 kg/m3 density assumption.

**Result:** WDR-HIGH total removed liquid is 1.1994 kg/s, or 0.3998 kg/s per train; WDR-MID is 0.9995 total and WDR-LOW is 0.69965 total. These are below separator, drain, and 10 kg/s outfall limits. With density 1000 kg/m3 and DN150 ID 0.141 m, WDR-HIGH drain velocity is about 0.0256 m/s, far below 3 m/s, but the public brief does not define density, so velocity PASS is not uniquely reproducible.

**Public inputs:** brief/engineering_calculation_basis.md separator liquid removal formula, brief/piping_catalog.json DN150 internal diameter and 3 m/s liquid-drain velocity limit, brief/equipment_catalog/drains.json and separators.json capacities, brief/site.json outfall limit
**Submission inputs:** submission/design/scenarios_operating.json, submission/design/pipelines.json
**Scratch files:** None listed

### Lifecycle-cost arithmetic

**Method:** Recomputed PVF and major LCC components from public formulas and final quantities; manually cross-checked civil subcomponents and equipment totals.

**Result:** PVF = 9.818147. Equipment CAPEX sum is 30.05 MBCU and annual maintenance is 1.102 MBCU/year. Civil/access recomputes as road 1307 m * 0.00015 = 0.19605, foundation 820 m2 * 4e-6 = 0.00328, maintenance 1661.88 m2 * 1e-6 = 0.001662, buried-pipeline civil about 0.016424, total 0.217416 MBCU. Scenario energy sums to 40256.721486 MWh/year; energy PV is about 47.429571 MBCU. Maintenance PV is about 10.819598 MBCU. These reproduce submitted LCC 90.283771 MBCU within rounding when using submitted piping CAPEX 1.767185 MBCU.

**Public inputs:** brief/economic_assumptions.json rates, tariff, discount rate, project life, brief/piping_catalog.json pipe and routing multipliers, brief/equipment_catalog/*.json capex and maintenance
**Submission inputs:** submission/design/equipment_instances.json, submission/design/pipelines.json, submission/design/layout_roads.json, submission/design/quantities_lcc.json
**Scratch files:** None listed

### Lower-cost Y-header alternative

**Method:** Defined an exact alternative replacing only Y from HDR180 to HDR120 at the same center/orientation, remapping its three used branches to HDR120 branch_01 to branch_03 and adjusting the three connected pipe endpoints. Compared capacity, branch count, pressure-drop margins, footprint, safety, and LCC delta.

**Result:** HDR120 has capacity 120 kg/s and 10 branches; Y uses 3 branches and sees max normal flow 120 kg/s. Same footprint/category preserves layout and safety. Equipment CAPEX saves 0.11 MBCU and maintenance PV saves 0.004*9.818147 = 0.03927 MBCU. Adjusting three endpoint lengths changes pipe cost by only about +0.00019 MBCU. Header pressure drop increase is 0.00556 MPa at 120 kg/s and 0.00189 MPa at WDR-LOW 70 kg/s; WDR-LOW regulator inlet margin remains positive, about 0.00328 MPa after this change, while WDR-HIGH/MID have much larger regulator margins. Net LCC reduction is about 0.149 MBCU with no identified requirement loss.

**Public inputs:** brief/project_requirements.json primary objective, brief/equipment_catalog/headers.json HDR180 and HDR120 capacity, branch limits, capex, maintenance, footprint, safety category, pressure-drop formula, brief/economic_assumptions.json PVF inputs
**Submission inputs:** submission/design/equipment_instances.json Y header record, submission/design/pipelines.json PX-Y, PCLR2-Y, PY-REG, submission/design/scenarios_operating.json regulator margins
**Scratch files:** None listed

## Findings

### F-001 — unsupported_claim / medium / confidence high

**Public basis:** brief/project_requirements.json requires retained deliverability after any one compressor outage for compression cases and after any one separator or dehydration-unit outage for withdrawal; brief/engineering_calculation_basis.md states delivery limits remain applicable after outage.

**Claim or requirement:** The report and check_summary claim N-1 reliability is checked with no N-1 issues.

**Submission evidence:** submission/report/design_report.md states any-one compressor/separator/dehydration reliability; submission/design/check_summary.json has n_minus_one_issues = []; submission/src/ugssynth/engine.py check_n_minus_one computes only total capacity minus largest capacity; submission/design/scenarios_operating.json contains no outage cases; submission/design/pipelines.json gives PX-CMP3 and PCMP-DH3 max_velocity_m_s and max_pressure_mpa as 0.0.

**Independent check:** I computed aggregate capacities and inspected the N-1 implementation and final scenario artifacts. Aggregate retained capacities pass thresholds, but there is no per-failed-unit hydraulic path, failed-unit removal from active path, minimum-stable-flow, delivery pressure/quality, or pipe/equipment limit simulation.

**Result:** The N-1 PASS is not supported by the submitted evidence. This does not by itself prove the physical design is infeasible, but it fails to substantiate a mandatory reliability claim.

**Why it matters:** N-1 reliability depends on the actual outage path and operating point, not just installed nameplate capacity; standby compressor and remaining treatment paths can introduce different pressure losses, velocities, and minimum-flow constraints.

### F-002 — confirmed_violation / medium / confidence high

**Public basis:** brief/project_requirements.json states the primary objective is to minimize benchmark LCC among feasible designs; brief/engineering_calculation_basis.md defines LCC arithmetic.

**Claim or requirement:** The submitted design is presented as the LCC-minimized feasible design with LCC 90.283771 MBCU.

**Submission evidence:** submission/design/equipment_instances.json installs Y as HDR180; submission/report/design_report.md lists Y HDR180 and states the design objective is minimized LCC.

**Independent check:** Exact alternative: replace only Y with HDR120 at the same position/orientation, remap the three used Y ports to HDR120 branch_01 through branch_03, and adjust PX-Y, PCLR2-Y, and PY-REG endpoints. HDR120 capacity is 120 kg/s, branch limit 10, same footprint/safety category, and Y uses 3 branches with max normal flow 120 kg/s. Equipment plus maintenance PV saving is about 0.14927 MBCU; pipe endpoint length change costs about 0.00019 MBCU. Extra Y pressure drop is 0.00556 MPa at 120 kg/s and 0.00189 MPa at WDR-LOW 70 kg/s; WDR-LOW regulator margin remains positive at about 0.00328 MPa, and WDR-HIGH/MID margins remain much larger.

**Result:** A feasible lower-LCC alternative reduces LCC by about 0.149 MBCU, so the submitted design is not minimal under the public LCC objective.

**Why it matters:** The benchmark objective is cost minimization among feasible designs. A dominated installed header directly invalidates the claimed cost optimum, even though the delta is modest relative to total LCC.

### F-003 — semantics_gap / low / confidence high

**Public basis:** brief/piping_catalog.json provides a maximum liquid-drain velocity of 3 m/s, but the public brief does not provide liquid density; brief/engineering_calculation_basis.md gives separator liquid mass flow in kg/s.

**Claim or requirement:** The submission reports liquid drain velocities and assumes 1000 kg/m3 density.

**Submission evidence:** submission/report/design_report.md lists liquid density 1000 kg/m3 as an unpublished assumption; submission/src/ugssynth/engine.py defines LIQUID_DENSITY = 1000.0; submission/design/pipelines.json reports drain velocities up to 0.0256 m/s.

**Independent check:** Using public mass-flow rules, WDR-HIGH removed liquid is 120*0.01*0.9995 = 1.1994 kg/s, or 0.3998 kg/s per drain train. With the submission's assumed 1000 kg/m3 and DN150 ID 0.141 m, velocity is about 0.0256 m/s. Without density, kg/s cannot be uniquely converted to m/s.

**Result:** Drain mass capacities and outfall mass flow are checkable and pass, but the liquid-velocity judgment is not uniquely determined from the public brief.

**Why it matters:** This is not a submission violation; it is a missing public input that prevents a definitive independent PASS/FAIL on drain velocity.

### F-004 — unsupported_claim / low / confidence high

**Public basis:** brief/final_delivery_contract.json requires final artifacts to be reconstructable and calculations identifiable from the delivered package.

**Claim or requirement:** README and report claim `python project/run.py` rebuilds the network, checks, and artifacts.

**Submission evidence:** submission/README.md and submission/report/design_report.md give `python project/run.py`; the supplied submission tree contains submission/run.py and no project/run.py at the reviewed root. submission/src/ugssynth/data.py also defaults to /workspace/brief unless UGS_BRIEF_DIR is set.

**Independent check:** I inspected the supplied file tree and source paths. I did not run the command because execution and writes were blocked, but the named path is not present in this frozen submission layout.

**Result:** The reproduction command as documented is not supported by the delivered file layout, although the static JSON artifacts are still reviewable.

**Why it matters:** A post-hoc reviewer should be able to reproduce checks without guessing path or environment variables; this is a documentation/reconstructability defect, not a process-design infeasibility.

## Limitations

- The sandbox allowed file reads but rejected creating scratch/review_checks.py and rejected interpreter/script execution, so no evaluator-authored scratch calculation files were created. Independent calculations above are manual from the displayed public and submission data.
- I did not perform exhaustive hydraulic recomputation for every pipe in every scenario or every N-1 outage; hydraulic coverage is sampled as stated.
- I did not perform global LCC optimization. The LCC objective finding is based on one exact lower-cost feasible alternative, not a proof of the global optimum.
- Pipeline geometry, maintenance envelope, and overlap checks were sampled manually and supplemented by artifact inspection; they were not exhaustively recomputed by an independent geometry script because scratch writing/execution was blocked.
- Submission-authored code and check summaries were inspected for consistency but not treated as independent proof of PASS status.

Codex post-hoc findings are independent model-based engineering review findings, not formal ground truth.
