import sys, json, math
sys.path.insert(0, "/workspace/project")
import router, nets
res = router.route_all(nets.NETS)
out = {}
for n in nets.NETS:
    r = res[n["id"]]
    L = 0.0
    if r["status"] == "ok":
        pts = r["pts"]
        L = sum(math.hypot(pts[k+1][0]-pts[k][0], pts[k+1][1]-pts[k][1]) for k in range(len(pts)-1))
    out[n["id"]] = dict(status=r["status"], pts=r["pts"], level=r["level"], length=L)
with open("/workspace/project/routes.json", "w") as f:
    json.dump(out, f, indent=1)
print("saved", len(out), "routes; total", round(sum(v["length"] for v in out.values()), 1))
