"""Design definition for UGS-SYNTH-D01 v1.1.

Coordinates in metres (site frame). Levels: ground / buried / rack_low / rack_high.

Injection train (grid -> wells) runs east-to-west:
  GRID-TIE -> MTR-I -> HDR-CS -> C-1/C-2 -> HDR-CD -> COOL -> HDR-W -> wells
Withdrawal train (wells -> grid) runs west-to-east:
  wells -> HDR-W -> REG-W -> HDR-R -> {SEP-x, DEH-x} -> HDR-T -> (HDR-M) or (HDR-CS boost) -> MTR-O -> GRID-TIE
The compressor bank is shared between injection and withdrawal boost service via headers.
"""

EQUIPMENT = {
    # ---- well-side manifold and withdrawal train
    "HDR-W":  ("HDR120", 150.0, 225.0, 0),
    "REG-W":  ("REG180", 215.0, 225.0, 0),
    "HDR-R":  ("HDR120", 265.0, 225.0, 0),
    "SEP-1":  ("SEP120", 330.0, 170.0, 0),
    "DEH-1":  ("DEHY120", 425.0, 170.0, 0),
    "SEP-2":  ("SEP120", 330.0, 280.0, 0),
    "DEH-2":  ("DEHY120", 425.0, 280.0, 0),
    "HDR-T":  ("HDR120", 490.0, 225.0, 0),
    "HDR-M":  ("HDR120", 535.0, 225.0, 0),
    "MTR-O":  ("MTR160", 620.0, 225.0, 0),
    # ---- injection train
    "MTR-I":  ("MTR160", 620.0, 300.0, 0),
    "HDR-CS": ("HDR120", 440.0, 320.0, 0),
    "HDR-CD": ("HDR120", 440.0, 430.0, 0),
    "COOL":   ("COOL120", 300.0, 425.0, 0),
    "C-1":    ("C60", 350.0, 380.0, 90),
    "C-2":    ("C60", 440.0, 380.0, 90),
    "C-3":    ("C40", 525.0, 380.0, 90),
    # ---- liquid handling
    "DRN-1":  ("DRN-L", 330.0, 140.0, 0),
    "DRN-2":  ("DRN-L", 330.0, 305.0, 0),
}

STUB = 3.0

