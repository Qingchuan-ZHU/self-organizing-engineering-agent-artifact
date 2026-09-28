"""Coordinate-descent optimiser for the pipeline diameters of the design.

The lifecycle cost depends on the diameters through piping CAPEX, pipeline civil
cost and the compressor/energy cost (losses change the required compressor
discharge pressures).  Equipment and maintenance costs are independent of the
diameters, so only the diameter-dependent part is optimised here.

Usage:  python optimize.py [--brief DIR] [--out FILE]
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ugs_basis as B
import ugs_design as D
from ugs_check import Design
import ugs_operate as O

DN_ORDER = ["DN150", "DN200", "DN250", "DN300", "DN350", "DN400", "DN450", "DN500",
            "DN600", "DN700"]


GROUPS = {
    "well branches": ["P-131", "P-132", "P-133", "P-134", "P-135", "P-136"],
    "injection suction manifold": ["P-103", "P-104", "P-105"],
    "injection discharge manifold": ["P-106", "P-107", "P-108"],
    "aftercooler inlet": ["P-109"],
    "withdrawal trunks": ["P-114", "P-115", "P-116"],
    "separator-dehydration": ["P-117", "P-118", "P-119"],
    "dehydration-header": ["P-120", "P-121", "P-122"],
    "boost feed (treated gas to suction header)": ["P-143"],
    "boost discharge (discharge header to delivery header)": ["P-144"],
}

SINGLES = ["P-101", "P-102", "P-113", "P-123", "P-128", "P-129", "P-130"]
ALL_PIPES = None  # filled from the design in main()


def make_design(case, dn_map):
    pipes = []
    for p in D.PIPES:
        q = dict(p)
        if p["tag"] in dn_map:
            q["dn"] = dn_map[p["tag"]]
        pipes.append(q)
    return Design(case, D.EQUIPMENT, pipes, D.ROADS)


def evaluate(design: Design):
    """Diameter-dependent part of the LCC (piping CAPEX + pipeline civil + energy
    PV) using the normal operating scenarios only, with hard penalties for any
    violated service limit so the optimiser cannot buy cheap pipe with an
    infeasible hydraulic state."""
    case = design.case
    ec = case.economic_assumptions
    pvf = case.pvf()
    piping = 0.0
    civil = 0.0
    for tag, pl in design.pipes.items():
        dn_cost = design.d(pl.dn)["installed_cost_mbcu_per_m"]
        cls_mult = design.pc(pl.cls)["installed_cost_multiplier"]
        for (p0, p1, lvl, idx) in pl.segments():
            ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            piping += ln * dn_cost * cls_mult * case.routing_levels[lvl]["installed_cost_multiplier"]
            civil += ln * case.routing_levels[lvl]["civil_cost_mbcu_per_m"]
    energy = 0.0
    penalty = 0.0
    for plan in O.build_plans(design):
        _, m = O.run_plan(design, plan)
        if plan["kind"] == "normal":
            energy += m.energy_mwh
        for tag, res in m.pipe_state.items():
            if res.flow <= 0:
                continue
            if not res.converged:
                penalty += 1000.0
            if res.velocity_m_s > case.max_gas_velocity:
                penalty += 1000.0 * (res.velocity_m_s - case.max_gas_velocity)
        for name, ok, detail in m.checks:
            if not ok:
                penalty += 1000.0
    return (piping + civil + energy * ec["energy_tariff_mbcu_per_mwh"] * pvf + penalty,
            energy, piping, civil)


def main():
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    ap.add_argument("--brief", default=str(here.parent.parent / "brief"))
    ap.add_argument("--out", default=str(here.parent / "deliverables" / "diameters.json"))
    args = ap.parse_args()
    case = B.CaseData(Path(args.brief))

    global ALL_PIPES
    ALL_PIPES = [p["tag"] for p in D.PIPES]
    dn_map = {p["tag"]: p["dn"] for p in D.PIPES}
    best_cost, energy, piping, civil = evaluate(make_design(case, dn_map))
    print(f"start: cost {best_cost:.4f} MBCU  energy {energy:.0f} MWh/a  "
          f"piping {piping:.3f}  civil {civil:.4f}")
    t0 = time.time()
    improved = True
    sweeps = 0
    while improved and sweeps < 8:
        improved = False
        sweeps += 1
        for name, tags in list(GROUPS.items()) + [(t, [t]) for t in ALL_PIPES]:
            orig = {t: dn_map[t] for t in tags}
            best_val = best_cost
            best_cfg = dict(orig)
            for cand in DN_ORDER:
                for t in tags:
                    dn_map[t] = cand
                val, e, p, c = evaluate(make_design(case, dn_map))
                if val < best_val - 1e-9:
                    best_val = val
                    best_cfg = {t: cand for t in tags}
            dn_map.update(best_cfg)
            if best_cfg != orig:
                improved = True
                best_cost = best_val
                print(f"  {name}: {orig} -> {best_cfg}   cost {best_cost:.4f} MBCU  "
                      f"({time.time() - t0:.1f} s)")
    print(f"final: {best_cost:.4f} MBCU after {sweeps} sweeps ({time.time() - t0:.1f} s)")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dn_map, indent=2))
    print(out)


if __name__ == "__main__":
    main()
