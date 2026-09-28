"""Driver: solve all scenarios, run all constraint checks (incl. N-1), compute LCC."""
import sys, json, math
sys.path.insert(0, "/workspace/project")
import ugs_core as C
import ugs_analysis as A
from ugs_design import load, load_catalog, INSTANCES, footprint, envelope_rects

CAT = A.CAT
ECON = A.ECON
PIPE = A.PIPE
LEN = A.LEN
LEVEL = A.LEVEL
DIAM_MAP = A.DIAM_MAP
CLASSES = A.CLASSES
LEVELS = A.LEVELS
SCEN = A.SCEN

CHECKS = []


def chk(ok, tag, scen, msg):
    CHECKS.append(dict(ok=bool(ok), tag=tag, scenario=scen, message=msg))


def lim(ok, tag, scen, msg):
    if not ok:
        chk(False, tag, scen, msg)
    else:
        chk(True, tag, scen, msg)


def solve_all(dg):
    res = {}
    for s in SCEN:
        if s["service"] == "injection":
            res[s["id"]] = A.solve_injection(s, dg)
        elif s["id"] in ("WDR-HIGH", "WDR-MID"):
            res[s["id"]] = A.solve_withdrawal_reg(s, dg)
        else:
            res[s["id"]] = A.solve_withdrawal_boost(s, dg)
    return res


