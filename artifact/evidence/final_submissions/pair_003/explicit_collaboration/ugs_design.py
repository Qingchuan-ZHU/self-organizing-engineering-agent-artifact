"""Proposed design for UGS-SYNTH-D01 (development case).

All coordinates are metres in the site coordinate system of brief/site.json.
Orientation follows the brief (counter-clockwise, degrees).
Routing levels: 'ground' for north-south branch runs, 'rack_low' for east-west main
runs, 'buried' for liquid-drain services.  Long continuous section drawings are
listed in segment order from the upstream physical end of the pipeline.

This file is pure data: no calculation is performed here.
"""

# --------------------------------------------------------------------------------------
# equipment instances
# --------------------------------------------------------------------------------------
# id, model_id, x, y, orientation_deg, description
EQUIPMENT = [
    # --- west / well side -------------------------------------------------------------
    ("HDR-WELL", "HDR120", 95.0, 225.0, 0, "Well-group manifold (6 well branches, injection feed, withdrawal take-off)"),
    ("HDR-WA", "HDR120", 150.0, 225.0, 0, "Withdrawal train feed manifold"),
    ("SEP-A", "SEP70", 195.0, 140.0, 0, "Withdrawal inlet separator, train A"),
    ("SEP-B", "SEP70", 195.0, 225.0, 0, "Withdrawal inlet separator, train B"),
    ("SEP-C", "SEP70", 195.0, 310.0, 0, "Withdrawal inlet separator, train C"),
    ("DEH-A", "DEHY70", 225.0, 140.0, 0, "Dehydration unit, train A"),
    ("DEH-B", "DEHY70", 225.0, 225.0, 0, "Dehydration unit, train B"),
    ("DEH-C", "DEHY70", 225.0, 310.0, 0, "Dehydration unit, train C"),
    ("DRN-A", "DRN-S", 200.0, 127.0, 0, "Closed drain drum, train A separator liquids"),
    ("DRN-B", "DRN-S", 200.0, 200.0, 0, "Closed drain drum, train B separator liquids"),
    ("DRN-C", "DRN-S", 200.0, 297.0, 0, "Closed drain drum, train C separator liquids"),
    ("HDR-WB", "HDR120", 265.0, 225.0, 0, "Treated-gas collection and pressure-control feed manifold"),
    ("REG-1", "REG180", 300.0, 225.0, 0, "Withdrawal pressure-control regulator (WDR-HIGH/WDR-MID)"),
    ("WCOMP-1", "C60", 330.0, 150.0, 0, "Withdrawal booster compressor 1 (WDR-LOW)"),
    ("WCOMP-2", "C60", 330.0, 110.0, 0, "Withdrawal booster compressor 2 (WDR-LOW)"),
    ("HDR-WC", "HDR120", 390.0, 225.0, 0, "Withdrawal pressure-control discharge manifold"),
    ("WMTR-1", "MTR160", 430.0, 205.0, 0, "GRID-TIE custody meter run (withdrawal export)"),
    # --- east / injection chain -------------------------------------------------------
    ("IMTR-1", "MTR160", 530.0, 105.0, 0, "GRID-TIE custody meter run (injection import)"),
    ("HDR-IM2", "HDR120", 560.0, 120.0, 0, "Compressor suction manifold"),
    ("ICOMP-1", "C60", 600.0, 90.0, 0, "Injection compressor 1"),
    ("ICOMP-2", "C60", 600.0, 120.0, 0, "Injection compressor 2"),
    ("ICOMP-3", "C40", 601.5, 150.0, 0, "Injection compressor 3"),
    ("HDR-IC", "HDR120", 640.0, 120.0, 0, "Compressor discharge manifold"),
    ("COOL-1", "COOL120", 670.0, 160.0, 0, "Injection gas aftercooler"),
]

