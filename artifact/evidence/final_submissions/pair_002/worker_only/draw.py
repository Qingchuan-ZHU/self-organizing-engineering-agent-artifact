"""Render a plan-view SVG of the design (site, zones, footprints, roads, pipelines)."""
import os
import lib_geom as G
import ugscat as U
import design as D
import solve as S

OUT = os.path.dirname(os.path.abspath(__file__))
eqmap, ifaces, pipes = S.build()
env_by_eq = {eid: S.envelopes(eqmap[eid]) for eid in eqmap}

W, H = 700.0, 450.0
SCALE = 1.35
wd, ht = W * SCALE + 40, H * SCALE + 40


def X(x):
    return 20 + x * SCALE


def Y(y):
    return ht - (20 + y * SCALE)


def poly(points, **attrs):
    pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in points)
    return f'<polygon points="{pts}" ' + " ".join(f'{k.replace("_","-")}="{v}"' for k, v in attrs.items()) + "/>"


def line(a, b, **attrs):
    return (f'<line x1="{X(a[0]):.1f}" y1="{Y(a[1]):.1f}" x2="{X(b[0]):.1f}" y2="{Y(b[1]):.1f}" '
            + " ".join(f'{k.replace("_","-")}="{v}"' for k, v in attrs.items()) + "/>")


out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{wd:.0f}" height="{ht:.0f}" '
       f'viewBox="0 0 {wd:.0f} {ht:.0f}" font-family="Helvetica,Arial" font-size="9">']
out.append(f'<rect width="{wd:.0f}" height="{ht:.0f}" fill="white"/>')

# site boundary
out.append(poly([tuple(p) for p in U.SITE["boundary_polygon_m"]], fill="none", stroke="#333", stroke_width="2"))
# no-build zones
for z in U.SITE["no_build_zones"]:
    out.append(poly([tuple(p) for p in z["polygon_m"]], fill="#fdd", stroke="#c99", stroke_dasharray="5,3"))
    cx = sum(p[0] for p in z["polygon_m"]) / len(z["polygon_m"])
    cy = sum(p[1] for p in z["polygon_m"]) / len(z["polygon_m"])
    out.append(f'<text x="{X(cx):.0f}" y="{Y(cy):.0f}" fill="#a66" text-anchor="middle">{z["zone_id"]}</text>')

# roads (paved strips)
for rid, r in D.ROADS.items():
    hw = r["width"] / 2
    for i in range(len(r["pts"]) - 1):
        out.append(poly(S.seg_rect(r["pts"][i], r["pts"][i + 1], hw), fill="#e8e8e8", stroke="#bbb"))

# pipelines
for pid, p in pipes.items():
    for s in p["segs"]:
        col = "#1f77b4" if p["spec"].get("medium") != "liquid" else "#d62728"
        out.append(line(s["a"], s["b"], stroke=col, stroke_width="2", opacity="0.65"))

# maintenance envelopes
for eid, envs in env_by_eq.items():
    for kind, poly_ in envs:
        col = "#ffd9a0" if kind == "clearance" else "#ffb3b3"
        out.append(poly(poly_, fill=col, opacity="0.30", stroke="none"))

# footprints
for eid, eq in eqmap.items():
    out.append(poly(eq["poly"], fill="#7fbf7f", stroke="#245c24", stroke_width="1.4", opacity="0.95"))
    out.append(f'<text x="{X(eq["x"]):.0f}" y="{Y(eq["y"]) + 3:.0f}" text-anchor="middle" fill="#04230a">{eid}</text>')

# interfaces
for iid, it in ifaces.items():
    x, y = it["pos"]
    out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4" fill="#4400cc"/>')
    out.append(f'<text x="{X(x) + 6:.0f}" y="{Y(y) - 5:.0f}" fill="#4400cc">{iid}</text>')

out.append(f'<text x="20" y="16" font-size="13" font-weight="bold">UGS-SYNTH-D01 v1.1 - plan view '
           f'(green = equipment, grey = roads, blue = gas pipes, red = liquid pipes, orange = maintenance envelopes)</text>')
out.append("</svg>")
open(os.path.join(OUT, "layout.svg"), "w").write("\n".join(out))
print("wrote layout.svg")
