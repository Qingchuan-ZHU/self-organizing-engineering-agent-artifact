"""Run build + geometry checks + scenario simulation. Prints a diagnostic report."""
import math, json, os
import lib_geom as G
import ugscat as U
import design as D
import solve as S
import sim as SIM

eqmap, ifaces, pipes = S.build()

print("=== GEOMETRY / LAYOUT CHECKS ===")
issues, road_polys, env_by_eq, allrects = S.check_geometry(eqmap, ifaces, pipes)
if not issues:
    print("  no geometry issues")
for it in issues:
    print("  !", it)

print()
print("=== PIPE LENGTHS ===")
tot = 0.0
for pid, p in pipes.items():
    print(f"  {pid:10s} {p['spec']['dia']:6s} {p['spec']['cls']:12s} {p['spec']['level']:8s} L={p['length']:8.2f} m")
    tot += p["length"]
print(f"  TOTAL {tot:.1f} m")

print()
print("=== SCENARIOS ===")
scens = {s["scenario_id"]: s for s in U.SCEN["scenarios"]}
results = {}
for sid, sc in scens.items():
    if sc["service"] == "injection":
        r = SIM.sim_injection(sc, eqmap, pipes)
    else:
        r = SIM.sim_withdrawal(sc, eqmap, pipes)
    results[sid] = r

for sid, r in results.items():
    print(f"-- {sid} ({r['service']})")
    if r["service"] == "injection":
        print(f"   Psuct={r['Psuct']:.3f} Tsuct={r['Tsuct']:.2f} Pd={r['Pd']:.3f} ratio={r['comp']['ratio']:.3f}")
        print(f"   comp Tout={r['comp']['T_out']:.2f} power/unit={r['comp']['power_mw']:.3f} total={r['comp_power_total']:.3f} MW")
        print(f"   cooler out={r['cooler_outlet_T']:.2f} duty={r['cooler_duty']:.3f} elec={r['cooler_power']:.4f}")
        print(f"   well min P={r['Pwell']:.4f} T={r['Twell']:.2f}")
        vv = [(pid, o['v']) for pid, o in r['rec'].items() if 'v' in o]
        print(f"   max pipe vel={max(v for _, v in vv):.2f} at {max(vv, key=lambda x: x[1])[0]}")
    else:
        print(f"   delivered={r['delivered']:.4f} boost={r['boost']}")
        if r["comp"]:
            print(f"   boost comp ratio={r['comp']['ratio']:.3f} Tout={r['comp']['T_out']:.2f} power={r['comp_power_total']:.3f}")
        print(f"   dehy energy={r['dehy_energy']:.3f}")
        for k, v in r["liquid"].items():
            print(f"   {k}: removed={v['m_removed']:.5f} kg/s f_out={v['f_out']:.3e}")
        vv = [(pid, o['v']) for pid, o in r['rec'].items() if 'v' in o]
        print(f"   max pipe vel={max(v for _, v in vv):.2f} at {max(vv, key=lambda x: x[1])[0]}")
        print(f"   T at MTR-O in = {r['rec']['MTR-O']['T']:.3f}")
