"""
UGS-SYNTH-D01 v1.1 design definition.

Defines the proposed equipment instances, the physical process topology
(ports + pipelines + routes), and the scenario operating paths.

Coordinate system: brief/site.json (metres).  Equipment footprints are
axis-aligned rectangles (all instances use orientation 0 or 90 deg, both of
which keep a rectangle axis-aligned).
"""
from __future__ import annotations

import json
import math
import os

import ugslib as U
from ugslib import CATALOG

# ---------------------------------------------------------------------------
# Equipment instances
# ---------------------------------------------------------------------------
# id: (model_id, cx, cy, orientation_deg, short description / duty)
EQUIPMENT_SPEC = [
    # ---- well-group manifold -------------------------------------------------
    ("HM",  "HDR180", 70.0,  250.0, 0,  "well-group gas manifold (6 wells)"),
    # ---- withdrawal treatment: separation ------------------------------------
    ("SEP1", "SEP70", 200.0, 200.0, 0,  "inlet separator A"),
    ("SEP2", "SEP70", 200.0, 216.0, 0,  "inlet separator B"),
    ("SEP3", "SEP70", 200.0, 232.0, 0,  "inlet separator C"),
    ("HSI", "HDR120", 150.0, 216.0, 0,  "separator inlet manifold"),
    ("HSD", "HDR120", 270.0, 216.0, 0,  "separator outlet / dehydration inlet manifold"),
    # ---- withdrawal treatment: dehydration -----------------------------------
    ("DH1", "DEHY70", 330.0, 200.0, 0,  "dehydration unit A"),
    ("DH2", "DEHY70", 330.0, 216.0, 0,  "dehydration unit B"),
    ("DH3", "DEHY70", 330.0, 232.0, 0,  "dehydration unit C"),
    # ---- compression station -------------------------------------------------
    ("HCS", "HDR120", 505.0, 210.0, 0,  "compressor suction manifold"),
    ("HCD", "HDR120", 505.0, 300.0, 0,  "compressor discharge manifold"),
    ("C1", "C60", 480.0, 250.0, 90, "compression unit A (base load)"),
    ("C2", "C60", 510.0, 250.0, 90, "compression unit B (base load)"),
    ("C3", "C40", 538.0, 250.0, 90, "compression unit C (N-1 / trim)"),
    # ---- injection after-cooling --------------------------------------------
    ("COOL", "COOL120", 505.0, 330.0, 90, "injection after-cooler"),
    # ---- delivery pressure control / metering --------------------------------
    ("REG", "REG120", 600.0, 300.0, 0,  "withdrawal delivery regulator"),
    ("MI", "MTR120", 655.0, 215.0, 90, "injection (import) fiscal meter"),
    ("MW", "MTR120", 655.0, 260.0, 0,  "withdrawal (export) fiscal meter"),
    # ---- liquid handling -----------------------------------------------------
    ("D1", "DRN-S", 400.0, 130.0, 0, "closed drain A"),
    ("D2", "DRN-S", 400.0, 140.0, 0, "closed drain B"),
    ("D3", "DRN-S", 400.0, 150.0, 0, "closed drain C"),
]

EQUIPMENT = {}
for _eid, _model, _cx, _cy, _ori, _desc in EQUIPMENT_SPEC:
    _m = CATALOG[_model]
    EQUIPMENT[_eid] = {
        "id": _eid,
        "model_id": _model,
        "category": _m["category"],
        "safety_category": _m["safety_category"],
        "cx": _cx, "cy": _cy, "orientation_deg": _ori,
        "description": _desc,
        "model": _m,
    }


def port_xy(eid, port_id):
    """Absolute plan coordinates of an equipment port."""
    e = EQUIPMENT[eid]
    m = e["model"]
    off = next(p["offset_m"] for p in m["ports"] if p["id"] == port_id)
    dx, dy = U.rotate((off[0], off[1]), e["orientation_deg"])
    return (e["cx"] + dx, e["cy"] + dy)


def port_type(eid, port_id):
    m = EQUIPMENT[eid]["model"]
    return next(p["type"] for p in m["ports"] if p["id"] == port_id)


# ---------------------------------------------------------------------------
# Boundary interfaces (from site.json / well_group_interfaces.json)
# ---------------------------------------------------------------------------
def boundary_xy(interface_id):
    for iface in U.SITE["external_interfaces"]:
        if iface["interface_id"] == interface_id:
            return tuple(iface["point_m"])
    raise KeyError(interface_id)


