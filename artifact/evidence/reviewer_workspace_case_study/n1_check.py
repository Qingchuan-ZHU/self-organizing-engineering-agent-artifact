"""n-1 re-checks: (a) the dehydration outage as it should be modelled (2 trains),
(b) injection n-1 with the catalogued cooler pressure drop applied,
(c) the energy / LCC consequence of the omitted cooler pressure drop."""
import json, math
exec(open("review/process_check.py").read().split("print(\"=== re-computation")[0])

LANES = [("SEP-A","DEH-A","CMP-A","P19","P22","P28","P03","P06"),
         ("SEP-B","DEH-B","CMP-B","P20","P23","P29","P04","P07"),
         ("SEP-C","DEH-C","CMP-C","P21","P24","P30","P05","P08")]

def withdrawal_plan(flow, lanes, compress):
    pre = [[["pipe", L[3], flow/len(lanes)], ["equipment", L[0], flow/len(lanes)],
            ["pipe", L[4], flow/len(lanes)], ["equipment", L[1], flow/len(lanes)],
            ["pipe", L[5], flow/len(lanes)]] for L in lanes]
    if compress:
        mid = [[["pipe", L[6], flow/len(lanes)], ["equipment", L[2], flow/len(lanes)],
                ["pipe", L[7], flow/len(lanes)]] for L in lanes]
        comp = ["parallel", mid]
    else:
        comp = ["pipe", "P09", flow]
    wells = [["parallel", [[["pipe", "P%02d" % (13+i), flow/6.0]] for i in range(6)]]]
    return wells + [["equipment","H-WELL",flow],["pipe","P12",flow],["equipment","H-SITE",flow],
                    ["parallel", pre], ["equipment","H-SUC",flow], comp,
                    ["equipment","H-DIS",flow],["pipe","P31",flow],["equipment","REG",flow],
                    ["pipe","P32",flow],["equipment","MTR-B",flow],["pipe","P33",flow]]

def check_log(sid, log, extra=()):
    probs = []
    for row in log:
        if row[0] == "pipe":
            _, name, m, pin, pout, v, cls, dn, conv = row
            if v > PIPING["maximum_gas_velocity_m_s"]+1e-6: probs.append(f"{sid}: {name} v={v:.2f}")
            if max(pin,pout) > CLASSES[cls]["maximum_allowable_pressure_mpa"]+1e-5:
                probs.append(f"{sid}: {name} p={max(pin,pout):.2f} > {cls}")
        else:
            _, name, kind, m, pin, pout, extra_v, tin, tout = row
            model = MODELS[EQ[name]["model_id"]]
            if model.get("capacity_kg_s") is not None and m > model["capacity_kg_s"]+1e-5:
                probs.append(f"{sid}: {name} m={m:.2f} > cap {model['capacity_kg_s']}")
            if kind == "compressor":
                ratio = pout/pin
                if ratio > model["maximum_pressure_ratio"]+1e-9: probs.append(f"{sid}: {name} ratio")
                if extra_v > model["maximum_power_mw"]+1e-9: probs.append(f"{sid}: {name} power")
                if m < model["minimum_stable_flow_kg_s"]-1e-9: probs.append(f"{sid}: {name} min flow")
                if tout > model["maximum_discharge_temperature_c"]+1e-6: probs.append(f"{sid}: {name} T")
            if kind in ("separator","filter") and extra_v > model["maximum_liquid_rate_kg_s"]+1e-9:
                probs.append(f"{sid}: {name} liquid")
    return probs

print("=== withdrawal dehydration outage modelled correctly (one train shut down) ===")
for sid in ("WDR-HIGH","WDR-MID","WDR-LOW"):
    sc = SCEN[sid]; flow = sc["required_total_flow_kg_s"]
    for out_lane in (1, 2):
        lanes = [LANES[i] for i in range(3) if i != out_lane]
        need = sc["required_sink_pressure_mpa"] > sc["source_pressure_mpa"]
        ctx = {"reg": 6.20, "cool": 40.0, "cool_dp": 0.035, "disch": 6.30}
        plan = withdrawal_plan(flow, lanes, need)
        st0 = {"m": flow, "p": sc["source_pressure_mpa"], "t": sc["source_temperature_c"],
               "w": sc["source_water_mg_sm3"], "l": sc["source_free_liquid_mass_fraction"]}
        log = []
        st, sinks = walk(plan, st0, ctx, log)
        probs = check_log(f"{sid}-N1-deh(train{out_lane+1})", log)
        ok_p = st["p"] >= sc["required_sink_pressure_mpa"]-1e-5
        print(f"{sid} train {out_lane+1} out: flow {flow} ({flow/sc['required_total_flow_kg_s']:.2f} of scenario)"
              f" sinkP {st['p']:.4f} T {st['t']:.2f} {'OK' if ok_p else 'FAIL'}"
              f" problems: {probs or 'none'}")

