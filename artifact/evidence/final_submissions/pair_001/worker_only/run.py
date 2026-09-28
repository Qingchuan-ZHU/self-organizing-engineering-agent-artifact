"""Entry point: build the UGS-SYNTH-D01 design and write all deliverables."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from build_outputs import build  # noqa: E402

if __name__ == "__main__":
    nw, res, lcc, checklist = build()
    print("LCC = %.4f MBCU" % lcc["lcc"])
    print("geometry issues:", len(checklist["geometry_issues"]))
    print("scenario violations:", sum(len(v) for v in checklist["scenario_violations"].values()))
    print("N-1 issues:", len(checklist["n_minus_one_issues"]))
    print("pipe-class issues:", len(checklist["pipe_class_issues"]))