# --------------------------------------------------------------------------------------
# pipelines: id, upstream (node, port), downstream (node, port), route, per-segment level,
#            DN, pipe class, service description
# --------------------------------------------------------------------------------------
GROUND = "ground"
RACK = "rack_low"
BURIED = "buried"

PIPELINES = [
    # ---- well group laterals (public boundary WG-01..WG-06 to well manifold) ----------
    dict(id="PL-WG-01", frm=("WG-01", "gas"), to=("HDR-WELL", "branch_07"),
         route=[(12, 45), (93.5, 45), (93.5, 223.5)], levels=[RACK, GROUND],
         dn="DN300", cls="CS-WET-160", service="well group lateral",
         note="Bidirectional well lateral; wet hydrocarbon gas in withdrawal, dry injection gas."),
    dict(id="PL-WG-02", frm=("WG-02", "gas"), to=("HDR-WELL", "branch_04"),
         route=[(12, 117), (92, 117), (92, 224.25)], levels=[RACK, GROUND],
         dn="DN300", cls="CS-WET-160", service="well group lateral"),
    dict(id="PL-WG-03", frm=("WG-03", "gas"), to=("HDR-WELL", "branch_08"),
         route=[(12, 189), (90, 189), (90, 225.75), (92, 225.75)], levels=[RACK, GROUND, GROUND],
         dn="DN300", cls="CS-WET-160", service="well group lateral"),
    dict(id="PL-WG-04", frm=("WG-04", "gas"), to=("HDR-WELL", "branch_01"),
         route=[(12, 261), (93, 261), (93, 226.5)], levels=[RACK, GROUND],
         dn="DN300", cls="CS-WET-160", service="well group lateral"),
    dict(id="PL-WG-05", frm=("WG-05", "gas"), to=("HDR-WELL", "branch_05"),
         route=[(12, 333), (95, 333), (95, 226.5)], levels=[RACK, GROUND],
         dn="DN300", cls="CS-WET-160", service="well group lateral"),
    dict(id="PL-WG-06", frm=("WG-06", "gas"), to=("HDR-WELL", "branch_09"),
         route=[(12, 405), (97, 405), (97, 226.5)], levels=[RACK, GROUND],
         dn="DN300", cls="CS-WET-160", service="well group lateral"),
    # ---- withdrawal: well manifold -> train feed manifold ----------------------------
    dict(id="PL-WF", frm=("HDR-WELL", "branch_02"), to=("HDR-WA", "branch_08"),
         route=[(98, 226), (147, 225.75)], levels=[RACK],
         dn="DN500", cls="CS-WET-160", service="wet gas feed to treatment"),
    # ---- train A / B / C -------------------------------------------------------------
    dict(id="PL-TA-1", frm=("HDR-WA", "branch_03"), to=("SEP-A", "gas_in"),
         route=[(151.5, 223.5), (151.5, 140), (191, 140)], levels=[GROUND, RACK],
         dn="DN350", cls="CS-WET-160", service="train A separator feed"),
    dict(id="PL-TB-1", frm=("HDR-WA", "branch_06"), to=("SEP-B", "gas_in"),
         route=[(153, 225), (191, 225)], levels=[RACK],
         dn="DN300", cls="CS-WET-160", service="train B separator feed"),
    dict(id="PL-TC-1", frm=("HDR-WA", "branch_09"), to=("SEP-C", "gas_in"),
         route=[(152, 226.5), (152, 310), (191, 310)], levels=[GROUND, RACK],
         dn="DN350", cls="CS-WET-160", service="train C separator feed"),
    dict(id="PL-TA-2", frm=("SEP-A", "gas_out"), to=("DEH-A", "gas_in"),
         route=[(199, 140), (220, 140)], levels=[RACK],
         dn="DN300", cls="CS-WET-160", service="train A wet gas"),
    dict(id="PL-TB-2", frm=("SEP-B", "gas_out"), to=("DEH-B", "gas_in"),
         route=[(199, 225), (220, 225)], levels=[RACK],
         dn="DN300", cls="CS-WET-160", service="train B wet gas"),
    dict(id="PL-TC-2", frm=("SEP-C", "gas_out"), to=("DEH-C", "gas_in"),
         route=[(199, 310), (220, 310)], levels=[RACK],
         dn="DN300", cls="CS-WET-160", service="train C wet gas"),
    dict(id="PL-TA-3", frm=("DEH-A", "gas_out"), to=("HDR-WB", "branch_03"),
         route=[(230, 140), (266.5, 140), (266.5, 223.5)], levels=[RACK, GROUND],
         dn="DN350", cls="CS-DRY-160", service="train A dry gas"),
    dict(id="PL-TB-3", frm=("DEH-B", "gas_out"), to=("HDR-WB", "branch_04"),
         route=[(230, 225), (262, 224.25)], levels=[GROUND],
         dn="DN300", cls="CS-DRY-160", service="train B dry gas"),
    dict(id="PL-TC-3", frm=("DEH-C", "gas_out"), to=("HDR-WB", "branch_01"),
         route=[(230, 310), (263, 310), (263, 226.5)], levels=[RACK, GROUND],
         dn="DN350", cls="CS-DRY-160", service="train C dry gas"),
    # ---- liquid side streams (separator liquid_out -> closed drain -> outfall) --------
    dict(id="PL-DA-1", frm=("SEP-A", "liquid_out"), to=("DRN-A", "drain_in"),
         route=[(195, 138), (195, 127), (199, 127)], levels=[GROUND, GROUND],
         dn="DN200", cls="CS-WET-100", service="train A separated liquid"),
    dict(id="PL-DB-1", frm=("SEP-B", "liquid_out"), to=("DRN-B", "drain_in"),
         route=[(195, 223), (195, 200), (199, 200)], levels=[GROUND, GROUND],
         dn="DN200", cls="CS-WET-100", service="train B separated liquid"),
    dict(id="PL-DC-1", frm=("SEP-C", "liquid_out"), to=("DRN-C", "drain_in"),
         route=[(195, 308), (195, 297), (199, 297)], levels=[GROUND, GROUND],
         dn="DN200", cls="CS-WET-100", service="train C separated liquid"),
    dict(id="PL-DA-2", frm=("DRN-A", "drain_out"), to=("LIQUID-DRAIN-OUTFALL", "drain"),
         route=[(201, 127), (675, 127), (680, 120)], levels=[BURIED, BURIED],
         dn="DN200", cls="CS-WET-100", service="closed drain to outfall (train A)"),
    dict(id="PL-DB-2", frm=("DRN-B", "drain_out"), to=("LIQUID-DRAIN-OUTFALL", "drain"),
         route=[(201, 200), (686, 200), (686, 127), (680, 120)], levels=[BURIED, BURIED, BURIED],
         dn="DN200", cls="CS-WET-100", service="closed drain to outfall (train B)"),
    dict(id="PL-DC-2", frm=("DRN-C", "drain_out"), to=("LIQUID-DRAIN-OUTFALL", "drain"),
         route=[(201, 297), (692, 297), (692, 127), (680, 120)], levels=[BURIED, BURIED, BURIED],
         dn="DN200", cls="CS-WET-100", service="closed drain to outfall (train C)"),
    # ---- pressure control --------------------------------------------------------------
    dict(id="PL-PC-R", frm=("HDR-WB", "branch_02"), to=("REG-1", "gas_in"),
         route=[(268, 226), (297.5, 225)], levels=[GROUND], dn="DN350", cls="CS-DRY-160",
         service="regulator feed (WDR-HIGH / WDR-MID)"),
    dict(id="PL-PC-C1", frm=("HDR-WB", "branch_06"), to=("WCOMP-1", "suction"),
         route=[(268, 225), (280, 225), (280, 150), (322.5, 150)], levels=[GROUND, GROUND, RACK],
         dn="DN350", cls="CS-DRY-160", service="withdrawal booster compressor 1 suction"),
    dict(id="PL-PC-C2", frm=("HDR-WB", "branch_10"), to=("WCOMP-2", "suction"),
         route=[(268, 224), (276, 224), (276, 110), (322.5, 110)], levels=[GROUND, GROUND, RACK],
         dn="DN350", cls="CS-DRY-160", service="withdrawal booster compressor 2 suction"),
    dict(id="PL-PC-R2", frm=("REG-1", "gas_out"), to=("HDR-WC", "branch_08"),
         route=[(302.5, 225), (387, 225.75)], levels=[GROUND], dn="DN400", cls="CS-WET-100",
         service="regulated gas to metering"),
    dict(id="PL-PC-C1o", frm=("WCOMP-1", "discharge"), to=("HDR-WC", "branch_04"),
         route=[(337.5, 150), (380, 150), (380, 224.25), (387, 224.25)], levels=[RACK, GROUND, RACK],
         dn="DN350", cls="CS-DRY-160", service="withdrawal booster compressor 1 discharge"),
    dict(id="PL-PC-C2o", frm=("WCOMP-2", "discharge"), to=("HDR-WC", "branch_03"),
         route=[(337.5, 110), (383, 110), (383, 223.5), (391.5, 223.5)], levels=[RACK, GROUND, RACK],
         dn="DN350", cls="CS-DRY-160", service="withdrawal booster compressor 2 discharge"),
    # ---- withdrawal metering ---------------------------------------------------------
    dict(id="PL-WM-1i", frm=("HDR-WC", "branch_02"), to=("WMTR-1", "gas_in"),
         route=[(393, 226), (410, 226), (410, 205), (428, 205)], levels=[RACK, GROUND, RACK],
         dn="DN400", cls="CS-WET-100", service="custody meter run feed (withdrawal)"),
    dict(id="PL-TIE-W", frm=("WMTR-1", "gas_out"), to=("GRID-TIE", "gas"),
         route=[(432, 205), (455, 205), (455, 225), (700, 225)], levels=[RACK, GROUND, RACK],
         dn="DN500", cls="CS-WET-100", service="GRID-TIE withdrawal export line (metered)"),
    # ---- injection chain --------------------------------------------------------------
    dict(id="PL-IF", frm=("GRID-TIE", "gas"), to=("IMTR-1", "gas_in"),
         route=[(700, 225), (696, 215), (696, 80), (524, 80), (524, 105), (528, 105)],
         levels=[GROUND, GROUND, RACK, GROUND, RACK],
         dn="DN700", cls="CS-WET-100", service="GRID-TIE injection import line (metered)"),
    dict(id="PL-IM-1o", frm=("IMTR-1", "gas_out"), to=("HDR-IM2", "branch_04"),
         route=[(532, 105), (550, 105), (550, 119.25), (557, 119.25)], levels=[RACK, GROUND, GROUND],
         dn="DN400", cls="CS-WET-100", service="custody meter run outlet (injection)"),
    dict(id="PL-IS-1", frm=("HDR-IM2", "branch_07"), to=("ICOMP-1", "suction"),
         route=[(558.5, 118.5), (558.5, 90), (592.5, 90)], levels=[GROUND, RACK],
         dn="DN400", cls="CS-WET-100", service="injection compressor 1 suction"),
    dict(id="PL-IS-2", frm=("HDR-IM2", "branch_06"), to=("ICOMP-2", "suction"),
         route=[(563, 120), (592.5, 120)], levels=[RACK],
         dn="DN400", cls="CS-WET-100", service="injection compressor 2 suction"),
    dict(id="PL-IS-3", frm=("HDR-IM2", "branch_02"), to=("ICOMP-3", "suction"),
         route=[(563, 121), (570, 121), (570, 150), (595.5, 150)], levels=[GROUND, GROUND, RACK],
         dn="DN300", cls="CS-WET-100", service="injection compressor 3 suction"),
    dict(id="PL-ID-1", frm=("ICOMP-1", "discharge"), to=("HDR-IC", "branch_07"),
         route=[(607.5, 90), (638.5, 90), (638.5, 118.5)], levels=[RACK, GROUND],
         dn="DN400", cls="CS-DRY-160", service="injection compressor 1 discharge"),
    dict(id="PL-ID-2", frm=("ICOMP-2", "discharge"), to=("HDR-IC", "branch_04"),
         route=[(607.5, 120), (637, 119.25)], levels=[GROUND],
         dn="DN400", cls="CS-DRY-160", service="injection compressor 2 discharge"),
    dict(id="PL-ID-3", frm=("ICOMP-3", "discharge"), to=("HDR-IC", "branch_01"),
         route=[(607.5, 150), (638, 150), (638, 121.5)], levels=[RACK, GROUND],
         dn="DN300", cls="CS-DRY-160", service="injection compressor 3 discharge"),
    dict(id="PL-IC", frm=("HDR-IC", "branch_02"), to=("COOL-1", "gas_in"),
         route=[(643, 121), (643, 140), (650, 140), (650, 160), (664, 160)],
         levels=[GROUND, RACK, GROUND, RACK],
         dn="DN500", cls="CS-DRY-160", service="compressor discharge to aftercooler"),
    dict(id="PL-IR", frm=("COOL-1", "gas_out"), to=("HDR-WELL", "branch_03"),
         route=[(676, 160), (683, 160), (683, 213), (96.5, 213), (96.5, 223.5)],
         levels=[RACK, GROUND, RACK, GROUND],
         dn="DN700", cls="CS-DRY-160", service="cooled injection gas to well manifold"),
]

