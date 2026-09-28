"""Independent cross-checks of the design calculations.

These checks deliberately use a different implementation style from the main
model (brute-force polygon geometry instead of clipping, an explicit iteration
instead of the packaged helper, hand-assembled cost arithmetic) so that a
mistake in the main model is unlikely to be repeated here.  They read only the
published brief data and ``deliverables/design.json``.

Usage:  python crosscheck.py [--brief DIR] [--design FILE]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

RU = 8.314462618
fails = []


def report(name, expected, actual, tol, unit=""):
    ok = abs(expected - actual) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {name}: independent {expected:.6f} vs design "
          f"{actual:.6f} {unit} (tol {tol:g})")
    if not ok:
        fails.append(name)


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default=str(here.parent.parent / "brief"))
    ap.add_argument("--design", default=str(here.parent / "deliverables" / "design.json"))
    args = ap.parse_args()
    brief = Path(args.brief)
    gp = json.loads((brief / "gas_properties.json").read_text())
    pc = json.loads((brief / "piping_catalog.json").read_text())
    ec = json.loads((brief / "economic_assumptions.json").read_text())
    design = json.loads(Path(args.design).read_text())

    mw = gp["molecular_weight_kg_mol"]
    k = gp["specific_heat_ratio"]
    cp = gp["heat_capacity_cp_j_kg_k"]

    def z(p, t):
        return min(gp["compressibility_proxy"]["maximum"],
                   max(gp["compressibility_proxy"]["minimum"],
                       0.90 + 0.08 * p / (p + 10.0) + 0.00015 * (t + 273.15 - 293.15)))

    def mu(p, t):
        return min(gp["viscosity_proxy"]["maximum"],
                   max(gp["viscosity_proxy"]["minimum"],
                       1.05e-5 * ((t + 273.15) / 293.15) ** 0.70 * (1 + 0.002 * p)))

    def rho(p, t):
        return p * 1e6 * mw / (z(p, t) * RU * (t + 273.15))

    def dp_mpa(p_in, t, m, length, d, eps):
        p_out = p_in
        for _ in range(8):
            p_mean = max(1e-6, (p_in + p_out) / 2)
            r = rho(p_mean, t)
            v = m / (r * math.pi * d * d / 4)
            re = r * v * d / mu(p_mean, t)
            f = 64 / re if re < 2300 else 0.25 / math.log10(eps / (3.7 * d) + 5.74 / re ** 0.9) ** 2
            p_new = max(1e-6, p_in - f * (length / d) * r * v * v / 2 / 1e6)
            if abs(p_new - p_out) < 1e-5:
                p_out = p_new
                break
            p_out = p_new
        return p_in - p_out

    by_tag = {e["tag"]: e for e in design["equipment"]}
    pipes = {p["tag"]: p for p in design["pipelines"]}
    classes = {c["class_id"]: c for c in pc["classes"]}
    dns = {d["nominal_diameter"]: d for d in pc["diameters"]}
    models = {}
    for f in (brief / "equipment_catalog").glob("*.json"):
        for m in json.loads(f.read_text())["models"]:
            models[m["model_id"]] = m

    # ---- 1. pipeline pressure loss, re-derived from the formula -------------
    sc = {s["scenario_id"]: s for s in design["scenarios"]}
    inj_low = sc["INJ-LOW"]
    for tag, t_stream in [("P-113", 50.0), ("P-131", 50.0), ("P-101", 25.0)]:
        pl = pipes[tag]
        cls = classes[pl["pipe_class"]]
        m_dot = inj_low["pipe_flows"].get(tag, 0.0)
        if m_dot <= 0:
            continue
        p_in = inj_low["unit_states"].get(pl["from_ref"][0], {}).get("p_out")
        if p_in is None:
            p_in = inj_low["unit_states"].get(pl["from_ref"][0], {}).get("p")
        indep = dp_mpa(p_in, t_stream, m_dot, pl["length_m"], pl["internal_diameter_m"],
                       cls["roughness_m"])
        p_out = inj_low["unit_states"].get(pl["to_ref"][0], {}).get("p_in")
        if p_out is None:
            p_out = inj_low["unit_states"].get(pl["to_ref"][0], {}).get("p")
        if p_out is not None:
            report(f"{tag} pressure loss (INJ-LOW)", indep, p_in - p_out, 2e-4, "MPa")

    # ---- 2. compressor power / discharge temperature ------------------------
    inj_high = sc["INJ-HIGH"]
    tag = "CMP-INJ-01"
    st = inj_high["unit_states"][tag]
    ratio = st["p_out"] / st["p_in"]
    indep_w = st["flow"] * cp * (st["t_in"] + 273.15) * (ratio ** ((k - 1) / k) - 1) / \
        (models[by_tag[tag]["model_id"]]["efficiency_proxy"] *
         models[by_tag[tag]["model_id"]]["driver_efficiency"]) / 1e6
    report(f"{tag} driver power (INJ-HIGH)", indep_w, st["power_mw"], 1e-6, "MW")
    indep_t = (st["t_in"] + 273.15) * (1 + (ratio ** ((k - 1) / k) - 1) /
                                       models[by_tag[tag]["model_id"]]["efficiency_proxy"]) - 273.15
    report(f"{tag} discharge temperature (INJ-HIGH)", indep_t, st["t_out"], 1e-5, "degC")
    report(f"{tag} pressure ratio", ratio, st["ratio"], 1e-6)

    # regulator JT step
    st = sc["WDR-HIGH"]["unit_states"]["REG-WDR-01"]
    jt = models[by_tag["REG-WDR-01"]["model_id"]]["jt_temperature_coefficient_k_per_mpa"]
    report("regulator outlet temperature (WDR-HIGH)",
           st["t_in"] - jt * (st["p_in"] - st["p_out"]), st["t_out"], 1e-6, "degC")

    # separator liquid removal
    sep = "SEP-WDR-01"
    st = sc["WDR-HIGH"]["unit_states"][sep]
    eff = models[by_tag[sep]["model_id"]]["liquid_removal_efficiency"]
    report(f"{sep} removed liquid (WDR-HIGH)", st["flow"] * st["liquid_in"] * eff,
           st["liquid_removed"], 1e-9, "kg/s")
    report(f"{sep} outlet free liquid", st["liquid_in"] * (1 - eff), st["liquid_out"], 1e-12)

    # ---- 3. geometry: brute-force minimum distance --------------------------
    def rect(cx, cy, L, W, ang):
        hx, hy = L / 2, W / 2
        pts = [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]
        a = math.radians(ang)
        return [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a),
                 cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]

    def seg_dist(p, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))

    def poly_dist(p1, p2):
        best = 1e9
        for p in p1:
            for i in range(len(p2)):
                best = min(best, seg_dist(p, p2[i], p2[(i + 1) % len(p2)]))
        for p in p2:
            for i in range(len(p1)):
                best = min(best, seg_dist(p, p1[i], p1[(i + 1) % len(p1)]))
        return best

    sep_matrix = json.loads((brief / "safety_requirements.json").read_text())["minimum_separation_m"]
    # brute force over every pair: the closest pair must still satisfy the matrix
    worst = None
    tags = list(by_tag)
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            a, b = by_tag[tags[i]], by_tag[tags[j]]
            pa = rect(a["x_m"], a["y_m"], a["footprint_m"]["length"], a["footprint_m"]["width"],
                      a["orientation_deg"])
            pb = rect(b["x_m"], b["y_m"], b["footprint_m"]["length"], b["footprint_m"]["width"],
                      b["orientation_deg"])
            d = poly_dist(pa, pb)
            req = sep_matrix[a["safety_category"]][b["safety_category"]]
            margin = d - req
            if worst is None or margin < worst[0]:
                worst = (margin, tags[i], tags[j], d, req)
    print(f"{'ok  ' if worst[0] >= -1e-6 else 'FAIL'} closest separation pair "
          f"{worst[1]}/{worst[2]}: distance {worst[3]:.4f} m vs required {worst[4]:g} m "
          f"(margin {worst[0]:+.4f} m)")
    if worst[0] < -1e-6:
        fails.append("separation")

    # ---- 4. cost arithmetic -------------------------------------------------
    piping = 0.0
    civil_pipe = 0.0
    for p in design["pipelines"]:
        c = classes[p["pipe_class"]]
        diam = dns[p["nominal_diameter"]]
        for seg in p["segments"]:
            lvl = pc["routing_levels"][seg["level"]]
            piping += seg["length_m"] * diam["installed_cost_mbcu_per_m"] * \
                c["installed_cost_multiplier"] * lvl["installed_cost_multiplier"]
            civil_pipe += seg["length_m"] * lvl["civil_cost_mbcu_per_m"]
    report("piping CAPEX", piping, design["lifecycle_cost"]["piping_capex_mbcu"], 1e-9, "MBCU")
    report("pipeline civil cost", civil_pipe,
           design["lifecycle_cost"]["civil_breakdown"]["pipeline_civil"], 1e-9, "MBCU")

    i, n = ec["discount_rate"], ec["project_life_years"]
    pvf = (1 - (1 + i) ** -n) / i
    report("present-value factor", pvf, design["lifecycle_cost"]["pvf"], 1e-12)

    capex = sum(models[e["model_id"]]["capex_mbcu"] for e in design["equipment"])
    maint = sum(models[e["model_id"]]["annual_maintenance_mbcu"] for e in design["equipment"])
    report("equipment CAPEX", capex, design["lifecycle_cost"]["equipment_capex_mbcu"], 1e-12, "MBCU")
    report("maintenance PV", maint * pvf, design["lifecycle_cost"]["maintenance_pv_mbcu"], 1e-9)
    road_len = 0.0
    for r in design["roads"]:
        pts = r["centreline"]
        road_len += sum(math.dist(pts[q], pts[q + 1]) for q in range(len(pts) - 1))
    report("road CAPEX", road_len * ec["civil"]["road_mbcu_per_m"],
           design["lifecycle_cost"]["civil_breakdown"]["roads"], 1e-9, "MBCU")
    lcc = (capex + piping + sum(design["lifecycle_cost"]["civil_breakdown"].values())
           + design["lifecycle_cost"]["energy_pv_mbcu"] + maint * pvf)
    report("LCC total", lcc, design["lifecycle_cost"]["lcc_mbcu"], 1e-6, "MBCU")

    # ---- 5. mass balance of every scenario ----------------------------------
    for s in design["scenarios"]:
        wsum = sum(s["well_group_flows"].values())
        ok = abs(wsum - s["source"]["flow"]) < 1e-4  # exported values are rounded to 1e-6
        if not ok:
            fails.append("mass balance " + s["scenario_id"])
        print(f"{'ok  ' if ok else 'FAIL'} mass balance {s['scenario_id']}: well-group allocation "
              f"{wsum:.6f} vs source {s['source']['flow']:.6f} kg/s")

    print()
    print("cross-check failures:", len(fails), fails if fails else "")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
