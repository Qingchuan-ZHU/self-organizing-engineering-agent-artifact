# Network semantics

This document defines the public physical-network rules for UGS-SYNTH-D01 v1.1. It does not prescribe a topology, operating sequence, route representation, or file format.

## Port compatibility and direction

Port types are physical service and direction labels. A connection is compatible only under these rules:

| Source-side port | Compatible destination-side port |
|---|---|
| `gas_out` | `gas_in`, `gas_bidirectional` |
| `gas_bidirectional` | `gas_in`, `gas_bidirectional` |
| `liquid_out` | `drain_in` |
| `drain_out` | `drain_in` |

The compatible pair may be listed in either endpoint order; its allowed physical flow direction is the direction shown in the table. `gas_in` is not a gas source. A `gas_out` remains one-way, and a seasonal operating scenario cannot treat it as bidirectional. Reverse station service may use a different physical path; only `gas_bidirectional` ports carry gas in either direction.

The external-interface `utility_in` port type marks an abstract utility boundary and has no process-piping connection. `road_access` marks the `ROAD-ENTRANCE` point and connects only to the site road network. These boundary port types are not compatible with gas or liquid-drain ports.

Every installed separator and filter `liquid_out` port is connected to a closed-drain `drain_in`, including when a particular scenario produces no removed liquid. A closed-drain `drain_out` discharges to another closed-drain `drain_in` or to the `LIQUID-DRAIN-OUTFALL` boundary. The public model includes no other liquid-service connection.

## Physical connection cardinality

An ordinary equipment port allows at most one physical connection. A port may declare `maximum_connections` to explicitly set a different limit. An external interface allows the number in its `maximum_connections` field; if that field is absent, the limit is one. The individual ports of a catalogued header are separate physical ports, each with the ordinary one-connection limit; the model's branch ports and `maximum_branch_connections` state the available branch count.

## Headers, junctions, and boundaries

Process branching or merging that requires multiple physical connections passes through catalogued header/manifold ports or another explicitly available component/interface. Arbitrary zero-cost process junctions are not part of this world. A header is a physical component with finite capacity, pressure drop, footprint, and a finite set of branch ports.

External interfaces are project boundaries, not internal process components. They may terminate the declared number of connections but may not be used as internal intermediate nodes or as a substitute for a process header. The `GRID-TIE`, well-group, and liquid-outfall limits in `site.json` and `well_group_interfaces.json` apply at those boundaries.

An interface's `maximum_flow_kg_s` is its boundary flow limit. Metering is a mandatory project requirement at `GRID-TIE`. In every scenario, all gas exchanged through that boundary must pass through active catalogued meter capacity whose combined rated capacity is at least the scenario's required gas flow. The public `minimum_active_meter_capacity_fraction_of_scenario_flow` is `1.0`.

The world imposes no acyclic-process-graph requirement. A physical loop is not disallowed solely because it is cyclic; it remains subject to the published port, mass-balance, pressure, capacity, temperature, and delivery rules.

## Liquid handling and pressure boundary

Separator and filter removal efficiency produces an explicit liquid side stream at `liquid_out`; the removed liquid cannot disappear from the process balance. The catalog's `maximum_liquid_rate_kg_s` is the maximum liquid flow at that outlet. The liquid must pass through a compatible liquid-drain route and available closed-drain capacity to the public outfall, within the outfall connection and flow limits.

For this synthetic case, a separator or filter `liquid_out` includes an idealized integral pressure letdown into the closed-drain pressure domain, at or below the catalogued `1 MPa` closed-drain limit. The liquid-drain network therefore uses the closed-drain pressure domain. Detailed liquid letdown equipment, flashing, and transient behavior are outside scope.

## Utility boundaries

Electric power, instrument air, and firewater are externally available abstract services. Their distribution networks are outside scope, and their availability/capacity is assumed sufficient unless a public requirement explicitly limits it. Catalogued equipment energy and heater duty still contribute to LCC under `engineering_calculation_basis.md`.
