# Anonymous engineering review: submission_H / pass_02

**Evaluation window:** 2026-09-25T06:42:25Z to 2026-09-25T06:54:36Z
**Evaluator process exit:** 0

The submission is broadly reconstructable and most sampled engineering arithmetic matched the public basis, but I found several auditability and compliance issues: rounded scenario flow data fail the published mass-flow tolerance, n-1 outage evidence is not exhaustive by individual unit, and the design retains higher-cost metering/regulation equipment despite exact lower-cost feasible catalog substitutions. Liquid-drain velocity remains partly unresolvable because the public brief omits liquid density.

## Finding counts

- confirmed_violation: 2 (high 0, medium 1, low 1)
- unsupported_claim: 2
- suspected_risk: 0
- semantics_gap: 1
- observation: 0

## Areas checked

| Area | Coverage | Details |
|---|---|---|
| deliverable_completeness_reconstructability | sampled | A. Compared brief/final_delivery_contract.json with submission/deliverables/design_report.md, design.json, layout.svg, README.md, and validation_report.md. The main reconstruction fields are present: equipment instances/model IDs, positions/orientations/ports, boundary interfaces, pipelines/routes/DN/classes/levels, roads, scenarios, quantities, LCC, assumptions, and limitations. Found precision and consistency gaps noted in findings. |
| physical_topology_and_port_semantics | sampled | B. Sampled gas, liquid, drain, boundary, meter, compressor, regulator, header, GRID-TIE, well-group, and outfall connection semantics from design.json and public catalogs. Header branch counts and GRID-TIE/outfall connection counts were inspected from submitted data and embedded checks. No independent port-direction violation was confirmed, but the check was not a full reimplementation over every connection. |
| operating_scenarios | sampled | C. Covered all six mandatory scenarios: INJ-LOW, INJ-MID, INJ-HIGH, WDR-HIGH, WDR-MID, and WDR-LOW. Independently checked delivered pressure/quality samples, all well allocation sums, representative active paths, and selected path flows. Found rounded allocation values that do not meet the public 1e-5 kg/s tolerance. |
| n_minus_1_reliability | sampled | D. Inspected design.json reliability records and submission/ugs_design.py N1_CASES. Verified that submitted code only enumerates selected failed units rather than every individual compressor, separator, and dehydration unit. Did not re-simulate all omitted outage hydraulics. |
| equipment_limits | sampled | E. Sampled capacity, pressure, compressor ratio/temperature/power, cooler duty, separator/dehydrator feed quality, meter capacity, regulator capacity, header capacity, and closed-drain capacity checks. Compressor/cooler calculations for INJ-HIGH and treatment/drain capacity checks matched limits in sampled cases. |
| hydraulic_calculations | sampled | F. Independently recomputed gas properties, velocity, Reynolds/friction-factor basis, and pressure loss for PL-IR in INJ-LOW and PL-WM-1i in WDR-HIGH, covering a high-flow/long line and the highest reported gas velocity. Did not independently recompute every pipe or verify every eight-update convergence trace. |
| gas_quality_and_temperature | sampled | G. Checked separator removal, dehydration outlet water, injection cooling, regulator JT cooling, and delivery quality/temperature samples. Sampled wet/dry class eligibility appeared consistent. No confirmed gas-quality violation found. |
| liquid_drain | sampled | H. Checked separator liquid mass formulas, closed-drain capacities, outfall capacity, drain connections, drain class compatibility, and DN200 drain-line velocity under the submission's gas-density proxy. Public liquid-density semantics are missing, so liquid-velocity pass/fail is a semantics gap. |
| geometry_layout_roads_maintenance | sampled | I. Sampled site containment, exclusion zones, road widths/connectivity, maintenance access, and representative equipment separations from coordinates and reports. Did not fully recompute all footprint overlaps, maintenance envelopes, or all 276 pairwise separation distances. |
| pipeline_geometry | sampled | J. Sampled port endpoint matching, site/exclusion containment, segment lengths, route levels, and crossing semantics for representative routes including well laterals, PL-IR, PL-WM-1i, and liquid drains. Did not fully recompute all segment overlaps/self-overlaps across all 88 segments. |
| lifecycle_cost_arithmetic | sampled | K. Independently recomputed all equipment CAPEX and maintenance sums, PV factor, annual energy from scenario powers/hours, energy PV, maintenance PV, and sample piping/civil costs. Did not independently sum every pipeline segment cost. |
| lcc_objective | sampled | L. Did not claim global optimality. Identified exact lower-cost feasible substitutions for the regulator and meters using public catalog data, with a conservative delta-LCC calculation. |
| unsupported_assumptions | sampled | M. Reviewed assumptions around liquid density, flow balancing of parallel units, idle branches, and non-public margin to GRID-TIE boundary capacity. Liquid velocity depends on an unprovided public density input; oversized meter/regulator selections add non-public margin. |
| internal_consistency | sampled | N. Cross-checked report, JSON, source, validation report, quantities, scenario records, reliability records, and LCC. Found inconsistencies in rounded flow data, n-1 coverage evidence, liquid total messages, and DRN-S stated capacity in the report. |