PIPES = {
    # injection feed
    "G-TIE-IN": dict(a="GRID-TIE.gas", b="MTR-I.gas_in", via=[(660.0, 270.0), (600.0, 300.0)], dia="DN700", cls="CS-WET-100", level="ground"),
    "G-IN-1":   dict(a="MTR-I.gas_out", b="HDR-CS.branch_03", via=[(625.0, 315.0), (441.5, 315.0)], dia="DN700", cls="CS-WET-100", level="ground"),
    # compressor suctions
    "G-C1S":    dict(a="HDR-CS.branch_04", b="C-1.suction", via=[(330.0, 319.25), (330.0, 369.5)], dia="DN600", cls="CS-WET-100", level="ground"),
    "G-C2S":    dict(a="HDR-CS.branch_05", b="C-2.suction", via=[], dia="DN600", cls="CS-WET-100", level="ground"),
    "G-C3S":    dict(a="HDR-CS.branch_02", b="C-3.suction", via=[(545.0, 319.5), (545.0, 371.0)], dia="DN250", cls="CS-WET-100", level="ground"),
    # compressor discharges
    "G-C1D":    dict(a="C-1.discharge", b="HDR-CD.branch_08", via=[(330.0, 390.5), (330.0, 428.5), (434.0, 428.5)], dia="DN450", cls="CS-WET-160", level="ground"),
    "G-C2D":    dict(a="C-2.discharge", b="HDR-CD.branch_07", via=[], dia="DN450", cls="CS-WET-160", level="ground"),
    "G-C3D":    dict(a="C-3.discharge", b="HDR-CD.branch_10", via=[(545.0, 389.0), (545.0, 427.0), (446.0, 427.0)], dia="DN200", cls="CS-WET-160", level="ground"),
    # injection conditioning
    "G-CD-CL":  dict(a="HDR-CD.branch_04", b="COOL.gas_in", via=[(310.0, 412.0), (285.0, 412.0), (285.0, 425.0)], dia="DN600", cls="CS-WET-160", level="ground"),
    "G-CL-W":   dict(a="COOL.gas_out", b="HDR-W.branch_02", via=[(340.0, 445.0), (90.0, 445.0), (90.0, 240.0), (156.0, 240.0)], dia="DN600", cls="CS-WET-160", level="ground"),
    # well manifold -> wells
    "G-W-1":    dict(a="HDR-W.branch_01", b="WG-01.gas", via=[], dia="DN250", cls="CS-WET-160", level="ground"),
    "G-W-2":    dict(a="HDR-W.branch_04", b="WG-02.gas", via=[], dia="DN250", cls="CS-WET-160", level="ground"),
    "G-W-3":    dict(a="HDR-W.branch_05", b="WG-03.gas", via=[(135.0, 216.0)], dia="DN250", cls="CS-WET-160", level="ground"),
    "G-W-4":    dict(a="HDR-W.branch_07", b="WG-04.gas", via=[], dia="DN250", cls="CS-WET-160", level="ground"),
    "G-W-5":    dict(a="HDR-W.branch_03", b="WG-05.gas", via=[(140.0, 213.0)], dia="DN250", cls="CS-WET-160", level="ground"),
    "G-W-6":    dict(a="HDR-W.branch_08", b="WG-06.gas", via=[], dia="DN250", cls="CS-WET-160", level="ground"),
    # withdrawal train
    "G-W-REG":  dict(a="HDR-W.branch_06", b="REG-W.gas_in", via=[], dia="DN600", cls="CS-WET-160", level="ground"),
    "G-REG-R":  dict(a="REG-W.gas_out", b="HDR-R.branch_01", via=[], dia="DN600", cls="CS-WET-100", level="ground"),
    "G-R-S1":   dict(a="HDR-R.branch_02", b="SEP-1.gas_in", via=[(300.0, 210.0)], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-R-S2":   dict(a="HDR-R.branch_03", b="SEP-2.gas_in", via=[(300.0, 240.0)], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-S1-D1":  dict(a="SEP-1.gas_out", b="DEH-1.gas_in", via=[], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-S2-D2":  dict(a="SEP-2.gas_out", b="DEH-2.gas_in", via=[], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-D1-T":   dict(a="DEH-1.gas_out", b="HDR-T.branch_01", via=[(455.0, 190.0)], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-D2-T":   dict(a="DEH-2.gas_out", b="HDR-T.branch_02", via=[(460.0, 258.0)], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-T-M":    dict(a="HDR-T.branch_03", b="HDR-M.branch_01", via=[(505.0, 215.0)], dia="DN400", cls="CS-WET-100", level="ground"),
    "G-M-TO":   dict(a="HDR-M.branch_03", b="MTR-O.gas_in", via=[(590.0, 220.5)], dia="DN500", cls="CS-WET-100", level="ground"),
    "G-TO-TIE": dict(a="MTR-O.gas_out", b="GRID-TIE.gas", via=[], dia="DN500", cls="CS-WET-100", level="ground"),
    # withdrawal boost
    "G-T-CS":   dict(a="HDR-T.branch_04", b="HDR-CS.branch_07", via=[(435.0, 290.0), (435.0, 315.0), (438.5, 315.0)], dia="DN600", cls="CS-WET-100", level="ground"),
    "G-CD-M":   dict(a="HDR-CD.branch_01", b="HDR-M.branch_02", via=[(541.0, 434.5), (541.0, 300.0)], dia="DN500", cls="CS-WET-100", level="ground"),
    # liquid drains
    "L-S1":     dict(a="SEP-1.liquid_out", b="DRN-1.drain_in", via=[], dia="DN150", cls="CS-WET-100", level="ground", medium="liquid"),
    "L-S2":     dict(a="SEP-2.liquid_out", b="DRN-2.drain_in", via=[(320.0, 274.5), (320.0, 305.0)], dia="DN150", cls="CS-WET-100", level="ground", medium="liquid"),
    "L-D1-O":   dict(a="DRN-1.drain_out", b="LIQUID-DRAIN-OUTFALL.drain", via=[(360.0, 120.0), (660.0, 120.0)], dia="DN150", cls="CS-WET-100", level="ground", medium="liquid"),
    "L-D2-O":   dict(a="DRN-2.drain_out", b="LIQUID-DRAIN-OUTFALL.drain", via=[(370.0, 310.0), (370.0, 150.0)], dia="DN150", cls="CS-WET-100", level="ground", medium="liquid"),
}

ROADS = {
    "R-A": dict(pts=[(0.0, 225.0), (100.0, 225.0)], width=6.0),
    "R-B": dict(pts=[(100.0, 110.0), (100.0, 430.0)], width=6.0),
    "R-C": dict(pts=[(100.0, 110.0), (620.0, 110.0)], width=6.0),
    "R-D": dict(pts=[(100.0, 178.0), (620.0, 178.0)], width=6.0),
    "R-E": dict(pts=[(100.0, 290.0), (545.0, 290.0)], width=6.0),
    "R-F": dict(pts=[(100.0, 365.0), (545.0, 365.0)], width=6.0),
}

WELL_IDS = ["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"]
WELL_PIPES = ["G-W-1", "G-W-2", "G-W-3", "G-W-4", "G-W-5", "G-W-6"]

METER_ACTIVE = {
    "INJ-LOW": ["MTR-I"], "INJ-MID": ["MTR-I"], "INJ-HIGH": ["MTR-I"],
    "WDR-HIGH": ["MTR-O"], "WDR-MID": ["MTR-O"], "WDR-LOW": ["MTR-O"],
}
