import sys, json
sys.path.insert(0, "/workspace/project")
import ugs_analysis as A
import ugs_lcc as L

dg = A.make_design(vtarget_gas=15.0)
res = L.solve_all(dg)
energy = L.check_scenarios(dg, res)
n1 = L.check_nminus1(dg)
lcc = L.compute_lcc(dg, energy)

bad = [c for c in L.CHECKS if not c["ok"]]
print(f"checks: {len(L.CHECKS)}  failed: {len(bad)}")
for b in bad:
    print("   FAIL", b["scenario"], b["tag"], b["message"])
print()
for sid, e in energy.items():
    print(f"  energy {sid:9s} {e:.3f} MW   annual {e*A.SCEN[[s['id'] for s in A.SCEN].index(sid)]['hours']:.0f} MWh")
print()
print("--- LCC breakdown (MBCU) ---")
for k, v in lcc["breakdown"].items():
    print(f"  {k:18s} {v:12.3f}")
print(f"  {'LCC TOTAL':18s} {lcc['lcc_mbcu']:12.3f}")
print()
print("road length", lcc["civil"]["road_length_m"], "footprint area", round(lcc["civil"]["footprint_area_m2"],1),
      "maint area", round(lcc["civil"]["maintenance_area_m2"],1))
print()
print("diameters/classes:")
for nid in sorted(dg["diam"]):
    print(f"  {nid:16s} {dg['diam'][nid]:7s} {dg['cls'][nid]:10s} {A.LEN[nid]:7.1f} m")
