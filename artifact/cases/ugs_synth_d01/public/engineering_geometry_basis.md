# Engineering geometry basis

This document defines the v1.1 site, equipment, maintenance, road, and pipeline geometry rules. Coordinates and lengths are in metres. Geometry rules are synthetic benchmark assumptions, not code-compliance criteria.

## Equipment placement and footprints

`(x_m, y_m)` is the centre of the catalogued rectangular equipment footprint. `orientation_deg` rotates the footprint and every local port offset about that centre. Positive rotation follows the standard counter-clockwise convention. A model may use only the values in its `orientation_options_deg`.

An equipment footprint must be within the site boundary, outside the interiors of all zones marked `equipment_exclusion`, and must not have positive-area overlap with another equipment footprint. Touching a site or exclusion-zone boundary is permitted within the geometry tolerance. The site boundary and zone polygons are in `site.json`.

Each model's `safety_category` is explicit: compressors use `compressor`; separators, dehydration units, filters, coolers, heaters, and headers use `hydrocarbon_treatment`; meters use `metering`; regulators use `pressure_control`; and closed drains use `drain`. For every equipment-category pair in the catalog, `safety_requirements.json` gives the minimum required separation. Separation is the shortest boundary-to-boundary distance between the two rotated footprint polygons, not centre distance. The matrix is symmetric and has an explicit value for every pair of categories used by equipment models.

## Maintenance geometry and access

`maintenance.clearance_m` expands the equipment footprint outward on every side by that distance, with straight/mitered corner joins. This is the routine maintenance envelope. A model with `heavy_maintenance: true` also has a rectangular removal envelope adjoining the footprint on `maintenance.side`. `side` is a direction in the equipment's local coordinates (`east`, `west`, `north`, or `south`) and rotates with the equipment. `removal_envelope_m` gives `[extent along the selected side, transverse width]`. The required envelope is the union of the routine clearance envelope and this removal envelope. A non-heavy-maintenance model has no removal envelope.

The required maintenance envelope must remain within the site, outside equipment-exclusion interiors, and clear of other equipment footprints. `road_access_required` means the envelope must be within `road_access_buffer_m` of a road network connected to `ROAD-ENTRANCE`. `crane_access_required` additionally requires that distance to be within `crane_access_buffer_m`. Values are in `maintenance_requirements.json`; each model's flags are in its equipment catalog.

For LCC, required maintenance area is the sum, over equipment instances, of each required maintenance-envelope area minus that instance's footprint area, with a negative result treated as zero. Overlap between different instances' maintenance envelopes is counted separately for each instance.

## Roads

A road is a polyline centreline with a published `width_m`. Its paved geometry is the centreline swept by half the width, including its joins and ends. The width must be at least `4 m`. The paved geometry must remain within the site boundary, outside interiors of zones marked `road_exclusion`, and clear of equipment footprints. Road sections connect when their paved geometries touch or overlap. The connected road network must contain the `ROAD-ENTRANCE` point.

Road-access and crane-access distances are measured from the required maintenance-envelope boundary to the nearest paved-road boundary. The respective maximum distances are `road_access_buffer_m` and `crane_access_buffer_m`. Road CAPEX uses centreline length; the published road rate is per metre and does not vary with width.

## Pipeline routes

A physical pipeline route joins the physical port at its source endpoint to the physical port at its destination endpoint. Its straight segments are continuous in order and meet both port coordinates within the geometry tolerance. A segment with length at or below the geometry tolerance is invalid. Every segment must remain within the site boundary, must not enter an interior marked `pipeline_exclusion`, and must not cross an equipment-footprint interior. Boundary contact is permitted within the geometry tolerance.

Each segment has one installation level: `ground`, `buried`, `rack_low`, or `rack_high`. These are distinct 2.5D installation levels; no explicit elevation is modeled. A transition between levels occurs at the shared endpoint of consecutive segments and adds no modelled route length, pressure loss, or LCC beyond the lengths and costs of the segments themselves. Different-level plan projections may cross.

Positive-length overlap between same-level pipeline segments is not allowed unless both segments explicitly use the same public corridor and that corridor allows co-routing. A pipeline may not overlap itself for a positive length. If a segment declares a corridor, its positive-length geometry must lie inside that corridor's interior, within the geometry tolerance, and its installation level must be listed in the corridor's `allowed_routing_levels`. `allows_co_routing` permits same-level shared length only for segments that both declare that same corridor.

## Numerical geometry boundary

The geometry tolerance is `1e-6 m`; the threshold for positive-length route overlap is also `1e-6 m`. Exclusion applies to zone interiors; a boundary touch within tolerance is not an entry into the excluded area. The site `boundary_polygon_m`, no-build zone `polygon_m` values and their `equipment_exclusion`, `pipeline_exclusion`, and `road_exclusion` flags define the plan-view geometry. The site `terrain.model` is `flat` and `elevation_m` is zero; no elevation correction is applied. Route, corridor, road, and footprint coordinates are interpreted in the site coordinate system in `site.json`.
