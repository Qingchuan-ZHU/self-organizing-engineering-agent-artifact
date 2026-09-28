"""
Diameter / pipe-class optimiser: local search on LCC.

Writes the optimised (diameter, class) selection to ../data/pipe_sizes.json.
"""
from __future__ import annotations

import json
import math
import os
import sys

import ugslib as U
import design as D
import checks as C
import model as M
import lcc as LC
from ugslib import DIAMETERS, CLASSES

T_COOL = 58.0
LINEUPS = {
    "INJ-LOW": {"C1": 60.0, "C2": 60.0},
    "INJ-MID": {"C1": 50.0, "C2": 50.0},
    "INJ-HIGH": {"C1": 37.5, "C2": 37.5},
}
MAX_GAS_V = U.PIPING["maximum_gas_velocity_m_s"]
MAX_LIQ_V = U.PIPING["maximum_liquid_drain_velocity_m_s"]
LIQ_RHO = U.LIQUID_DENSITY


N1_CASES = [
    ("INJ-LOW", {"C2": 60.0, "C3": 24.0}, 84.0),
    ("INJ-MID", {"C2": 50.0, "C3": 20.0}, 70.0),
    ("INJ-HIGH", {"C2": 37.5, "C3": 15.0}, 52.5),
]


def run_all(with_n1=True):
    res = [M.solve_injection(s, f, T_cool=T_COOL) for s, f in LINEUPS.items()]
    res.append(M.solve_withdrawal("WDR-HIGH", use_bypass=True))
    res.append(M.solve_withdrawal("WDR-MID", use_bypass=True))
    res.append(M.solve_withdrawal("WDR-LOW", comp_lineup={"C1": 35.0, "C2": 35.0}, use_bypass=False))
    if with_n1:
        for sid, lineup, flow in N1_CASES:
            res.append(M.solve_injection(sid, lineup, flow=flow, T_cool=T_COOL))
        res.append(M.solve_withdrawal("WDR-HIGH", use_bypass=True,
                                      sep_list=["SEP1", "SEP2"], flow=84.0))
        res.append(M.solve_withdrawal("WDR-HIGH", use_bypass=True,
                                      dh_list=["DH1", "DH2"], flow=84.0))
        res.append(M.solve_withdrawal("WDR-LOW", comp_lineup={"C2": 35.0, "C3": 14.0},
                                      use_bypass=False, flow=49.0))
    return res


def evaluate():
    res = run_all(with_n1=False)
    return res, LC.lifecycle_cost(res)


def pipe_stats(res, pid):
    """(max pressure, max velocity, max mass flow) for one pipeline."""
    p, v, m = 0.0, 0.0, 0.0
    for r in res:
        for t in r["trace"]:
            if t["kind"] == "pipe" and t["id"] == pid:
                p = max(p, t["P_in"], t["P_out"])
                v = max(v, t.get("v", 0.0))
                m = max(m, t["m"])
    return p, v, m


FLOW_MAX = {}
RHO_MIN = {}
PMAX_ALL = {}


def build_flow_envelope():
    """Maximum mass flow and minimum density per pipeline over all scenarios
    (normal operation and every N-1 outage case)."""
    global FLOW_MAX, RHO_MIN, PMAX_ALL
    res = run_all()
    FLOW_MAX, RHO_MIN, PMAX_ALL = {}, {}, {}
    for r in res:
        for t in r["trace"]:
            if t["kind"] != "pipe":
                continue
            pid = t["id"]
            FLOW_MAX[pid] = max(FLOW_MAX.get(pid, 0.0), t["m"])
            RHO_MIN[pid] = min(RHO_MIN.get(pid, 1e9), t["rho"])
            PMAX_ALL[pid] = max(PMAX_ALL.get(pid, 0.0), t["P_in"], t["P_out"])


def velocity_for(pid, res, dn, service):
    """Max velocity of this pipeline's medium with the given diameter."""
    m = FLOW_MAX.get(pid, 0.0)
    d = DIAMETERS[dn]["internal_diameter_m"]
    a = math.pi * d * d / 4.0
    if a <= 0:
        return 0.0
    if service == "liquid_drain":
        return m / (LIQ_RHO * a)
    rho = RHO_MIN.get(pid, 50.0)
    return m / (rho * a)


def choose_class(pmax):
    return "CS-WET-100" if pmax <= 10.0 + 1e-9 else "CS-WET-160"


def optimize(passes=8, verbose=True):
    build_flow_envelope()
    res, L = evaluate()
    best_lcc = L["lcc"]
    for it in range(passes):
        improved = False
        for pid in list(D.PIPELINES):
            p = D.PIPELINES[pid]
            service = p["service"]
            pmax = PMAX_ALL.get(pid, 1e9)
            cls_ok = "CS-WET-100" if service == "liquid_drain" else choose_class(pmax)
            cur_dn, cur_cls = p["dn"], p["cls"]
            best_dn, best_lcc_here = cur_dn, best_lcc
            for dn in DIAMETERS:
                v = velocity_for(pid, res, dn, service)
                lim = MAX_LIQ_V if service == "liquid_drain" else MAX_GAS_V
                if v > lim + 1e-9:
                    continue
                p["dn"], p["cls"] = dn, cls_ok
                r2, L2 = evaluate()
                if L2["lcc"] < best_lcc_here - 1e-9:
                    best_dn, best_lcc_here = dn, L2["lcc"]
            p["dn"], p["cls"] = best_dn, cls_ok
            if best_dn != cur_dn or cls_ok != cur_cls:
                improved = True
                res, L = evaluate()
                best_lcc = L["lcc"]
                if verbose:
                    print(f"  pass{it} {pid}: {cur_dn}/{cur_cls} -> {best_dn}/{cls_ok}"
                          f"  LCC={best_lcc:.4f}")
        if not improved:
            break
    return res, L


if __name__ == "__main__":
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    res, L = optimize(passes)
    print("OPTIMISED LCC %.6f" % L["lcc"])
    out = {pid: {"dn": D.PIPELINES[pid]["dn"], "cls": D.PIPELINES[pid]["cls"]}
           for pid in D.PIPELINES}
    path = os.path.join(os.path.dirname(__file__), "..", "data", "pipe_sizes.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    for pid in sorted(out):
        print(pid, out[pid]["dn"], out[pid]["cls"])
