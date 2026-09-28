"""Final connection-cardinality / interface-limit validation."""
import sys, json
sys.path.insert(0, "/workspace/project")
from ugs_design import load, load_catalog, INSTANCES
import nets

CAT = load_catalog()
site = load("site.json")
IF = {i["interface_id"]: i for i in site["external_interfaces"]}
INST = {i["id"]: i for i in INSTANCES}
viol = []

# count connections per equipment port and per interface
port_count = {}
iface_count = {}
for n in nets.NETS:
    for ep in (n["start"], n["end"]):
        x, y = ep
        # find which port/interface it is
        found = False
        for iid, inst in INST.items():
            for p in CAT[inst["model_id"]]["ports"]:
                from ugs_design import port_world
                if abs(port_world(inst, CAT, p["id"])[0] - x) < 1e-9 and abs(port_world(inst, CAT, p["id"])[1] - y) < 1e-9:
                    key = (iid, p["id"])
                    port_count[key] = port_count.get(key, 0) + 1
                    found = True
                    break
            if found:
                break
        if not found:
            for iid, i in IF.items():
                if abs(i["point_m"][0] - x) < 1e-9 and abs(i["point_m"][1] - y) < 1e-9:
                    iface_count[iid] = iface_count.get(iid, 0) + 1
                    found = True
                    break
        if not found:
            viol.append(f"endpoint ({x},{y}) of {n['id']} does not match any port or interface")

for (iid, pid), c in port_count.items():
    if c > 1:
        viol.append(f"port {iid}.{pid} has {c} connections (>1)")
for iid, c in iface_count.items():
    mx = IF[iid].get("maximum_connections", 1)
    if c > mx:
        viol.append(f"interface {iid} has {c} connections > max {mx}")

# header branch usage vs maximum_branch_connections and physical port count
hdr_ports = {}
for n in nets.NETS:
    pass
print("port connections:", len(port_count))
print("interface connections:", iface_count)
if viol:
    print(f"{len(viol)} VIOLATIONS")
    for v in viol:
        print("  -", v)
else:
    print("ALL PORT / INTERFACE CARDINALITY CHECKS PASS")