## Independent calculations

### Scenario allocation flow-sum check

**Method:** Manually summed the delivered allocation values shown in the final JSON for each scenario and compared absolute error to 1e-5 kg/s.

**Result:** INJ-LOW and WDR-HIGH: 6*20.0 = 120.0. INJ-HIGH: 6*12.5 = 75.0. INJ-MID and WDR-MID: 6*16.6667 = 100.0002, error 2e-4 kg/s. WDR-LOW: 6*11.6667 = 70.0002, error 2e-4 kg/s. Treatment splits also show 3*33.3333 = 99.9999 and 3*23.3333 = 69.9999, errors above tolerance.

**Public inputs:** brief/engineering_calculation_basis.md: well-group allocations for a scenario sum to required_total_flow_kg_s, brief/engineering_calculation_basis.md: mass-flow tolerance is 1e-5 kg/s, brief/operating_scenarios.json: required flows 120, 100, 75, 120, 100, and 70 kg/s
**Submission inputs:** submission/deliverables/design.json: scenarios[].well_group_flows_kg_s, submission/deliverables/design.json: operating_path train split values such as 33.3333 and 23.3333 kg/s
**Scratch files:** None listed

### N-1 outage evidence enumeration

**Method:** Enumerated installed relevant units and mandatory scenarios, then compared expected individual failed-unit cases with the submitted N1_CASES list.

**Result:** At least 29 individual outage cases are required for exhaustive evidence: 11 compressor cases and 18 withdrawal treatment cases. The submission lists 12 cases and omits several individual failed units, including ICOMP-1/ICOMP-3 for INJ-MID and INJ-HIGH, WCOMP-2 for WDR-LOW, SEP-B/SEP-C, and DEH-A/DEH-C cases.

**Public inputs:** brief/project_requirements.json: compression_n_minus_one and withdrawal_treatment_n_minus_one require one unit unavailable at a time, brief/engineering_calculation_basis.md: delivery limits remain applicable after outage
**Submission inputs:** submission/ugs_design.py N1_CASES, submission/deliverables/design.json reliability array, submission/ugs_validate.py check_reliability iterates D.N1_CASES
**Scratch files:** None listed

### PL-IR INJ-LOW gas hydraulic spot check

**Method:** Manual recomputation at representative mean pressure using public gas-property and Darcy pressure-loss formulas.

**Result:** Calculated Z about 0.940, density about 63.8 kg/m3, velocity about 5.53 m/s, friction factor about 0.0095, and pressure loss about 0.0093 MPa. This matches submitted velocity 5.534 m/s and pressure loss 0.009312 MPa within displayed precision.

**Public inputs:** brief/gas_properties.json Z, viscosity, and density formulas, brief/piping_catalog.json DN700 internal diameter 0.658 m and CS-DRY-160 roughness 1.5e-5 m, brief/engineering_calculation_basis.md Darcy/Swamee-Jain pressure-loss basis
**Submission inputs:** submission/deliverables/design.json: PL-IR length 657.0 m, submission/deliverables/design.json: INJ-LOW PL-IR flow 120 kg/s, P_in 8.57934 MPa, P_out 8.57003 MPa, T 40 C
**Scratch files:** None listed

### PL-WM-1i WDR-HIGH highest-velocity gas hydraulic spot check

**Method:** Manual gas-property and pressure-loss recomputation at representative mean pressure.

**Result:** Calculated density about 50.4 kg/m3, velocity about 21.47 m/s, and pressure loss about 0.0213 MPa. This matches submitted velocity 21.467 m/s and pressure loss 0.02153 MPa within displayed precision; velocity is below 25 m/s.

