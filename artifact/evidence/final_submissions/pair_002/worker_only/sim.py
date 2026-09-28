"""Scenario simulation for UGS-SYNTH-D01.

Models every active pipeline explicitly, including the compressor-branch pipes and
the parallel well / treatment branches.
"""
import math
import lib_geom as G
import ugscat as U
import design as D

CP = U.CP
A_EXP = (U.K - 1.0) / U.K
LIQ_DENSITY = 700.0  # ASSUMPTION: liquid (condensate) density for drain velocity checks

REG_SETPOINT = 6.5    # withdrawal pressure-control setpoint (no-boost) [MPa]
BOOST_TARGET = 6.20   # withdrawal boost delivered-pressure target [MPa]
COOL_SETPOINT = 45.0  # injection cooler outlet target [degC]
WELL_MARGIN = 0.10    # target margin above required sink pressure [MPa]


def p_pipe(eqmap, pipes, pid, P, T, m):
    p = pipes[pid]
    d = U.DIAM[p["spec"]["dia"]]
    cl = U.CLS[p["spec"]["cls"]]
    Dm = d["internal_diameter_m"]
    Po, v, Re, conv = U.pipe_loss_mpa(P, T, m, Dm, cl["roughness_m"], p["length"])
    return dict(P=Po, T=T, v=v, Re=Re, conv=conv, D=Dm, cls=cl, dia=d, length=p["length"], m=m)


def p_header(eqmap, hid, P, m):
    mdl = eqmap[hid]["m"]
    dP = mdl["pressure_drop_at_capacity_mpa"] * (m / mdl["capacity_kg_s"]) ** 2
    return dict(P=P - dP, dP=dP, m=m)


def p_equip(eqmap, eid, P, T, m):
    mdl = eqmap[eid]["m"]
    cat = mdl["category"]
    out = dict(P=P, T=T, energy_mw=0.0, duty_mw=0.0)
    if cat in ("separator", "filter", "dehydration", "cooler", "heater", "meter"):
        out["P"] = P - mdl["pressure_drop_mpa"]
    elif cat == "regulator":
        Pout = min(P, REG_SETPOINT)
        out["P"] = Pout
        out["T"] = T - mdl["jt_temperature_coefficient_k_per_mpa"] * (P - Pout)
    elif cat == "closed_drain":
        pass
    if cat == "dehydration":
        out["energy_mw"] = m * mdl["energy_mw_per_kg_s"]
    if cat == "cooler":
        Tout = min(T, COOL_SETPOINT)
        Tout = max(Tout, mdl["minimum_outlet_temperature_c"])
        duty = m * CP * abs(Tout - T) / 1e6
        out["T"] = Tout
        out["duty_mw"] = duty
        out["energy_mw"] = duty * mdl["electric_power_fraction_of_duty"]
    return out


def comp_Tout(T_in, r, eta):
    return (T_in + 273.15) * (1 + (r ** A_EXP - 1) / eta) - 273.15


def comp_power(m, T_in, r, eta, eta_drv):
    return m * CP * (T_in + 273.15) * (r ** A_EXP - 1) / (eta * eta_drv) / 1e6


def _run_units(eqmap, pipes, units, Pcs, Tcs, m_unit, P_cd_in, rec):
    """Given suction-header pressure Pcs and required discharge-header inlet pressure
    P_cd_in, solve each unit's operating point. units=[(cid, spipe, dpipe)]."""
    info = []
    for cid, sp, dp in units:
        mdl = eqmap[cid]["m"]
        eta = mdl["efficiency_proxy"]
        # suction branch
        os_ = p_pipe(eqmap, pipes, sp, Pcs, Tcs, m_unit)
        rec[sp] = os_
        Ps = os_["P"]
        # discharge branch: find Pd s.t. Pd - loss(dp) = P_cd_in
        Pd = P_cd_in
        dP = 0.0
        for _ in range(40):
            r = Pd / Ps
            Tout = comp_Tout(Tcs, r, eta)
            od = p_pipe(eqmap, pipes, dp, Pd, Tout, m_unit)
            newPd = P_cd_in + (Pd - od["P"])
            if abs(newPd - Pd) < 1e-7:
                Pd = newPd
                break
            Pd = newPd
        r = Pd / Ps
        Tout = comp_Tout(Tcs, r, eta)
        od = p_pipe(eqmap, pipes, dp, Pd, Tout, m_unit)
        rec[dp] = od
        W = comp_power(m_unit, Tcs, r, eta, mdl["driver_efficiency"])
        info.append(dict(id=cid, Ps=Ps, Ts=Tcs, Pd=Pd, ratio=r, T_out=Tout, power_mw=W, flow=m_unit))
    return info


