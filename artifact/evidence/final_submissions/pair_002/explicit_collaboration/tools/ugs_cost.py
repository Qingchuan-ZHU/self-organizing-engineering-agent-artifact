"""Pipeline / equipment conformance checks, quantities, lifecycle cost and
deliverable export for UGS-SYNTH-D01."""

from __future__ import annotations

import json
import math
from pathlib import Path

import ugs_basis as B
from ugs_basis import (
    TOL_GEOMETRY_M, TOL_MASS_FLOW_KG_S, TOL_PRESSURE_MPA, TOL_TEMPERATURE_C,
    TOL_VELOCITY_M_S,
)
from ugs_check import Design, LIQUID_DENSITY_ASSUMED_KG_M3


# ---------------------------------------------------------------------------
# conformance checks that need scenario results
# ---------------------------------------------------------------------------

DRAIN_PIPE_OWNER = {"P-137": "SEP-WDR-01", "P-138": "SEP-WDR-02", "P-139": "SEP-WDR-03",
                    "P-140": "SEP-WDR-01", "P-141": "SEP-WDR-02", "P-142": "SEP-WDR-03"}


def check_pipes_against_service(design: Design, marches):
    """Velocity limits, pipe-class rating / compatibility, drain compatibility."""
    case = design.case
    for tag, pl in design.pipes.items():
        pc = design.pc(pl.cls)
        dn = design.d(pl.dn)
        if pl.service == "liquid_drain":
            owner = DRAIN_PIPE_OWNER[tag]
            flowmax = max((m.sep_liquid.get(owner, 0.0) for m in marches), default=0.0)
            area = math.pi * dn["internal_diameter_m"] ** 2 / 4.0
            vmax = (flowmax / LIQUID_DENSITY_ASSUMED_KG_M3) / area
            design.add(f"{tag} liquid drain velocity <= {case.max_liquid_drain_velocity:g} m/s",
                       vmax <= case.max_liquid_drain_velocity + TOL_VELOCITY_M_S,
                       f"{vmax:.4f} m/s at {flowmax:.4f} kg/s liquid "
                       f"(assumed density {LIQUID_DENSITY_ASSUMED_KG_M3:.0f} kg/m3)")
            design.add(f"{tag} pipe class {pl.cls} is liquid-drain compatible",
                       pc["liquid_drain_compatible"])
            continue

        vmax, pmax, tmax, tmin = 0.0, 0.0, -1e9, 1e9
        wet = False
        for m in marches:
            res = m.pipe_state.get(tag)
            if res is None or res.flow <= 0:
                continue
            vmax = max(vmax, res.velocity_m_s)
            src_node = pl.a[0]
            st = m.state.get(src_node)
            if st is not None:
                pmax = max(pmax, st.get("p_out", st.get("p", 0.0)))
                tmax = max(tmax, st.get("t_out", st.get("t", 0.0)))
                tmin = min(tmin, st.get("t_out", st.get("t", 0.0)))
                if st.get("water", 0.0) > 50.0 + 1e-5 or \
                        st.get("liquid_out", st.get("liquid", 0.0)) > 1e-4 + 1e-9:
                    wet = True
        if vmax > 0:
            design.add(f"{tag} gas velocity <= {case.max_gas_velocity:g} m/s",
                       vmax <= case.max_gas_velocity + TOL_VELOCITY_M_S, f"{vmax:.3f} m/s")
        if pmax > 0:
            design.add(f"{tag} pipe class {pl.cls} rated for {pmax:.4f} MPa",
                       pc["maximum_allowable_pressure_mpa"] + TOL_PRESSURE_MPA >= pmax,
                       f"rating {pc['maximum_allowable_pressure_mpa']:.1f} MPa")
            lo, hi = pc["temperature_limits_c"]
            design.add(f"{tag} pipe class {pl.cls} temperature range covers service",
                       lo - TOL_TEMPERATURE_C <= tmin and tmax <= hi + TOL_TEMPERATURE_C,
                       f"service {tmin:.2f}..{tmax:.2f} degC, class {lo}..{hi} degC")
            design.add(f"{tag} pipe class {pl.cls} compatible with {'wet' if wet else 'dry'} gas",
                       pc["wet_gas_compatible"] if wet else pc["dry_gas_compatible"],
                       f"conveyed condition: {'wet' if wet else 'dry'}")