BOUNDARY_PORTS = {
    "GRID-TIE": ("gas_bidirectional", boundary_xy("GRID-TIE")),
    "LIQUID-DRAIN-OUTFALL": ("drain_in", boundary_xy("LIQUID-DRAIN-OUTFALL")),
    "ROAD-ENTRANCE": ("road_access", boundary_xy("ROAD-ENTRANCE")),
}
for _wg in U.WELL_GROUPS["well_groups"]:
    BOUNDARY_PORTS[_wg["interface_id"]] = (_wg["port_type"], tuple(_wg["point_m"]))


# ---------------------------------------------------------------------------
# Pipelines.  Each entry: id -> dict
#   src / dst : ("E", equipment_id, port_id) or ("B", interface_id, port_id)
#   route     : [ (x,y), ... ]  ordered waypoints, first = source port,
#               last = destination port
#   dn        : nominal diameter key
#   cls       : pipe class id
#   level     : ground | buried | rack_low | rack_high
#   service   : gas | liquid_drain
#   corridor  : optional declared co-routing corridor id
# ---------------------------------------------------------------------------
def P(src, dst, route, dn, cls, level="ground", service="gas", corridor=None, pid=None):
    return {"id": pid, "src": src, "dst": dst, "route": [tuple(p) for p in route],
            "dn": dn, "cls": cls, "level": level, "service": service,
            "corridor": corridor}


_WG_XY = {wg["interface_id"]: tuple(wg["point_m"]) for wg in U.WELL_GROUPS["well_groups"]}
_OUTFALL = boundary_xy("LIQUID-DRAIN-OUTFALL")
_GRID = boundary_xy("GRID-TIE")

