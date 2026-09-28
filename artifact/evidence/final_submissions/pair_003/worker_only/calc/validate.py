"""
Full design validation + lifecycle cost + quantity take-off.

Writes ../results/validation.json, ../results/scenario_results.json,
../results/lcc.json, ../results/quantities.json and prints a report.
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
from ugslib import CATALOG, DIAMETERS, CLASSES

T_COOL = 58.0
LINEUPS = {
    "INJ-LOW": {"C1": 60.0, "C2": 60.0},
    "INJ-MID": {"C1": 50.0, "C2": 50.0},
    "INJ-HIGH": {"C1": 37.5, "C2": 37.5},
}
N1_CASES = [
    ("INJ-LOW", {"C2": 60.0, "C3": 24.0}, 84.0),
    ("INJ-MID", {"C2": 50.0, "C3": 20.0}, 70.0),
    ("INJ-HIGH", {"C2": 37.5, "C3": 15.0}, 52.5),
]
RES = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(RES, exist_ok=True)


def normal_results():
    r = [M.solve_injection(s, f, T_cool=T_COOL) for s, f in LINEUPS.items()]
    r.append(M.solve_withdrawal("WDR-HIGH", use_bypass=True))
    r.append(M.solve_withdrawal("WDR-MID", use_bypass=True))
    r.append(M.solve_withdrawal("WDR-LOW", comp_lineup={"C1": 35.0, "C2": 35.0}, use_bypass=False))
    return r


def n1_results():
    out = []
    for sid, lineup, flow in N1_CASES:
        out.append(("compressor N-1: " + sid, M.solve_injection(sid, lineup, flow=flow, T_cool=T_COOL)))
    out.append(("separator N-1: WDR-HIGH",
                M.solve_withdrawal("WDR-HIGH", use_bypass=True, sep_list=["SEP1", "SEP2"], flow=84.0)))
    out.append(("dehydration N-1: WDR-HIGH",
                M.solve_withdrawal("WDR-HIGH", use_bypass=True, dh_list=["DH1", "DH2"], flow=84.0)))
    out.append(("compressor N-1: WDR-LOW",
                M.solve_withdrawal("WDR-LOW", comp_lineup={"C2": 35.0, "C3": 14.0},
                                   use_bypass=False, flow=49.0)))
    out.append(("separator+dehydration N-1: WDR-LOW",
                M.solve_withdrawal("WDR-LOW", comp_lineup={"C1": 35.0, "C2": 35.0}, use_bypass=False,
                                   sep_list=["SEP1", "SEP2"], dh_list=["DH1", "DH2"], flow=49.0)))
    return out


# ---------------------------------------------------------------------------
def port_cardinality_issues():
    issues = []
    uses = {}
    for pid, p in D.PIPELINES.items():
        for ref in (p["src"], p["dst"]):
            key = (ref[0], ref[1], ref[2])
            uses.setdefault(key, []).append(pid)
    for key, pids in uses.items():
        kind, iid, port = key
        if kind == "E":
            mod = D.EQUIPMENT[iid]["model"]
            lim = 1
            for pp in mod["ports"]:
                if pp["id"] == port:
                    lim = pp.get("maximum_connections", 1)
            if len(pids) > lim:
                issues.append(f"{iid}.{port}: {len(pids)} connections > {lim}")
        else:
            iface = next(i for i in U.SITE["external_interfaces"] if i["interface_id"] == iid)
            lim = iface.get("maximum_connections", 1)
            if len(pids) > lim:
                issues.append(f"{iid}: {len(pids)} connections > {lim}")
    return issues


def port_type_issues():
    compat = {("gas_out", "gas_in"), ("gas_out", "gas_bidirectional"),
              ("gas_bidirectional", "gas_in"), ("gas_bidirectional", "gas_bidirectional"),
              ("liquid_out", "drain_in"), ("drain_out", "drain_in")}
    issues = []
    for pid, p in D.PIPELINES.items():
        def ptype(ref):
            if ref[0] == "E":
                return D.port_type(ref[1], ref[2])
            return D.BOUNDARY_PORTS[ref[1]][0]
        a, b = ptype(p["src"]), ptype(p["dst"])
        if (a, b) not in compat and (b, a) not in compat:
            issues.append(f"{pid}: incompatible ports {a} -> {b}")
    return issues


def velocity_issues(results):
    issues = []
    for r in results:
        for t in r["trace"]:
            if t["kind"] != "pipe":
                continue
            p = D.PIPELINES[t["id"]]
            lim = U.MAX_LIQ_V if p["service"] == "liquid_drain" else U.MAX_GAS_V
            if t["v"] > lim + 1e-6:
                issues.append(f"{r['scenario']} {t['id']}: v={t['v']:.3f} > {lim}")
    return issues


def class_issues(results):
    issues = []
    pmax = {}
    for r in results:
        for t in r["trace"]:
            if t["kind"] != "pipe":
                continue
            pmax[t["id"]] = max(pmax.get(t["id"], 0.0), t["P_in"], t["P_out"])
    for pid, p in D.PIPELINES.items():
        cls = CLASSES[p["cls"]]
        if pmax.get(pid, 0.0) > cls["maximum_allowable_pressure_mpa"] + 1e-6:
            issues.append(f"{pid}: max pressure {pmax[pid]:.3f} > class rating "
                          f"{cls['maximum_allowable_pressure_mpa']}")
        if not cls["liquid_drain_compatible"] and p["service"] == "liquid_drain":
            issues.append(f"{pid}: class not liquid-drain compatible")
    return issues


def equipment_envelope_issues(results):
    issues = []
    for r in results:
        for t in r["trace"]:
            if t["kind"] == "compressor":
                mod = CATALOG[t["model"]]
                if t["m"] > mod["capacity_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow {t['m']} > capacity")
                if t["m"] < mod["minimum_stable_flow_kg_s"] - 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow {t['m']} < min stable")
                if t["ratio"] > mod["maximum_pressure_ratio"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: ratio {t['ratio']:.3f} > max")
                if t["P_in"] > mod["maximum_suction_pressure_mpa"] + 1e-6:
                    issues.append(f"{r['scenario']} {t['id']}: suction P too high")
                if t["P_out"] > mod["maximum_discharge_pressure_mpa"] + 1e-6:
                    issues.append(f"{r['scenario']} {t['id']}: discharge P too high")
                if t["T_in"] > mod["maximum_suction_temperature_c"] + 1e-4:
                    issues.append(f"{r['scenario']} {t['id']}: suction T too high")
                if t["T_out"] > mod["maximum_discharge_temperature_c"] + 1e-4:
                    issues.append(f"{r['scenario']} {t['id']}: discharge T too high")
                if t["power_mw"] > mod["maximum_power_mw"] + 1e-6:
                    issues.append(f"{r['scenario']} {t['id']}: power too high")
            elif t["kind"] == "cooler":
                mod = CATALOG[t["model"]]
                if t["m"] > mod["capacity_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow > capacity")
                if t["duty_mw"] > mod["maximum_duty_mw"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: duty > maximum")
                if t["T_out"] < mod["minimum_outlet_temperature_c"] - 1e-4:
                    issues.append(f"{r['scenario']} {t['id']}: outlet T below minimum")
            elif t["kind"] == "separator":
                mod = CATALOG[t["model"]]
                if t["m"] > mod["capacity_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow > capacity")
                if t["fl_in"] > mod["maximum_feed_free_liquid_fraction"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: feed free liquid too high")
                if t["liquid_removed_kg_s"] > mod["maximum_liquid_rate_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: liquid rate too high")
            elif t["kind"] == "dehydration":
                mod = CATALOG[t["model"]]
                if t["m"] > mod["capacity_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow > capacity")
            elif t["kind"] == "meter":
                mod = CATALOG[t["model"]]
                if t["m"] > mod["capacity_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow {t['m']} > meter capacity")
                if t["P_in"] > mod["maximum_pressure_mpa"] + 1e-6:
                    issues.append(f"{r['scenario']} {t['id']}: pressure too high")
            elif t["kind"] == "regulator":
                mod = CATALOG[t["model"]]
                if t["m"] > mod["capacity_kg_s"] + 1e-9:
                    issues.append(f"{r['scenario']} {t['id']}: flow > capacity")
                if t["P_in"] > mod["maximum_pressure_mpa"] + 1e-6:
                    issues.append(f"{r['scenario']} {t['id']}: inlet pressure too high")
    return issues


def delivery_issues(results):
    issues = []
    req = {s["scenario_id"]: s for s in U.SCENARIOS["scenarios"]}
    for r in results:
        sc = req[r["scenario"]]
        if r["total_flow"] + 1e-9 < sc["required_total_flow_kg_s"] - 1e-9:
            continue  # N-1 partial-flow case handled by the caller
        for iface, d in r["delivery"].items():
            if d["P"] < sc["required_sink_pressure_mpa"] - 1e-5:
                issues.append(f"{r['scenario']} {iface}: P {d['P']:.5f} < required "
                              f"{sc['required_sink_pressure_mpa']}")
            if d["fl"] > M.DELIV_MAX_FL + 1e-9:
                issues.append(f"{r['scenario']} {iface}: free liquid {d['fl']:.2e} > limit")
            if d["water"] > M.DELIV_MAX_W + 1e-5:
                issues.append(f"{r['scenario']} {iface}: water {d['water']} > limit")
            if not (M.DELIV_T[0] <= d["T"] <= M.DELIV_T[1]):
                issues.append(f"{r['scenario']} {iface}: T {d['T']:.3f} outside limits")
    return issues


def metering_issues(results):
    issues = []
    req = {s["scenario_id"]: s for s in U.SCENARIOS["scenarios"]}
    for r in results:
        sc = req[r["scenario"]]
        meters = [t for t in r["trace"] if t["kind"] == "meter"]
        cap = sum(CATALOG[t["model"]]["capacity_kg_s"] for t in meters)
        if cap + 1e-9 < r["total_flow"]:
            issues.append(f"{r['scenario']}: active meter capacity {cap} < flow {r['total_flow']}")
    return issues


def boundary_issues(results):
    issues = []
    for r in results:
        if r["service"] == "withdrawal":
            for w, f in r["well_flows"].items():
                if f > 25.0 + 1e-9:
                    issues.append(f"{r['scenario']} {w}: allocation {f} > 25 kg/s")
        if r["service"] == "injection":
            for w, f in r["well_flows"].items():
                if f > 25.0 + 1e-9:
                    issues.append(f"{r['scenario']} {w}: allocation {f} > 25 kg/s")
        if r.get("liquid_total_kg_s", 0.0) > 10.0 + 1e-9:
            issues.append(f"{r['scenario']}: liquid outfall flow > 10 kg/s")
    return issues


def completeness_issues(results):
    issues = []
    seen_p, seen_e = set(), set()
    for r in results:
        for t in r["trace"]:
            if t["kind"] == "pipe":
                seen_p.add(t["id"])
            else:
                seen_e.add(t["id"])
    for pid in D.PIPELINES:
        if pid not in seen_p:
            issues.append(f"{pid}: never appears in any scenario path")
    for eid in D.EQUIPMENT:
        if eid not in seen_e:
            issues.append(f"{eid}: never appears in any scenario path")
    return issues


def main():
    rep = {}
    rep["geometry"] = C.check_geometry()
    rep["roads"] = C.check_roads()
    rep["access"], acc_info = C.check_maintenance_access()
    rep["pipelines"] = C.check_pipelines()
    rep["port_cardinality"] = port_cardinality_issues()
    rep["port_types"] = port_type_issues()

    res = normal_results()
    n1 = n1_results()
    all_res = res + [r for _, r in n1]
    rep["velocity"] = velocity_issues(all_res)
    rep["pipe_class"] = class_issues(all_res)
    rep["equipment_envelope"] = equipment_envelope_issues(all_res)
    rep["delivery"] = delivery_issues(res)
    rep["metering"] = metering_issues(res)
    rep["boundary"] = boundary_issues(all_res)
    rep["completeness"] = completeness_issues(all_res)
    rep["n1_delivery"] = []
    req = {s["scenario_id"]: s for s in U.SCENARIOS["scenarios"]}
    for label, r in n1:
        frac = r["total_flow"] / req[r["scenario"]]["required_total_flow_kg_s"]
        if frac < 0.7 - 1e-9:
            rep["n1_delivery"].append(f"{label}: retained flow {frac:.3f} < 0.7")
        for iface, d in r["delivery"].items():
            if d["P"] < req[r["scenario"]]["required_sink_pressure_mpa"] - 1e-5:
                rep["n1_delivery"].append(f"{label}: {iface} P below limit")
            if d["fl"] > M.DELIV_MAX_FL + 1e-9 or d["water"] > M.DELIV_MAX_W + 1e-5:
                rep["n1_delivery"].append(f"{label}: quality limit exceeded")
            if not (M.DELIV_T[0] <= d["T"] <= M.DELIV_T[1]):
                rep["n1_delivery"].append(f"{label}: temperature outside limits")

    L = LC.lifecycle_cost(res)
    Q = LC.quantities()

    # operating hours check
    reps = []
    tot_issues = 0
    for k, v in rep.items():
        tot_issues += len(v)
    rep["_summary"] = {k: len(v) for k, v in rep.items()}
    rep["_total"] = tot_issues

    with open(os.path.join(RES, "validation.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    with open(os.path.join(RES, "lcc.json"), "w") as fh:
        json.dump({k: v for k, v in L.items() if not k.endswith("_detail")}, fh, indent=1)
    with open(os.path.join(RES, "quantities.json"), "w") as fh:
        json.dump(Q, fh, indent=1)
    with open(os.path.join(RES, "scenario_results.json"), "w") as fh:
        json.dump({"normal": res, "n1": {lbl: r for lbl, r in n1}}, fh, indent=1)

    print("VALIDATION ISSUES")
    for k, v in rep.items():
        if k.startswith("_"):
            continue
        print(f"  {k:22s} {len(v)}")
        for s in v[:8]:
            print("      ", s)
    print("TOTAL ISSUES:", tot_issues)
    print()
    print("LCC = %.4f MBCU" % L["lcc"])
    for k in ("equipment_capex", "piping_capex", "civil_capex_total", "energy_pv",
              "maintenance_pv", "annual_energy_mwh", "annual_maintenance_mbcu"):
        print("   %-26s %.4f" % (k, L[k]))
    print()
    print("SCENARIO SUMMARY")
    for r in res:
        d = next(iter(r["delivery"].values()))
        print("  %-9s m=%6.1f  Pdel=%.3f  Tdel=%.2f  water=%.1f  fl=%.2e  Pwr=%.3f MW"
              % (r["scenario"], r["total_flow"], d["P"], d["T"], d["water"], d["fl"],
                 r["compressor_power_mw"] + r["aux_power_mw"] + r.get("dehyd_power_mw", 0.0)))
    print()
    print("N-1 SUMMARY")
    for lbl, r in n1:
        d = next(iter(r["delivery"].values()))
        print("  %-34s m=%6.1f  Pdel=%.3f T=%.1f fl=%.2e water=%.1f"
              % (lbl, r["total_flow"], d["P"], d["T"], d["fl"], d["water"]))
    return rep, L, Q, res, n1


if __name__ == "__main__":
    main()