**Public inputs:** brief/gas_properties.json gas-property formulas, brief/piping_catalog.json DN400 internal diameter 0.376 m, CS-WET-100 roughness 4.5e-5 m, gas velocity limit 25 m/s
**Submission inputs:** submission/deliverables/design.json: PL-WM-1i length 56.0 m, submission/deliverables/design.json: WDR-HIGH PL-WM-1i flow 120 kg/s, P_in 6.13168 MPa, P_out 6.11015 MPa, T 13.215 C
**Scratch files:** None listed

### INJ-HIGH compressor and cooler sample

**Method:** Manual compressor ratio, outlet temperature, driver power, and cooler duty/electric-power calculation.

**Result:** Compressor ratio about 2.105 is below 2.4; outlet temperature about 94.8 C and power about 6.68 MW match the submitted values and are below limits. Cooler thermal duty about 10.1 MW is below 32 MW; electric power about 0.353 MW matches the submission.

**Public inputs:** brief/engineering_calculation_basis.md compressor outlet temperature and power formulas, brief/gas_properties.json cp 2450 J/kg/K and k 1.3, brief/equipment_catalog/compressors.json C60 efficiency 0.80, driver efficiency 0.96, pressure ratio and temperature limits, brief/equipment_catalog/thermal_equipment.json COOL120 duty limit 32 MW and electric power fraction 0.035
**Submission inputs:** submission/deliverables/design.json: INJ-HIGH ICOMP-1 flow 37.5 kg/s, suction about 6.46006 MPa and 25 C, discharge 13.60025 MPa, T_out 94.855 C, submission/deliverables/design.json: COOL-1 flow 75 kg/s, inlet about 94.845 C, outlet 40 C, cooling electric 0.35272 MW
**Scratch files:** None listed

### Liquid drain mass and velocity basis check

**Method:** Calculated normal and n-1 separated liquid flows. For velocity, also evaluated the submission's stated gas-density proxy at 1 MPa and 20 C because the public brief does not provide liquid density.

**Result:** Normal separated liquid is 1.1994 kg/s for WDR-HIGH, 0.9995 kg/s for WDR-MID, and 0.69965 kg/s for WDR-LOW. Per-train normal rates and the n-1 worst rate of about 0.4198 kg/s are below SEP70 and DRN-S capacity. Under the submission's gas-density proxy, DN200 velocity is about 1.84 m/s, below 3.0 m/s, but this is not a definitive public-basis pass because liquid density is unspecified.

**Public inputs:** brief/engineering_calculation_basis.md separator liquid formula m_dot*f_in*eta_L, brief/equipment_catalog/separators.json SEP70 liquid removal efficiency 0.9995 and liquid rate limit 2.0 kg/s, brief/equipment_catalog/drains.json DRN-S capacity 0.8 kg/s, brief/site.json liquid outfall capacity 10 kg/s, brief/piping_catalog.json DN200 internal diameter 0.188 m and liquid velocity limit 3.0 m/s
**Submission inputs:** submission/deliverables/design.json withdrawal scenario flows and liquid validation entries, submission/deliverables/design.json drain lines PL-DA/DB/DC-1/2 use DN200 CS-WET-100
**Scratch files:** None listed

### LCC arithmetic and lower-cost substitutions

**Method:** Manually summed catalog equipment CAPEX and maintenance, recomputed PVF, annual energy from scenario powers and hours, and compared exact lower-cost catalog substitutions with unchanged geometry and capacity checks.

**Result:** PVF is 9.818147. Equipment CAPEX sums to 42.37 MBCU and annual maintenance to 1.391 MBCU. Scenario powers/hours give about 40452.3 MWh/year, matching the reported 40452.2 after rounding. Replacing REG180 with REG120 saves about 0.1593 MBCU PV; replacing two MTR160 meters with MTR120 meters saves about 0.2385 MBCU PV. Conservative combined LCC reduction is at least 0.3978 MBCU before any energy benefit from lower meter pressure drop.

**Public inputs:** brief/economic_assumptions.json discount rate 0.08, life 20 years, tariff 0.00012 MBCU/MWh, brief/equipment_catalog/metering_regulation.json MTR120, MTR160, REG120, REG180 costs, maintenance, capacities, pressure limits, footprints, and ports, brief/project_requirements.json metering capacity is scenario-flow based
**Submission inputs:** submission/deliverables/design.json lcc values and equipment list, submission/deliverables/design.json scenario powers and annual hours, submission/deliverables/design_report.md limitation noting REG180 retained over REG120
**Scratch files:** None listed