PIPELINE_SPEC = [
    # ---------------- well-group branches (bidirectional gas) ----------------
    P(("E", "HM", "branch_11"), ("B", "WG-01", "gas"),
      [(68, 248.5), (68, 244), (40, 244), (40, 45), (12, 45)], "DN350", "CS-WET-160"),
    P(("E", "HM", "branch_07"), ("B", "WG-02", "gas"),
      [(70, 248.5), (70, 242), (46, 242), (46, 117), (12, 117)], "DN300", "CS-WET-160"),
    P(("E", "HM", "branch_03"), ("B", "WG-03", "gas"),
      [(72, 248.5), (72, 240), (52, 240), (52, 189), (12, 189)], "DN300", "CS-WET-160"),
    P(("E", "HM", "branch_04"), ("B", "WG-04", "gas"),
      [(67, 249), (58, 249), (58, 261), (12, 261)], "DN250", "CS-WET-160"),
    P(("E", "HM", "branch_08"), ("B", "WG-05", "gas"),
      [(67, 250), (54, 250), (54, 333), (12, 333)], "DN300", "CS-WET-160"),
    P(("E", "HM", "branch_12"), ("B", "WG-06", "gas"),
      [(67, 251), (50, 251), (50, 405), (12, 405)], "DN300", "CS-WET-160"),
    # ---------------- withdrawal trunk: HM -> separator manifold ------------
    P(("E", "HM", "branch_05"), ("E", "HSI", "branch_05"),
      [(69.25, 251.5), (69.25, 262), (130, 262), (130, 230), (150, 230), (150, 217.5)],
      "DN600", "CS-WET-160"),
    # ---------------- separator manifold -> separators ----------------------
    P(("E", "HSI", "branch_04"), ("E", "SEP1", "gas_in"),
      [(147, 215.25), (190, 215.25), (190, 200), (196, 200)], "DN250", "CS-WET-160"),
    P(("E", "HSI", "branch_08"), ("E", "SEP2", "gas_in"),
      [(147, 216.75), (188, 216.75), (188, 216), (196, 216)], "DN250", "CS-WET-160"),
    P(("E", "HSI", "branch_07"), ("E", "SEP3", "gas_in"),
      [(148.5, 214.5), (186, 214.5), (186, 232), (196, 232)], "DN250", "CS-WET-160"),
    # ---------------- separators -> combined manifold -----------------------
    P(("E", "SEP1", "gas_out"), ("E", "HSD", "branch_04"),
      [(204, 200), (240, 200), (240, 215.25), (267, 215.25)], "DN300", "CS-WET-160"),
    P(("E", "SEP2", "gas_out"), ("E", "HSD", "branch_08"),
      [(204, 216), (238, 216), (238, 216.75), (267, 216.75)], "DN300", "CS-WET-160"),
    P(("E", "SEP3", "gas_out"), ("E", "HSD", "branch_03"),
      [(204, 232), (236, 232), (236, 210), (271.5, 210), (271.5, 214.5)], "DN300", "CS-WET-160"),
    # ---------------- combined manifold -> dehydration ----------------------
    P(("E", "HSD", "branch_02"), ("E", "DH1", "gas_in"),
      [(273, 217), (300, 217), (300, 200), (325, 200)], "DN250", "CS-WET-160"),
    P(("E", "HSD", "branch_06"), ("E", "DH2", "gas_in"),
      [(273, 216), (325, 216)], "DN250", "CS-WET-160"),
    P(("E", "HSD", "branch_10"), ("E", "DH3", "gas_in"),
      [(273, 215), (296, 215), (296, 232), (325, 232)], "DN250", "CS-WET-160"),
    # ---------------- dehydration -> compressor suction manifold ------------
    P(("E", "DH1", "gas_out"), ("E", "HCS", "branch_04"),
      [(335, 200), (370, 200), (370, 209.25), (502, 209.25)], "DN250", "CS-WET-160"),
    P(("E", "DH2", "gas_out"), ("E", "HCS", "branch_08"),
      [(335, 216), (374, 216), (374, 210.75), (502, 210.75)], "DN250", "CS-WET-160"),
    P(("E", "DH3", "gas_out"), ("E", "HCS", "branch_07"),
      [(335, 232), (378, 232), (378, 204), (503.5, 204), (503.5, 208.5)], "DN300", "CS-WET-160"),
    # ---------------- suction manifold -> compressors -----------------------
    P(("E", "HCS", "branch_01"), ("E", "C1", "suction"),
      [(503, 211.5), (503, 236), (480, 236), (480, 242.5)], "DN600", "CS-WET-100"),
    P(("E", "HCS", "branch_05"), ("E", "C2", "suction"),
      [(505, 211.5), (505, 238), (510, 238), (510, 242.5)], "DN600", "CS-WET-100"),
    P(("E", "HCS", "branch_09"), ("E", "C3", "suction"),
      [(507, 211.5), (507, 240), (538, 240), (538, 244)], "DN200", "CS-WET-100"),
    # ---------------- compressors -> discharge manifold ---------------------
    P(("E", "C1", "discharge"), ("E", "HCD", "branch_04"),
      [(480, 257.5), (480, 262), (499, 262), (499, 299.25), (502, 299.25)], "DN500", "CS-WET-160"),
    P(("E", "C2", "discharge"), ("E", "HCD", "branch_07"),
      [(510, 257.5), (510, 264), (503.5, 264), (503.5, 298.5)], "DN450", "CS-WET-160"),
    P(("E", "C3", "discharge"), ("E", "HCD", "branch_08"),
      [(538, 256), (538, 268), (495, 268), (495, 300.75), (502, 300.75)], "DN200", "CS-WET-160"),
    # ---------------- compressor-station bypass -----------------------------
    P(("E", "HCS", "branch_10"), ("E", "HCD", "branch_03"),
      [(508, 209), (548, 209), (548, 285), (506.5, 285), (506.5, 298.5)], "DN350", "CS-WET-160"),
    # ---------------- discharge manifold -> after-cooler --------------------
    P(("E", "HCD", "branch_01"), ("E", "COOL", "gas_in"),
      [(503, 301.5), (503, 318), (505, 318), (505, 324)], "DN600", "CS-WET-160"),
    # ---------------- after-cooler -> well manifold -------------------------
    P(("E", "COOL", "gas_out"), ("E", "HM", "branch_01"),
      [(505, 336), (150, 336), (150, 255), (67.75, 255), (67.75, 251.5)], "DN600", "CS-WET-160"),
    # ---------------- discharge manifold -> withdrawal regulator ------------
    P(("E", "HCD", "branch_02"), ("E", "REG", "gas_in"),
      [(508, 301), (560, 301), (560, 300), (597.5, 300)], "DN500", "CS-WET-160"),
    # ---------------- regulator -> export meter -----------------------------
    P(("E", "REG", "gas_out"), ("E", "MW", "gas_in"),
      [(602.5, 300), (630, 300), (630, 260), (653, 260)], "DN500", "CS-WET-100"),
    # ---------------- export meter -> GRID-TIE ------------------------------
    P(("E", "MW", "gas_out"), ("B", "GRID-TIE", "gas"),
      [(657, 260), (693, 260), (693, 232), (700, 232), (700, 225)], "DN500", "CS-WET-100"),
    # ---------------- GRID-TIE -> import meter ------------------------------
    P(("B", "GRID-TIE", "gas"), ("E", "MI", "gas_in"),
      [(700, 225), (693, 225), (693, 208), (655, 208), (655, 213)], "DN700", "CS-WET-100"),
    # ---------------- import meter -> suction manifold ----------------------
    P(("E", "MI", "gas_out"), ("E", "HCS", "branch_06"),
      [(655, 217), (655, 220), (600, 220), (600, 205), (515, 205), (515, 210), (508, 210)],
      "DN700", "CS-WET-100"),
    # ---------------- separator liquid lines to closed drains ---------------
    P(("E", "SEP1", "liquid_out"), ("E", "D1", "drain_in"),
      [(200, 198), (240, 198), (240, 130), (399, 130)], "DN150", "CS-WET-100",
      level="ground", service="liquid_drain"),
    P(("E", "SEP2", "liquid_out"), ("E", "D2", "drain_in"),
      [(200, 214), (230, 214), (230, 140), (399, 140)], "DN150", "CS-WET-100",
      level="ground", service="liquid_drain"),
    P(("E", "SEP3", "liquid_out"), ("E", "D3", "drain_in"),
      [(200, 230), (220, 230), (220, 150), (399, 150)], "DN150", "CS-WET-100",
      level="ground", service="liquid_drain"),
    # ---------------- closed drains to liquid outfall -----------------------
    P(("E", "D1", "drain_out"), ("B", "LIQUID-DRAIN-OUTFALL", "drain"),
      [(401, 130), (660, 130), (660, 120), (680, 120)], "DN150", "CS-WET-100",
      level="ground", service="liquid_drain"),
    P(("E", "D2", "drain_out"), ("B", "LIQUID-DRAIN-OUTFALL", "drain"),
      [(401, 140), (676, 140), (676, 132), (680, 132), (680, 120)], "DN150", "CS-WET-100",
      level="ground", service="liquid_drain"),
    P(("E", "D3", "drain_out"), ("B", "LIQUID-DRAIN-OUTFALL", "drain"),
      [(401, 150), (672, 150), (672, 100), (680, 100), (680, 120)], "DN150", "CS-WET-100",
      level="ground", service="liquid_drain"),
]

