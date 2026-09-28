"""Loads the published benchmark catalogs and site data.

All data are read from the read-only ``brief/`` directory.  Nothing in this
module invents data: every numeric quantity comes from the published files.
"""
import json
import os

def _find_brief():
    env = os.environ.get("UGS_BRIEF_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, os.pardir, os.pardir, "brief"),
                 os.path.join(here, os.pardir, "brief"),
                 os.path.join(here, "brief"),
                 "brief"):
        if os.path.isdir(cand):
            return os.path.normpath(cand)
    return "brief"


BRIEF = _find_brief()

_CAT_FILES = [
    "compressors", "dehydration", "drains", "filters", "headers",
    "metering_regulation", "separators", "thermal_equipment",
]


def _load(path):
    with open(os.path.join(BRIEF, path), "r", encoding="utf-8") as fh:
        return json.load(fh)


MODELS = {}          # model_id -> model dict (with 'category')
for _f in _CAT_FILES:
    _data = _load(os.path.join("equipment_catalog", _f + ".json"))
    for _m in _data["models"]:
        MODELS[_m["model_id"]] = _m

GAS = _load("gas_properties.json")
ECON = _load("economic_assumptions.json")
PIPING = _load("piping_catalog.json")
SITE = _load("site.json")
SCEN = _load("operating_scenarios.json")
REQS = _load("project_requirements.json")
MAINT = _load("maintenance_requirements.json")
SAFETY = _load("safety_requirements.json")
WELLS = _load("well_group_interfaces.json")
CASEMETA = _load("case.json")

DIAMS = {d["nominal_diameter"]: d for d in PIPING["diameters"]}
CLASSES = {c["class_id"]: c for c in PIPING["classes"]}
LEVELS = PIPING["routing_levels"]

# interfaces -------------------------------------------------------------
INTERFACES = {}
for _i in SITE["external_interfaces"]:
    INTERFACES[_i["interface_id"]] = _i

WELL_IFACE_IDS = [w["interface_id"] for w in WELLS["well_groups"]]
