"""Gas-property and hydraulic correlations from engineering_calculation_basis.md."""
from __future__ import annotations

import math

R_UNIVERSAL = 8.314462618  # J/(mol K)
P_FLOOR_MPA = 1e-6


def kelvin(t_c: float) -> float:
    return t_c + 273.15


def celsius(t_k: float) -> float:
    return t_k - 273.15


class GasProperties:
    def __init__(self, gas: dict):
        self.mw = gas["molecular_weight_kg_mol"]
        self.cp = gas["heat_capacity_cp_j_kg_k"]
        self.k = gas["specific_heat_ratio"]
        self.z_min = gas["compressibility_proxy"]["minimum"]
        self.z_max = gas["compressibility_proxy"]["maximum"]
        self.mu_min = gas["viscosity_proxy"]["minimum"]
        self.mu_max = gas["viscosity_proxy"]["maximum"]

    def compressibility(self, p_mpa: float, t_c: float) -> float:
        p = max(p_mpa, P_FLOOR_MPA)
        tk = kelvin(t_c)
        z = 0.90 + 0.08 * p / (p + 10.0) + 0.00015 * (tk - 293.15)
        return min(max(z, self.z_min), self.z_max)

    def viscosity(self, p_mpa: float, t_c: float) -> float:
        p = max(p_mpa, P_FLOOR_MPA)
        tk = kelvin(t_c)
        mu = 1.05e-5 * (tk / 293.15) ** 0.70 * (1.0 + 0.002 * p)
        return min(max(mu, self.mu_min), self.mu_max)

    def density(self, p_mpa: float, t_c: float) -> float:
        p = max(p_mpa, P_FLOOR_MPA)
        tk = kelvin(t_c)
        z = self.compressibility(p, t_c)
        return (p * 1e6) * self.mw / (z * R_UNIVERSAL * tk)


def darcy_friction_factor(re: float, epsilon: float, d: float) -> float:
    if re < 2300.0:
        return 64.0 / re if re > 0 else 0.0
    rel = epsilon / (3.7 * d) + 5.74 / (re ** 0.9)
    return 0.25 / (math.log10(rel) ** 2)


def pipe_velocity(m_dot: float, rho: float, d: float) -> float:
    area = math.pi * d * d / 4.0
    return m_dot / (rho * area)


def pipe_pressure_loss_mpa(m_dot: float, length: float, d: float, epsilon: float,
                           rho: float, mu: float) -> tuple[float, float, float]:
    """Return (deltaP_mpa, velocity_m_s, reynolds)."""
    area = math.pi * d * d / 4.0
    v = m_dot / (rho * area)
    re = rho * v * d / mu
    f = darcy_friction_factor(re, epsilon, d)
    dp_pa = f * (length / d) * rho * v * v / 2.0
    return dp_pa / 1e6, v, re


def solve_pipe_exit_pressure(p_in_mpa: float, t_c: float, m_dot: float, length: float,
                             d: float, epsilon: float, gas: GasProperties,
                             max_iter: int = 8, tol: float = 1e-5):
    """Fixed-point outlet pressure convention from the calculation basis.

    Temperature is treated as constant through the segment (no heat transfer is
    modelled).  The returned properties are evaluated at the mean pressure.
    """
    if length <= 0.0 or m_dot <= 0.0:
        rho = gas.density(p_in_mpa, t_c)
        return {"converged": True, "p_out": p_in_mpa, "dp": 0.0, "v": 0.0,
                "re": 0.0, "rho": rho, "mu": gas.viscosity(p_in_mpa, t_c),
                "p_mean": p_in_mpa}
    p_out = p_in_mpa
    converged = False
    for _ in range(max_iter):
        p_mean = (p_in_mpa + p_out) / 2.0
        rho = gas.density(p_mean, t_c)
        mu = gas.viscosity(p_mean, t_c)
        dp, v, re = pipe_pressure_loss_mpa(m_dot, length, d, epsilon, rho, mu)
        new_out = max(P_FLOOR_MPA, p_in_mpa - dp)
        if abs(new_out - p_out) < tol:
            p_out = new_out
            converged = True
            break
        p_out = new_out
    p_mean = (p_in_mpa + p_out) / 2.0
    rho = gas.density(p_mean, t_c)
    mu = gas.viscosity(p_mean, t_c)
    dp, v, re = pipe_pressure_loss_mpa(m_dot, length, d, epsilon, rho, mu)
    return {"converged": converged, "p_out": p_out, "dp": p_in_mpa - p_out,
            "v": v, "re": re, "rho": rho, "mu": mu, "p_mean": p_mean}


def compressor_outlet_temperature(t_in_c: float, ratio: float, k: float, eta: float) -> float:
    if ratio <= 1.0:
        return t_in_c
    tk = kelvin(t_in_c)
    return celsius(tk * (1.0 + (ratio ** ((k - 1.0) / k) - 1.0) / eta))


def compressor_power_mw(m_dot: float, cp: float, t_in_c: float, ratio: float,
                        k: float, eta: float, eta_driver: float) -> float:
    if ratio <= 1.0 or m_dot <= 0.0:
        return 0.0
    tk = kelvin(t_in_c)
    w = m_dot * cp * tk * (ratio ** ((k - 1.0) / k) - 1.0) / (eta * eta_driver)
    return w / 1e6


def regulator_outlet_temperature(t_in_c: float, p_in: float, p_out: float, jt: float) -> float:
    if p_in <= p_out:
        return t_in_c
    return t_in_c - jt * (p_in - p_out)