## Findings

### F-001 — confirmed_violation / low / confidence high

**Public basis:** brief/engineering_calculation_basis.md states that well-group allocations for a scenario sum to required_total_flow_kg_s and gives a mass-flow comparison tolerance of 1e-5 kg/s.

**Claim or requirement:** Scenario-specific operating flows in the final deliverable must conserve the required scenario flow within the published tolerance.

**Submission evidence:** submission/deliverables/design.json records INJ-MID and WDR-MID well_group_flows_kg_s as 16.6667 kg/s for each of six well groups, and WDR-LOW as 11.6667 kg/s for each of six well groups. The operating_path also contains rounded treatment splits such as 33.3333 and 23.3333 kg/s.

**Independent check:** 6*16.6667 = 100.0002 kg/s, which differs from the 100 kg/s requirement by 2e-4 kg/s. 6*11.6667 = 70.0002 kg/s, which differs from the 70 kg/s requirement by 2e-4 kg/s. Treatment splits 3*33.3333 and 3*23.3333 differ by about 1e-4 kg/s.

**Result:** The final artifact values do not satisfy the public 1e-5 kg/s mass-flow tolerance. This appears to be an export precision problem, but the final design.json is the reconstructable deliverable.

**Why it matters:** An independent reviewer reconstructing from the final JSON cannot verify flow conservation to the benchmark tolerance for several mandatory scenarios.

### F-002 — unsupported_claim / medium / confidence high

**Public basis:** brief/project_requirements.json requires any-one compressor outage for scenarios with required_sink_pressure_mpa > source_pressure_mpa and any-one separator or dehydration-unit outage for withdrawal scenarios, with delivery requirements still applicable.

**Claim or requirement:** The submission claims n-1 reliability PASS and validation_report.md says each required n-1 case is re-solved at 70% of scenario flow with one unit out.

**Submission evidence:** submission/deliverables/design.json lists only 12 reliability records. submission/ugs_design.py N1_CASES includes all three injection compressors only for INJ-LOW, only ICOMP-2 for INJ-MID and INJ-HIGH, only WCOMP-1 for WDR-LOW, only separator train A for each withdrawal scenario, and only dehydration train B for each withdrawal scenario. submission/ugs_validate.py check_reliability iterates only D.N1_CASES.

**Independent check:** The installed relevant units imply at least 29 individual outage checks for exhaustive evidence: 3 injection compressors across INJ-LOW/MID/HIGH, 2 withdrawal compressors for WDR-LOW, 3 separators across WDR-HIGH/MID/LOW, and 3 dehydration units across WDR-HIGH/MID/LOW. The submitted evidence covers 12 selected cases.

**Result:** The submission demonstrates representative n-1 cases but does not provide exhaustive evidence for any-one compressor, separator, and dehydration-unit outage. The design may be feasible, but the claimed n-1 PASS is not fully supported by the final artifacts.

**Why it matters:** N-1 reliability is a mandatory requirement, and asymmetric route lengths/pressure drops mean representative identical-unit testing is not equivalent to proving every individual outage.

### F-003 — confirmed_violation / medium / confidence high

**Public basis:** brief/project_requirements.json states the primary objective is to minimize benchmark LCC among feasible designs. The metering requirement requires active meter capacity at least 1.0 times scenario flow, not the GRID-TIE boundary maximum. brief/equipment_catalog/metering_regulation.json provides lower-cost MTR120 and REG120 models with the same pressure rating, footprints, and port layouts as the selected larger models for this service.

**Claim or requirement:** A feasible design should not retain higher-cost catalog equipment solely for non-public margin if exact lower-cost catalog substitutions satisfy all public requirements.

**Submission evidence:** submission/deliverables/design.json installs two MTR160 meters and one REG180 regulator. submission/deliverables/design_report.md explicitly says REG180 was retained over REG120 despite a 0.16 MBCU LCC penalty so the regulator is not exactly duty-matched. validation_report.md also applies a non-public check that meter capacity covers the whole GRID-TIE boundary limit.

