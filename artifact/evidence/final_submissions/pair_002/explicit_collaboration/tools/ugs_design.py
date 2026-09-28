"""Design definition for UGS-SYNTH-D01.

The design is described by data: equipment instances with positions and
orientations, physical connections (pipelines) with their routes, diameters and
pipe classes, a road network, and the operating plan for every published
scenario (normal operation plus the required single-unit-outage cases).

Units: m, MPa, degC, kg/s, MW, MBCU.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# equipment instances
# ---------------------------------------------------------------------------

EQUIPMENT = [
    # well-side manifold (shared by injection and withdrawal)
    dict(tag="WH-01", model="HDR180", x=30.0, y=225.0, o=0,
         role="Well-group manifold header: 6 well-group branches, 3 withdrawal train "
              "branches, 1 injection trunk branch."),
    # injection chain (flow direction south -> north, orientation 90 deg)
    dict(tag="MTR-INJ-01", model="MTR120", x=640.0, y=92.0, o=90,
         role="Injection custody meter at GRID-TIE."),
    dict(tag="HDR-INJ-SUC-01", model="HDR180", x=620.0, y=110.0, o=0,
         role="Injection compressor suction header."),
    dict(tag="CMP-INJ-01", model="C60", x=620.0, y=132.0, o=90,
         role="Injection compressor 1 (lead)."),
    dict(tag="CMP-INJ-02", model="C60", x=570.0, y=132.0, o=90,
         role="Injection compressor 2 (lead)."),
    dict(tag="CMP-INJ-03", model="C40", x=520.0, y=131.0, o=90,
         role="Injection compressor 3 (N-1 support unit)."),
    dict(tag="HDR-INJ-DIS-01", model="HDR180", x=620.0, y=168.0, o=0,
         role="Injection compressor discharge header."),
    dict(tag="COOL-INJ-01", model="COOL120", x=600.0, y=190.0, o=90,
         role="Injection aftercooler; its outlet connects directly to the injection trunk."),
    # withdrawal treatment trains (flow direction west -> east, orientation 0 deg)
    dict(tag="SEP-WDR-01", model="SEP70", x=430.0, y=210.0, o=0,
         role="Withdrawal inlet separator, train A."),
    dict(tag="SEP-WDR-02", model="SEP70", x=430.0, y=240.0, o=0,
         role="Withdrawal inlet separator, train B."),
    dict(tag="SEP-WDR-03", model="SEP70", x=430.0, y=270.0, o=0,
         role="Withdrawal inlet separator, train C."),
    dict(tag="DEHY-WDR-01", model="DEHY70", x=475.0, y=210.0, o=0,
         role="Withdrawal dehydration unit, train A."),
    dict(tag="DEHY-WDR-02", model="DEHY70", x=475.0, y=240.0, o=0,
         role="Withdrawal dehydration unit, train B."),
    dict(tag="DEHY-WDR-03", model="DEHY70", x=475.0, y=270.0, o=0,
         role="Withdrawal dehydration unit, train C."),
    dict(tag="HDR-TRT-OUT-01", model="HDR180", x=510.0, y=240.0, o=0,
         role="Treated-gas collection header; feeds the boost compressors or the bypass."),

    dict(tag="HDR-DLV-01", model="HDR180", x=585.0, y=240.0, o=0,
         role="Delivery header (bypass / boost-compressor merge)."),
    dict(tag="REG-WDR-01", model="REG120", x=620.0, y=240.0, o=0,
         role="Delivery pressure regulator at GRID-TIE."),
    dict(tag="MTR-WDR-01", model="MTR120", x=650.0, y=240.0, o=0,
         role="Withdrawal custody meter at GRID-TIE."),
    # closed drains (one per liquid-producing unit)
    dict(tag="DRN-WDR-01", model="DRN-S", x=560.0, y=36.0, o=0,
         role="Closed drain of SEP-WDR-01."),
    dict(tag="DRN-WDR-02", model="DRN-S", x=580.0, y=40.0, o=0,
         role="Closed drain of SEP-WDR-02."),
    dict(tag="DRN-WDR-03", model="DRN-S", x=600.0, y=44.0, o=0,
         role="Closed drain of SEP-WDR-03."),
]

# ---------------------------------------------------------------------------
# pipelines
#
# a / b are endpoint references:
#   ("<equipment tag>", "<port id>")  or  ("<interface id>", "<port id>")
# wp are intermediate route vertices; the first and last route points are the
# endpoint port coordinates, which the verification pass re-computes.
# level of a segment = seg_levels[i] if given else ``level``.
# ---------------------------------------------------------------------------

PIPES = [
    # ---------------- injection path ----------------
    dict(tag="P-101", a=("GRID-TIE", "gas"), b=("MTR-INJ-01", "gas_in"),
         dn="DN700", cls="CS-DRY-160", level="ground", wp=[(680.0, 225.0), (680.0, 90.0)],
         role="GRID-TIE to injection custody meter."),
    dict(tag="P-102", a=("MTR-INJ-01", "gas_out"), b=("HDR-INJ-SUC-01", "branch_02"),
         dn="DN700", cls="CS-DRY-160", level="ground", wp=[(640.0, 111.125)],
         role="Injection meter to compressor suction header."),
    dict(tag="P-103", a=("HDR-INJ-SUC-01", "branch_01"), b=("CMP-INJ-03", "suction"),
         dn="DN200", cls="CS-DRY-160", level="ground", wp=[(617.75, 113.0), (520.0, 113.0)],
         role="Suction header to injection compressor 3."),
    dict(tag="P-104", a=("HDR-INJ-SUC-01", "branch_05"), b=("CMP-INJ-02", "suction"),
         dn="DN500", cls="CS-DRY-160", level="ground", wp=[(619.25, 114.0), (570.0, 114.0)],
         role="Suction header to injection compressor 2."),
    dict(tag="P-105", a=("HDR-INJ-SUC-01", "branch_09"), b=("CMP-INJ-01", "suction"),
         dn="DN500", cls="CS-DRY-160", level="ground", wp=[(620.75, 116.0), (620.0, 116.0)],
         role="Suction header to injection compressor 1."),
    dict(tag="P-106", a=("CMP-INJ-01", "discharge"), b=("HDR-INJ-DIS-01", "branch_07"),
         dn="DN400", cls="CS-DRY-160", level="ground", wp=[(620.0, 148.0), (620.0, 158.0)],
         seg_levels={1: "rack_low"},
         role="Injection compressor 1 discharge (rack crossing over the unit access road)."),
    dict(tag="P-107", a=("CMP-INJ-02", "discharge"), b=("HDR-INJ-DIS-01", "branch_11"),
         dn="DN450", cls="CS-DRY-160", level="ground",
         wp=[(570.0, 148.0), (570.0, 158.0), (618.0, 158.0)],
         seg_levels={1: "rack_low"},
         role="Injection compressor 2 discharge (rack crossing over the unit access road)."),
    dict(tag="P-108", a=("CMP-INJ-03", "discharge"), b=("HDR-INJ-DIS-01", "branch_03"),
         dn="DN250", cls="CS-DRY-160", level="rack_high",
         wp=[(520.0, 150.0), (520.0, 160.0), (622.0, 160.0)],
         role="Injection compressor 3 discharge (elevated rack)."),
    dict(tag="P-109", a=("HDR-INJ-DIS-01", "branch_08"), b=("COOL-INJ-01", "gas_in"),
         dn="DN600", cls="CS-DRY-160", level="ground", wp=[(600.0, 168.0)],
         role="Discharge header to the injection aftercooler."),
    dict(tag="P-113", a=("COOL-INJ-01", "gas_out"), b=("WH-01", "branch_08"),
         dn="DN600", cls="CS-DRY-160", level="buried",
         wp=[(18.0, 196.0), (18.0, 225.0)],
         role="Injection trunk from the aftercooler outlet to the well-group manifold."),
    # ---------------- withdrawal, well side ----------------
    dict(tag="P-114", a=("WH-01", "branch_06"), b=("SEP-WDR-03", "gas_in"),
         dn="DN300", cls="CS-WET-160", level="buried",
         wp=[(40.0, 225.375), (40.0, 270.0)],
         role="Withdrawal trunk, train C."),
    dict(tag="P-115", a=("WH-01", "branch_10"), b=("SEP-WDR-02", "gas_in"),
         dn="DN300", cls="CS-WET-160", level="buried",
         wp=[(44.0, 224.625), (44.0, 240.0)],
         role="Withdrawal trunk, train B."),
    dict(tag="P-116", a=("WH-01", "branch_14"), b=("SEP-WDR-01", "gas_in"),
         dn="DN300", cls="CS-WET-160", level="buried",
         wp=[(38.0, 223.875), (38.0, 210.0)],
         role="Withdrawal trunk, train A."),
    # ---------------- withdrawal, treatment ----------------
    dict(tag="P-117", a=("SEP-WDR-01", "gas_out"), b=("DEHY-WDR-01", "gas_in"),
         dn="DN300", cls="CS-WET-160", level="ground", wp=[],
         role="Separator to dehydration, train A."),
    dict(tag="P-118", a=("SEP-WDR-02", "gas_out"), b=("DEHY-WDR-02", "gas_in"),
         dn="DN300", cls="CS-WET-160", level="ground", wp=[],
         role="Separator to dehydration, train B."),
    dict(tag="P-119", a=("SEP-WDR-03", "gas_out"), b=("DEHY-WDR-03", "gas_in"),
         dn="DN400", cls="CS-WET-160", level="ground", wp=[],
         role="Separator to dehydration, train C."),
    dict(tag="P-120", a=("DEHY-WDR-01", "gas_out"), b=("HDR-TRT-OUT-01", "branch_04"),
         dn="DN350", cls="CS-DRY-160", level="ground", wp=[(500.0, 210.0), (500.0, 239.0)],
         role="Dehydration to treated-gas header, train A."),
    dict(tag="P-121", a=("DEHY-WDR-02", "gas_out"), b=("HDR-TRT-OUT-01", "branch_08"),
         dn="DN300", cls="CS-DRY-160", level="ground", wp=[],
         role="Dehydration to treated-gas header, train B."),
    dict(tag="P-122", a=("DEHY-WDR-03", "gas_out"), b=("HDR-TRT-OUT-01", "branch_12"),
         dn="DN350", cls="CS-DRY-160", level="ground", wp=[(503.0, 270.0), (503.0, 241.0)],
         role="Dehydration to treated-gas header, train C."),
    dict(tag="P-123", a=("HDR-TRT-OUT-01", "branch_06"), b=("HDR-DLV-01", "branch_08"),
         dn="DN350", cls="CS-DRY-160", level="rack_low",
         wp=[(582.0, 240.375)],
         role="Delivery bypass around the compressor boost path (WDR-HIGH and WDR-MID)."),
    dict(tag="P-143", a=("HDR-TRT-OUT-01", "branch_03"), b=("HDR-INJ-SUC-01", "branch_08"),
         dn="DN500", cls="CS-DRY-160", level="ground",
         wp=[(512.0, 232.0), (590.0, 232.0), (590.0, 110.0)],
         role="Treated gas to the compressor suction header: feeds the boost service "
              "(WDR-LOW) through the injection compressor set."),
    dict(tag="P-144", a=("HDR-INJ-DIS-01", "branch_02"), b=("HDR-DLV-01", "branch_09"),
         dn="DN450", cls="CS-DRY-160", level="ground",
         wp=[(628.0, 169.125), (628.0, 250.0), (585.75, 250.0)],
         role="Boost-service discharge from the compressor discharge header to the "
              "delivery header."),
    dict(tag="P-128", a=("HDR-DLV-01", "branch_02"), b=("REG-WDR-01", "gas_in"),
         dn="DN450", cls="CS-DRY-160", level="ground",
         wp=[(605.0, 241.125), (605.0, 240.0)],
         role="Delivery header to pressure regulator."),
    dict(tag="P-129", a=("REG-WDR-01", "gas_out"), b=("MTR-WDR-01", "gas_in"),
         dn="DN450", cls="CS-DRY-160", level="ground", wp=[],
         role="Regulator to withdrawal custody meter."),
    dict(tag="P-130", a=("MTR-WDR-01", "gas_out"), b=("GRID-TIE", "gas"),
         dn="DN450", cls="CS-DRY-160", level="ground",
         wp=[(700.0, 240.0)],
         role="Withdrawal custody meter to GRID-TIE."),
    # ---------------- well-group branches ----------------
    dict(tag="P-131", a=("WH-01", "branch_09"), b=("WG-06", "gas"),
         dn="DN300", cls="CS-WET-160", level="ground", wp=[(30.75, 405.0)],
         role="Well-group branch WG-06."),
    dict(tag="P-132", a=("WH-01", "branch_05"), b=("WG-05", "gas"),
         dn="DN300", cls="CS-WET-160", level="ground", wp=[(29.25, 333.0)],
         role="Well-group branch WG-05."),
    dict(tag="P-133", a=("WH-01", "branch_01"), b=("WG-04", "gas"),
         dn="DN250", cls="CS-WET-160", level="ground", wp=[(27.75, 261.0)],
         role="Well-group branch WG-04."),
    dict(tag="P-134", a=("WH-01", "branch_11"), b=("WG-03", "gas"),
         dn="DN250", cls="CS-WET-160", level="ground", wp=[(28.0, 189.0)],
         role="Well-group branch WG-03."),
    dict(tag="P-135", a=("WH-01", "branch_07"), b=("WG-02", "gas"),
         dn="DN300", cls="CS-WET-160", level="ground", wp=[(30.0, 117.0)],
         role="Well-group branch WG-02."),
    dict(tag="P-136", a=("WH-01", "branch_03"), b=("WG-01", "gas"),
         dn="DN300", cls="CS-WET-160", level="ground", wp=[(32.0, 45.0)],
         role="Well-group branch WG-01."),
    # ---------------- liquid drain system ----------------
    dict(tag="P-137", a=("SEP-WDR-01", "liquid_out"), b=("DRN-WDR-01", "drain_in"),
         dn="DN150", cls="CS-WET-100", level="buried",
         wp=[(418.0, 208.0), (418.0, 36.0)],
         service="liquid_drain",
         role="Separator train A liquid drain line."),
    dict(tag="P-138", a=("SEP-WDR-02", "liquid_out"), b=("DRN-WDR-02", "drain_in"),
         dn="DN150", cls="CS-WET-100", level="buried",
         wp=[(414.0, 238.0), (414.0, 40.0)],
         service="liquid_drain",
         role="Separator train B liquid drain line."),
    dict(tag="P-139", a=("SEP-WDR-03", "liquid_out"), b=("DRN-WDR-03", "drain_in"),
         dn="DN150", cls="CS-WET-100", level="buried",
         wp=[(410.0, 268.0), (410.0, 44.0)],
         service="liquid_drain",
         role="Separator train C liquid drain line."),
    dict(tag="P-140", a=("DRN-WDR-01", "drain_out"), b=("LIQUID-DRAIN-OUTFALL", "drain"),
         dn="DN150", cls="CS-WET-100", level="buried",
         wp=[(680.0, 36.0)],
         service="liquid_drain",
         role="Closed drain 1 discharge to outfall."),
    dict(tag="P-141", a=("DRN-WDR-02", "drain_out"), b=("LIQUID-DRAIN-OUTFALL", "drain"),
         dn="DN150", cls="CS-WET-100", level="buried",
         wp=[(665.0, 40.0), (665.0, 120.0)],
         service="liquid_drain",
         role="Closed drain 2 discharge to outfall."),
    dict(tag="P-142", a=("DRN-WDR-03", "drain_out"), b=("LIQUID-DRAIN-OUTFALL", "drain"),
         dn="DN150", cls="CS-WET-100", level="buried",
         wp=[(660.0, 44.0), (660.0, 140.0), (680.0, 140.0)],
         service="liquid_drain",
         role="Closed drain 3 discharge to outfall."),
]

# ---------------------------------------------------------------------------
# roads (centreline polylines with width)
# ---------------------------------------------------------------------------

ROADS = [
    dict(tag="RD-01", width_m=8.0,
         pts=[(4.0, 225.0), (18.0, 225.0), (18.0, 300.0), (690.0, 300.0)],
         role="Main site access road from ROAD-ENTRANCE, running along the south of the "
              "withdrawal train area."),
    dict(tag="RD-02", width_m=8.0, pts=[(690.0, 300.0), (690.0, 151.5)],
         role="Access spine on the east side of the site."),
    dict(tag="RD-03", width_m=6.0, pts=[(690.0, 151.5), (510.0, 151.5)],
         role="Injection compressor maintenance road (crane access for heavy maintenance)."),
    dict(tag="RD-05", width_m=6.0, pts=[(418.0, 300.0), (418.0, 200.0)],
         role="Separator maintenance road."),
]

# interface / sink definitions per scenario are added in ugs_check.