# ---------------------------------------------------------------------------
# quantities and LCC
# ---------------------------------------------------------------------------

def quantities(design: Design):
    q = dict(
        equipment={},
        pipe_length_by_level={},
        pipe_length_by_dn={},
        pipe_length_total_m=0.0,
        road_length_m=0.0,
        footprint_area_m2=0.0,
        maintenance_area_m2=0.0,
    )
    for tag, n in design.nodes.items():
        q["equipment"].setdefault(n.model["model_id"], 0)
        q["equipment"][n.model["model_id"]] += 1
        q["footprint_area_m2"] += B.polygon_area(n.footprint)
        q["maintenance_area_m2"] += n.maintenance_area_m2()
    for tag, pl in design.pipes.items():
        for (p0, p1, lvl, idx) in pl.segments():
            ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            q["pipe_length_by_level"][lvl] = q["pipe_length_by_level"].get(lvl, 0.0) + ln
            q["pipe_length_by_dn"][pl.dn] = q["pipe_length_by_dn"].get(pl.dn, 0.0) + ln
            q["pipe_length_total_m"] += ln
    for r in design.roads:
        q["road_length_m"] += B.polyline_length([tuple(p) for p in r["pts"]])
    return q


def compute_lcc(design: Design, normal_marches):
    case = design.case
    ec = case.economic_assumptions
    pvf = case.pvf()
    q = quantities(design)

    equipment_capex = sum(n.model["capex_mbcu"] for n in design.nodes.values())
    equipment_maint = sum(n.model["annual_maintenance_mbcu"] for n in design.nodes.values())

    piping_capex = 0.0
    pipeline_civil = 0.0
    for tag, pl in design.pipes.items():
        dn_cost = design.d(pl.dn)["installed_cost_mbcu_per_m"]
        cls_mult = design.pc(pl.cls)["installed_cost_multiplier"]
        for (p0, p1, lvl, idx) in pl.segments():
            ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            lvl_mult = case.routing_levels[lvl]["installed_cost_multiplier"]
            piping_capex += ln * dn_cost * cls_mult * lvl_mult
            pipeline_civil += ln * case.routing_levels[lvl]["civil_cost_mbcu_per_m"]

    road_capex = q["road_length_m"] * ec["civil"]["road_mbcu_per_m"]
    foundation_capex = q["footprint_area_m2"] * ec["civil"]["foundation_mbcu_per_m2"]
    maintenance_capex = q["maintenance_area_m2"] * ec["civil"]["maintenance_area_mbcu_per_m2"]
    civil_capex = road_capex + foundation_capex + maintenance_capex + pipeline_civil

    annual_mwh = sum(m.energy_mwh for m in normal_marches)
    energy_annual_cost = annual_mwh * ec["energy_tariff_mbcu_per_mwh"]
    energy_pv = energy_annual_cost * pvf
    maintenance_pv = equipment_maint * pvf

    lcc = equipment_capex + piping_capex + civil_capex + energy_pv + maintenance_pv
    return dict(
        pvf=pvf,
        equipment_capex_mbcu=equipment_capex,
        piping_capex_mbcu=piping_capex,
        civil_capex_mbcu=civil_capex,
        civil_breakdown=dict(roads=road_capex, foundations=foundation_capex,
                             maintenance_area=maintenance_capex, pipeline_civil=pipeline_civil),
        annual_energy_mwh=annual_mwh,
        energy_annual_cost_mbcu=energy_annual_cost,
        energy_pv_mbcu=energy_pv,
        equipment_maintenance_mbcu_per_year=equipment_maint,
        maintenance_pv_mbcu=maintenance_pv,
        lcc_mbcu=lcc,
        quantities=q,
    )
