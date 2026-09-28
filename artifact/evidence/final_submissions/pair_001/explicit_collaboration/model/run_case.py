"""Runs the complete case (all scenarios + all n-1 cases), checks every published
requirement and writes the deliverable data files."""
import json
import math
import os
import catalog as C
import design as D
import geometry as G
import process as PR
import scenarios as S
import checks as CHK
import quantities as Q
import analysis as A

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deliverables")
SCEN_IDS = ["INJ-LOW", "INJ-MID", "INJ-HIGH", "WDR-HIGH", "WDR-MID", "WDR-LOW"]

# --------------------------------------------------------------- case matrix
def n1_cases():
    """Every single-unit outage required by the published n-1 rules.

    "one unit unavailable at a time" is applied to every individual unit of each
    affected category, not to a representative unit.
    """
    out = []
    nmin1 = C.REQS["reliability_requirements"]["compression_n_minus_one"]
    tmin1 = C.REQS["reliability_requirements"]["withdrawal_treatment_n_minus_one"]
    for sid in SCEN_IDS:
        scen = A.SCEN_BY_ID[sid]
        flow = scen["required_total_flow_kg_s"]
        if A.needs_compression(scen):
            cap = 2 * C.MODELS["C60"]["capacity_kg_s"]
            retained = min(flow, cap)
            for i in (0, 1, 2):
                out.append({"scenario": sid, "outage": ("compressor", i),
                            "flow": retained,
                            "required_fraction": nmin1["minimum_retained_flow_fraction"]})
        if scen["service"] == "withdrawal":
            retained = min(flow, 2 * C.MODELS["SEP70"]["capacity_kg_s"])
            for cat in tmin1["failed_equipment_categories"]:
                for i in (0, 1, 2):
                    out.append({"scenario": sid, "outage": (cat, i), "flow": retained,
                                "required_fraction": tmin1["minimum_retained_flow_fraction"]})
    return out


def op_minus_one(scen_id, outage, flow, label):
    """Run one outage case; return result + checks."""
    res = A.run_case(scen_id, flow=flow, outage=outage, label=label)
    errs = A.check_case(res)
    return res, errs


def main():
    os.makedirs(OUT, exist_ok=True)
    chk, eq, roads, segs = CHK.run()
    assert not chk.errors, chk.errors

    normal = {}
    n1 = []
    errors = []
    for sid in SCEN_IDS:
        res = A.run_case(sid)
        normal[sid] = res
        errors += [f"{sid}: {e}" for e in A.check_case(res)]
    unit_of = {"compressor": ("CMP-A", "CMP-B", "CMP-C"),
               "separator": ("SEP-A", "SEP-B", "SEP-C"),
               "dehydration": ("DEH-A", "DEH-B", "DEH-C")}
    for case in n1_cases():
        label = (f"{case['scenario']}-N1-"
                 f"{unit_of[case['outage'][0]][case['outage'][1]]}")
        res, errs = op_minus_one(case["scenario"], case["outage"], case["flow"], label)
        scen = A.SCEN_BY_ID[case["scenario"]]
        retained_frac = case["flow"] / scen["required_total_flow_kg_s"]
        ok = retained_frac + 1e-9 >= case["required_fraction"]
        n1.append({"case": label, "scenario": case["scenario"], "outage": case["outage"],
                   "flow_kg_s": case["flow"], "retained_fraction": retained_frac,
                   "required_fraction": case["required_fraction"], "feasible": ok,
                   "violations": errs, "result": res})
        errors += [f"{label}: {e}" for e in errs]
        if not ok:
            errors.append(f"{label}: retained fraction below requirement")

    energy = {sid: Q.scenario_energy(normal[sid]) for sid in SCEN_IDS}
    lcc = Q.lifecycle_cost(eq, roads, segs, energy)

    summary = {
        "case_id": C.CASEMETA["case_id"],
        "geometry_errors": chk.errors,
        "operating_case_errors": errors,
        "lcc_mbcu": lcc["lcc_mbcu"],
        "annual_energy_mwh": lcc["annual_energy_mwh"],
        "equipment_count": len(eq),
        "pipeline_count": len(S.PIPES),
        "n1_cases": [{k: v for k, v in c.items() if k != "result"} for c in n1],
    }
    with open(os.path.join(OUT, "case_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("geometry_errors",)}, indent=1))
    return chk, eq, roads, segs, normal, n1, lcc, energy, errors


if __name__ == "__main__":
    main()
