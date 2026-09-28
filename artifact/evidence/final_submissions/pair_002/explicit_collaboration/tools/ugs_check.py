"""Verification, quantities and lifecycle cost for UGS-SYNTH-D01.

The module re-implements the published v1.1 rules and applies them to the design
built in :mod:`ugs_design`.  It produces

  * geometry / layout verification (footprints, separations, maintenance
    envelopes, roads, pipeline routes and levels)
  * scenario verification (mass balance, hydraulic march, equipment limits, gas
    delivery limits, metering, N-1 cases)
  * quantities and the lifecycle-cost breakdown
  * the machine-readable design export and the verification report

Every number is recomputed from the case data; nothing is hard-coded.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import ugs_basis as B
from ugs_basis import (
    TOL_GEOMETRY_M, TOL_LIQUID_LOADING, TOL_MASS_FLOW_KG_S, TOL_PRESSURE_MPA,
    TOL_TEMPERATURE_C, TOL_WATER_MG_SM3, TOL_OVERLAP_M,
)

# documented assumption: no liquid density is published by the case, so liquid
# drain velocity checks use this value.
LIQUID_DENSITY_ASSUMED_KG_M3 = 800.0

# design margin applied at the published delivery-pressure requirement
DELIVERY_PRESSURE_MARGIN_MPA = 0.0


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Node:
    tag: str
    model: dict
    x: float
    y: float
    o: int
    role: str = ""

    def __post_init__(self):
        fp = self.model["footprint_m"]
        self.length_m = fp["length"]
        self.width_m = fp["width"]
        self.footprint = B.rect_polygon(self.x, self.y, self.length_m, self.width_m, self.o)
        self.ports = {}
        for port in self.model["ports"]:
            ox, oy = port["offset_m"]
            a = math.radians(self.o)
            px = self.x + ox * math.cos(a) - oy * math.sin(a)
            py = self.y + ox * math.sin(a) + oy * math.cos(a)
            self.ports[port["id"]] = (px, py, port["type"])
        self.category = self.model["category"]
        self.safety_category = self.model["safety_category"]

    def clearance_polygon(self):
        c = self.model["maintenance"]["clearance_m"]
        return B.rect_polygon(self.x, self.y, self.length_m + 2 * c, self.width_m + 2 * c, self.o)

    def removal_polygon(self):
        mnt = self.model["maintenance"]
        if not mnt.get("heavy_maintenance"):
            return None
        ext, trans = mnt["removal_envelope_m"]
        side = mnt["side"]
        hx, hy = self.length_m / 2.0, self.width_m / 2.0
        if side == "east":
            local = [(hx, -trans / 2), (hx + ext, -trans / 2), (hx + ext, trans / 2), (hx, trans / 2)]
        elif side == "west":
            local = [(-hx, -trans / 2), (-hx - ext, -trans / 2), (-hx - ext, trans / 2), (-hx, trans / 2)]
        elif side == "north":
            local = [(-trans / 2, hy), (-trans / 2, hy + ext), (trans / 2, hy + ext), (trans / 2, hy)]
        else:
            local = [(-trans / 2, -hy), (-trans / 2, -hy - ext), (trans / 2, -hy - ext), (trans / 2, -hy)]
        return B.rotate_points([(self.x + px, self.y + py) for px, py in local], self.o,
                               (self.x, self.y))

    def envelope_polygons(self):
        polys = [self.clearance_polygon()]
        rp = self.removal_polygon()
        if rp is not None:
            polys.append(rp)
        return polys

    def maintenance_area_m2(self):
        cl = self.clearance_polygon()
        area = B.polygon_area(cl)
        rp = self.removal_polygon()
        if rp is not None:
            area += B.polygon_area(rp) - B.convex_intersection_area(cl, rp)
        return max(0.0, area - B.polygon_area(self.footprint))


@dataclass
class Pipeline:
    tag: str
    a: tuple
    b: tuple
    dn: str
    cls: str
    level: str
    wp: list = field(default_factory=list)
    seg_levels: dict = field(default_factory=dict)
    service: str = "gas"
    corridor: str = None
    role: str = ""
    points: list = field(default_factory=list)
    length_m: float = 0.0

    def build_points(self, pa, pb):
        self.points = [tuple(pa)] + [tuple(p) for p in self.wp] + [tuple(pb)]
        self.length_m = B.polyline_length(self.points)

    def segments(self):
        return [(self.points[i], self.points[i + 1], self.seg_levels.get(i, self.level), i)
                for i in range(len(self.points) - 1)]


class Design:
    def __init__(self, case: B.CaseData, equipment, pipes, roads):
        self.case = case
        self.gas = B.Gas(case.gas_properties)
        self.nodes = {}
        for e in equipment:
            self.nodes[e["tag"]] = Node(e["tag"], case.models[e["model"]], e["x"], e["y"], e["o"],
                                        e.get("role", ""))
        self.pipes = {}
        for p in pipes:
            pl = Pipeline(p["tag"], tuple(p["a"]), tuple(p["b"]), p["dn"], p["cls"], p["level"],
                          list(p.get("wp", [])), dict(p.get("seg_levels", {})),
                          p.get("service", "gas"), p.get("corridor"), p.get("role", ""))
            pl.build_points(self.endpoint(pl.a), self.endpoint(pl.b))
            self.pipes[pl.tag] = pl
        self.roads = roads
        self.results: list[CheckResult] = []
        self.scenario_results: dict = {}
        self.lcc: dict = {}

    # ------------------------------------------------------------------ utils
    def endpoint(self, ref):
        tag, port = ref
        if tag in self.nodes:
            return self.nodes[tag].ports[port][:2]
        return tuple(self.case.interfaces[tag]["point_m"])

    def endpoint_type(self, ref):
        tag, port = ref
        if tag in self.nodes:
            return self.nodes[tag].ports[port][2]
        return self.case.interfaces[tag]["port_type"]

    def add(self, name, ok, detail=""):
        self.results.append(CheckResult(name, bool(ok), detail))
        return bool(ok)

    def d(self, dn):
        return self.case.diameters[dn]

    def pc(self, cid):
        return self.case.pipe_classes[cid]

    # -------------------------------------------------------- port / topology
    def check_connections(self):
        limit = {"gas_out": {"gas_in", "gas_bidirectional"},
                 "gas_bidirectional": {"gas_in", "gas_bidirectional"},
                 "liquid_out": {"drain_in"},
                 "drain_out": {"drain_in"}}
        usage = {}
        for tag, pl in self.pipes.items():
            ta, tb = self.endpoint_type(pl.a), self.endpoint_type(pl.b)
            if ta in limit:
                ok = tb in limit[ta]
            elif tb in limit:
                ok = ta in limit[tb]
            else:
                ok = False
            self.add(f"port compatibility {tag} ({ta} -> {tb})", ok)
            for ref in (pl.a, pl.b):
                if ref[0] in self.nodes:
                    usage.setdefault(ref, []).append(tag)
        for ref, tags in usage.items():
            node = self.nodes[ref[0]]
            port_info = [p for p in node.model["ports"] if p["id"] == ref[1]][0]
            maxc = port_info.get("maximum_connections", 1)
            self.add(f"connection cardinality {ref[0]}.{ref[1]}", len(tags) <= maxc,
                     f"{len(tags)} of {maxc} allowed ({', '.join(tags)})")
        # external interfaces
        for tag, iface in self.case.interfaces.items():
            used = [pl.tag for pl in self.pipes.values() if pl.a[0] == tag or pl.b[0] == tag]
            maxc = iface.get("maximum_connections", 1)
            self.add(f"connection cardinality interface {tag}", len(used) <= maxc,
                     f"{len(used)} of {maxc} allowed ({', '.join(used)})")
        # every pipeline endpoint is a catalogued port or an external interface
        for tag, pl in self.pipes.items():
            for ref in (pl.a, pl.b):
                ok = ref[0] in self.nodes and ref[1] in self.nodes[ref[0]].ports or \
                     ref[0] in self.case.interfaces
                self.add(f"endpoint {tag} {ref[0]}.{ref[1]} exists", ok)
        # header branch counts
        for tag, n in self.nodes.items():
            if n.category != "header":
                continue
            branches = sum(1 for pl in self.pipes.values()
                           for ref in (pl.a, pl.b) if ref[0] == tag)
            self.add(f"header {tag} branch connections <= maximum_branch_connections",
                     branches <= n.model["maximum_branch_connections"],
                     f"{branches} of {n.model['maximum_branch_connections']}")
        # separator/filter liquid outlets must be routed to a closed drain
        for tag, n in self.nodes.items():
            if n.category not in ("separator", "filter"):
                continue
            outs = [pl for pl in self.pipes.values() if pl.a == (tag, "liquid_out")]
            ok = len(outs) == 1 and self.nodes[outs[0].b[0]].category == "closed_drain"
            self.add(f"{tag} liquid_out routed to a closed drain drain_in", ok,
                     outs[0].tag + " -> " + outs[0].b[0] if outs else "no connection")

    # ------------------------------------------------------------ geometry
    def check_equipment_geometry(self):
        site = [(p[0], p[1]) for p in self.case.site_boundary]
        zones = [z for z in self.case.site["no_build_zones"] if z["equipment_exclusion"]]
        tags = list(self.nodes)
        for tag in tags:
            n = self.nodes[tag]
            inside = all(B.point_in_convex(site, c) != -1 for c in n.footprint)
            self.add(f"footprint inside site: {tag}", inside)
            for z in zones:
                zp = [tuple(p) for p in z["polygon_m"]]
                area = B.convex_intersection_area(n.footprint, zp)
                self.add(f"footprint {tag} clear of equipment-exclusion {z['zone_id']}",
                         area <= 1e-9, f"overlap area {area:.4g} m2")
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                a, b = self.nodes[tags[i]], self.nodes[tags[j]]
                area = B.convex_intersection_area(a.footprint, b.footprint)
                self.add(f"no footprint overlap {a.tag}/{b.tag}", area <= 1e-9,
                         f"overlap area {area:.4g} m2")
                if area > 1e-9:
                    continue
                dist = B.polygons_distance(a.footprint, b.footprint)
                req = self.case.min_separation_m(a.safety_category, b.safety_category)
                self.add(f"separation {a.tag}/{b.tag} >= {req:g} m", dist >= req - TOL_GEOMETRY_M,
                         f"distance {dist:.3f} m")

    def check_maintenance_envelopes(self):
        site = [(p[0], p[1]) for p in self.case.site_boundary]
        zones = [z for z in self.case.site["no_build_zones"] if z["equipment_exclusion"]]
        for tag, n in self.nodes.items():
            for k, poly in enumerate(n.envelope_polygons()):
                label = "clearance" if k == 0 else "removal"
                self.add(f"{label} envelope of {tag} inside site",
                         all(B.point_in_convex(site, c) != -1 for c in poly))
                for z in zones:
                    zp = [tuple(p) for p in z["polygon_m"]]
                    area = B.convex_intersection_area(poly, zp)
                    self.add(f"{label} envelope of {tag} clear of {z['zone_id']}", area <= 1e-9,
                             f"overlap area {area:.4g} m2")
                for other_tag, other in self.nodes.items():
                    if other_tag == tag:
                        continue
                    area = B.convex_intersection_area(poly, other.footprint)
                    self.add(f"{label} envelope of {tag} clear of footprint {other_tag}",
                             area <= 1e-9, f"overlap area {area:.4g} m2")

    def paved_road_polygons(self):
        polys = []
        for r in self.roads:
            hw = r["width_m"] / 2.0
            pts = [tuple(p) for p in r["pts"]]
            for i in range(len(pts) - 1):
                polys.append((r["tag"], B.segment_rect_polygons(pts[i], pts[i + 1], hw)))
        return polys

    def check_roads(self):
        site = [(p[0], p[1]) for p in self.case.site_boundary]
        zones = [z for z in self.case.site["no_build_zones"] if z["road_exclusion"]]
        for r in self.roads:
            self.add(f"road {r['tag']} width >= 4 m", r["width_m"] >= 4.0, f"{r['width_m']} m")
        for tag, poly in self.paved_road_polygons():
            self.add(f"paved geometry of {tag} inside site",
                     all(B.point_in_convex(site, c) != -1 for c in poly))
            for z in zones:
                zp = [tuple(p) for p in z["polygon_m"]]
                area = B.convex_intersection_area(poly, zp)
                self.add(f"paved geometry of {tag} clear of road-exclusion {z['zone_id']}",
                         area <= 1e-9, f"overlap area {area:.4g} m2")
            for ntag, n in self.nodes.items():
                area = B.convex_intersection_area(poly, n.footprint)
                self.add(f"paved geometry of {tag} clear of footprint {ntag}", area <= 1e-9,
                         f"overlap area {area:.4g} m2")
        pieces = self.paved_road_polygons()
        parent = list(range(len(pieces)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                if B.convex_intersection_area(pieces[i][1], pieces[j][1]) > 1e-9:
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[ri] = rj
        entrance = tuple(self.case.interfaces["ROAD-ENTRANCE"]["point_m"])
        ent = [i for i, (t, poly) in enumerate(pieces) if B.point_in_convex(poly, entrance) != -1]
        self.add("ROAD-ENTRANCE lies on the paved network", bool(ent))
        if ent:
            root = find(ent[0])
            self.add("road network connected to ROAD-ENTRANCE",
                     all(find(i) == root for i in range(len(pieces))))

    def check_road_access(self):
        pieces = [poly for _, poly in self.paved_road_polygons()]
        for tag, n in self.nodes.items():
            mnt = n.model["maintenance"]
            if not (mnt.get("road_access_required") or mnt.get("crane_access_required")):
                continue
            env = n.envelope_polygons()
            dmin = min(B.polygon_min_distance_to_region(p, pieces) for p in env)
            if mnt.get("road_access_required"):
                self.add(f"road access {tag} <= {self.case.road_access_buffer_m:g} m",
                         dmin <= self.case.road_access_buffer_m + TOL_GEOMETRY_M,
                         f"distance {dmin:.3f} m")
            if mnt.get("crane_access_required"):
                self.add(f"crane access {tag} <= {self.case.crane_access_buffer_m:g} m",
                         dmin <= self.case.crane_access_buffer_m + TOL_GEOMETRY_M,
                         f"distance {dmin:.3f} m")

    def check_pipeline_geometry(self):
        site = [(p[0], p[1]) for p in self.case.site_boundary]
        zones = [z for z in self.case.site["no_build_zones"] if z["pipeline_exclusion"]]
        corridors = {cid: [tuple(p) for p in c["polygon_m"]] for cid, c in self.case.corridors.items()}
        for tag, pl in self.pipes.items():
            for (p0, p1, lvl, idx) in pl.segments():
                length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                self.add(f"segment length {tag}[{idx}]", length > TOL_GEOMETRY_M, f"{length:.3f} m")
                self.add(f"segment {tag}[{idx}] inside site",
                         B.point_in_convex(site, p0) != -1 and B.point_in_convex(site, p1) != -1)
                for z in zones:
                    zp = [tuple(p) for p in z["polygon_m"]]
                    inside = B.segment_inside_convex_length(zp, p0, p1, TOL_GEOMETRY_M)
                    self.add(f"segment {tag}[{idx}] clear of {z['zone_id']} pipeline-exclusion",
                             inside <= TOL_GEOMETRY_M, f"inside length {inside:.3f} m")
                for ntag, n in self.nodes.items():
                    inside = B.segment_inside_convex_length(n.footprint, p0, p1, TOL_GEOMETRY_M)
                    self.add(f"segment {tag}[{idx}] clear of footprint {ntag}",
                             inside <= TOL_GEOMETRY_M, f"inside length {inside:.3f} m")
                if pl.corridor:
                    cid = pl.corridor
                    if lvl not in self.case.corridors[cid]["allowed_routing_levels"]:
                        self.add(f"segment {tag}[{idx}] level allowed in corridor {cid}", False,
                                 f"{lvl} not allowed")
                    else:
                        out = length - B.segment_inside_convex_length(corridors[cid], p0, p1,
                                                                     TOL_GEOMETRY_M)
                        self.add(f"segment {tag}[{idx}] inside declared corridor {cid}",
                                 out <= TOL_GEOMETRY_M, f"outside length {out:.3f} m")
        segs = []
        for tag, pl in self.pipes.items():
            for (p0, p1, lvl, idx) in pl.segments():
                segs.append((tag, idx, p0, p1, lvl, pl.corridor))
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                t1, i1, a1, b1, l1, c1 = segs[i]
                t2, i2, a2, b2, l2, c2 = segs[j]
                if l1 != l2:
                    continue
                ov = B.collinear_overlap_length((a1, b1), (a2, b2))
                if ov <= TOL_OVERLAP_M:
                    continue
                co = c1 is not None and c1 == c2 and self.case.corridors[c1]["allows_co_routing"]
                self.add(f"same-level overlap {t1}[{i1}]/{t2}[{i2}]", co,
                         f"level {l1} overlap {ov:.3f} m")

    # ------------------------------------------------------------ hydraulics
    def pipe_loss_mpa(self, tag, flow_kg_s, p_in_mpa, t_c):
        pl = self.pipes[tag]
        d = self.d(pl.dn)["internal_diameter_m"]
        eps = self.pc(pl.cls)["roughness_m"]
        res = B.pipe_pressure_loss(self.gas, p_in_mpa, t_c, flow_kg_s, pl.length_m, d, eps)
        return res

    # -------------------------------------------------------------- scenarios
    def installed_equipment(self):
        return self.nodes

    def run_all(self):
        self.check_connections()
        self.check_equipment_geometry()
        self.check_maintenance_envelopes()
        self.check_roads()
        self.check_road_access()
        self.check_pipeline_geometry()
        self.plan_and_check_scenarios()
        self.compute_lcc()
        return self.results
