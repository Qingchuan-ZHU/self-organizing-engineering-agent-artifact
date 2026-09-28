# UGS-SYNTH-D01 Benchmark Provenance

## Scope and result

This repository-level review covers the 22 frozen files in `cases/ugs_synth_d01/public/` in the release package and their source-tree counterparts. It records provenance evidence and attribution; it is not a legal opinion or a rights clearance.

The review found a staged in-repository development history, synthetic benchmark markers on all 19 JSON files, and no third-party vendor identity, proprietary project dataset, named regulatory-standard source, or copied standard/vendor table in the reviewed files or their repository history. The calculation basis names the Swamee–Jain approximation; its method reference is included below. No third-party source was identified for the benchmark-specific data. This does not prove that no unrecorded third-party material exists.

**Redistribution status:** benchmark provenance reviewed; no specific third-party copied-content blocker identified; final licensing and redistribution decisions remain with the authorized human owner. No license is selected by this review.

## Frozen benchmark identity

- Scope: 22 files: 19 JSON and 3 Markdown.
- Source tree: `cases/ugs_synth_d01/public/`.
- Release copy: `cases/ugs_synth_d01/public/`.
- Public-world SHA-256 before review: `af4260bc8e15bb44364038b6eeea9a6a6942677ae8e5e610971689415fd0880e`.
- Source and release copy have the same 22 relative paths and identical per-file SHA-256 values. All eight frozen run configurations record the same public-world SHA.
- No public-world file was changed for this review.

## Provenance method and repository history

The review compared the source tree with the byte-identical release copy; checked all 19 JSON root-level `provenance` objects; inspected the three rule documents, benchmark values, equipment model identifiers, and explicit source/standard/vendor markers; and followed the Git history of each current public-world file. This was a repository-scoped review, not a broad internet similarity search.

The relevant history was verified from Git:

| Commit | Date | Verified public-world change |
|---|---|---|
| `6961bc83b39f67e294241704d07b6caba326a195` | 2026-09-23 | Added the 19 JSON files that remain in the current public world as part of “Define UGS-SYNTH-D01 public design space.” The same commit introduced the initial D01 design-space material. |
| `dc783bf9e6bf56dceb4966ff1e7c77c8ae358356` | 2026-09-24 | Reset the public world to a smaller general-purpose design space, revised the JSON set, and added `engineering_calculation_basis.md`. In `site.json` and `well_group_interfaces.json`, its changes remove only `case_id` and `schema_version`; their numeric geometry and interface limits were not changed in that commit. |
| `b2c673c6ae2784d29a8b826811e140db16ad50f1` | 2026-09-24 | Closed the v1.1 engineering-world semantics: revised 17 JSON files, updated the calculation basis, and added `engineering_geometry_basis.md` and `network_semantics.md`. |

The source repository also contains `scripts/build_ugs_synth_d01.py`, whose tracked history begins with the initial D01 design-space commit and whose legacy v1.0 definitions label deterministic values as synthetic assumptions. The script is identified in its own docstring as a legacy generator; it is corroborating development context, not the generator or authority for the current v1.1 file contents.

The per-file table below records first appearance, the latest material semantic update identified in the reviewed history, and each current source file hash. For `site.json` and `well_group_interfaces.json`, no material semantic rewrite after their first appearance was found; the later `dc783bf` change was metadata-only as described above.

## File-by-file inventory

“Low,” “Review,” and “High” below are provenance/redistribution review statuses, not engineering-risk ratings. “No third-party source identified” describes the repository evidence inspected; it is not a claim that no source exists.