**Independent check:** Replace REG180 with REG120: capacity 120 kg/s equals the maximum normal regulator flow and exceeds n-1 retained flows; pressure rating, JT coefficient, footprint, and ports remain compatible. Savings are 0.12 MBCU CAPEX plus 0.004*9.818147 = 0.0393 MBCU maintenance PV. Replace both MTR160 meters with MTR120 meters: capacity 120 kg/s equals the maximum published scenario flow, satisfying the public metering requirement; pressure rating, footprint, and ports remain compatible, and pressure drop is lower. Savings are 2*(0.08 + 0.004*9.818147) = 0.2385 MBCU. Combined conservative LCC reduction is at least 0.3978 MBCU, before any small energy benefit.

**Result:** An exact lower-cost feasible alternative exists with LCC at most about 105.6728 MBCU versus the submitted 106.0706 MBCU. The retained oversizing satisfies extra margin preferences but not the published LCC-minimization objective.

**Why it matters:** The benchmark objective is lifecycle-cost minimization among feasible designs; unnecessary catalog oversizing directly worsens the scored objective.

### F-004 — semantics_gap / low / confidence high

**Public basis:** brief/piping_catalog.json gives a maximum_liquid_drain_velocity_m_s of 3.0, but the public brief provides gas density formulas only and no liquid density or liquid velocity calculation basis. brief/network_semantics.md defines the drain pressure domain but not liquid density.

**Claim or requirement:** Liquid-drain velocity compliance should be judged against the public basis; the submission claims drain velocities pass using a gas-density proxy at 1 MPa.

**Submission evidence:** submission/deliverables/validation_report.md says drain-line liquid velocities are checked using the published gas-density proxy at the 1 MPa drain-domain limit, and submission/deliverables/design.json validation entries report about 1.837 m/s for DN200 drain lines at 0.4198 kg/s.

**Independent check:** The worst n-1 separator liquid rate is 0.7*120/2*0.01*0.9995 = 0.4198 kg/s. DN200 area is about 0.0278 m2. Using the gas-density proxy at 1 MPa and 20 C gives velocity about 1.84 m/s; using an actual liquid density would give a much lower value. The public brief does not specify which density is authoritative for liquid service.

**Result:** Separator liquid rates, drain drum capacities, and outfall capacity are checkable and pass in sampled cases, but liquid-drain velocity cannot be definitively passed or failed from public inputs alone.

**Why it matters:** This is not a submission violation, but it prevents a unique independent judgment for one required liquid-drain check.

### F-005 — unsupported_claim / low / confidence high

**Public basis:** brief/engineering_calculation_basis.md defines separator removed liquid as m_dot*f_in*eta_L. brief/equipment_catalog/drains.json gives DRN-S capacity as 0.8 kg/s.

**Claim or requirement:** Liquid totals and equipment stated capacities in the final reports should match the public formulas and catalog values.

**Submission evidence:** submission/deliverables/design.json validation entries state WDR-MID total separated liquid 1.1994 kg/s and WDR-LOW total separated liquid 1.1994 kg/s. submission/deliverables/design_report.md section 4 states DRN-S closed drain drum capacity as 2.0 kg/s, while design.json equipment entries list DRN-S capacity_kg_s as 0.8.

**Independent check:** WDR-MID removed liquid should be 100*0.01*0.9995 = 0.9995 kg/s total. WDR-LOW should be 70*0.01*0.9995 = 0.69965 kg/s total. DRN-S catalog capacity is 0.8 kg/s, not 2.0 kg/s.

**Result:** The submitted liquid validation text and report table contain unsupported values. The corrected values still satisfy outfall and DRN-S capacity limits, so this is an auditability/internal-consistency issue rather than an infeasibility finding.

**Why it matters:** Incorrect reported totals and capacities make it harder to independently audit liquid handling, even though the underlying sampled capacity margins remain adequate.

## Limitations

- No scratch files were created: the execution environment exposed to the evaluator was read-only, despite the requested scratch workflow.
- Inline Python/Node and PowerShell variable/pipeline execution were rejected by policy, so calculations were performed manually from inspected public and submission files rather than by saved scratch scripts.
- The submission's own validator was not executed; its code and generated reports were inspected only. A self-check PASS would not have been treated as independent evidence.
- Geometry overlap, road/access, and all-pipeline hydraulic checks were sampled rather than fully reimplemented across every segment and equipment pair.
- The lower-cost LCC alternative calculation is conservative for energy because it did not recompute reduced compression from the lower MTR120 pressure drop; it only counts catalog CAPEX and maintenance savings.

Codex post-hoc findings are independent model-based engineering review findings, not formal ground truth.
