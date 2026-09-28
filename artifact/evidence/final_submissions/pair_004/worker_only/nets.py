"""Physical connection list (nets) for the UGS facility."""
import sys
sys.path.insert(0, "/workspace/project")
from ugs_design import load, load_catalog, INSTANCES, port_world

cat = load_catalog()
site = load("site.json")
IF = {i["interface_id"]: i["point_m"] for i in site["external_interfaces"]}
INST = {i["id"]: i for i in INSTANCES}


def P(iid, pid):
    return port_world(INST[iid], cat, pid)


WG = {"WG-01": (12, 45), "WG-02": (12, 117), "WG-03": (12, 189),
      "WG-04": (12, 261), "WG-05": (12, 333), "WG-06": (12, 405)}

NETS = []


def net(nid, start, end, service="gas", level="ground"):
    NETS.append(dict(id=nid, start=start, end=end, service=service, level=level))


# --- GRID-TIE metering legs
net("N-MTRINJ-GRID", P("MTR-INJ", "gas_in"), IF["GRID-TIE"])
net("N-MTRINJ-GS", P("MTR-INJ", "gas_out"), P("H-GS", "branch_02"))
net("N-GS-MTRWDR", P("H-GS", "branch_10"), P("MTR-WDR", "gas_in"))
net("N-MTRWDR-GRID", P("MTR-WDR", "gas_out"), IF["GRID-TIE"])

# --- injection compressor suction (GS -> compressors)
net("N-GS-CI1", P("H-GS", "branch_04"), P("C-I1", "suction"))
net("N-GS-CI2", P("H-GS", "branch_07"), P("C-I2", "suction"))
net("N-GS-CI3", P("H-GS", "branch_08"), P("C-I3", "suction"))
# --- compressor discharge (compressors -> CH)
net("N-CI1-CH", P("C-I1", "discharge"), P("H-CH", "branch_04"))
net("N-CI2-CH", P("C-I2", "discharge"), P("H-CH", "branch_08"))
net("N-CI3-CH", P("C-I3", "discharge"), P("H-CH", "branch_01"))
# --- cooler
net("N-CH-COOL", P("H-CH", "branch_02"), P("COOL-1", "gas_in"))
net("N-COOL-WS", P("COOL-1", "gas_out"), P("H-WS", "branch_06"))

# --- wells
net("N-WS-WG1", P("H-WS", "branch_04"), WG["WG-01"])
net("N-WS-WG2", P("H-WS", "branch_01"), WG["WG-02"])
net("N-WS-WG3", P("H-WS", "branch_05"), WG["WG-03"])
net("N-WS-WG4", P("H-WS", "branch_08"), WG["WG-04"])
net("N-WS-WG5", P("H-WS", "branch_07"), WG["WG-05"])
net("N-WS-WG6", P("H-WS", "branch_09"), WG["WG-06"])

# --- separators feed (WS -> separators)
net("N-WS-SEP1", P("H-WS", "branch_02"), P("SEP-1", "gas_in"))
net("N-WS-SEP2", P("H-WS", "branch_10"), P("SEP-2", "gas_in"))
net("N-WS-SEP3", P("H-WS", "branch_03"), P("SEP-3", "gas_in"))
net("N-SEP1-DEH1", P("SEP-1", "gas_out"), P("DEH-1", "gas_in"))
net("N-SEP2-DEH2", P("SEP-2", "gas_out"), P("DEH-2", "gas_in"))
net("N-SEP3-DEH3", P("SEP-3", "gas_out"), P("DEH-3", "gas_in"))
net("N-DEH1-TS", P("DEH-1", "gas_out"), P("H-TS", "branch_04"))
net("N-DEH2-TS", P("DEH-2", "gas_out"), P("H-TS", "branch_01"))
net("N-DEH3-TS", P("DEH-3", "gas_out"), P("H-TS", "branch_02"))

# --- regulation / boosting (TS -> grid side)
net("N-TS-REG", P("H-TS", "branch_06"), P("REG-1", "gas_in"))
net("N-REG-GS", P("REG-1", "gas_out"), P("H-GS", "branch_06"))
net("N-TS-CW1", P("H-TS", "branch_03"), P("C-W1", "suction"))
net("N-TS-CW2", P("H-TS", "branch_10"), P("C-W2", "suction"))
net("N-CW1-GS", P("C-W1", "discharge"), P("H-GS", "branch_05"))
net("N-CW2-GS", P("C-W2", "discharge"), P("H-GS", "branch_09"))

# --- liquid drains
net("N-SEP1-DRN1", P("SEP-1", "liquid_out"), P("DRN-1", "drain_in"), "liquid")
net("N-SEP2-DRN2", P("SEP-2", "liquid_out"), P("DRN-2", "drain_in"), "liquid")
net("N-SEP3-DRN3", P("SEP-3", "liquid_out"), P("DRN-3", "drain_in"), "liquid")
net("N-DRN1-OUT", P("DRN-1", "drain_out"), IF["LIQUID-DRAIN-OUTFALL"], "liquid")
net("N-DRN2-OUT", P("DRN-2", "drain_out"), IF["LIQUID-DRAIN-OUTFALL"], "liquid")
net("N-DRN3-OUT", P("DRN-3", "drain_out"), IF["LIQUID-DRAIN-OUTFALL"], "liquid")