| File | Content class | Origin assessment | Third-party dependency | Redistribution note | Review status |
|---|---|---|---|---|---|
| `case.json` | synthetic benchmark metadata | D01 case identity/version and file scope in the project history | None identified | No specific third-party content identified; final rights decision pending | Low |
| `economic_assumptions.json` | synthetic cost assumptions | Project-specific rates and a 20-year, 8% benchmark horizon | None identified; MBCU is the benchmark cost unit label, with no currency conversion or quote source | Rates are not represented as tariffs, bids, or real procurement prices; final rights decision pending | Low |
| `engineering_calculation_basis.md` | synthetic benchmark rules using generic engineering equations | Project-authored tolerances, proxies, limits, and calculation semantics | Generic engineering/math relations; the named Swamee–Jain correlation is attributed below | Method attribution added; no copied article prose/table identified; final rights decision pending | Review |
| `engineering_geometry_basis.md` | synthetic geometry | Project-authored site, footprint, road, access, and route semantics | None identified | No specific third-party content identified; final rights decision pending | Low |
| `equipment_catalog/compressors.json` | synthetic equipment catalog | Internal model IDs `C40`, `C60`, `C80`, `C60H` and benchmark parameters | No vendor identity, product code, or vendor source identified | Capacity, pressure, efficiency, footprint, cost, and maintenance values are assumptions, not real-device specifications | Low |
| `equipment_catalog/dehydration.json` | synthetic equipment catalog | Internal model IDs `DEHY40`, `DEHY70`, `DEHY120` and benchmark parameters | No vendor identity, product code, or vendor source identified | Capacity, pressure, outlet-water, energy, footprint, cost, and maintenance values are assumptions | Low |
| `equipment_catalog/drains.json` | synthetic equipment catalog | Internal model IDs `DRN-S`, `DRN-L` and benchmark parameters | No vendor identity, product code, or vendor source identified | Capacity, pressure, footprint, cost, and maintenance values are assumptions | Low |
| `equipment_catalog/filters.json` | synthetic equipment catalog | Internal model IDs `FIL60`, `FIL120` and benchmark parameters | No vendor identity, product code, or vendor source identified | Capacity, removal, pressure-drop, footprint, cost, and maintenance values are assumptions | Low |
| `equipment_catalog/headers.json` | synthetic equipment catalog | Internal model IDs `HDR60`, `HDR120`, `HDR180` and benchmark port layouts | No vendor identity, product code, or vendor source identified | Capacity, pressure-drop, ports, footprint, cost, and maintenance values are assumptions | Low |
| `equipment_catalog/metering_regulation.json` | synthetic equipment catalog | Internal model IDs `MTR*` and `REG*` and benchmark parameters | No vendor identity, product code, or vendor source identified | Capacity, pressure, temperature-coefficient, footprint, cost, and maintenance values are assumptions | Low |
| `equipment_catalog/separators.json` | synthetic equipment catalog | Internal model IDs `SEP40`, `SEP70`, `SEP120` and benchmark parameters | No vendor identity, product code, or vendor source identified | Capacity, removal, pressure-drop, footprint, cost, and maintenance values are assumptions | Low |
| `equipment_catalog/thermal_equipment.json` | synthetic equipment catalog | Internal model IDs `COOL*` and `HEAT*` and benchmark parameters | No vendor identity, product code, or vendor source identified | Duty, temperature, power, footprint, cost, and maintenance values are assumptions | Low |
| `final_delivery_contract.json` | synthetic benchmark rules | Project-authored deliverable and reconstruction requirements | None identified | No specific third-party content identified; final rights decision pending | Low |
| `gas_properties.json` | synthetic gas-property assumptions | Deterministic proxy coefficients and explicit model boundary | Generic gas-property relation; proxy coefficients are benchmark-defined | Not a production thermodynamic property package; final rights decision pending | Low |
| `maintenance_requirements.json` | synthetic maintenance/access assumptions | Project-specific access buffers | None identified | No specific third-party content identified; final rights decision pending | Low |
| `network_semantics.md` | synthetic network semantics | Project-authored port, connection, header, drain, and utility-boundary rules | None identified | No specific third-party content identified; final rights decision pending | Low |
| `operating_scenarios.json` | synthetic scenario data | Six benchmark injection/withdrawal scenarios and abstract interfaces | No client, field, or source dataset identified | Scenario values are assumptions, not operating records; final rights decision pending | Low |
| `piping_catalog.json` | synthetic benchmark catalog | Ten nominal sizes, three internal class IDs, and benchmark costs/rules | No external catalog source identified | Not represented as a commercial pipe schedule or procurement catalog; final rights decision pending | Low |
| `project_requirements.json` | synthetic benchmark rules | Project-specific scope, delivery, reliability, utility, and objective rules | None identified | Includes “vendor procurement” only as excluded scope; it does not identify vendor content | Low |
| `safety_requirements.json` | synthetic safety matrix | Project-specific five-category separation matrix | No standard or vendor source identified | Must not be interpreted as an industrial safety code; final rights decision pending | Low |
| `site.json` | synthetic geometry | Local 700 m × 450 m plot, abstract interfaces, and benchmark zones/corridors | No place name, latitude/longitude, company facility, or source map identified | Coordinates and labels are benchmark assumptions; final rights decision pending | Low |
| `well_group_interfaces.json` | synthetic scenario/interface data | Six generic `WG-01`–`WG-06` interfaces and limits | No real well identifiers or source dataset identified | Interface values are assumptions, not production data; final rights decision pending | Low |

