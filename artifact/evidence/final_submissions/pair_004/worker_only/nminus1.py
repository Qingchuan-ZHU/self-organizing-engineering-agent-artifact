"""N-1 reliability verification with full hydraulics."""
import sys, math
sys.path.insert(0, "/workspace/project")
import ugs_analysis as A
from ugs_design import load, load_catalog

CAT = A.CAT


def injection_n1(s, dg, lost, retained=0.7):
    """Injection with one compressor unavailable; deliver retained*m."""
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    units = [("C-I1", "C60", "N-GS-CI1", "N-CI1-CH"),
             ("C-I2", "C60", "N-GS-CI2", "N-CI2-CH"),
             ("C-I3", "C40", "N-GS-CI3", "N-CI3-CH")]
    active = [u for u in units if u[0] != lost]
    m = retained * s["m"]; T0 = s["Tsrc"]
    mfull = s["m"]
    # upstream uses full-bore lines; flow is the retained flow
    P, _ = A.pout(s["Psrc"], m, Dyn["N-MTRINJ-GRID"], A.LEN["N-MTRINJ-GRID"], epsn["N-MTRINJ-GRID"], T0)
    P -= CAT["MTR120"]["pressure_drop_mpa"]
    P, _ = A.pout(P, m, Dyn["N-MTRINJ-GS"], A.LEN["N-MTRINJ-GS"], epsn["N-MTRINJ-GS"], T0)
    P_GS_out = P - A.hdr_dp(m)
    cap = {u[0]: CAT[u[1]]["capacity_kg_s"] for u in active}
    tot = sum(cap.values())
    alloc = {k: m * v / tot for k, v in cap.items()}
    suct = {}
    for cid, mid, nid, dn in active:
        Po, _ = A.pout(P_GS_out, alloc[cid], Dyn[nid], A.LEN[nid], epsn[nid], T0)
        suct[cid] = Po

    def eval_ch(P_CH):
        Thot = 80.0; info = {}
        for _ in range(80):
            Ts = []
            for cid, mid, nid, dn in active:
                mdl = CAT[mid]; q = alloc[cid]
                Po, rr = A.pout(P_CH, q, Dyn[dn], A.LEN[dn], epsn[dn], Thot)
                Pd = P_CH + (P_CH - Po)
                r = max(Pd / suct[cid], 1e-9)
                To = A.T_out_c(T0, r, mdl["efficiency_proxy"])
                Ts.append((q, To))
                info[cid] = dict(mid=mid, Pd=Pd, r=r, To=To, q=q, Ps=suct[cid])
            newT = sum(a * b for a, b in Ts) / sum(a for a, _ in Ts)
            if abs(newT - Thot) < 1e-8:
                Thot = newT; break
            Thot = newT
        Tcool = min(Thot, A.T_COOL)
        Pf, _ = A.pout(P_CH, m, Dyn["N-CH-COOL"], A.LEN["N-CH-COOL"], epsn["N-CH-COOL"], Thot)
        Pf -= CAT["COOL120"]["pressure_drop_mpa"]
        Pw, _ = A.pout(Pf, m, Dyn["N-COOL-WS"], A.LEN["N-COOL-WS"], epsn["N-COOL-WS"], Tcool)
        Pw -= A.hdr_dp(m)
        well = []
        for i in range(1, 7):
            nid = f"N-WS-WG{i}"
            Po, r = A.pout(Pw, m / 6, Dyn[nid], A.LEN[nid], epsn[nid], Tcool)
            well.append(Po)
        return Thot, Tcool, min(well), info

    lo, hi = s["Psink"], s["Psink"] + 9.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if eval_ch(mid)[2] < s["Psink"]:
            lo = mid
        else:
            hi = mid
    P_CH = (lo + hi) / 2
    Thot, Tcool, wp, info = eval_ch(P_CH)
    msgs = []; ok = True
    for cid, d in info.items():
        mdl = CAT[d["mid"]]
        if d["r"] > mdl["maximum_pressure_ratio"] + 1e-9: ok = False; msgs.append(f"{cid} r={d['r']:.2f}")
        if d["To"] > mdl["maximum_discharge_temperature_c"] + 1e-4: ok = False; msgs.append(f"{cid} Tout={d['To']:.0f}")
        if d["Pd"] > mdl["maximum_discharge_pressure_mpa"] + 1e-5: ok = False; msgs.append(f"{cid} Pd={d['Pd']:.2f}")
        if d["Ps"] > mdl["maximum_suction_pressure_mpa"] + 1e-5: ok = False; msgs.append(f"{cid} Ps={d['Ps']:.2f}")
        if not (mdl["minimum_stable_flow_kg_s"] - 1e-9 <= d["q"] <= mdl["capacity_kg_s"] + 1e-9):
            ok = False; msgs.append(f"{cid} q={d['q']:.1f}")
    if wp < s["Psink"] - 1e-4: ok = False; msgs.append(f"wellP={wp:.3f}")
    if Tcool > 60 + 1e-4: ok = False; msgs.append(f"T={Tcool:.1f}")
    duty = m * A.CP * max(0.0, Thot - Tcool) / 1e6
    if duty > CAT["COOL120"]["maximum_duty_mw"] + 1e-9: ok = False; msgs.append(f"duty={duty:.1f}")
    return dict(ok=ok, lost=lost, retained_flow=round(m, 3), P_CH=round(P_CH, 3),
                compressors={k: dict(ratio=round(v["r"], 3), flow=round(v["q"], 2),
                                     outlet_c=round(v["To"], 1)) for k, v in info.items()},
                well_min_mpa=round(wp, 3), cooler_duty_mw=round(duty, 3), msgs=msgs)


