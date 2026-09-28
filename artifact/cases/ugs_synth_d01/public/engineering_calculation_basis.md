# Deterministic engineering calculation basis

This basis defines the v1.1 synthetic calculation rules. It is not production thermodynamics, vendor data, procurement pricing, regulatory criteria, or code-compliance guidance. SI units apply unless stated otherwise. The equations describe engineering outcomes and do not prescribe a work sequence, program structure, or software library.

## Numerical conventions

The following tolerances apply when a calculated value is compared with a published limit. A value within the stated tolerance of a limit is treated as equal to that limit.

| Quantity | Tolerance |
|---|---:|
| Mass flow | `1e-5 kg/s` |
| Pressure | `1e-5 MPa` |
| Temperature | `1e-4 degC` |
| Geometry | `1e-6 m` |
| Same-level route overlap length | `1e-6 m` |
| Gas or liquid velocity | `1e-6 m/s` |
| Electrical or thermal power | `1e-6 MW` |
| Water content | `1e-5 mg/Sm3` |
| Free-liquid loading | `1e-9` (dimensionless) |
| LCC | `1e-8 MBCU` |

The minimum pressure used in a gas-property calculation is `1e-6 MPa`. Coordinates and lengths are in metres; pressure in MPa; temperature in degrees Celsius unless a formula explicitly uses kelvin; flow in kg/s; power in MW; energy in MWh; and cost in MBCU.

## Scenario flow and stream quality

`scenario_id` identifies a mandatory scenario; `service` is `injection` or `withdrawal`; `source_interface` and `sink_interfaces` identify its public boundaries; `source_pressure_mpa`, `source_temperature_c`, `source_water_mg_sm3`, and `source_free_liquid_mass_fraction` are inlet conditions; `required_total_flow_kg_s` is its required gas mass flow; `required_sink_pressure_mpa` is its delivery-pressure limit; and `annual_hours` is its annual weight. The full stated flow is required in normal operation. Injection is from `GRID-TIE` to the six well-group interfaces. A withdrawal `source_interface` of `well_groups` means all six public well groups are available as sources; withdrawal terminates at `GRID-TIE`.

`minimum_flow_kg_s` and `maximum_flow_per_interface_kg_s` define the permitted flow range for each well group; `maximum_bidirectional_flow_kg_s` is the same 25 kg/s well-group boundary limit. Well-group allocations for a scenario sum to its `required_total_flow_kg_s`. `operating_hours_per_year` is the sum of scenario `annual_hours`.

`maximum_water_content_mg_sm3`, `maximum_free_liquid_mass_fraction`, and `temperature_limits_c` are the gas-delivery limits. `maximum_free_liquid_mass_fraction` and `source_free_liquid_mass_fraction` use the gas-mass loading convention stated below. `compression_n_minus_one` applies when `required_sink_pressure_mpa > source_pressure_mpa`; after any one compressor is unavailable, at least `minimum_retained_flow_fraction` of scenario flow remains deliverable. `withdrawal_treatment_n_minus_one` applies to each withdrawal scenario after any one separator or dehydration unit is unavailable. In both cases, the same delivery limits remain applicable. The GRID-TIE metering requirement is satisfied only when all exchanged gas passes through active meter capacity at least equal to full scenario flow.

For v1.1, the fields named `*_free_liquid_mass_fraction` denote the synthetic free-liquid loading in kg liquid per kg gas; the gas-flow values remain on a gas-mass basis. At a mixing point, gas flow is summed, while temperature, water content, and free-liquid loading are gas-flow-weighted. Mixed pressure is the lowest incoming pressure. A split conserves gas flow across its branches.

The project delivery limits apply to gas delivered at the scenario sink interfaces: free-liquid loading, water content, and temperature must remain within `project_requirements.json`. Each scenario's `annual_hours` is its annual weight; the weights sum to `operating_hours_per_year`.

Water content and free-liquid loading are separate benchmark quality quantities. Changes in pressure or temperature do not induce modeled condensation or vaporization, and compressors, regulators, heaters, coolers, separators, and filters do not change water content. A dehydration unit sets outlet water content to its catalogued normal value; the removed water quantity, regeneration stream, and water disposal are outside this case's process model.

## Gas properties and pipe pressure loss

For pressure `P` in MPa and temperature `T_K` in kelvin:

- `Z_raw = 0.90 + 0.08 P / (P + 10) + 0.00015 (T_K - 293.15)`; `Z` is clamped to the bounds in `gas_properties.json`.
- `mu_raw = 1.05e-5 (T_K / 293.15)^0.70 (1 + 0.002 P)` Pa·s; `mu` is clamped to the bounds in `gas_properties.json`.
- `rho = (P × 1e6) MW / (Z R_u T_K)`, where `MW` is `molecular_weight_kg_mol` and `R_u = 8.314462618 J/(mol·K)`.
- Celsius converts to kelvin by adding `273.15`.

`heat_capacity_cp_j_kg_k` is constant-pressure heat capacity, and `specific_heat_ratio` is the heat-capacity ratio. Compressibility and viscosity use their published formulas and `minimum`/`maximum` bounds in `gas_properties.json`.

