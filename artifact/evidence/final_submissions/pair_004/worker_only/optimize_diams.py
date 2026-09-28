"""Per-link pipe diameter coordinate descent to minimise benchmark LCC."""
import sys
sys.path.insert(0, "/workspace/project")
import ugs_analysis as A
import ugs_lcc as L

HIGH = set(["N-TS-REG", "N-TS-CW1", "N-TS-CW2", "N-DEH1-TS", "N-DEH2-TS", "N-DEH3-TS",
            "N-SEP1-DEH1", "N-SEP2-DEH2", "N-SEP3-DEH3", "N-WS-SEP1", "N-WS-SEP2", "N-WS-SEP3",
            "N-CI1-CH", "N-CI2-CH", "N-CI3-CH", "N-CH-COOL", "N-COOL-WS"] + [f"N-WS-WG{i}" for i in range(1, 7)])
WET = set(["N-WS-SEP1", "N-WS-SEP2", "N-WS-SEP3", "N-SEP1-DEH1", "N-SEP2-DEH2", "N-SEP3-DEH3"] + [f"N-WS-WG{i}" for i in range(1, 7)])


def class_for(nid, tbl):
    if (nid.startswith("N-SEP") and "-DRN" in nid) or nid.startswith("N-DRN"):
        return "CS-WET-100"
    if nid in HIGH:
        return "CS-WET-160" if nid in WET else "CS-DRY-160"
    return "CS-WET-100"


A.class_for = class_for
A.T_COOL = 58.0

TBL = A.build_tables()
CLS = {nid: class_for(nid, TBL) for nid in A.LEN}
EPS = {nid: A.CLASSES[CLS[nid]]["roughness_m"] for nid in A.LEN}


def design_from(diam):
    Dyn = {nid: A.DIAM_MAP[dn]["internal_diameter_m"] for nid, dn in diam.items()}
    return dict(tbl=TBL, diam=dict(diam), Dyn=Dyn, cls=CLS, epsn=EPS)


def lcc_of(diam, collect=False):
    dg = design_from(diam)
    if collect:
        del L.CHECKS[:]
    res = L.solve_all(dg)
    en = L.check_scenarios(dg, res)
    lcc = L.compute_lcc(dg, en)
    nfail = len([c for c in L.CHECKS if not c["ok"]])
    if not collect:
        del L.CHECKS[:]
    return lcc["lcc_mbcu"], nfail


def optimize(start_vt=7.0):
    diam = A.make_design(start_vt)["diam"]
    best, _ = lcc_of(diam)
    order = sorted(A.LEN, key=lambda k: -A.LEN[k])
    for it in range(3):
        improved = False
        for nid in order:
            cur = diam[nid]
            bestdn = cur
            for d in A.DIAMS:
                dn = d["nominal_diameter"]
                if dn == cur:
                    continue
                trial = dict(diam); trial[nid] = dn
                v, nf = lcc_of(trial)
                if nf == 0 and v < best - 1e-9:
                    best = v; bestdn = dn
            if bestdn != cur:
                diam[nid] = bestdn
                improved = True
        if not improved:
            break
    return diam, best


if __name__ == "__main__":
    diam, best = optimize()
    v, nf = lcc_of(diam, collect=True)
    print("final LCC", round(v, 4), "fails", nf)
    for nid in sorted(diam):
        print(f"  {nid:16s} {diam[nid]:7s} {CLS[nid]:10s} {A.LEN[nid]:7.1f}")
    import json
    json.dump(diam, open("/workspace/project/diam_opt.json", "w"), indent=1)
    print("saved diam_opt.json")