def check_scenarios(dg, res):
    Dyn, epsn, tbl = dg["Dyn"], dg["epsn"], dg["tbl"]
    energy = {}
    for s in SCEN:
        sid = s["id"]; m = s["m"]; r = res[sid]
        if s["service"] == "injection":
            # meter
            lim(m <= CAT["MTR120"]["capacity_kg_s"] + 1e-9, "meter", sid, f"meter flow {m} > cap")
            # headers
            for h in ("H-GS", "H-CH", "H-WS"):
                lim(m <= CAT["HDR120"]["capacity_kg_s"] + 1e-9, "header", sid, f"{h} flow {m} > cap")
            # compressors
            Wt = 0.0
            for cid, info in r["comp"].items():
                mdl = CAT[{"C-I1": "C60", "C-I2": "C60"}[cid]]
                lim(info["r"] <= mdl["maximum_pressure_ratio"] + 1e-9, "comp-ratio", sid, f"{cid} r={info['r']:.3f}")
                lim(info["To"] <= mdl["maximum_discharge_temperature_c"] + 1e-4, "comp-tout", sid, f"{cid} Tout={info['To']:.1f}")
                lim(info["Ps"] <= mdl["maximum_suction_pressure_mpa"] + 1e-5, "comp-psuct", sid, f"{cid} Psuct={info['Ps']:.2f}")
                lim(info["Pd"] <= mdl["maximum_discharge_pressure_mpa"] + 1e-5, "comp-pdis", sid, f"{cid} Pdis={info['Pd']:.2f}")
                lim(mdl["minimum_stable_flow_kg_s"] - 1e-9 <= info["q"] <= mdl["capacity_kg_s"] + 1e-9, "comp-flow", sid,
                    f"{cid} q={info['q']:.2f}")
                W = A.power_mw(info["q"], s["Tsrc"], info["r"], mdl["efficiency_proxy"], mdl["driver_efficiency"])
                Wt += W
                lim(W <= mdl["maximum_power_mw"] + 1e-9, "comp-power", sid, f"{cid} W={W:.2f}")
            duty = m * A.CP * max(0.0, r["Thot"] - r["Tcool"]) / 1e6
            lim(duty <= CAT["COOL120"]["maximum_duty_mw"] + 1e-9, "cooler-duty", sid, f"duty={duty:.2f}")
            lim(r["Tcool"] >= CAT["COOL120"]["minimum_outlet_temperature_c"] - 1e-4, "cooler-tout", sid, f"Tout={r['Tcool']:.1f}")
            lim(min(w[0] for w in r["wells"]) >= s["Psink"] - 1e-5, "injection-delivery", sid,
                f"well P={min(w[0] for w in r['wells']):.3f} < {s['Psink']}")
            lim(-10.0 <= r["Tcool"] <= 60.0 + 1e-4, "delivery-temp", sid, f"T={r['Tcool']:.2f}")
            for i, (P, v) in enumerate(r["wells"], start=1):
                lim(v <= A.GAS_VMAX + 1e-6, "velocity", sid, f"N-WS-WG{i} v={v:.2f}")
            for nid in ("N-MTRINJ-GRID", "N-MTRINJ-GS", "N-GS-CI1", "N-GS-CI2", "N-CI1-CH", "N-CI2-CH",
                        "N-CH-COOL", "N-COOL-WS"):
                q = A.scenario_flows(s).get(nid)
                if q:
                    rr = C.pipe_pressure_loss_mpa(10.0, q, Dyn[nid], LEN[nid], epsn[nid], 40.0, A.GP)
                    lim(rr["v"] <= A.GAS_VMAX + 1e-6, "velocity", sid, f"{nid} v={rr['v']:.2f}")
            energy[sid] = Wt + duty * CAT["COOL120"]["electric_power_fraction_of_duty"]
        else:
            # treatment
            fl = s["fl"]
            lim(fl <= CAT["SEP70"]["maximum_feed_free_liquid_fraction"] + 1e-9, "sep-feed", sid, f"sep feed fl={fl}")
            liq = (m / 3.0) * fl * CAT["SEP70"]["liquid_removal_efficiency"]
            lim(liq <= CAT["SEP70"]["maximum_liquid_rate_kg_s"] + 1e-9, "sep-liquid", sid, f"sep liq={liq:.3f}")
            flout = fl * (1 - CAT["SEP70"]["liquid_removal_efficiency"])
            lim(flout <= CAT["DEHY70"]["maximum_feed_free_liquid_fraction"] + 1e-9, "dehy-feed", sid, f"dehy feed fl={flout:.2e}")
            lim(CAT["DEHY70"]["normal_outlet_water_mg_sm3"] <= 50.0 + 1e-5, "dehy-water", sid, "dehy water")
            lim(flout <= 0.0001 + 1e-9, "delivery-fl", sid, f"delivered fl={flout:.2e}")
            for h in ("H-WS", "H-TS", "H-GS"):
                lim(m <= CAT["HDR120"]["capacity_kg_s"] + 1e-9, "header", sid, f"{h} flow {m}")
            lim(m <= CAT["MTR120"]["capacity_kg_s"] + 1e-9, "meter", sid, "meter flow")
            dehy_E = m * CAT["DEHY70"]["energy_mw_per_kg_s"]
            if sid in ("WDR-HIGH", "WDR-MID"):
                lim(r["P_reg_in"] <= CAT["REG120"]["maximum_pressure_mpa"] + 1e-5, "reg-pin", sid, f"Pin={r['P_reg_in']:.2f}")
                lim(r["P_reg_in"] > r["Preg_out"] + 1e-6, "reg-dp", sid, "no dP")
                lim(m <= CAT["REG120"]["capacity_kg_s"] + 1e-9, "reg-flow", sid, "reg flow")
                lim(-10.0 <= r["Tdel"] <= 60.0 + 1e-4, "delivery-temp", sid, f"T={r['Tdel']:.2f}")
                lim(r["Pgrid"] >= s["Psink"] - 1e-5, "delivery-pressure", sid, f"Pgrid={r['Pgrid']:.3f}")
                energy[sid] = dehy_E
            else:
                Wt = 0.0
                for c in r["comp"]:
                    mdl = CAT["C60"]
                    lim(c["r"] <= mdl["maximum_pressure_ratio"] + 1e-9, "comp-ratio", sid, f"{c['id']} r={c['r']:.3f}")
                    lim(c["Ps"] <= mdl["maximum_suction_pressure_mpa"] + 1e-5, "comp-psuct", sid, f"{c['id']} Psuct={c['Ps']:.2f}")
                    lim(c["Pd"] <= mdl["maximum_discharge_pressure_mpa"] + 1e-5, "comp-pdis", sid, f"{c['id']} Pd={c['Pd']:.2f}")
                    lim(mdl["minimum_stable_flow_kg_s"] - 1e-9 <= c["q"] <= mdl["capacity_kg_s"] + 1e-9, "comp-flow", sid,
                        f"{c['id']} q={c['q']}")
                    lim(c["W"] <= mdl["maximum_power_mw"] + 1e-9, "comp-power", sid, f"{c['id']} W={c['W']:.2f}")
                    Wt += c["W"]
                lim(-10.0 <= r["Tdel"] <= 60.0 + 1e-4, "delivery-temp", sid, f"T={r['Tdel']:.2f}")
                lim(r["Pgrid"] >= s["Psink"] - 1e-5, "delivery-pressure", sid, f"Pgrid={r['Pgrid']:.3f}")
                energy[sid] = Wt + dehy_E
            for nid, v in r["velocities"]:
                lim(v <= A.GAS_VMAX + 1e-6, "velocity", sid, f"{nid} v={v:.2f}")
            # liquid drain velocity
            liqflow = m * fl / 3.0
            for nid in ("N-SEP1-DRN1", "N-DRN1-OUT"):
                D = Dyn[nid]
                v = liqflow / (A.CP_LIQ * math.pi * D * D / 4.0)
                lim(v <= A.PIPE["maximum_liquid_drain_velocity_m_s"] + 1e-6, "liq-velocity", sid, f"{nid} v={v:.2f}")
    return energy


