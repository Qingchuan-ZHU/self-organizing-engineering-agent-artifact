"""Physical design model: equipment instances, pipes, and scenario plans.

Coordinates are metres in the site frame.  Pipe routes are given as an ordered
list of interior waypoints; the endpoints are the port coordinates.
"""
from __future__ import annotations

from .geometry import rotate


def port_xy(model: dict, x: float, y: float, ori: float, port_id: str):
    for p in model["ports"]:
        if p["id"] == port_id:
            ox, oy = p["offset_m"]
            return rotate(x + ox, y + oy, x, y, ori)
    raise KeyError(port_id)


# ----------------------------------------------------------------------------
# Equipment instances: id -> (model_id, x, y, orientation_deg)
# ----------------------------------------------------------------------------
EQUIPMENT = {
    # headers -----------------------------------------------------------------
    "WH":  ("HDR180", 180.0, 225.0, 0.0),   # well-side bidirectional header
    "WP":  ("HDR180", 320.0, 225.0, 0.0),   # well-side process header
    "X":   ("HDR180", 440.0, 225.0, 0.0),   # compression suction / process header
    "DH":  ("HDR180", 560.0, 225.0, 0.0),   # compressor discharge header
    # compression -------------------------------------------------------------
    "CMP1": ("C60", 300.0, 345.0, 0.0),
    "CMP2": ("C60", 385.0, 345.0, 0.0),
    "CMP3": ("C40", 458.0, 345.0, 0.0),
    "CLR1": ("COOL120", 620.0, 300.0, 0.0),
    "CLR2": ("COOL70", 600.0, 120.0, 0.0),
    "Y":   ("HDR180", 600.0, 190.0, 0.0),   # grid-delivery merge header
    # treatment ---------------------------------------------------------------
    "SEP1": ("SEP70", 430.0, 110.0, 0.0),
    "SEP2": ("SEP70", 430.0, 135.0, 0.0),
    "SEP3": ("SEP70", 430.0, 160.0, 0.0),
    "DHY1": ("DEHY70", 550.0, 110.0, 0.0),
    "DHY2": ("DEHY70", 550.0, 135.0, 0.0),
    "DHY3": ("DEHY70", 550.0, 160.0, 0.0),
    # pressure control / metering --------------------------------------------
    "REG1": ("REG120", 650.0, 165.0, 0.0),
    "MTR-INJ": ("MTR120", 650.0, 292.0, 0.0),
    "MTR-WDR": ("MTR120", 668.0, 170.0, 0.0),
    # drains ------------------------------------------------------------------
    "DRN1": ("DRN-S", 430.0, 62.0, 0.0),
    "DRN2": ("DRN-S", 462.0, 62.0, 0.0),
    "DRN3": ("DRN-S", 494.0, 62.0, 0.0),
}

# Interface ports (id, port_id, x, y)
INTERFACES = {
    "GRID-TIE": ("gas", 700.0, 225.0),
    "WG-01": ("gas", 12.0, 45.0),
    "WG-02": ("gas", 12.0, 117.0),
    "WG-03": ("gas", 12.0, 189.0),
    "WG-04": ("gas", 12.0, 261.0),
    "WG-05": ("gas", 12.0, 333.0),
    "WG-06": ("gas", 12.0, 405.0),
    "LIQUID-DRAIN-OUTFALL": ("drain", 680.0, 120.0),
    "ROAD-ENTRANCE": ("access", 0.0, 225.0),
}


def E(port: str):
    eq, pf = port.split(".")
    return eq, pf


# ----------------------------------------------------------------------------
# Pipes: id -> dict(from, to, waypoints, level, dn, pipe_class, corridor)
# ----------------------------------------------------------------------------
PIPES = {}

def _pipe(pid, a, b, level, dn, cls, waypoints=(), corridor=None):
    PIPES[pid] = {
        "id": pid, "from": a, "to": b, "waypoints": list(waypoints),
        "level": level, "dn": dn, "class": cls, "corridor": corridor,
    }


# well gathering / trunk ------------------------------------------------------
_pipe("PGRID-INJ", "GRID-TIE.gas", "MTR-INJ.gas_in", "ground", "DN400", "CS-WET-160",
      waypoints=[(690.0, 292.0)])
_pipe("PINJ-X", "MTR-INJ.gas_out", "X.branch_01", "ground", "DN400", "CS-WET-160")
_pipe("PWH-WP", "WH.branch_07", "WP.branch_01", "ground", "DN350", "CS-WET-160")
_pipe("PWP-CLR", "WP.branch_02", "CLR1.gas_out", "ground", "DN350", "CS-DRY-160")

# well laterals
_well_ports = ["branch_01", "branch_02", "branch_03", "branch_04", "branch_05", "branch_06"]
for i, (wg, bp) in enumerate(zip(["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"],
                                  _well_ports), start=1):
    _pipe(f"PWG{i}", f"{wg}.gas", f"WH.{bp}", "ground", "DN150", "CS-WET-160")