# --------------------------------------------------------------------------------------
# roads (access network)
# --------------------------------------------------------------------------------------
ROADS = [
    dict(id="RD-MAIN", width_m=6.0, centerline_m=[(0, 225), (40, 225), (40, 190), (640, 190)]),
    dict(id="RD-SEP", width_m=5.0, centerline_m=[(181, 130), (181, 330)]),
    dict(id="RD-WCOMP", width_m=5.0, centerline_m=[(355, 100), (355, 190)]),
    dict(id="RD-ICOMP", width_m=5.0, centerline_m=[(622.5, 90), (622.5, 190)]),
]

# --------------------------------------------------------------------------------------
# scenario operating definitions
# --------------------------------------------------------------------------------------
# Each scenario lists the ordered element chain of the active operating path.
# Element kinds:  ('pipe', pipeline_id, flow_fraction, declared_level_hint)
#                 ('equip', instance_id, flow_fraction, setpoint dict)
#                 ('par', [chain, chain, ...])   parallel block, equal split, chain may be
#                                                "" (inactive) or a list of elements
#
# flow_fraction is the fraction of the scenario's required total gas flow.

def _train(t):
    return [
        ("pipe", "PL-T%s-1" % t, 1.0 / 3.0),
        ("equip", "SEP-%s" % t, 1.0 / 3.0, {}),
        ("pipe", "PL-T%s-2" % t, 1.0 / 3.0),
        ("equip", "DEH-%s" % t, 1.0 / 3.0, {}),
        ("pipe", "PL-T%s-3" % t, 1.0 / 3.0),
    ]


