"""Loaders for the UGS-SYNTH-D01 v1.1 brief data.

All catalog / site / scenario data is read from the read-only brief/ tree so the
calculations always run against the published assumptions.
"""
from __future__ import annotations

import json
import os

BRIEF_DIR = os.environ.get("UGS_BRIEF_DIR", "/workspace/brief")


def _load(relpath: str) -> dict:
    with open(os.path.join(BRIEF_DIR, relpath), encoding="utf-8") as fh:
        return json.load(fh)


class Brief:
    """Container for every published brief artefact used by the design."""

    def __init__(self, brief_dir: str | None = None):
        global BRIEF_DIR
        if brief_dir:
            BRIEF_DIR = brief_dir
        self.case = _load("case.json")
        self.economics = _load("economic_assumptions.json")
        self.gas = _load("gas_properties.json")
        self.maintenance = _load("maintenance_requirements.json")
        self.scenarios = _load("operating_scenarios.json")
        self.piping = _load("piping_catalog.json")
        self.requirements = _load("project_requirements.json")
        self.safety = _load("safety_requirements.json")
        self.site = _load("site.json")
        self.well_groups = _load("well_group_interfaces.json")
        self.delivery = _load("final_delivery_contract.json")

        self.catalog: dict[str, dict] = {}
        for name in (
            "compressors",
            "dehydration",
            "drains",
            "filters",
            "headers",
            "metering_regulation",
            "separators",
            "thermal_equipment",
        ):
            block = _load(f"equipment_catalog/{name}.json")
            for model in block["models"]:
                self.catalog[model["model_id"]] = model
