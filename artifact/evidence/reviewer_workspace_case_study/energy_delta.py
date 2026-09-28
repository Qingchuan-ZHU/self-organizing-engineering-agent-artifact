import json, math
exec(open("review/process_check.py").read().split('print("=== re-computation')[0])

def scenario_energy(entry, cool_dp):
    sc, ctx, st, sinks, log = run_scenario(entry, cool_dp)
    mw = 0.0
    for row in log:
        if row[0] != "pipe":
            if row[2] == "compressor": mw += row[6]
            elif row[2] == "cooler": mw += row[6]*MODELS["COOL120"]["electric_power_fraction_of_duty"]
            elif row[2] == "dehydration": mw += row[6]
    return mw*sc["annual_hours"]

tot0 = tot1 = 0.0
for entry in PLAN["scenarios"]:
    e0 = scenario_energy(entry, 0.0); e1 = scenario_energy(entry, 0.035)
    tot0 += e0; tot1 += e1
    print(f"{entry['scenario_id']:9s} {e0:10.3f} -> {e1:10.3f} MWh/y")
i, N = ECON["discount_rate"], ECON["project_life_years"]
pvf = (1-(1+i)**(-N))/i
tar = ECON["energy_tariff_mbcu_per_mwh"]
lcc = load("submission/deliverables/lifecycle_cost.json")
print(f"total {tot0:.2f} -> {tot1:.2f} MWh/y ; dLCC = {(tot1-tot0)*tar*pvf:.4f} MBCU")
print(f"reported LCC {lcc['lcc_mbcu']:.4f} -> {lcc['lcc_mbcu']+(tot1-tot0)*tar*pvf:.4f} MBCU")
