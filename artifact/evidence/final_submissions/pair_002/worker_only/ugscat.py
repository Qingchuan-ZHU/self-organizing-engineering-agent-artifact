"""Catalogs + gas-property + hydraulics helpers for UGS-SYNTH-D01."""
import json, math, os

BRIEF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brief")


def load(name):
    with open(os.path.join(BRIEF, name)) as f:
        return json.load(f)


CAT = {}
for fn in ["compressors", "separators", "dehydration", "filters", "headers",
           "metering_regulation", "thermal_equipment", "drains"]:
    for m in load(f"equipment_catalog/{fn}.json")["models"]:
        CAT[m["model_id"]] = m

PIPING = load("piping_catalog.json")
SITE = load("site.json")
SCEN = load("operating_scenarios.json")
WELLS = load("well_group_interfaces.json")
PROJ = load("project_requirements.json")
ECON = load("economic_assumptions.json")
SAFETY = load("safety_requirements.json")
MAINT = load("maintenance_requirements.json")
GAS = load("gas_properties.json")

DIAM = {d["nominal_diameter"]: d for d in PIPING["diameters"]}
CLS = {c["class_id"]: c for c in PIPING["classes"]}
LEVELS = PIPING["routing_levels"]

R_U = 8.314462618
MW = GAS["molecular_weight_kg_mol"]
CP = GAS["heat_capacity_cp_j_kg_k"]
K = GAS["specific_heat_ratio"]

DIA_TOL = 1e-6


def z_factor(P, T_c):
    Tk = T_c + 273.15
    z = 0.90 + 0.08 * P / (P + 10.0) + 0.00015 * (Tk - 293.15)
    return min(max(z, GAS["compressibility_proxy"]["minimum"]), GAS["compressibility_proxy"]["maximum"])


def viscosity(P, T_c):
    Tk = T_c + 273.15
    mu = 1.05e-5 * (Tk / 293.15) ** 0.70 * (1 + 0.002 * P)
    return min(max(mu, GAS["viscosity_proxy"]["minimum"]), GAS["viscosity_proxy"]["maximum"])


def density(P, T_c):
    P = max(P, 1e-6)
    Tk = T_c + 273.15
    return (P * 1e6) * MW / (z_factor(P, T_c) * R_U * Tk)


def friction_factor(Re, eps, D):
    if Re < 2300:
        return 64.0 / Re
    rel = eps / (3.7 * D) + 5.74 / Re ** 0.9
    return 0.25 / (math.log10(rel) ** 2)


def pipe_loss_mpa(P_in, T_c, m_dot, D, eps, L):
    """Fixed-point outlet pressure per the calculation basis. Returns (P_out, v, Re, converged)."""
    if m_dot <= 0 or L <= 0:
        return max(P_in, 1e-6), 0.0, 0.0, True
    P_out = P_in
    converged = False
    v = Re = 0.0
    for _ in range(8):
        P_mean = (P_in + P_out) / 2.0
        rho = density(P_mean, T_c)
        mu = viscosity(P_mean, T_c)
        A = math.pi * D * D / 4.0
        v = m_dot / (rho * A)
        Re = rho * v * D / mu
        f = friction_factor(Re, eps, D)
        dP = f * (L / D) * rho * v * v / 2.0 / 1e6
        new = max(1e-6, P_in - dP)
        if abs(new - P_out) < 1e-5:
            P_out = new
            converged = True
            break
        P_out = new
    return P_out, v, Re, converged