# treatment -------------------------------------------------------------------
_wpsep = ["branch_03", "branch_04", "branch_05"]
for i in range(1, 4):
    _pipe(f"PWP-SEP{i}", f"WP.{_wpsep[i-1]}", f"SEP{i}.gas_in", "ground", "DN200", "CS-WET-160")
    _pipe(f"PSEP-DHY{i}", f"SEP{i}.gas_out", f"DHY{i}.gas_in", "ground", "DN250", "CS-WET-160")
    _pipe(f"PDHY-X{i}", f"DHY{i}.gas_out", f"X.branch_0{1+i}", "ground", "DN250", "CS-DRY-160")

# compression -----------------------------------------------------------------
_xcomp = ["branch_06", "branch_07", "branch_08"]
for i in range(1, 4):
    _pipe(f"PX-CMP{i}", f"X.{_xcomp[i-1]}", f"CMP{i}.suction", "ground", "DN300", "CS-DRY-160")
    _pipe(f"PCMP-DH{i}", f"CMP{i}.discharge", f"DH.branch_0{i}", "ground", "DN250", "CS-DRY-160")

_pipe("PX-Y", "X.branch_05", "Y.branch_02", "ground", "DN350", "CS-DRY-160")
_pipe("PDH-CLR", "DH.branch_04", "CLR1.gas_in", "ground", "DN400", "CS-DRY-160")
_pipe("PDH-CLR2", "DH.branch_05", "CLR2.gas_in", "ground", "DN400", "CS-DRY-160")
_pipe("PCLR2-Y", "CLR2.gas_out", "Y.branch_01", "ground", "DN400", "CS-DRY-160")
_pipe("PY-REG", "Y.branch_03", "REG1.gas_in", "ground", "DN400", "CS-DRY-160")
_pipe("PREG-MTR", "REG1.gas_out", "MTR-WDR.gas_in", "ground", "DN400", "CS-DRY-160")
_pipe("PMTR-GRID", "MTR-WDR.gas_out", "GRID-TIE.gas", "ground", "DN400", "CS-DRY-160")

# drains ----------------------------------------------------------------------
for i in range(1, 4):
    _pipe(f"PSEP-DRN{i}", f"SEP{i}.liquid_out", f"DRN{i}.drain_in", "buried", "DN150", "CS-WET-100")
    _pipe(f"PDRN-OUT{i}", f"DRN{i}.drain_out", "LIQUID-DRAIN-OUTFALL.drain", "buried", "DN150",
          "CS-WET-100", waypoints=[])


# ----------------------------------------------------------------------------
# Road network (centreline polylines, width in metres).
# ----------------------------------------------------------------------------
ROADS = [
    {"id": "R-MAIN", "width": 6.0, "points": [(0.0, 225.0), (140.0, 225.0),
                                              (140.0, 205.0), (640.0, 205.0)]},
    {"id": "R-CMP", "width": 6.0, "points": [(250.0, 205.0), (250.0, 355.0),
                                             (500.0, 355.0)]},
    {"id": "R-SEP", "width": 6.0, "points": [(420.0, 205.0), (420.0, 98.0),
                                             (560.0, 98.0)]},
]


# ----------------------------------------------------------------------------
# Optimised pipe sizes (greedy LCC minimisation; see report).
# ----------------------------------------------------------------------------
_DN_OVERRIDE = {
    "PCLR2-Y": "DN450",
    "PCMP-DH1": "DN450",
    "PCMP-DH2": "DN450",
    "PCMP-DH3": "DN200",
    "PDH-CLR": "DN600",
    "PDH-CLR2": "DN450",
    "PDHY-X1": "DN250",
    "PDHY-X2": "DN250",
    "PDHY-X3": "DN250",
    "PDRN-OUT1": "DN150",
    "PDRN-OUT2": "DN150",
    "PDRN-OUT3": "DN150",
    "PGRID-INJ": "DN700",
    "PINJ-X": "DN700",
    "PMTR-GRID": "DN450",
    "PREG-MTR": "DN450",
    "PSEP-DHY1": "DN200",
    "PSEP-DHY2": "DN200",
    "PSEP-DHY3": "DN200",
    "PSEP-DRN1": "DN150",
    "PSEP-DRN2": "DN150",
    "PSEP-DRN3": "DN150",
    "PWG1": "DN200",
    "PWG2": "DN200",
    "PWG3": "DN200",
    "PWG4": "DN200",
    "PWG5": "DN200",
    "PWG6": "DN200",
    "PWH-WP": "DN700",
    "PWP-CLR": "DN600",
    "PWP-SEP1": "DN350",
    "PWP-SEP2": "DN350",
    "PWP-SEP3": "DN300",
    "PX-CMP1": "DN500",
    "PX-CMP2": "DN500",
    "PX-CMP3": "DN250",
    "PX-Y": "DN350",
    "PY-REG": "DN450",
}
for _pid, _dn in _DN_OVERRIDE.items():
    PIPES[_pid]["dn"] = _dn