## File-level Git and SHA-256 traceability

SHA-256 values below are for the current source-tree file bytes. The release-package copies match these values. “First appearance” is the file-add commit reported by `git log --follow --diff-filter=A`; the semantic-update entry reflects the reviewed path history.

| File | First appearance commit | Major semantic update / history note | Current source SHA-256 |
|---|---|---|---|
| `case.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `080cc44e86dedf19ec5a42aefe1d0bcbba946ecaef3a0051260b48de6e2650e8` |
| `economic_assumptions.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `ae71c8c5b0a86c0096493c028d75ae0ad594f5dfb955a8d6e63631fcc15d0896` |
| `engineering_calculation_basis.md` | `dc783bf9e6bf56dceb4966ff1e7c77c8ae358356` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `e9c1f4a53cb2a801dd9e092c15c6462c777ef02fadfb74ff6eb9fe3f1b4162bb` |
| `engineering_geometry_basis.md` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | Added with v1.1 semantics in `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `0531c067bb22d60a9b3cdf8d3308721bd0104e0d6feec87daac2d5ba966c8315` |
| `equipment_catalog/compressors.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `c88919e864f551815a50dc706f41fd01b8337fa86bea56aeef412d20e54a1da7` |
| `equipment_catalog/dehydration.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `550fe7a96dbceff1488661ba05d34c3cb464b0d0fb96be9c03ae89eb6e5bc459` |
| `equipment_catalog/drains.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `3d85d43734c5832b596c0595417b1c4b81ff7f5229c96e2ff28121d5f1a9e9c6` |
| `equipment_catalog/filters.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `d314cc23755294773a08eedf0a2de98868f236462fa6615d00b3e82d67761b0c` |
| `equipment_catalog/headers.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `f4f3081b23033bd450980e79bca85d31f722f42b078620c60af760453d9fb80f` |
| `equipment_catalog/metering_regulation.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `745a9427e4cbfa889e64f27ab5d42a2d096a28411016639392212cb45bfc4c64` |
| `equipment_catalog/separators.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `35f7276b402f6845fd01bd14955fab542a596706c6aac7f025396f67b077e2b6` |
| `equipment_catalog/thermal_equipment.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `ffa7f31e907ddbf4672328920666505160bd34f6a1144931736ec3657fd7e033` |
| `final_delivery_contract.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `dde8dbdfe2dfd1bf086289358fa4a2f2b002fe535a0ca9ca0d0c6e55e15023f5` |
| `gas_properties.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `ff8a1650fbee84f3c2e472dc5318021ae1f1838400a24cb4c95b3371289aacf8` |
| `maintenance_requirements.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `471332a4bf079bcb51590882f55383fac5b677f8be7edbea45d605acd9a08b55` |
| `network_semantics.md` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | Added with v1.1 semantics in `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `05ac3d8184b34531004a574dc329ae6a4d3a5eb1e62ed3d50d826c43a7af25d4` |
| `operating_scenarios.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `b402120a59660383697ed3f468218c027f5a6a9b09975ace325d74969771f649` |
| `piping_catalog.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `cee8ee256712bb5b5731b11e3ddb153419c216869e2b9f495f12001418d485eb` |
| `project_requirements.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `8024ba75f46589508d52a2691172aad4532808f0ebf65528e00da06d61d2905e` |
| `safety_requirements.json` | `6961bc83b39f67e294241704d07b6caba326a195` | `b2c673c6ae2784d29a8b826811e140db16ad50f1` | `5fb5d18e8253ff8e133bd539eca63a49582c97a3b25ce4bb01b7d6c7a22edf23` |
| `site.json` | `6961bc83b39f67e294241704d07b6caba326a195` | No material semantic rewrite found; `dc783bf9e6bf56dceb4966ff1e7c77c8ae358356` removed schema metadata | `402848a71612030e92fa0315b4b2df1d533d61e5fcfa4bfe4b40fb2b47ba870a` |
| `well_group_interfaces.json` | `6961bc83b39f67e294241704d07b6caba326a195` | No material semantic rewrite found; `dc783bf9e6bf56dceb4966ff1e7c77c8ae358356` removed schema metadata | `54f913e24305318ec01bba1ab05172d05c02a98bc237fcc119574b92a23a5202` |

## Synthetic content categories

### Site, interfaces, and operating scenarios

The site is a local-coordinate 700 m × 450 m rectangle with abstract `GRID-TIE`, `WG-01`–`WG-06`, utility, road, and drain interfaces. The six injection/withdrawal scenarios use benchmark flow, pressure, temperature, water-content, liquid-loading, and annual-hour values. The files contain no named location, latitude/longitude, company facility, named storage field, customer record, or real well identifier.