SCENARIO_PATHS = {
    "WDR-HIGH": {
        "source": "well_groups",
        "sink": "GRID-TIE",
        "chain": [
            ("source_par", [
                [("pipe", "PL-WG-01", 1.0 / 6.0)], [("pipe", "PL-WG-02", 1.0 / 6.0)],
                [("pipe", "PL-WG-03", 1.0 / 6.0)], [("pipe", "PL-WG-04", 1.0 / 6.0)],
                [("pipe", "PL-WG-05", 1.0 / 6.0)], [("pipe", "PL-WG-06", 1.0 / 6.0)],
            ]),
            ("equip", "HDR-WELL", 1.0, {}),
            ("pipe", "PL-WF", 1.0),
            ("equip", "HDR-WA", 1.0, {}),
            ("par", [_train("A"), _train("B"), _train("C")]),
            ("equip", "HDR-WB", 1.0, {}),
            ("par", [
                [("pipe", "PL-PC-R", 1.0), ("equip", "REG-1", 1.0, {"mode": "regulate"}),
                 ("pipe", "PL-PC-R2", 1.0)],
                [("pipe", "PL-PC-C1", 0.0), ("equip", "WCOMP-1", 0.0, {"mode": "off"}), ("pipe", "PL-PC-C1o", 0.0)],
                [("pipe", "PL-PC-C2", 0.0), ("equip", "WCOMP-2", 0.0, {"mode": "off"}), ("pipe", "PL-PC-C2o", 0.0)],
            ]),
            ("equip", "HDR-WC", 1.0, {}),
            ("pipe", "PL-WM-1i", 1.0),
            ("equip", "WMTR-1", 1.0, {}),
            ("pipe", "PL-TIE-W", 1.0),
        ],
    },
    "INJ-LOW": {
        "source": "GRID-TIE",
        "sink": "well_groups",
        "chain": [
            ("pipe", "PL-IF", 1.0),
            ("equip", "IMTR-1", 1.0, {}),
            ("pipe", "PL-IM-1o", 1.0),
            ("equip", "HDR-IM2", 1.0, {}),
            ("par", [
                [("pipe", "PL-IS-1", 0.5), ("equip", "ICOMP-1", 0.5, {"mode": "compress"}),
                 ("pipe", "PL-ID-1", 0.5)],
                [("pipe", "PL-IS-2", 0.5), ("equip", "ICOMP-2", 0.5, {"mode": "compress"}),
                 ("pipe", "PL-ID-2", 0.5)],
                [("pipe", "PL-IS-3", 0.0), ("equip", "ICOMP-3", 0.0, {"mode": "standby"}),
                 ("pipe", "PL-ID-3", 0.0)],
            ]),
            ("equip", "HDR-IC", 1.0, {}),
            ("pipe", "PL-IC", 1.0),
            ("equip", "COOL-1", 1.0, {"mode": "cool", "t_out_c": 40.0}),
            ("pipe", "PL-IR", 1.0),
            ("equip", "HDR-WELL", 1.0, {}),
            ("split", [
                [("pipe", "PL-WG-01", 1.0 / 6.0)], [("pipe", "PL-WG-02", 1.0 / 6.0)],
                [("pipe", "PL-WG-03", 1.0 / 6.0)], [("pipe", "PL-WG-04", 1.0 / 6.0)],
                [("pipe", "PL-WG-05", 1.0 / 6.0)], [("pipe", "PL-WG-06", 1.0 / 6.0)],
            ]),
        ],
    },
}

