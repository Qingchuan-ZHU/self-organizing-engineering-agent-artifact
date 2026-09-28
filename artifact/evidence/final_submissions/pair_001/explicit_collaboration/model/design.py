"""Physical design definition for UGS-SYNTH-D01 (synthetic benchmark case).

Everything here is a design *choice* made by this project.  Published data
(catalogue, site, scenarios, economics) is read through ``catalog``.

Coordinate system: site coordinates (m), x east, y north, origin at the
south-west corner of the site boundary.

Levels: ``ground`` (at grade piping), ``buried`` (drains and road crossings),
``rack_low`` (unused), ``rack_high`` (unused).
"""

# ---------------------------------------------------------------- equipment
# id, model, (x, y), orientation_deg
EQUIPMENT = [
    # --- well manifold (west) ------------------------------------------
    ("H-WELL", "HDR120", (90.0, 180.0), 0),
    # --- station headers ------------------------------------------------
    ("H-SITE", "HDR120", (250.0, 140.0), 0),
    ("H-SUC", "HDR120", (430.0, 140.0), 0),
    ("H-DIS", "HDR120", (545.0, 140.0), 0),
    # --- withdrawal treatment train: 3 parallel lanes -------------------
    ("SEP-A", "SEP70", (290.0, 70.0), 0),
    ("SEP-B", "SEP70", (290.0, 140.0), 0),
    ("SEP-C", "SEP70", (290.0, 210.0), 0),
    ("DEH-A", "DEHY70", (380.0, 70.0), 0),
    ("DEH-B", "DEHY70", (380.0, 140.0), 0),
    ("DEH-C", "DEHY70", (380.0, 210.0), 0),
    # --- compression: 3 parallel units ---------------------------------
    ("CMP-A", "C60", (480.0, 70.0), 0),
    ("CMP-B", "C60", (480.0, 140.0), 0),
    ("CMP-C", "C60", (480.0, 210.0), 0),
    # --- injection aftercooler / withdrawal pressure control -----------
    ("COOL", "COOL120", (560.0, 190.0), 90),
    ("REG", "REG120", (580.0, 205.0), 0),
    # --- grid-tie metering ---------------------------------------------
    ("MTR-A", "MTR120", (620.0, 225.0), 90),   # injection meter
    ("MTR-B", "MTR120", (620.0, 270.0), 90),   # withdrawal meter
    # --- closed drains (one per separator) -----------------------------
    ("DRN-A", "DRN-S", (280.0, 55.0), 0),
    ("DRN-B", "DRN-S", (280.0, 125.0), 0),
    ("DRN-C", "DRN-S", (280.0, 195.0), 0),
]

# ---------------------------------------------------------------- roads
# id, centreline, width_m
ROADS = [
    ("RD-MAIN", [(4.0, 225.0), (560.0, 225.0)], 8.0),
    ("RD-CRANE", [(505.0, 225.0), (505.0, 50.0)], 6.0),
    ("RD-SEP", [(302.0, 225.0), (302.0, 50.0)], 6.0),
]