# ------------------------------------------------------------------ N-1
def check_nminus1(dg):
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    out = {}
    # compression N-1: injection scenarios + WDR-LOW
    comp_cases = [s for s in SCEN if s["Psink"] > s["Psrc"]]
    for s in comp_cases:
        frac = 0.7
        mN = frac * s["m"]
        if s["service"] == "injection":
            # worst case: a C60 unit lost -> remaining C60 + C40
            cap = {"C-I1": CAT["C60"]["capacity_kg_s"], "C-I2": CAT["C60"]["capacity_kg_s"],
                   "C-I3": CAT["C40"]["capacity_kg_s"]}
            # allocate proportionally to capacity among remaining {C-I1(60), C-I3(40)}
            remain = {"C-I1": 60.0, "C-I3": 40.0}
            tot = sum(remain.values())
            alloc = {k: mN * v / tot for k, v in remain.items()}
            # upstream pressures
            T0 = s["Tsrc"]
            P, _ = A.pout(s["Psrc"], s["m"], Dyn["N-MTRINJ-GRID"], LEN["N-MTRINJ-GRID"], epsn["N-MTRINJ-GRID"], T0)
            P -= CAT["MTR120"]["pressure_drop_mpa"]
            P, _ = A.pout(P, s["m"], Dyn["N-MTRINJ-GS"], LEN["N-MTRINJ-GS"], epsn["N-MTRINJ-GS"], T0)
            P_GS_out = P - A.hdr_dp(s["m"])
            suct = {}
            for cid, nid in (("C-I1", "N-GS-CI1"), ("C-I3", "N-GS-CI3")):
                Po, _ = A.pout(P_GS_out, alloc[cid], Dyn[nid], LEN[nid], epsn[nid], T0)
                suct[cid] = Po
            dn = {"C-I1": "N-CI1-CH", "C-I3": "N-CI3-CH"}
            ok = True; msgs = []
            Thot = 80.0
            for _ in range(60):
                Ts = []
                for cid in alloc:
                    mdl = CAT[{"C-I1": "C60", "C-I3": "C40"}[cid]]
                    rr = A.pout(s["Psink"] + 1.0, alloc[cid], Dyn[dn[cid]], LEN[dn[cid]], epsn[dn[cid]], Thot)
                    Pd = (s["Psink"] + 1.0)
                    r = Pd / suct[cid]
                    To = A.T_out_c(T0, r, mdl["efficiency_proxy"])
                    Ts.append((alloc[cid], To))
                    if r > mdl["maximum_pressure_ratio"] + 1e-9:
                        ok = False; msgs.append(f"{cid} ratio {r:.2f}>{mdl['maximum_pressure_ratio']}")
                    if To > mdl["maximum_discharge_temperature_c"] + 1e-4:
                        ok = False; msgs.append(f"{cid} Tout {To:.0f}")
                    if alloc[cid] > mdl["capacity_kg_s"] + 1e-9 or alloc[cid] < mdl["minimum_stable_flow_kg_s"] - 1e-9:
                        ok = False; msgs.append(f"{cid} flow {alloc[cid]:.1f}")
                newT = sum(a * b for a, b in Ts) / sum(a for a, _ in Ts)
                if abs(newT - Thot) < 1e-7: Thot = newT; break
                Thot = newT
            # downstream to wells at mN
            Tcool = min(Thot, A.T_COOL)
            Pf, _ = A.pout(s["Psink"] + 1.0, mN, Dyn["N-CH-COOL"], LEN["N-CH-COOL"], epsn["N-CH-COOL"], Thot)
            Pf -= CAT["COOL120"]["pressure_drop_mpa"]
            Pw, _ = A.pout(Pf, mN, Dyn["N-COOL-WS"], LEN["N-COOL-WS"], epsn["N-COOL-WS"], Tcool)
            Pw -= A.hdr_dp(mN)
            wells = []
            for i in range(1, 7):
                nid = f"N-WS-WG{i}"
                Po, r = A.pout(Pw, mN / 6, Dyn[nid], LEN[nid], epsn[nid], Tcool)
                wells.append(Po)
                if r["v"] > A.GAS_VMAX + 1e-6:
                    ok = False; msgs.append(f"{nid} v={r['v']:.1f}")
            wells_ok = min(wells) >= s["Psink"] - 1e-3
            ok = ok and wells_ok and (mN / 6 <= 25)
            chk(ok, "N-1 compression", s["id"],
                f"retained {mN:.1f} kg/s ({frac*100:.0f}%) deliverable={wells_ok}; " + "; ".join(msgs))
            out[s["id"]] = dict(ok=ok, retained_flow=mN, msgs=msgs)
        else:
            # WDR-LOW boosters: one of two lost
            r1 = A.solve_withdrawal_boost(s, dg)
            # single booster must carry mN=49 at required discharge
            Ps = r1["Psuct"][0]
            r = r1["Pd"] / Ps
            mdl = CAT["C60"]
            ok = (mN <= mdl["capacity_kg_s"] + 1e-9 and mN >= mdl["minimum_stable_flow_kg_s"] - 1e-9
                  and r <= mdl["maximum_pressure_ratio"] + 1e-9 and r1["Tdel"] <= 60 + 1e-4)
            chk(ok, "N-1 compression", s["id"], f"single booster retained {mN:.1f} kg/s, r={r:.2f}")
            out[s["id"]] = dict(ok=ok, retained_flow=mN)
    # withdrawal treatment N-1
    for s in SCEN:
        if s["service"] != "withdrawal":
            continue
        mN = 0.7 * s["m"]
        per = mN / 2.0
        ok = True; msgs = []
        if per > CAT["SEP70"]["capacity_kg_s"] + 1e-9:
            ok = False; msgs.append(f"sep {per:.1f}>{CAT['SEP70']['capacity_kg_s']}")
        if per > CAT["DEHY70"]["capacity_kg_s"] + 1e-9:
            ok = False; msgs.append(f"dehy {per:.1f}>{CAT['DEHY70']['capacity_kg_s']}")
        liq = per * s["fl"] * CAT["SEP70"]["liquid_removal_efficiency"]
        if liq > CAT["SEP70"]["maximum_liquid_rate_kg_s"] + 1e-9:
            ok = False; msgs.append(f"sep liq {liq:.2f}")
        chk(ok, "N-1 treatment", s["id"], f"retained {mN:.1f} kg/s over 2 trains ({per:.1f} each); " + "; ".join(msgs))
        out.setdefault(s["id"], {})["treatment_n1"] = dict(ok=ok, retained=mN)
    return out