# WDR-MID / WDR-LOW differ only in boundary conditions, flow and compressor split.
SCENARIO_PATHS["WDR-MID"] = SCENARIO_PATHS["WDR-HIGH"]
SCENARIO_PATHS["INJ-MID"] = SCENARIO_PATHS["INJ-LOW"]
SCENARIO_PATHS["INJ-HIGH"] = SCENARIO_PATHS["INJ-LOW"]

# withdrawal booster split for WDR-LOW (two units in service, one at 50%)
WDR_LOW_CHAIN = [
    ("source_par", [
        [("pipe", "PL-WG-01", 1.0 / 6.0)], [("pipe", "PL-WG-02", 1.0 / 6.0)],
        [("pipe", "PL-WG-03", 1.0 / 6.0)], [("pipe", "PL-WG-04", 1.0 / 6.0)],
        [("pipe", "PL-WG-05", 1.0 / 6.0)], [("pipe", "PL-WG-06", 1.0 / 6.0)],
    ]),
    ("equip", "HDR-WELL", 1.0, {}),
    ("pipe", "PL-WF", 1.0),
    ("equip", "HDR-WA", 1.0, {}),
    ("par", [_train("A"), _train("B"), _train("C")]),
    ("equip", "HDR-WB", 1.0, {}),
    ("par", [
        [("pipe", "PL-PC-R", 0.0), ("equip", "REG-1", 0.0, {"mode": "off"}), ("pipe", "PL-PC-R2", 0.0)],
        [("pipe", "PL-PC-C1", 0.5), ("equip", "WCOMP-1", 0.5, {"mode": "compress"}), ("pipe", "PL-PC-C1o", 0.5)],
        [("pipe", "PL-PC-C2", 0.5), ("equip", "WCOMP-2", 0.5, {"mode": "compress"}), ("pipe", "PL-PC-C2o", 0.5)],
    ]),
]
# reuse the rest of the withdrawal chain (manifolds, metering, export line)
SCENARIO_PATHS["WDR-LOW"] = {
    "source": "well_groups",
    "sink": "GRID-TIE",
    "chain": WDR_LOW_CHAIN + SCENARIO_PATHS["WDR-HIGH"]["chain"][7:],
}