PIPELINES = {}
for _i, _p in enumerate(PIPELINE_SPEC, start=1):
    _p = dict(_p)
    _p["id"] = "PL-%02d" % _i
    PIPELINES[_p["id"]] = _p


# Optional frozen pipe-size selection produced by calc/optimize.py.
# If present it overrides the nominal sizes written in PIPELINE_SPEC above.
_SIZES = os.path.join(os.path.dirname(__file__), "..", "data", "pipe_sizes.json")
if os.path.exists(_SIZES):
    with open(_SIZES, "r", encoding="utf-8") as _fh:
        for _pid, _v in json.load(_fh).items():
            if _pid in PIPELINES:
                PIPELINES[_pid]["dn"] = _v["dn"]
                PIPELINES[_pid]["cls"] = _v["cls"]


def pipe_length(pid):
    pts = PIPELINES[pid]["route"]
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def pipe_endpoint(pid, which):
    """Plan coordinate of the source ('src') or destination ('dst') end."""
    e = PIPELINES[pid]
    ref = e["src"] if which == "src" else e["dst"]
    if ref[0] == "E":
        return port_xy(ref[1], ref[2])
    return boundary_xy(ref[1])


# ---------------------------------------------------------------------------
# Roads
# ---------------------------------------------------------------------------
ROADS = [
    {"id": "R1", "centreline": [(2.5, 225), (690, 225)], "width_m": 5.0,
     "desc": "main site access road from ROAD-ENTRANCE"},
    {"id": "R2", "centreline": [(470, 225), (470, 276)], "width_m": 8.0,
     "desc": "north spur to compression station"},
    {"id": "R3", "centreline": [(456, 270), (564, 270)], "width_m": 8.0,
     "desc": "compression station crane/road access spur"},
    {"id": "R4", "centreline": [(188, 225), (188, 195)], "width_m": 8.0,
     "desc": "separator maintenance access spur"},
]
