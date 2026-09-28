"""UGS-SYNTH-D01 v1.1 - facility layout, equipment instances, roads.

Coordinates are (x_m, y_m) in the site coordinate system (site origin at (0,0)).
Orientations are degrees CCW; only catalog-supported values are used.
"""
import json
import os

BRIEF = "/workspace/brief"

def load(name):
    with open(os.path.join(BRIEF, name)) as f:
        return json.load(f)

def load_catalog():
    cat = {}
    for fn in os.listdir(os.path.join(BRIEF, "equipment_catalog")):
        d = load(os.path.join("equipment_catalog", fn))
        for m in d["models"]:
            cat[m["model_id"]] = m
    return cat


# ------------------------------------------------------------------ layout
# Each instance: id, model_id, x, y, orientation_deg
INSTANCES = [
    # --- grid-side metering (east) ---
    dict(id="MTR-INJ", model_id="MTR120", x=615, y=240, o=0),
    dict(id="MTR-WDR", model_id="MTR120", x=615, y=210, o=0),
    # --- grid-side header ---
    dict(id="H-GS",    model_id="HDR120", x=560, y=200, o=0),
    # --- injection compressor discharge header ---
    dict(id="H-CH",    model_id="HDR120", x=455, y=200, o=0),
    # --- well-side header ---
    dict(id="H-WS",    model_id="HDR120", x=350, y=200, o=0),
    # --- treated header ---
    dict(id="H-TS",    model_id="HDR120", x=460, y=262, o=0),
    # --- injection aftercooler ---
    dict(id="COOL-1",  model_id="COOL120", x=485, y=240, o=0),
    # --- injection compressors (2 x C60 + 1 x C40) ---
    dict(id="C-I1",    model_id="C60", x=360, y=140, o=0),
    dict(id="C-I2",    model_id="C60", x=390, y=140, o=0),
    dict(id="C-I3",    model_id="C40", x=420, y=140, o=0),
    # --- withdrawal boosters ---
    dict(id="C-W1",    model_id="C60", x=515, y=140, o=0),
    dict(id="C-W2",    model_id="C60", x=550, y=140, o=0),
    # --- withdrawal separation ---
    dict(id="SEP-1",   model_id="SEP70", x=368, y=292, o=0),
    dict(id="SEP-2",   model_id="SEP70", x=452, y=292, o=0),
    dict(id="SEP-3",   model_id="SEP70", x=535, y=292, o=0),
    # --- withdrawal dehydration ---
    dict(id="DEH-1",   model_id="DEHY70", x=400, y=292, o=0),
    dict(id="DEH-2",   model_id="DEHY70", x=485, y=292, o=0),
    dict(id="DEH-3",   model_id="DEHY70", x=568, y=292, o=0),
    # --- withdrawal regulation ---
    dict(id="REG-1",   model_id="REG120", x=605, y=180, o=0),
    # --- closed drains ---
    dict(id="DRN-1",   model_id="DRN-S", x=595, y=140, o=0),
    dict(id="DRN-2",   model_id="DRN-S", x=595, y=155, o=0),
    dict(id="DRN-3",   model_id="DRN-S", x=595, y=170, o=0),
]

# ------------------------------------------------------------------ roads
ROADS = [
    dict(id="RD-MAIN",  pts=[(3, 225), (597, 225)], width=6.0),
    dict(id="RD-WEST",  pts=[(341, 130), (341, 302)], width=6.0),
    dict(id="RD-EAST",  pts=[(470, 225), (470, 302)], width=6.0),
    dict(id="RD-NORTH", pts=[(335, 302), (585, 302)], width=6.0),
    dict(id="RD-SOUTH", pts=[(335, 130), (585, 130)], width=6.0),
]


def footprint(inst, cat, expand=0.0):
    m = cat[inst["model_id"]]
    L = m["footprint_m"]["length"] + 2 * expand
    W = m["footprint_m"]["width"] + 2 * expand
    if inst["o"] % 180 == 0:
        hx, hy = L / 2.0, W / 2.0
    else:
        hx, hy = W / 2.0, L / 2.0
    return (inst["x"] - hx, inst["y"] - hy, inst["x"] + hx, inst["y"] + hy)


def rotate(off, o):
    x, y = off
    if o % 360 == 0:
        return (x, y)
    if o % 360 == 90:
        return (-y, x)
    if o % 360 == 180:
        return (-x, -y)
    return (y, -x)


def port_world(inst, cat, port_id):
    m = cat[inst["model_id"]]
    for p in m["ports"]:
        if p["id"] == port_id:
            dx, dy = rotate(p["offset_m"], inst["o"])
            return (inst["x"] + dx, inst["y"] + dy)
    raise KeyError((inst["id"], port_id))


def envelope_rects(inst, cat):
    m = cat[inst["model_id"]]
    cl = footprint(inst, cat, m["maintenance"]["clearance_m"])
    rects = [cl]
    if m["maintenance"].get("heavy_maintenance"):
        side = m["maintenance"]["side"]
        ext, tw = m["maintenance"]["removal_envelope_m"]
        L = m["footprint_m"]["length"]; W = m["footprint_m"]["width"]
        if side == "east":
            lx0, lx1, ly0, ly1 = L / 2, L / 2 + ext, -tw / 2, tw / 2
        elif side == "west":
            lx0, lx1, ly0, ly1 = -L / 2 - ext, -L / 2, -tw / 2, tw / 2
        elif side == "north":
            lx0, lx1, ly0, ly1 = -tw / 2, tw / 2, W / 2, W / 2 + ext
        else:
            lx0, lx1, ly0, ly1 = -tw / 2, tw / 2, -W / 2 - ext, -W / 2
        corners = [(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)]
        wc = [rotate(c, inst["o"]) for c in corners]
        xs = [inst["x"] + c[0] for c in wc]; ys = [inst["y"] + c[1] for c in wc]
        rects.append((min(xs), min(ys), max(xs), max(ys)))
    return rects