def sim_injection(scen, eqmap, pipes):
    sid = scen["scenario_id"]
    Q = scen["required_total_flow_kg_s"]
    rec = {}
    P, T = scen["source_pressure_mpa"], scen["source_temperature_c"]
    o = p_pipe(eqmap, pipes, "G-TIE-IN", P, T, Q); rec["G-TIE-IN"] = o; P, T = o["P"], o["T"]
    o = p_equip(eqmap, "MTR-I", P, T, Q); rec["MTR-I"] = o; P, T = o["P"], o["T"]
    o = p_pipe(eqmap, pipes, "G-IN-1", P, T, Q); rec["G-IN-1"] = o; P, T = o["P"], o["T"]
    h = p_header(eqmap, "HDR-CS", P, Q); rec["HDR-CS"] = h
    Pcs, Tcs = h["P"], T
    units = [("C-1", "G-C1S", "G-C1D"), ("C-2", "G-C2S", "G-C2D")]
    target = scen["required_sink_pressure_mpa"] + WELL_MARGIN
    P_cd_in = target + 0.5
    info = None
    for _ in range(200):
        info = _run_units(eqmap, pipes, units, Pcs, Tcs, Q / 2.0, P_cd_in, rec)
        h2 = p_header(eqmap, "HDR-CD", P_cd_in, Q); rec["HDR-CD"] = h2
        Px = h2["P"]
        Tcomp = sum(i["T_out"] for i in info) / len(info)
        o = p_pipe(eqmap, pipes, "G-CD-CL", Px, Tcomp, Q); rec["G-CD-CL"] = o; Px = o["P"]
        o = p_equip(eqmap, "COOL", Px, Tcomp, Q); rec["COOL"] = o; Px, Tc = o["P"], o["T"]
        o = p_pipe(eqmap, pipes, "G-CL-W", Px, Tc, Q); rec["G-CL-W"] = o; Px, Tc = o["P"], o["T"]
        hw = p_header(eqmap, "HDR-W", Px, Q); rec["HDR-W"] = hw; Px = hw["P"]
        mins = []
        for wpid in D.WELL_PIPES:
            ow = p_pipe(eqmap, pipes, wpid, Px, Tc, Q / 6.0)
            rec[wpid] = ow
            mins.append(ow["P"])
        Pw = min(mins)
        err = target - Pw
        if abs(err) < 1e-7:
            break
        P_cd_in += err
    total_power = sum(i["power_mw"] for i in info)
    # worst-case (per-unit) operating point for limit checks
    worst = max(info, key=lambda i: i["ratio"])
    return dict(scenario=sid, service="injection", Q=Q, rec=rec, units=info,
                comp=dict(ratio=worst["ratio"], T_out=worst["T_out"], power_mw=max(i["power_mw"] for i in info),
                          Ps=min(i["Ps"] for i in info), Ts=Tcs, Pd=max(i["Pd"] for i in info)),
                comp_power_total=total_power, Psuct=min(i["Ps"] for i in info), Tsuct=Tcs,
                Pd=max(i["Pd"] for i in info), Pwell=Pw, Twell=Tc,
                cooler_outlet_T=rec["COOL"]["T"], cooler_duty=rec["COOL"]["duty_mw"],
                cooler_power=rec["COOL"]["energy_mw"])


