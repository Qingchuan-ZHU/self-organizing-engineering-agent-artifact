"""UGS-SYNTH-D01 v1.1 - scenario hydraulics (see brief/engineering_calculation_basis.md)."""
import sys, json, math
sys.path.insert(0, "/workspace/project")
import ugs_core as C
from ugs_design import load, load_catalog, INSTANCES

GP = load("gas_properties.json")
PIPE = load("piping_catalog.json")
ECON = load("economic_assumptions.json")
CAT = load_catalog()
SITE = load("site.json")

CP = GP["heat_capacity_cp_j_kg_k"]
K = GP["specific_heat_ratio"]
AEXP = (K - 1.0) / K
GAS_VMAX = PIPE["maximum_gas_velocity_m_s"]
LIQ_VMAX = PIPE["maximum_liquid_drain_velocity_m_s"]
DIAMS = PIPE["diameters"]
DIAM_MAP = {d["nominal_diameter"]: d for d in DIAMS}
CLASSES = {c["class_id"]: c for c in PIPE["classes"]}
LEVELS = PIPE["routing_levels"]

ROUTES = json.load(open("/workspace/project/routes.json"))
LEN = {k: v["length"] for k, v in ROUTES.items()}
LEVEL = {k: v["level"] for k, v in ROUTES.items()}

SCEN = [
    dict(id="INJ-LOW",  service="injection", m=120, Psrc=6.5, Tsrc=25, water=40,  fl=0.0,  Psink=8.5,  hours=900),
    dict(id="INJ-MID",  service="injection", m=100, Psrc=6.5, Tsrc=25, water=40,  fl=0.0,  Psink=11.0, hours=1300),
    dict(id="INJ-HIGH", service="injection", m=75,  Psrc=6.5, Tsrc=25, water=40,  fl=0.0,  Psink=13.5, hours=600),
    dict(id="WDR-HIGH", service="withdrawal", m=120, Psrc=12.0, Tsrc=20, water=220, fl=0.01, Psink=6.0, hours=500),
    dict(id="WDR-MID",  service="withdrawal", m=100, Psrc=8.0,  Tsrc=20, water=220, fl=0.01, Psink=6.0, hours=900),
    dict(id="WDR-LOW",  service="withdrawal", m=70,  Psrc=4.5,  Tsrc=20, water=220, fl=0.01, Psink=6.0, hours=800),
]
T_COOL = 55.0
CP_LIQ = 1000.0  # assumed liquid density for drain velocity sizing (documented)


def pout(P_in, m, D, L, eps, T):
    """Return (P_out, result-dict)."""
    r = C.pipe_pressure_loss_mpa(P_in, m, D, L, eps, T, GP)
    return r["P_out"], r


def hdr_dp(m, model_id="HDR120"):
    mdl = CAT[model_id]
    return mdl["pressure_drop_at_capacity_mpa"] * (m / mdl["capacity_kg_s"]) ** 2


def T_out_c(T_in, r, eta):
    return C.c_to_k(T_in) * (1.0 + (r ** AEXP - 1.0) / eta) - 273.15


def power_mw(m, T_in, r, eta, drv):
    return m * CP * C.c_to_k(T_in) * (r ** AEXP - 1.0) / (eta * drv) / 1e6


def scenario_flows(s):
    m = s["m"]; f = {}
    if s["service"] == "injection":
        f["N-MTRINJ-GRID"] = m; f["N-MTRINJ-GS"] = m
        f["N-GS-CI1"] = m / 2; f["N-GS-CI2"] = m / 2
        f["N-CI1-CH"] = m / 2; f["N-CI2-CH"] = m / 2
        f["N-CH-COOL"] = m; f["N-COOL-WS"] = m
        for i in range(1, 7):
            f[f"N-WS-WG{i}"] = m / 6
    else:
        for i in range(1, 7):
            f[f"N-WS-WG{i}"] = m / 6
        for i in range(1, 4):
            f[f"N-WS-SEP{i}"] = m / 3
            f[f"N-SEP{i}-DEH{i}"] = m / 3
            f[f"N-DEH{i}-TS"] = m / 3
        if s["id"] in ("WDR-HIGH", "WDR-MID"):
            f["N-TS-REG"] = m; f["N-REG-GS"] = m
        else:
            f["N-TS-CW1"] = m / 2; f["N-TS-CW2"] = m / 2
            f["N-CW1-GS"] = m / 2; f["N-CW2-GS"] = m / 2
        f["N-GS-MTRWDR"] = m; f["N-MTRWDR-GRID"] = m
        liq = m * s["fl"]
        for i in range(1, 4):
            f[f"N-SEP{i}-DRN{i}"] = liq / 3
            f[f"N-DRN{i}-OUT"] = liq / 3
    return f