print("\n=== injection n-1 (one compressor out) with cooler dP = 0.035 ===")
for sid in ("INJ-LOW","INJ-MID","INJ-HIGH"):
    entry = [e for e in PLAN["scenarios"] if e["scenario_id"] == sid][0]
    sc = SCEN[sid]; flow = sc["required_total_flow_kg_s"]
    lanes = [LANES[i] for i in (0, 1)]
    per = flow/2
    plan = [["pipe","P01",flow],["equipment","MTR-A",flow],["pipe","P02",flow],
            ["equipment","H-SUC",flow],
            ["parallel", [[["pipe",L[6],per],["equipment",L[2],per],["pipe",L[7],per]] for L in lanes]],
            ["equipment","H-DIS",flow],["pipe","P10",flow],["equipment","COOL",flow],
            ["pipe","P11",flow],["equipment","H-SITE",flow],["pipe","P12",flow],
            ["equipment","H-WELL",flow],
            ["parallel", [[["pipe","P%02d" % (13+i), flow/6.0]] for i in range(6)]]]
    ctx = {"reg": 6.20, "cool": 40.0, "cool_dp": 0.035, "disch": None}
    st0 = {"m": flow, "p": sc["source_pressure_mpa"], "t": sc["source_temperature_c"],
           "w": sc["source_water_mg_sm3"], "l": sc["source_free_liquid_mass_fraction"]}
    target = sc["required_sink_pressure_mpa"] + 0.05
    lo, hi = 1e-3, 20.0
    for _ in range(60):
        mid = 0.5*(lo+hi); ctx["disch"] = mid
        _, sinks = walk(plan, st0, ctx, [])
        if min(s["p"] for s in sinks) < target: lo = mid
        else: hi = mid
    ctx["disch"] = hi
    log = []
    st, sinks = walk(plan, st0, ctx, log)
    probs = check_log(f"{sid}-N1-cmp", log)
    print(f"{sid} n-1 compressor: {per:.1f} kg/s per unit out of 60; discharge {ctx['disch']:.4f}; "
          f"min sink {min(s['p'] for s in sinks):.4f}; retained {flow/sc['required_total_flow_kg_s']:.2f}; "
          f"problems: {probs or 'none'}")

print("\n=== energy/LCC effect of the omitted cooler pressure drop ===")
def scenario_energy(entry, cool_dp):
    sc, ctx, st, sinks, log = run_scenario(entry, cool_dp)
    mw = 0.0
    for row in log:
        if row[0] != "pipe" and row[2] == "compressor": mw += row[6]
        if row[0] != "pipe" and row[2] == "cooler": mw += row[6]*MODELS["COOL120"]["electric_power_fraction_of_duty"]
        if row[0] != "pipe" and row[2] == "dehydration": mw += row[6]
    return mw*sc["annual_hours"]
tot0 = tot = 0.0
for entry in PLAN["scenarios"]:
    e0 = scenario_energy(entry, 0.0); e1 = scenario_energy(entry, 0.035)
    tot0 += e0; tot += e1
    if entry["scenario_id"].startswith("INJ"):
        print(f"  {entry['scenario_id']}: {e0:.1f} -> {e1:.1f} MWh/y")
pv = lambda x: x*ECON["energy_tariff_mbcu_per_mwh"]*((1-(1+ECON['discount_rate'])**(-ECON['project_life_years']))/ECON['discount_rate']) if False else None
i, N = ECON["discount_rate"], ECON["project_life_years"]
pvf = (1-(1+i)**(-N))/i
d = (tot-tot0)*ECON["energy_tariff_mbcu_per_mwh"]*pvf
print(f"  total annual energy {tot0:.2f} -> {tot:.2f} MWh/y ; LCC +{d:.4f} MBCU")