### Equipment catalogs

The eight catalogs define 28 case-internal model IDs, including `C40`/`C60`/`C80`/`C60H`, `DEHY40`/`DEHY70`/`DEHY120`, `SEP40`/`SEP70`/`SEP120`, and the `DRN*`, `FIL*`, `HDR*`, `MTR*`, `REG*`, `COOL*`, and `HEAT*` families. The files expose no manufacturer, brand, product number, proprietary curve, quotation, or datasheet reference. Their capacities, pressure limits, efficiencies/proxies, dimensions, maintenance parameters, CAPEX, and annual maintenance values are deterministic benchmark assumptions, not claims about real equipment.

### Piping catalog

The ten published internal diameters are a benchmark table: each is exactly 0.94 × its nominal diameter in millimetres (`DN150` → 0.141 m through `DN700` → 0.658 m). The three `CS-WET-*`/`CS-DRY-*` class IDs, roughnesses, pressure limits, compatibility flags, and MBCU costs are case definitions. No ASME/API pipe schedule, manufacturer table, or external piping catalog source was identified. The table is not represented as a commercial pipe schedule or procurement catalog.

### Safety constraints

The five-category separation matrix (`compressor`, `hydrocarbon_treatment`, `pressure_control`, `metering`, `drain`) is benchmark-specific and its source file explicitly labels distances synthetic and not code-compliance criteria. **The separation matrix is a benchmark-specific synthetic constraint matrix and must not be interpreted as an industrial safety code.** No API, NFPA, ASME, ISO, GB, or SY standard reference or copied separation table was identified in the reviewed public-world files.

### Economic assumptions

The 20-year life, 8% discount rate, energy tariff, and civil, equipment, piping, and maintenance rates are stated in MBCU. MBCU is used as the benchmark's abstract cost unit; no actual currency conversion, tariff source, vendor quote, or procurement basis is given. These figures are not represented as real prices or project estimates.

### Benchmark-specific rules

Port direction/cardinality, header and liquid-drain behavior, reliability selectors, numerical tolerances, maintenance envelopes, road/access rules, route/corridor semantics, safety distances, and the LCC composition are authored D01 rules. They define this benchmark's decision space and are not regulatory or production-project requirements.

## Generic engineering methods used

The calculation basis uses generic mathematical/engineering relations for gas density, Reynolds number, Darcy friction factor and pressure loss, compressor temperature/power, Joule–Thomson temperature change, heat duty, and present value. `gas_properties.json` also supplies explicitly bounded synthetic compressibility and viscosity proxy formulas. These methods are not claimed as original. Benchmark-specific coefficients, thresholds, proxy correlations, and decision semantics remain synthetic case definitions.

The Darcy friction-factor calculation names the Swamee–Jain approximation. The citation below acknowledges that named engineering correlation used by the benchmark. **The frozen benchmark file itself is unchanged.**

## Third-party content review

- Vendor IDs, manufacturers, branded product identifiers, proprietary performance curves, vendor quotations, datasheet text, and real procurement-price sources: none identified in the reviewed 22 files or their Git provenance.
- Named regulatory-standard identifiers and copied standard tables/text: none identified in the reviewed public-world files or their Git provenance.
- A mention of “vendor procurement” occurs only in `project_requirements.json` as excluded project scope; it does not identify or reproduce vendor material.
- Named method: Swamee–Jain is present as a formula/correlation and attributed below; no copied article passage or table was identified.
- Provenance review statuses: 21 Low, 1 Review (the calculation basis because it names a published correlation), 0 High. These labels are not a legal determination.

The finding is: **No third-party source identified in repository provenance review.** This describes the evidence reviewed; it does not establish provenance outside the repository or settle redistribution rights.

## Redistribution status and limitation

Benchmark provenance is reviewed; no specific third-party vendor, proprietary-project, or copied-standard content blocker was identified. The release-governance decision assigns the benchmark and authored documentation to CC BY 4.0, with the frozen-evidence rights boundary stated in `LICENSE.md`. This report records provenance findings and does not claim legal clearance or override third-party rights.

This is a repository provenance review, not legal advice or a substitute for formal rights clearance.

## References

Swamee, P. K., and Jain, A. K. (1976). “Explicit Equations for Pipe-Flow Problems.” *Journal of the Hydraulics Division*, 102(5), 657–664. [https://doi.org/10.1061/JYCEAJ.0004542](https://doi.org/10.1061/JYCEAJ.0004542).