def link_wet(nid, s):
    if s["service"] == "injection":
        return False
    return nid.startswith("N-WS-") or nid.startswith("N-SEP")


def build_tables():
    tbl = {k: [] for k in LEN}
    for s in SCEN:
        f = scenario_flows(s)
        for nid, q in f.items():
            if nid not in tbl:
                continue
            if (nid.startswith("N-SEP") and "-DRN" in nid) or nid.startswith("N-DRN"):
                tbl[nid].append(dict(q=q, P=1.0, T=20.0, service="liquid", wet=True))
                continue
            wet = link_wet(nid, s)
            if s["service"] == "injection":
                if nid in ("N-CI1-CH", "N-CI2-CH", "N-CH-COOL"):
                    P, T = 13.0, 90.0
                elif nid == "N-COOL-WS" or nid.startswith("N-WS-WG"):
                    P, T = 13.0, T_COOL
                else:
                    P, T = 6.5, 25.0
            else:
                if nid.startswith("N-WS-WG"):
                    P, T = max(s["Psrc"], 1.0), 20.0
                elif nid.startswith("N-WS-SEP") or nid.startswith("N-SEP") or nid.startswith("N-DEH"):
                    P, T = max(s["Psrc"] - 0.2, 1.0), 20.0
                elif nid == "N-TS-REG" or nid.startswith("N-TS-CW"):
                    P, T = max(s["Psrc"] - 0.3, 1.0), 20.0
                else:
                    P, T = 6.2, 15.0
            tbl[nid].append(dict(q=q, P=P, T=T, service="gas", wet=wet))
    return tbl


def choose_diameters(tbl, vtarget_gas=15.0):
    choice = {}
    for nid, rows in tbl.items():
        is_liq = bool(rows) and all(r["service"] == "liquid" for r in rows)
        best = DIAMS[-1]
        for d in DIAMS:
            D = d["internal_diameter_m"]
            ok = True; vgmax = 0.0
            for r in rows:
                if r["q"] <= 0:
                    continue
                if is_liq:
                    v = r["q"] / (CP_LIQ * math.pi * D * D / 4.0)
                    if v > LIQ_VMAX:
                        ok = False
                else:
                    v = C.gas_velocity(max(r["P"], 1e-6), r["T"], r["q"], D, GP)
                    vgmax = max(vgmax, v)
                    if v > GAS_VMAX:
                        ok = False
            if ok and (is_liq or vgmax <= vtarget_gas):
                best = d
                break
        choice[nid] = best["nominal_diameter"]
    return choice


def class_for(nid, tbl):
    rows = tbl[nid]
    if not rows:
        return "CS-WET-100"
    if all(r["service"] == "liquid" for r in rows):
        return "CS-WET-100"
    maxP = max(r["P"] for r in rows)
    wet = any(r["wet"] for r in rows)
    if maxP <= 10.0:
        return "CS-WET-100"
    return "CS-WET-160" if wet else "CS-DRY-160"


def make_design(vtarget_gas=15.0):
    tbl = build_tables()
    diam = choose_diameters(tbl, vtarget_gas)
    Dyn = {nid: DIAM_MAP[dn]["internal_diameter_m"] for nid, dn in diam.items()}
    cls = {nid: class_for(nid, tbl) for nid in LEN}
    epsn = {nid: CLASSES[cls[nid]]["roughness_m"] for nid in LEN}
    return dict(tbl=tbl, diam=diam, Dyn=Dyn, cls=cls, epsn=epsn)