def withdrawal_treatment_n1(s, dg, retained=0.7):
    """Withdrawal with 2 of 3 separator/dehydration trains in service."""
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    m = retained * s["m"]; T0 = s["Tsrc"]
    Pws = []
    for i in range(1, 7):
        nid = f"N-WS-WG{i}"
        Po, _ = A.pout(s["Psrc"], m / 6, Dyn[nid], A.LEN[nid], epsn[nid], T0)
        Pws.append(Po)
    P_WS = min(Pws); P_WS_out = P_WS - A.hdr_dp(m)
    P_sep = []
    for i in range(1, 3):
        nid = f"N-WS-SEP{i}"
        Po, _ = A.pout(P_WS_out, m / 2, Dyn[nid], A.LEN[nid], epsn[nid], T0)
        P_sep.append(Po - CAT["SEP70"]["pressure_drop_mpa"])
    P_ts = None
    for i in range(1, 3):
        n1 = f"N-SEP{i}-DEH{i}"
        Po, _ = A.pout(P_sep[i - 1], m / 2, Dyn[n1], A.LEN[n1], epsn[n1], T0)
        Po -= CAT["DEHY70"]["pressure_drop_mpa"]
        n2 = f"N-DEH{i}-TS"
        Po2, _ = A.pout(Po, m / 2, Dyn[n2], A.LEN[n2], epsn[n2], T0)
        P_ts = Po2 if P_ts is None else min(P_ts, Po2)
    P_TS_out = P_ts - A.hdr_dp(m)
    liq = (m / 2) * s["fl"] * CAT["SEP70"]["liquid_removal_efficiency"]
    ok = liq <= CAT["SEP70"]["maximum_liquid_rate_kg_s"] + 1e-9
    msgs = [] if ok else [f"sep liq={liq:.2f}"]
    if s["id"] in ("WDR-HIGH", "WDR-MID"):
        P_reg_in, _ = A.pout(P_TS_out, m, Dyn["N-TS-REG"], A.LEN["N-TS-REG"], epsn["N-TS-REG"], T0)
        ok = ok and (P_reg_in <= CAT["REG120"]["maximum_pressure_mpa"] + 1e-5) and (P_reg_in > s["Psink"])
    else:
        Psuct, _ = A.pout(P_TS_out, m / 2, Dyn["N-TS-CW1"], A.LEN["N-TS-CW1"], epsn["N-TS-CW1"], T0)
        r = 1.43
        ok = ok and (Psuct <= CAT["C60"]["maximum_suction_pressure_mpa"] + 1e-5) and (m / 2 <= CAT["C60"]["capacity_kg_s"] + 1e-9)
    return dict(ok=ok, retained_flow=round(m, 3), per_train_kg_s=round(m / 2, 3),
                separator_liquid_kg_s=round(liq, 3), msgs=msgs)


def run_all(dg):
    out = {"injection": [], "withdrawal_treatment": [], "withdrawal_compression": []}
    for s in A.SCEN:
        if s["service"] == "injection":
            for lost in ("C-I1", "C-I2", "C-I3"):
                out["injection"].append(dict(scenario=s["id"], **injection_n1(s, dg, lost)))
        else:
            out["withdrawal_treatment"].append(dict(scenario=s["id"], **withdrawal_treatment_n1(s, dg)))
            if s["Psink"] > s["Psrc"]:
                # single booster
                m = 0.7 * s["m"]
                r1 = A.solve_withdrawal_boost(s, dg)
                Ps = r1["Psuct"][0]
                r = r1["Pd"] / Ps
                ok = (m <= CAT["C60"]["capacity_kg_s"] + 1e-9 and m >= CAT["C60"]["minimum_stable_flow_kg_s"] - 1e-9
                      and r <= CAT["C60"]["maximum_pressure_ratio"] + 1e-9)
                out["withdrawal_compression"].append(dict(scenario=s["id"], ok=ok, lost="C-W2",
                                                          retained_flow=round(m, 3), ratio=round(r, 3)))
    return out


if __name__ == "__main__":
    import json
    diam = json.load(open("/workspace/project/diam_opt.json"))
    dg = A.make_design(); dg["diam"] = diam
    dg["Dyn"] = {nid: A.DIAM_MAP[dn]["internal_diameter_m"] for nid, dn in diam.items()}
    r = run_all(dg)
    for k, v in r.items():
        for e in v:
            print(k, e)