# ---------------------------------------------------------------- pipelines
# Each entry:
#   id, src(node,port), dst(node,port), waypoints, DN, class_id, base level,
#   service ('gas' | 'liquid'), note
#
# The waypoint list *includes* the end points; the first segment leaves the
# source port along its outward normal and the last segment arrives at the
# destination port along its outward normal.
PIPELINES = [
    # ---- grid tie / metering ------------------------------------------
    ("P01", ("GRID-TIE", "gas"), ("MTR-A", "gas_in"),
     [(700.0, 225.0), (690.0, 210.0), (620.0, 210.0), (620.0, 223.0)],
     "DN600", "CS-DRY-160", "ground", "gas", "injection feed from grid tie"),
    ("P02", ("MTR-A", "gas_out"), ("H-SUC", "branch_05"),
     [(620.0, 227.0), (620.0, 240.0), (430.0, 240.0), (430.0, 141.5)],
     "DN600", "CS-DRY-160", "ground", "gas", "metered injection gas to station"),
    ("P33", ("MTR-B", "gas_out"), ("GRID-TIE", "gas"),
     [(620.0, 272.0), (620.0, 300.0), (690.0, 300.0), (690.0, 240.0), (700.0, 240.0), (700.0, 225.0)],
     "DN400", "CS-DRY-160", "ground", "gas", "withdrawal gas to grid tie"),

    # ---- compressor suction / discharge -------------------------------
    ("P03", ("H-SUC", "branch_10"), ("CMP-A", "suction"),
     [(433.0, 139.0), (445.0, 139.0), (445.0, 70.0), (472.5, 70.0)],
     "DN400", "CS-DRY-160", "ground", "gas", "train A suction"),
    ("P04", ("H-SUC", "branch_06"), ("CMP-B", "suction"),
     [(433.0, 140.0), (472.5, 140.0)],
     "DN400", "CS-DRY-160", "ground", "gas", "train B suction"),
    ("P05", ("H-SUC", "branch_02"), ("CMP-C", "suction"),
     [(433.0, 141.0), (455.0, 141.0), (455.0, 210.0), (472.5, 210.0)],
     "DN400", "CS-DRY-160", "ground", "gas", "train C suction"),
    ("P06", ("CMP-A", "discharge"), ("H-DIS", "branch_10"),
     [(487.5, 70.0), (565.0, 70.0), (565.0, 139.0), (548.0, 139.0)],
     "DN350", "CS-DRY-160", "ground", "gas", "train A discharge"),
    ("P07", ("CMP-B", "discharge"), ("H-DIS", "branch_06"),
     [(487.5, 140.0), (530.0, 140.0), (530.0, 152.0), (575.0, 152.0), (575.0, 140.0), (548.0, 140.0)],
     "DN350", "CS-DRY-160", "ground", "gas", "train B discharge"),
    ("P08", ("CMP-C", "discharge"), ("H-DIS", "branch_02"),
     [(487.5, 210.0), (585.0, 210.0), (585.0, 141.0), (548.0, 141.0)],
     "DN400", "CS-DRY-160", "ground", "gas", "train C discharge"),
    ("P09", ("H-SUC", "branch_07"), ("H-DIS", "branch_07"),
     [(428.5, 138.5), (428.5, 118.0), (543.5, 118.0), (543.5, 138.5)],
     "DN350", "CS-DRY-160", "ground", "gas", "compressor bank bypass"),

    # ---- aftercooling (injection only) --------------------------------
    ("P10", ("H-DIS", "branch_09"), ("COOL", "gas_in"),
     [(547.0, 141.5), (547.0, 160.0), (560.0, 160.0), (560.0, 184.0)],
     "DN600", "CS-DRY-160", "ground", "gas", "hot discharge gas to aftercooler"),
    ("P11", ("COOL", "gas_out"), ("H-SITE", "branch_05"),
     [(560.0, 196.0), (560.0, 200.0), (250.0, 200.0), (250.0, 141.5)],
     "DN600", "CS-DRY-160", "ground", "gas", "cooled injection gas to station header"),

    # ---- well header / distribution ------------------------------------
    ("P12", ("H-SITE", "branch_04"), ("H-WELL", "branch_06"),
     [(247.0, 139.25), (230.0, 139.25), (230.0, 180.0), (93.0, 180.0)],
     "DN600", "CS-WET-160", "ground", "gas", "main trunk header to well manifold"),
    ("P13", ("H-WELL", "branch_03"), ("WG-01", "gas"),
     [(91.5, 178.5), (91.5, 170.0), (40.0, 170.0), (40.0, 45.0), (12.0, 45.0)],
     "DN300", "CS-WET-160", "ground", "gas", "well group 01 branch"),
    ("P14", ("H-WELL", "branch_07"), ("WG-02", "gas"),
     [(88.5, 178.5), (88.5, 168.0), (55.0, 168.0), (55.0, 117.0), (12.0, 117.0)],
     "DN300", "CS-WET-160", "ground", "gas", "well group 02 branch"),
    ("P15", ("H-WELL", "branch_01"), ("WG-03", "gas"),
     [(88.0, 181.5), (88.0, 189.0), (12.0, 189.0)],
     "DN250", "CS-WET-160", "ground", "gas", "well group 03 branch"),
    ("P16", ("H-WELL", "branch_05"), ("WG-04", "gas"),
     [(90.0, 181.5), (90.0, 200.0), (65.0, 200.0), (65.0, 261.0), (12.0, 261.0)],
     "DN300", "CS-WET-160", "ground", "gas", "well group 04 branch"),
    ("P17", ("H-WELL", "branch_09"), ("WG-05", "gas"),
     [(92.0, 181.5), (92.0, 215.0), (80.0, 215.0), (80.0, 333.0), (12.0, 333.0)],
     "DN300", "CS-WET-160", "ground", "gas", "well group 05 branch"),
    ("P18", ("H-WELL", "branch_04"), ("WG-06", "gas"),
     [(87.0, 179.25), (60.0, 179.25), (60.0, 405.0), (12.0, 405.0)],
     "DN350", "CS-WET-160", "ground", "gas", "well group 06 branch"),

    # ---- withdrawal treatment train ------------------------------------
    ("P19", ("H-SITE", "branch_10"), ("SEP-A", "gas_in"),
     [(253.0, 139.0), (265.0, 139.0), (265.0, 70.0), (286.0, 70.0)],
     "DN300", "CS-WET-160", "ground", "gas", "train A feed"),
    ("P20", ("H-SITE", "branch_06"), ("SEP-B", "gas_in"),
     [(253.0, 140.0), (286.0, 140.0)],
     "DN250", "CS-WET-160", "ground", "gas", "train B feed"),
    ("P21", ("H-SITE", "branch_02"), ("SEP-C", "gas_in"),
     [(253.0, 141.0), (283.5, 141.0), (283.5, 210.0), (286.0, 210.0)],
     "DN300", "CS-WET-160", "ground", "gas", "train C feed"),
    ("P22", ("SEP-A", "gas_out"), ("DEH-A", "gas_in"),
     [(294.0, 70.0), (296.0, 70.0), (296.0, 95.0), (350.0, 95.0), (350.0, 70.0), (375.0, 70.0)],
     "DN350", "CS-WET-160", "ground", "gas", "train A separated gas to dehydrator"),
    ("P23", ("SEP-B", "gas_out"), ("DEH-B", "gas_in"),
     [(294.0, 140.0), (375.0, 140.0)],
     "DN300", "CS-WET-160", "ground", "gas", "train B separated gas to dehydrator"),
    ("P24", ("SEP-C", "gas_out"), ("DEH-C", "gas_in"),
     [(294.0, 210.0), (375.0, 210.0)],
     "DN350", "CS-WET-160", "ground", "gas", "train C separated gas to dehydrator"),
    ("P28", ("DEH-A", "gas_out"), ("H-SUC", "branch_04"),
     [(385.0, 70.0), (405.0, 70.0), (405.0, 139.25), (427.0, 139.25)],
     "DN350", "CS-DRY-160", "ground", "gas", "train A dry gas"),
    ("P29", ("DEH-B", "gas_out"), ("H-SUC", "branch_08"),
     [(385.0, 140.0), (400.0, 140.0), (400.0, 140.75), (427.0, 140.75)],
     "DN300", "CS-DRY-160", "ground", "gas", "train B dry gas"),
    ("P30", ("DEH-C", "gas_out"), ("H-SUC", "branch_09"),
     [(385.0, 210.0), (432.0, 210.0), (432.0, 141.5)],
     "DN350", "CS-DRY-160", "ground", "gas", "train C dry gas"),

    # ---- pressure control and metering on the withdrawal path ----------
    ("P31", ("H-DIS", "branch_05"), ("REG", "gas_in"),
     [(545.0, 141.5), (545.0, 205.0), (577.5, 205.0)],
     "DN350", "CS-DRY-160", "ground", "gas", "to grid pressure control"),
    ("P32", ("REG", "gas_out"), ("MTR-B", "gas_in"),
     [(582.5, 205.0), (600.0, 205.0), (600.0, 255.0), (620.0, 255.0), (620.0, 268.0)],
     "DN400", "CS-DRY-160", "ground", "gas", "controlled gas to grid meter"),

    # ---- liquid drains --------------------------------------------------
    ("P34", ("SEP-A", "liquid_out"), ("DRN-A", "drain_in"),
     [(290.0, 68.0), (290.0, 64.0), (275.0, 64.0), (275.0, 55.0), (279.0, 55.0)],
     "DN200", "CS-WET-100", "buried", "liquid", "train A drain"),
    ("P35", ("SEP-B", "liquid_out"), ("DRN-B", "drain_in"),
     [(290.0, 138.0), (290.0, 134.0), (275.0, 134.0), (275.0, 125.0), (279.0, 125.0)],
     "DN200", "CS-WET-100", "buried", "liquid", "train B drain"),
    ("P36", ("SEP-C", "liquid_out"), ("DRN-C", "drain_in"),
     [(290.0, 208.0), (290.0, 204.0), (275.0, 204.0), (275.0, 195.0), (279.0, 195.0)],
     "DN200", "CS-WET-100", "buried", "liquid", "train C drain"),
    ("P37", ("DRN-A", "drain_out"), ("LIQUID-DRAIN-OUTFALL", "drain"),
     [(281.0, 55.0), (282.0, 55.0), (282.0, 105.0), (655.0, 105.0), (655.0, 120.0), (680.0, 120.0)],
     "DN200", "CS-WET-100", "buried", "liquid", "drain discharge line A"),
    ("P38", ("DRN-B", "drain_out"), ("LIQUID-DRAIN-OUTFALL", "drain"),
     [(281.0, 125.0), (284.0, 125.0), (284.0, 110.0), (650.0, 110.0), (668.0, 110.0), (668.0, 150.0), (680.0, 150.0), (680.0, 120.0)],
     "DN200", "CS-WET-100", "buried", "liquid", "drain discharge line B"),
    ("P39", ("DRN-C", "drain_out"), ("LIQUID-DRAIN-OUTFALL", "drain"),
     [(281.0, 195.0), (283.0, 195.0), (283.0, 115.0), (645.0, 115.0), (645.0, 80.0), (680.0, 80.0), (680.0, 120.0)],
     "DN200", "CS-WET-100", "buried", "liquid", "drain discharge line C"),
]