# --------------------------------------------------------------------------------------
# reliability (n-1) operating cases that must remain deliverable
# --------------------------------------------------------------------------------------
N1_CASES = [
    dict(case="compressor outage, INJ-LOW (120 kg/s), C60 lost", scenario="INJ-LOW",
         failed="compressor", failed_unit="ICOMP-1",
         note="C60 lost; retained capacity 100 kg/s vs 84 kg/s required"),
    dict(case="compressor outage, INJ-LOW (120 kg/s), second C60 lost", scenario="INJ-LOW",
         failed="compressor", failed_unit="ICOMP-2",
         note="other C60 lost; retained capacity 100 kg/s vs 84 kg/s required"),
    dict(case="compressor outage, INJ-LOW (120 kg/s), C40 standby lost", scenario="INJ-LOW",
         failed="compressor", failed_unit="ICOMP-3",
         note="stand-by C40 lost; the two C60 units still cover the full 120 kg/s scenario flow"),
    dict(case="compressor outage, INJ-MID (100 kg/s)", scenario="INJ-MID",
         failed="compressor", failed_unit="ICOMP-2",
         note="100 kg/s retained capacity vs 70 kg/s required"),
    dict(case="compressor outage, INJ-HIGH (75 kg/s)", scenario="INJ-HIGH",
         failed="compressor", failed_unit="ICOMP-2",
         note="100 kg/s retained capacity vs 52.5 kg/s required"),
    dict(case="compressor outage, WDR-LOW (70 kg/s)", scenario="WDR-LOW",
         failed="compressor", failed_unit="WCOMP-1",
         note="60 kg/s retained capacity vs 49 kg/s required"),
    dict(case="separator outage, WDR-HIGH", scenario="WDR-HIGH", failed="separator", failed_unit="A",
         note="trains B and C in service, 140 kg/s capacity vs 84 kg/s required"),
    dict(case="separator outage, WDR-MID", scenario="WDR-MID", failed="separator", failed_unit="A",
         note="trains B and C in service"),
    dict(case="separator outage, WDR-LOW", scenario="WDR-LOW", failed="separator", failed_unit="A",
         note="trains B and C in service"),
    dict(case="dehydration outage, WDR-HIGH", scenario="WDR-HIGH", failed="dehydration", failed_unit="B",
         note="trains A and C in service"),
    dict(case="dehydration outage, WDR-MID", scenario="WDR-MID", failed="dehydration", failed_unit="B",
         note="trains A and C in service"),
    dict(case="dehydration outage, WDR-LOW", scenario="WDR-LOW", failed="dehydration", failed_unit="B",
         note="trains A and C in service"),
]