For a straight pipe segment with internal diameter `D`, area `A = πD²/4`, gas mass flow `m_dot`, density `rho`, viscosity `mu`, and roughness `epsilon`: `v = m_dot/(rho A)`, `Re = rho v D/mu`, and relative roughness is `epsilon/D`. The Darcy friction factor is `64/Re` for `Re < 2300`; otherwise it is the Swamee–Jain approximation `0.25/[log10(epsilon/(3.7D) + 5.74/Re^0.9)]²`. Pressure loss is `deltaP = f_D (L/D) rho v²/2` Pa, divided by `1e6` for MPa. No minor-loss allowance or elevation correction is included. The pressure-loss length is the sum of the straight segment lengths in that physical pipeline.

The representative mean pressure is `P_mean = (P_in + P_out) / 2`. The fixed-point convention starts with trial `P_out = P_in`, recalculates gas properties and pressure loss at `P_mean`, then updates `P_out = max(1e-6 MPa, P_in - deltaP)`. Convergence is reached when consecutive outlet-pressure estimates differ by less than `1e-5 MPa`. At most eight updates are evaluated. A value that has not converged after eight updates does not establish a valid pressure-loss result for the scenario.

The published maximum gas velocity applies to every gas pipeline. A pipe class must be pressure-rated for the highest pressure on the pipeline, have a compatible temperature range, and declare compatibility with the conveyed gas condition. Gas is dry when both water content and free-liquid loading are at or below their delivery limits; otherwise it is wet. Liquid-drain pipelines require a class marked `liquid_drain_compatible` and must remain within the published liquid-drain velocity limit. Pipe roughness, ratings, compatibility, and cost multipliers are in `piping_catalog.json`.

In the piping catalog, `nominal_diameter` and `nominal_diameter_mm` identify a size; `internal_diameter_m` is used in hydraulic calculations; and `installed_cost_mbcu_per_m` is its base installed cost. A pipe class's `maximum_allowable_pressure_mpa`, `temperature_limits_c`, and `roughness_m` define its rating and hydraulic surface. `wet_gas_compatible`, `dry_gas_compatible`, and `liquid_drain_compatible` define its service eligibility. `installed_cost_multiplier` changes installed piping CAPEX. For each `routing_level`, `installed_cost_multiplier` changes piping CAPEX and `civil_cost_mbcu_per_m` is its per-pipeline-length civil rate. `maximum_gas_velocity_m_s` and `maximum_liquid_drain_velocity_m_s` are service velocity limits.

## Equipment model parameters

Each catalog model's `category` identifies its equipment type; its explicit `safety_category` identifies the category used by the public separation matrix. `capacity_kg_s` is the rated gas flow for process equipment and the rated liquid flow for a closed drain. `capex_mbcu` is one-time equipment capital cost; `annual_maintenance_mbcu` is annual maintenance cost. `footprint_m` gives the rectangular length and width. `orientation_options_deg` lists the permitted orientations. Port types, local offsets, and connection cardinality are defined in `network_semantics.md` and `engineering_geometry_basis.md`.

Catalog pressure limits apply to the equipment's process pressure. Compressor models instead publish separate suction and discharge pressure limits and a maximum pressure ratio. A compressor's operating gas flow must not exceed its capacity or fall below its minimum stable flow when running. Its pressure ratio, discharge temperature, and driver power must remain within the model limits. Compressor outlet temperature is `T_out = T_in [1 + (r^((k-1)/k)-1)/eta]`; driver power is `W = m_dot cp T_in (r^((k-1)/k)-1)/(eta eta_driver)` W, converted to MW. Here `r` is outlet/inlet pressure, `k` is the published heat-capacity ratio, `eta` is `efficiency_proxy`, and `eta_driver` is `driver_efficiency`.

For equipment with `pressure_drop_mpa`, the value is the fixed pressure loss across the equipment. A header instead uses `deltaP = pressure_drop_at_capacity_mpa (m_dot/capacity_kg_s)^2`; its `maximum_branch_connections` and individual branch ports define the available physical branches.

Separator and filter liquid removal is a side stream. If inlet gas flow is `m_dot`, inlet free-liquid loading is `f_in`, and removal efficiency is `eta_L`, then removed liquid flow is `m_dot f_in eta_L` and outlet loading is `f_out = f_in (1 - eta_L)`. Gas flow is unchanged by this side-stream separation. The removed liquid exits through `liquid_out`; its flow must remain within the model's `maximum_liquid_rate_kg_s` and be conveyed to closed-drain service. `maximum_feed_free_liquid_fraction` limits inlet loading.

Dehydration outlet water content is the model's `normal_outlet_water_mg_sm3`; its energy demand is gas flow times `energy_mw_per_kg_s`. Its maximum feed free-liquid loading applies at its inlet. For a regulator, `T_out = T_in - JT (P_in - P_out)`, with `JT` from `jt_temperature_coefficient_k_per_mpa`. A cooler or heater's duty magnitude is `Q = m_dot cp |T_out - T_in|` MW. Duty must be within `maximum_duty_mw` and the outlet temperature within the catalog limit. Cooler power is duty times `electric_power_fraction_of_duty`; heater duty is counted as energy demand at 100% of duty. Meter flow may not exceed its catalog capacity or pressure limit.