# ------------------------------------------------------------------ LCC
def road_length():
    tot = 0.0
    from ugs_design import ROADS
    for rd in ROADS:
        pts = rd["pts"]
        for k in range(len(pts) - 1):
            tot += math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1])
    return tot


def compute_lcc(dg, energy):
    result = {}
    eq_capex = 0.0
    equi = []
    for inst in INSTANCES:
        m = CAT[inst["model_id"]]
        eq_capex += m["capex_mbcu"]
        equi.append(dict(id=inst["id"], model=inst["model_id"], capex=m["capex_mbcu"],
                         maint=m["annual_maintenance_mbcu"]))
    result["equipment_capex"] = eq_capex
    result["equipment"] = equi

    # piping capex
    pipe_capex = 0.0
    plines = []
    for nid, length in LEN.items():
        if length <= 0:
            continue
        dn = dg["diam"][nid]
        cid = dg["cls"][nid]
        lvl = LEVEL[nid]
        upm = DIAM_MAP[dn]["installed_cost_mbcu_per_m"]
        cmult = CLASSES[cid]["installed_cost_multiplier"]
        lmult = LEVELS[lvl]["installed_cost_multiplier"]
        cost = length * upm * cmult * lmult
        pipe_capex += cost
        plines.append(dict(net=nid, dn=dn, cls=cid, level=lvl, length=round(length, 3),
                           cost=round(cost, 6)))
    result["piping_capex"] = pipe_capex
    result["pipelines"] = plines

    # civil
    rl = road_length()
    road_cost = rl * ECON["civil"]["road_mbcu_per_m"]
    fp_area = 0.0
    maint_area = 0.0
    for inst in INSTANCES:
        fr = footprint(inst, CAT)
        fa = (fr[2] - fr[0]) * (fr[3] - fr[1])
        fp_area += fa
        rects = envelope_rects(inst, CAT)
        ua = rects[0]
        area = (ua[2] - ua[0]) * (ua[3] - ua[1])
        for rr in rects[1:]:
            a2 = (rr[2] - rr[0]) * (rr[3] - rr[1])
            inter = C.rect_overlap_area(ua, rr)
            area = area + a2 - inter
            ua = rr
        maint_area += max(0.0, area - fa)
    found_cost = fp_area * ECON["civil"]["foundation_mbcu_per_m2"]
    maint_cost = maint_area * ECON["civil"]["maintenance_area_mbcu_per_m2"]
    pipe_civil = 0.0
    for nid, length in LEN.items():
        if length <= 0:
            continue
        pipe_civil += length * LEVELS[LEVEL[nid]]["civil_cost_mbcu_per_m"]
    civil_total = road_cost + found_cost + maint_cost + pipe_civil
    result["civil"] = dict(road_length_m=round(rl, 3), road_cost=road_cost, footprint_area_m2=fp_area,
                           foundation_cost=found_cost, maintenance_area_m2=maint_area,
                           maintenance_cost=maint_cost, pipeline_civil=pipe_civil, total=civil_total)

    # energy
    hours = {s["id"]: s["hours"] for s in SCEN}
    ann_energy_mwh = sum(energy[sid] * hours[sid] for sid in energy)
    i = ECON["discount_rate"]; N = ECON["project_life_years"]
    pvf = (1 - (1 + i) ** (-N)) / i
    ann_energy_cost = ann_energy_mwh * ECON["energy_tariff_mbcu_per_mwh"]
    energy_pv = ann_energy_cost * pvf
    result["energy"] = dict(per_scenario_mwh={sid: round(energy[sid] * hours[sid], 1) for sid in energy},
                            annual_mwh=round(ann_energy_mwh, 1), annual_cost=ann_energy_cost,
                            pvf=pvf, present_value=energy_pv)

    ann_maint = sum(CAT[inst["model_id"]]["annual_maintenance_mbcu"] for inst in INSTANCES)
    maint_pv = ann_maint * pvf
    result["maintenance"] = dict(annual=ann_maint, pvf=pvf, present_value=maint_pv)

    lcc = eq_capex + pipe_capex + civil_total + energy_pv + maint_pv
    result["lcc_mbcu"] = lcc
    result["breakdown"] = dict(equipment_capex=eq_capex, piping_capex=pipe_capex, civil=civil_total,
                               energy_pv=energy_pv, maintenance_pv=maint_pv)
    return result