def sim_withdrawal(scen, eqmap, pipes):
    sid = scen["scenario_id"]
    Q = scen["required_total_flow_kg_s"]
    rec = {}
    Pin, T = scen["source_pressure_mpa"], scen["source_temperature_c"]
    wellP = []
    for wpid in D.WELL_PIPES:
        o = p_pipe(eqmap, pipes, wpid, Pin, T, Q / 6.0); rec[wpid] = o; wellP.append(o["P"])
    P = min(wellP)
    h = p_header(eqmap, "HDR-W", P, Q); rec["HDR-W"] = h; P = h["P"]
    o = p_pipe(eqmap, pipes, "G-W-REG", P, T, Q); rec["G-W-REG"] = o; P, T = o["P"], o["T"]
    o = p_equip(eqmap, "REG-W", P, T, Q); rec["REG-W"] = o; P, T = o["P"], o["T"]
    o = p_pipe(eqmap, pipes, "G-REG-R", P, T, Q); rec["G-REG-R"] = o; P, T = o["P"], o["T"]
    h = p_header(eqmap, "HDR-R", P, Q); rec["HDR-R"] = h; P = h["P"]
    train = []
    for tr, (rs, sd, dt) in enumerate([("G-R-S1", "G-S1-D1", "G-D1-T"), ("G-R-S2", "G-S2-D2", "G-D2-T")]):
        Pt, Tt = P, T
        o = p_pipe(eqmap, pipes, rs, Pt, Tt, Q / 2.0); rec[rs] = o; Pt, Tt = o["P"], o["T"]
        sep = "SEP-1" if tr == 0 else "SEP-2"
        deh = "DEH-1" if tr == 0 else "DEH-2"
        o = p_equip(eqmap, sep, Pt, Tt, Q / 2.0); rec[sep] = o; Pt, Tt = o["P"], o["T"]
        o = p_pipe(eqmap, pipes, sd, Pt, Tt, Q / 2.0); rec[sd] = o; Pt, Tt = o["P"], o["T"]
        o = p_equip(eqmap, deh, Pt, Tt, Q / 2.0); rec[deh] = o; Pt, Tt = o["P"], o["T"]
        o = p_pipe(eqmap, pipes, dt, Pt, Tt, Q / 2.0); rec[dt] = o
        train.append((o["P"], o["T"]))
    P = min(t[0] for t in train)
    T = sum(t[1] for t in train) / len(train)
    h = p_header(eqmap, "HDR-T", P, Q); rec["HDR-T"] = h; P = h["P"]
    boost = scen["required_sink_pressure_mpa"] > scen["source_pressure_mpa"]
    comp = None
    total_power = 0.0
    if boost:
        o = p_pipe(eqmap, pipes, "G-T-CS", P, T, Q); rec["G-T-CS"] = o; P, T = o["P"], o["T"]
        h = p_header(eqmap, "HDR-CS", P, Q); rec["HDR-CS"] = h; P = h["P"]
        Pcs, Tcs = P, T
        units = [("C-1", "G-C1S", "G-C1D"), ("C-2", "G-C2S", "G-C2D")]
        target = BOOST_TARGET
        P_cd_in = target + 0.5
        info = None
        for _ in range(200):
            info = _run_units(eqmap, pipes, units, Pcs, Tcs, Q / 2.0, P_cd_in, rec)
            h2 = p_header(eqmap, "HDR-CD", P_cd_in, Q); rec["HDR-CD"] = h2
            Px = h2["P"]
            Tcomp = sum(i["T_out"] for i in info) / len(info)
            o = p_pipe(eqmap, pipes, "G-CD-M", Px, Tcomp, Q); rec["G-CD-M"] = o; Px = o["P"]
            hx = p_header(eqmap, "HDR-M", Px, Q); rec["HDR-M"] = hx; Px = hx["P"]
            o = p_pipe(eqmap, pipes, "G-M-TO", Px, Tcomp, Q); rec["G-M-TO"] = o; Px = o["P"]
            ox = p_equip(eqmap, "MTR-O", Px, Tcomp, Q); rec["MTR-O"] = ox; Px = ox["P"]
            o = p_pipe(eqmap, pipes, "G-TO-TIE", Px, Tcomp, Q); rec["G-TO-TIE"] = o
            Pdel = o["P"]
            err = target - Pdel
            if abs(err) < 1e-7:
                break
            P_cd_in += err
        total_power = sum(i["power_mw"] for i in info)
        worst = max(info, key=lambda i: i["T_out"])
        comp = dict(ratio=worst["ratio"], T_out=worst["T_out"], power_mw=total_power,
                    Ps=min(i["Ps"] for i in info), Pd=max(i["Pd"] for i in info))
        delivered = Pdel
    else:
        o = p_pipe(eqmap, pipes, "G-T-M", P, T, Q); rec["G-T-M"] = o; P, T = o["P"], o["T"]
        h = p_header(eqmap, "HDR-M", P, Q); rec["HDR-M"] = h; P = h["P"]
        o = p_pipe(eqmap, pipes, "G-M-TO", P, T, Q); rec["G-M-TO"] = o; P, T = o["P"], o["T"]
        o = p_equip(eqmap, "MTR-O", P, T, Q); rec["MTR-O"] = o; P, T = o["P"], o["T"]
        o = p_pipe(eqmap, pipes, "G-TO-TIE", P, T, Q); rec["G-TO-TIE"] = o; P, T = o["P"], o["T"]
        delivered = P
    liq = {}
    for sep in ("SEP-1", "SEP-2"):
        mdl = eqmap[sep]["m"]
        fin = scen["source_free_liquid_mass_fraction"]
        liq[sep] = dict(m_removed=(Q / 2.0) * fin * mdl["liquid_removal_efficiency"],
                        f_out=fin * (1 - mdl["liquid_removal_efficiency"]))
    dehy_energy = sum(rec[d]["energy_mw"] for d in ("DEH-1", "DEH-2"))
    return dict(scenario=sid, service="withdrawal", Q=Q, rec=rec, comp=comp,
                comp_power_total=total_power, delivered=delivered, boost=boost,
                dehy_energy=dehy_energy, liquid=liq, f_in=scen["source_free_liquid_mass_fraction"])