# ------------------------------------------------------------------ solvers
def solve_injection(s, dg):
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    m = s["m"]; T0 = s["Tsrc"]
    P, _ = pout(s["Psrc"], m, Dyn["N-MTRINJ-GRID"], LEN["N-MTRINJ-GRID"], epsn["N-MTRINJ-GRID"], T0)
    P -= CAT["MTR120"]["pressure_drop_mpa"]
    P, _ = pout(P, m, Dyn["N-MTRINJ-GS"], LEN["N-MTRINJ-GS"], epsn["N-MTRINJ-GS"], T0)
    P_GS = P
    P_GS_out = P_GS - hdr_dp(m)
    suct = {}
    for cid, nid in (("C-I1", "N-GS-CI1"), ("C-I2", "N-GS-CI2")):
        q = m / 2
        Po, r = pout(P_GS_out, q, Dyn[nid], LEN[nid], epsn[nid], T0)
        suct[cid] = dict(P=Po, q=q, v=r["v"])

    def eval_ch(P_CH):
        Thot = 80.0; info = {}
        for _ in range(80):
            Ts = []
            for cid, nid, dn in (("C-I1", "N-GS-CI1", "N-CI1-CH"), ("C-I2", "N-GS-CI2", "N-CI2-CH")):
                mdl = CAT["C60"]
                q = m / 2
                Po2, rr = pout(P_CH, q, Dyn[dn], LEN[dn], epsn[dn], Thot)
                Pd = P_CH + (P_CH - Po2)
                r = max(Pd / suct[cid]["P"], 1e-9)
                To = T_out_c(T0, r, mdl["efficiency_proxy"])
                Ts.append((q, To))
                info[cid] = dict(Pd=Pd, r=r, To=To, q=q, Ps=suct[cid]["P"])
            newT = sum(a * b for a, b in Ts) / sum(a for a, _ in Ts)
            if abs(newT - Thot) < 1e-8:
                Thot = newT; break
            Thot = newT
        Tcool = min(Thot, T_COOL)
        Pf, _ = pout(P_CH, m, Dyn["N-CH-COOL"], LEN["N-CH-COOL"], epsn["N-CH-COOL"], Thot)
        Pf -= CAT["COOL120"]["pressure_drop_mpa"]
        Pw, _ = pout(Pf, m, Dyn["N-COOL-WS"], LEN["N-COOL-WS"], epsn["N-COOL-WS"], Tcool)
        Pw -= hdr_dp(m)
        well = []
        for i in range(1, 7):
            nid = f"N-WS-WG{i}"
            Po, r = pout(Pw, m / 6, Dyn[nid], LEN[nid], epsn[nid], Tcool)
            well.append((Po, r["v"]))
        return Thot, Tcool, well, info

    lo, hi = s["Psink"], s["Psink"] + 9.0
    for _ in range(90):
        mid = (lo + hi) / 2
        _, _, well, _ = eval_ch(mid)
        if min(w[0] for w in well) < s["Psink"]:
            lo = mid
        else:
            hi = mid
    P_CH = (lo + hi) / 2
    Thot, Tcool, well, info = eval_ch(P_CH)
    return dict(P_GS=P_GS, P_CH=P_CH, Thot=Thot, Tcool=Tcool, wells=well, comp=info, suct=suct)


def _withdraw_upstream(s, dg):
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    m = s["m"]; T0 = s["Tsrc"]
    Pws = []; vv = []
    for i in range(1, 7):
        nid = f"N-WS-WG{i}"
        Po, r = pout(s["Psrc"], m / 6, Dyn[nid], LEN[nid], epsn[nid], T0)
        Pws.append(Po); vv.append((nid, r["v"]))
    P_WS = min(Pws)
    P_WS_out = P_WS - hdr_dp(m)
    P_sep_out = []
    for i in range(1, 4):
        nid = f"N-WS-SEP{i}"
        Po, r = pout(P_WS_out, m / 3, Dyn[nid], LEN[nid], epsn[nid], T0)
        vv.append((nid, r["v"]))
        Po -= CAT["SEP70"]["pressure_drop_mpa"]
        P_sep_out.append(Po)
    P_ts = None
    for i in range(1, 4):
        n1 = f"N-SEP{i}-DEH{i}"
        Po, _ = pout(P_sep_out[i - 1], m / 3, Dyn[n1], LEN[n1], epsn[n1], T0)
        Po -= CAT["DEHY70"]["pressure_drop_mpa"]
        n2 = f"N-DEH{i}-TS"
        Po2, r2 = pout(Po, m / 3, Dyn[n2], LEN[n2], epsn[n2], T0)
        vv.append((n2, r2["v"]))
        P_ts = Po2 if P_ts is None else min(P_ts, Po2)
    return P_WS, P_ts, vv


