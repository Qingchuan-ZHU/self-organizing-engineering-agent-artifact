"""Gas properties, pipe hydraulics and equipment models (published formulas)."""
import math
import catalog as C

RU = 8.314462618
MW = C.GAS["molecular_weight_kg_mol"]
CP = C.GAS["heat_capacity_cp_j_kg_k"]
K = C.GAS["specific_heat_ratio"]
P_MIN = 1e-6

Z_MIN = C.GAS["compressibility_proxy"]["minimum"]
Z_MAX = C.GAS["compressibility_proxy"]["maximum"]
MU_MIN = C.GAS["viscosity_proxy"]["minimum"]
MU_MAX = C.GAS["viscosity_proxy"]["maximum"]


def z_factor(p_mpa, t_c):
    p = max(p_mpa, P_MIN)
    t_k = t_c + 273.15
    z = 0.90 + 0.08 * p / (p + 10.0) + 0.00015 * (t_k - 293.15)
    return min(Z_MAX, max(Z_MIN, z))


def viscosity(p_mpa, t_c):
    p = max(p_mpa, P_MIN)
    t_k = t_c + 273.15
    mu = 1.05e-5 * (t_k / 293.15) ** 0.70 * (1.0 + 0.002 * p)
    return min(MU_MAX, max(MU_MIN, mu))


def density(p_mpa, t_c):
    p = max(p_mpa, P_MIN)
    t_k = t_c + 273.15
    return (p * 1e6) * MW / (z_factor(p, t_c) * RU * t_k)


def friction_factor(re, eps, d):
    if re < 2300.0:
        return 64.0 / re if re > 0 else 0.0
    rel = eps / (3.7 * d)
    return 0.25 / (math.log10(rel + 5.74 / re ** 0.9) ** 2)


def pipe_velocity(m_dot, p_mpa, t_c, d_in):
    a = math.pi * d_in ** 2 / 4.0
    return m_dot / (density(p_mpa, t_c) * a)


def pipe_outlet_pressure(m_dot, p_in, t_c, length_m, d_in, eps, max_updates=8):
    """Published fixed-point convention.  Returns (p_out, converged, n_updates)."""
    p_out = p_in
    for i in range(1, max_updates + 1):
        p_mean = 0.5 * (p_in + p_out)
        rho = density(p_mean, t_c)
        mu = viscosity(p_mean, t_c)
        area = math.pi * d_in ** 2 / 4.0
        v = m_dot / (rho * area)
        re = rho * v * d_in / mu
        f = friction_factor(re, eps, d_in)
        dp = f * (length_m / d_in) * rho * v * v / 2.0 / 1e6      # MPa
        new = max(P_MIN, p_in - dp)
        if abs(new - p_out) < 1e-5:
            return new, True, i
        p_out = new
    return p_out, False, max_updates


def compressor_outlet_temperature(t_in_c, ratio, eta):
    t_in_k = t_in_c + 273.15
    return t_in_k * (1.0 + (ratio ** ((K - 1.0) / K) - 1.0) / eta) - 273.15


def compressor_power_mw(m_dot, t_in_c, ratio, eta, eta_driver):
    t_in_k = t_in_c + 273.15
    w = m_dot * CP * t_in_k * (ratio ** ((K - 1.0) / K) - 1.0) / (eta * eta_driver)
    return w / 1e6


# ------------------------------------------------------------------ helpers
def pvf(discount_rate, years):
    if discount_rate == 0:
        return float(years)
    return (1.0 - (1.0 + discount_rate) ** (-years)) / discount_rate
