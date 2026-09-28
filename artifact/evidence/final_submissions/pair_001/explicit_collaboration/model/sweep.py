"""Coordinate-descent optimisation of the pipe diameters (minimise LCC)."""
import sys
import itertools
import catalog as C
import design as D
import checks as CHK
import quantities as Q
import analysis as A
import scenarios as S

SCEN_IDS = ["INJ-LOW", "INJ-MID", "INJ-HIGH", "WDR-HIGH", "WDR-MID", "WDR-LOW"]
DIA_ORDER = [d["nominal_diameter"] for d in C.PIPING["diameters"]]


def set_dn(pid, dn):
    S.PIPES[pid]["dn"] = dn
    S.PIPES[pid]["id_m"] = C.DIAMS[dn]["internal_diameter_m"]
    S.PIPES[pid]["cost_rate"] = C.DIAMS[dn]["installed_cost_mbcu_per_m"]


def evaluate_lcc(eq, roads, segs, verbose=False):
    energy = {}
    errs = []
    for sid in SCEN_IDS:
        res = A.run_case(sid)
        errs += A.check_case(res)
        energy[sid] = Q.scenario_energy(res)
    lcc = Q.lifecycle_cost(eq, roads, segs, energy)
    if verbose:
        for e in errs:
            print("   ", e)
    return lcc, errs, energy


def main(max_passes=6):
    chk, eq, roads, segs = CHK.run()
    assert not chk.errors, chk.errors
    base, errs, _ = evaluate_lcc(eq, roads, segs)
    print(f"baseline LCC {base['lcc_mbcu']:.4f}  (errors {len(errs)})")
    best = base["lcc_mbcu"]
    for p in range(max_passes):
        improved = False
        for pid in sorted(S.PIPES):
            cur = S.PIPES[pid]["dn"]
            i = DIA_ORDER.index(cur)
            for direction in (+1, -1):
                while True:
                    j = DIA_ORDER.index(cur) + direction
                    if j < 0 or j >= len(DIA_ORDER):
                        break
                    if S.PIPES[pid]["service"] == "liquid" and DIA_ORDER[j] in ("DN150",):
                        break
                    cand = DIA_ORDER[j]
                    set_dn(pid, cand)
                    lcc, errs, _ = evaluate_lcc(eq, roads, segs)
                    if not errs and lcc["lcc_mbcu"] < best - 1e-7:
                        best = lcc["lcc_mbcu"]
                        cur = cand
                        improved = True
                        print(f"  pass{p+1} {pid}: {cand} -> LCC {best:.4f}", flush=True)
                    else:
                        set_dn(pid, cur)
                        break
        if not improved:
            break
    print("final LCC", round(best, 4))
    for pid in sorted(S.PIPES):
        print(f"   {pid}: {S.PIPES[pid]['dn']}")
    lcc, errs, energy = evaluate_lcc(eq, roads, segs, verbose=True)
    print("errors:", errs)
    print({k: round(v, 4) for k, v in lcc.items() if k != "detail"})


if __name__ == "__main__":
    main()