def solve_withdrawal_reg(s, dg):
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    m = s["m"]; T0 = s["Tsrc"]
    P_WS, P_ts, vv = _withdraw_upstream(s, dg)
    P_TS_out = P_ts - hdr_dp(m)
    P_reg_in, _ = pout(P_TS_out, m, Dyn["N-TS-REG"], LEN["N-TS-REG"], epsn["N-TS-REG"], T0)
    vv.append(("N-TS-REG", C.pipe_pressure_loss_mpa(P_TS_out, m, Dyn["N-TS-REG"], LEN["N-TS-REG"],
                                                    epsn["N-TS-REG"], T0, GP)["v"]))
    Treg = [T0]

    def grid_p(Preg_out, T):
        P, _ = pout(Preg_out, m, Dyn["N-REG-GS"], LEN["N-REG-GS"], epsn["N-REG-GS"], T)
        P -= hdr_dp(m)
        P, _ = pout(P, m, Dyn["N-GS-MTRWDR"], LEN["N-GS-MTRWDR"], epsn["N-GS-MTRWDR"], T)
        P -= CAT["MTR120"]["pressure_drop_mpa"]
        P, _ = pout(P, m, Dyn["N-MTRWDR-GRID"], LEN["N-MTRWDR-GRID"], epsn["N-MTRWDR-GRID"], T)
        return P

    lo, hi = 0.5, P_reg_in
    for _ in range(140):
        mid = (lo + hi) / 2
        Treg[0] = T0 - CAT["REG120"]["jt_temperature_coefficient_k_per_mpa"] * (P_reg_in - mid)
        if grid_p(mid, Treg[0]) > s["Psink"]:
            hi = mid
        else:
            lo = mid
    Preg_out = (lo + hi) / 2
    Treg[0] = T0 - CAT["REG120"]["jt_temperature_coefficient_k_per_mpa"] * (P_reg_in - Preg_out)
    Pgrid = grid_p(Preg_out, Treg[0])
    for nid in ("N-REG-GS", "N-GS-MTRWDR", "N-MTRWDR-GRID"):
        vv.append((nid, C.pipe_pressure_loss_mpa(max(Preg_out, 1.0), m, Dyn[nid], LEN[nid], epsn[nid], Treg[0], GP)["v"]))
    return dict(P_WS=P_WS, P_TS=P_ts, P_reg_in=P_reg_in, Preg_out=Preg_out, Pgrid=Pgrid,
                Tdel=Treg[0], velocities=vv)


def solve_withdrawal_boost(s, dg):
    Dyn, epsn = dg["Dyn"], dg["epsn"]
    m = s["m"]; T0 = s["Tsrc"]
    P_WS, P_ts, vv = _withdraw_upstream(s, dg)
    P_TS_out = P_ts - hdr_dp(m)
    Psuct = []
    for nid in ("N-TS-CW1", "N-TS-CW2"):
        Po, r = pout(P_TS_out, m / 2, Dyn[nid], LEN[nid], epsn[nid], T0)
        Psuct.append(Po); vv.append((nid, r["v"]))
    Tb = [T0 + 25.0]

    def grid_p(Pd, T):
        P, _ = pout(Pd, m / 2, Dyn["N-CW1-GS"], LEN["N-CW1-GS"], epsn["N-CW1-GS"], T)
        P -= hdr_dp(m)
        P, _ = pout(P, m, Dyn["N-GS-MTRWDR"], LEN["N-GS-MTRWDR"], epsn["N-GS-MTRWDR"], T)
        P -= CAT["MTR120"]["pressure_drop_mpa"]
        P, _ = pout(P, m, Dyn["N-MTRWDR-GRID"], LEN["N-MTRWDR-GRID"], epsn["N-MTRWDR-GRID"], T)
        return P

    Ps_min = min(Psuct)
    lo, hi = Ps_min + 0.05, Ps_min + 9.0
    for _ in range(140):
        mid = (lo + hi) / 2
        Tb[0] = T_out_c(T0, mid / Ps_min, CAT["C60"]["efficiency_proxy"])
        if grid_p(mid, Tb[0]) > s["Psink"]:
            hi = mid
        else:
            lo = mid
    Pd = (lo + hi) / 2
    Tb[0] = T_out_c(T0, Pd / Ps_min, CAT["C60"]["efficiency_proxy"])
    Pgrid = grid_p(Pd, Tb[0])
    comp = []
    for i, nid in enumerate(("N-TS-CW1", "N-TS-CW2"), start=1):
        r = Pd / Psuct[i - 1]
        W = power_mw(m / 2, T0, r, CAT["C60"]["efficiency_proxy"], CAT["C60"]["driver_efficiency"])
        comp.append(dict(id=f"C-W{i}", Ps=Psuct[i - 1], Pd=Pd, r=r, W=W, q=m / 2))
        n2 = f"N-CW{i}-GS"
        vv.append((n2, C.pipe_pressure_loss_mpa(max(Pd, 1.0), m / 2, Dyn[n2], LEN[n2], epsn[n2], Tb[0], GP)["v"]))
    return dict(P_WS=P_WS, P_TS=P_ts, Psuct=Psuct, Pd=Pd, Pgrid=Pgrid, Tdel=Tb[0],
                comp=comp, velocities=vv)