Closed-drain flow may not exceed its model capacity or maximum pressure. The liquid-drain outfall's published connection and flow limits apply to the combined liquid discharge. The idealized pressure boundary for liquid transfer is defined in `network_semantics.md`.

The equipment catalog identifiers have these meanings and units (the catalog unit maps are authoritative for the displayed quantities):

| Catalog properties | Meaning |
|---|---|
| `category`, `safety_category`, `model_id` | Equipment type, explicit separation category, and public model identity. |
| `capacity_kg_s`, `capex_mbcu`, `annual_maintenance_mbcu` | Rated gas or liquid flow, one-time capital cost, and annual maintenance cost. |
| `footprint_m.length`, `footprint_m.width`, `orientation_options_deg` | Rectangular footprint dimensions and permitted rotations. |
| `ports[].id`, `ports[].type`, `ports[].offset_m` | Local port identity, service/direction type, and local coordinate offset. |
| `maintenance.clearance_m`, `maintenance.side`, `maintenance.removal_envelope_m` | Routine clearance, local heavy-maintenance side, and `[outward extent, transverse width]`. The latter two are present only for heavy-maintenance models. |
| `maintenance.heavy_maintenance`, `maintenance.road_access_required`, `maintenance.crane_access_required` | Whether a removal envelope is required and whether the published road/crane access distances apply. |
| Compressor: `minimum_stable_flow_kg_s`, `maximum_pressure_ratio`, `efficiency_proxy`, `driver_efficiency` | Minimum stable gas flow, maximum pressure ratio, compression efficiency proxy, and driver efficiency. |
| Compressor: `maximum_suction_pressure_mpa`, `maximum_discharge_pressure_mpa`, `maximum_suction_temperature_c`, `maximum_discharge_temperature_c`, `maximum_power_mw` | Compressor operating-envelope limits. |
| Process pressure fields: `maximum_pressure_mpa`, `pressure_drop_mpa` | Maximum equipment pressure and fixed pressure loss; compressor models use their separate suction/discharge limits. |
| Separator/filter: `maximum_feed_free_liquid_fraction`, `liquid_removal_efficiency`, `maximum_liquid_rate_kg_s` | Maximum inlet liquid loading, fraction of that loading removed, and maximum liquid side-stream flow. |
| Dehydration: `maximum_feed_free_liquid_fraction`, `normal_outlet_water_mg_sm3`, `energy_mw_per_kg_s` | Maximum inlet liquid loading, outlet water content, and power per gas flow. |
| Cooler: `minimum_outlet_temperature_c`, `maximum_duty_mw`, `electric_power_fraction_of_duty` | Minimum outlet temperature, maximum heat-removal duty, and electrical-power fraction of duty. |
| Heater: `maximum_outlet_temperature_c`, `maximum_duty_mw` | Maximum outlet temperature and maximum heat-addition duty. |
| Regulator: `jt_temperature_coefficient_k_per_mpa` | Temperature decrease per MPa of pressure reduction. |
| Header: `maximum_branch_connections`, `pressure_drop_at_capacity_mpa` | Maximum branch count and pressure drop at rated gas flow. |
| Closed drain: `maximum_pressure_mpa` | Maximum pressure in the idealized drain domain. |

Efficiency, pressure ratio, liquid loading, and electric-power fraction are dimensionless. Temperature coefficients use K/MPa. Catalogued footprint, port, clearance, and removal dimensions are metres; pressure is MPa; flow is kg/s; duty and power are MW; and costs use the catalog's MBCU units.

## Lifecycle-cost basis

The present-value factor for annual costs over `N` years at `discount_rate` `i` and `project_life_years` `N` is `PVF = (1 - (1+i)^(-N))/i`; when `i = 0`, `PVF = N`.

- Equipment CAPEX is the sum of `capex_mbcu` for every installed equipment instance.
- Piping CAPEX is summed for every installed pipeline segment: segment length × diameter installed cost per metre × pipe-class multiplier × routing-level installed-cost multiplier.
- Civil/access CAPEX is road centreline length × `road_mbcu_per_m`, plus equipment footprint area × `foundation_mbcu_per_m2`, plus required maintenance-envelope area × `maintenance_area_mbcu_per_m2`, plus pipeline length × the selected routing level's `civil_cost_mbcu_per_m`. Routing-level civil cost is charged **per pipeline installed length**, including every co-routed pipeline; shared physical corridor length is not deduplicated.
- Annual energy is the sum across scenarios of catalogued equipment power or duty in MW × scenario hours. Energy cost is annual MWh × `energy_tariff_mbcu_per_mwh`; its present value is annual energy cost × PVF.
- Annual maintenance is the sum of installed models' annual maintenance values; its present value is annual maintenance × PVF.

`LCC = equipment CAPEX + piping CAPEX + civil/access CAPEX + energy present value + maintenance present value`, in MBCU. The complete set of rates is in `economic_assumptions.json` and `piping_catalog.json`. No other score is combined with LCC.
