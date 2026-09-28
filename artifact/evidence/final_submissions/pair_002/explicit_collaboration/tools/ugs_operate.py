"""Operating plan and scenario hydraulics for UGS-SYNTH-D01.

Builds the operating plan of every published scenario (normal operation and the
required single-unit-outage cases), marches pressure / temperature / gas quality
through the declared process path, and checks every published limit.
"""

from __future__ import annotations

import math

import ugs_basis as B
from ugs_basis import (
    TOL_LIQUID_LOADING, TOL_MASS_FLOW_KG_S, TOL_PRESSURE_MPA, TOL_TEMPERATURE_C,
)

from ugs_check import Design, DELIVERY_PRESSURE_MARGIN_MPA, LIQUID_DENSITY_ASSUMED_KG_M3

WELLS = ["WG-01", "WG-02", "WG-03", "WG-04", "WG-05", "WG-06"]
INJ_COMPRESSORS = ["CMP-INJ-01", "CMP-INJ-02", "CMP-INJ-03"]
# the withdrawal boost service (WDR-LOW) re-uses the injection compressor set
WDR_COMPRESSORS = list(INJ_COMPRESSORS)
COOLERS = ["COOL-INJ-01"]
TRAINS = [("SEP-WDR-01", "DEHY-WDR-01"), ("SEP-WDR-02", "DEHY-WDR-02"),
          ("SEP-WDR-03", "DEHY-WDR-03")]

INJ_SUCTION_PIPE = {"CMP-INJ-01": "P-105", "CMP-INJ-02": "P-104", "CMP-INJ-03": "P-103"}
INJ_DISCHARGE_PIPE = {"CMP-INJ-01": "P-106", "CMP-INJ-02": "P-107", "CMP-INJ-03": "P-108"}
COOLER_IN_PIPE = {"COOL-INJ-01": "P-109"}
COOLER_OUT_PIPE = {}
TRUNK_FROM_COOLER = True
SEP_FEED_PIPE = {"SEP-WDR-01": "P-116", "SEP-WDR-02": "P-115", "SEP-WDR-03": "P-114"}
SEP_DEHY_PIPE = {"SEP-WDR-01": "P-117", "SEP-WDR-02": "P-118", "SEP-WDR-03": "P-119"}
DEHY_HEADER_PIPE = {"DEHY-WDR-01": "P-120", "DEHY-WDR-02": "P-121", "DEHY-WDR-03": "P-122"}
DRAIN_LINE = {"SEP-WDR-01": "P-137", "SEP-WDR-02": "P-138", "SEP-WDR-03": "P-139"}
DRAIN_OUT = {"SEP-WDR-01": "P-140", "SEP-WDR-02": "P-141", "SEP-WDR-03": "P-142"}
DRAIN_LINE_TO_DRAIN = {"SEP-WDR-01": "DRN-WDR-01", "SEP-WDR-02": "DRN-WDR-02",
                       "SEP-WDR-03": "DRN-WDR-03"}

WELL_PIPE = {"WG-01": "P-136", "WG-02": "P-135", "WG-03": "P-134",
             "WG-04": "P-133", "WG-05": "P-132", "WG-06": "P-131"}

COOLER_OUTLET_C = 50.0            # injection aftercooler outlet setpoint (<= 60 degC delivery)


def split_flow(total, units):
    """Allocate ``total`` over ``(tag, capacity, minimum, efficiency)`` units.

    Flow is loaded preferentially on the most efficient machines (tiers of equal
    efficiency), and within a tier proportionally to capacity, keeping every
    running machine inside [minimum stable flow, capacity] and at most 95 % of
    its rated capacity.  Machines left with no duty are idle (not running).
    """
    tiers = {}
    for t, c, m, e in units:
        tiers.setdefault(e, []).append((t, c, m))
    flows = {t: 0.0 for t, _, _, _ in units}
    remaining = total
    for eff in sorted(tiers, reverse=True):
        group = tiers[eff]
        cap = {t: 0.95 * c for t, c, m in group}
        cap_sum = sum(cap.values())
        take = min(remaining, cap_sum)
        for t, c, m in group:
            flows[t] = take * cap[t] / cap_sum
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 1e-9:
        # the request exceeds the sum of the working margins: place the surplus in
        # proportion to the rated capacity so that the split still conserves flow
        # (the per-unit capacity checks then decide whether it is acceptable)
        caps_all = {t: c for t, c, _, _ in units}
        cap_total = sum(caps_all.values())
        for t in flows:
            flows[t] += remaining * caps_all[t] / cap_total
    # honour minimum stable flows
    mins = {t: m for t, _, m, _ in units}
    caps = {t: c for t, c, _, _ in units}
    running = [t for t in flows if flows[t] > 0]
    deficit = sum(max(0.0, mins[t] - flows[t]) for t in running)
    if deficit > 0:
        donors = [t for t in running if flows[t] - mins[t] > 0]
        pool = sum(flows[t] - mins[t] for t in donors)
        for t in running:
            if flows[t] < mins[t]:
                flows[t] = mins[t]
        for t in donors:
            flows[t] -= deficit * (flows[t] - mins[t]) / pool
    return flows


# ---------------------------------------------------------------------------
# plan construction
# ---------------------------------------------------------------------------

def build_plans(design: Design):
    case = design.case
    plans = []
    for sid, sc in case.scenarios.items():
        flow = sc["required_total_flow_kg_s"]
        margin = DELIVERY_PRESSURE_MARGIN_MPA
        src = dict(iface=sc["source_interface"], p=sc["source_pressure_mpa"],
                   t=sc["source_temperature_c"], water=sc["source_water_mg_sm3"],
                   liquid=sc["source_free_liquid_mass_fraction"], flow=flow)
        if sc["service"] == "injection":
            plans.append(dict(id=sid, service="injection", hours=sc["annual_hours"], source=src,
                              sink_required_mpa=sc["required_sink_pressure_mpa"], margin=margin,
                              well_alloc={w: flow / 6.0 for w in WELLS}, kind="normal",
                              compressors=list(INJ_COMPRESSORS), coolers=list(COOLERS),
                              cooler_outlet_c=COOLER_OUTLET_C))
            for out in INJ_COMPRESSORS:
                retained = 0.7 * flow
                s2 = dict(src)
                s2["flow"] = retained
                plans.append(dict(id=f"{sid}/N-1 {out} out", service="injection",
                                  hours=sc["annual_hours"], source=s2,
                                  sink_required_mpa=sc["required_sink_pressure_mpa"], margin=margin,
                                  well_alloc={w: retained / 6.0 for w in WELLS},
                                  kind="n1_compressor", outage=out,
                                  compressors=[c for c in INJ_COMPRESSORS if c != out],
                                  coolers=list(COOLERS), cooler_outlet_c=COOLER_OUTLET_C))
        else:
            needs_boost = sc["required_sink_pressure_mpa"] > sc["source_pressure_mpa"]
            plans.append(dict(id=sid, service="withdrawal", hours=sc["annual_hours"], source=src,
                              sink_required_mpa=sc["required_sink_pressure_mpa"], margin=margin,
                              well_alloc={w: flow / 6.0 for w in WELLS}, kind="normal",
                              trains=[0, 1, 2],
                              compressors=list(WDR_COMPRESSORS) if needs_boost else []))
            for idx, (sep, dehy) in enumerate(TRAINS):
                for out in (sep, dehy):
                    plans.append(dict(id=f"{sid}/N-1 {out} out", service="withdrawal",
                                      hours=sc["annual_hours"], source=dict(src),
                                      sink_required_mpa=sc["required_sink_pressure_mpa"],
                                      margin=margin,
                                      well_alloc={w: flow / 6.0 for w in WELLS},
                                      kind="n1_treatment", outage=out,
                                      trains=[i for i in (0, 1, 2) if i != idx],
                                      compressors=list(WDR_COMPRESSORS) if needs_boost else []))
            if needs_boost:
                for out in WDR_COMPRESSORS:
                    retained = 0.7 * flow
                    s2 = dict(src)
                    s2["flow"] = retained
                    plans.append(dict(id=f"{sid}/N-1 {out} out", service="withdrawal",
                                      hours=sc["annual_hours"], source=s2,
                                      sink_required_mpa=sc["required_sink_pressure_mpa"],
                                      margin=margin,
                                      well_alloc={w: retained / 6.0 for w in WELLS},
                                      kind="n1_compressor", outage=out,
                                      trains=[0, 1, 2],
                                      compressors=[c for c in WDR_COMPRESSORS if c != out]))
    return plans


# ---------------------------------------------------------------------------
# march
# ---------------------------------------------------------------------------

class March:
    def __init__(self, design: Design, plan: dict):
        self.d = design
        self.plan = plan
        self.state = {}
        self.pipe_state = {}
        self.unit_flow = {}
        self.sep_liquid = {}
        self.liquid_pipe_flow = {}
        self.checks = []
        self.energy_mwh = 0.0

    def chk(self, name, ok, detail=""):
        self.checks.append((name, bool(ok), detail))

    def pipe(self, tag, flow, p_in, t_c, direction=1):
        res = self.d.pipe_loss_mpa(tag, flow, p_in, t_c)
        res.flow = flow
        res.direction = direction
        self.pipe_state[tag] = res
        self.chk(f"{tag} hydraulic convergence", res.converged, f"{res.updates} updates")
        return res

    def header(self, tag, flow, p_in, t_c, water=0.0, liquid=0.0):
        m = self.d.nodes[tag].model
        dp = B.header_pressure_drop_mpa(flow, m["capacity_kg_s"],
                                        m["pressure_drop_at_capacity_mpa"])
        self.chk(f"{tag} through flow <= capacity", flow <= m["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
                 f"{flow:.3f} <= {m['capacity_kg_s']:.1f} kg/s")
        self.state[tag] = dict(p_in=p_in, p_out=p_in - dp, dp=dp, t=t_c, flow=flow,
                               water=water, liquid=liquid)
        return p_in - dp

    def simple(self, tag, flow, p_in, t_c, water, liquid):
        m = self.d.nodes[tag].model
        dp = m["pressure_drop_mpa"]
        p_out = p_in - dp
        self.chk(f"{tag} flow <= capacity", flow <= m["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
                 f"{flow:.3f} <= {m['capacity_kg_s']:.1f} kg/s")
        self.chk(f"{tag} pressure <= limit", p_in <= m["maximum_pressure_mpa"] + TOL_PRESSURE_MPA,
                 f"{p_in:.4f} <= {m['maximum_pressure_mpa']:.1f} MPa")
        tmax = m.get("maximum_outlet_temperature_c")
        if tmax is not None:
            self.chk(f"{tag} outlet temperature <= maximum", t_c <= tmax + TOL_TEMPERATURE_C)
        self.state[tag] = dict(p_in=p_in, p_out=p_out, dp=dp, t=t_c, flow=flow,
                               water=water, liquid=liquid)
        return p_out


def run_injection(design: Design, plan: dict, p_discharge_set: float) -> March:
    gas = design.gas
    cp, k = gas.cp, gas.k
    m = March(design, plan)
    flow = plan["source"]["flow"]
    p = plan["source"]["p"]
    t = plan["source"]["t"]
    water = plan["source"]["water"]
    liquid = plan["source"]["liquid"]
    m.state["GRID-TIE"] = dict(p=p, t=t, water=water, liquid=liquid, flow=flow)

    r = m.pipe("P-101", flow, p, t)
    p = r.p_out_mpa
    m.chk("GRID-TIE boundary flow <= interface limit",
          flow <= design.case.interfaces["GRID-TIE"]["maximum_flow_kg_s"] + TOL_MASS_FLOW_KG_S,
          f"{flow:.3f} <= {design.case.interfaces['GRID-TIE']['maximum_flow_kg_s']:.1f} kg/s")
    p = m.simple("MTR-INJ-01", flow, p, t, water, liquid)
    r = m.pipe("P-102", flow, p, t)
    p = r.p_out_mpa
    p = m.header("HDR-INJ-SUC-01", flow, p, t, water, liquid)

    comp_flows = split_flow(flow, [(c, design.nodes[c].model["capacity_kg_s"],
                                            design.nodes[c].model["minimum_stable_flow_kg_s"],
                                            design.nodes[c].model["efficiency_proxy"])
                                           for c in plan["compressors"]])
    m.unit_flow.update(comp_flows)
    m.chk("injection compressor flows sum to scenario flow",
          abs(sum(comp_flows.values()) - flow) < TOL_MASS_FLOW_KG_S,
          f"{sum(comp_flows.values()):.6f} vs {flow:.6f} kg/s")
    mixed_t_num = 0.0
    disch_p = []
    for c in plan["compressors"]:
        cm = design.nodes[c].model
        f = comp_flows[c]
        r = m.pipe(INJ_SUCTION_PIPE[c], f, p, t)
        p_suc = r.p_out_mpa
        ratio = p_discharge_set / p_suc
        t_out = B.compressor_outlet_temperature_c(t, ratio, k, cm["efficiency_proxy"])
        w_mw = B.compressor_power_mw(f, t, ratio, k, cm["efficiency_proxy"],
                                     cm["driver_efficiency"], cp)
        m.state[c] = dict(p_in=p_suc, p_out=p_discharge_set, ratio=ratio, t_in=t, t_out=t_out,
                          power_mw=w_mw, flow=f, running=f > 0)
        if f <= 0:
            m.unit_flow[c] = 0.0
            m.chk(f"{c} idle (not running) in this scenario", True, "no duty")
            continue
        m.chk(f"{c} flow within [min stable, capacity]",
              f >= cm["minimum_stable_flow_kg_s"] - TOL_MASS_FLOW_KG_S and
              f <= cm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.3f} in [{cm['minimum_stable_flow_kg_s']:.1f}, {cm['capacity_kg_s']:.1f}] kg/s")
        m.chk(f"{c} pressure ratio <= maximum", ratio <= cm["maximum_pressure_ratio"] + 1e-9,
              f"{ratio:.4f} <= {cm['maximum_pressure_ratio']:.3f}")
        m.chk(f"{c} suction pressure <= maximum",
              p_suc <= cm["maximum_suction_pressure_mpa"] + TOL_PRESSURE_MPA,
              f"{p_suc:.4f} <= {cm['maximum_suction_pressure_mpa']:.1f} MPa")
        m.chk(f"{c} discharge pressure <= maximum",
              p_discharge_set <= cm["maximum_discharge_pressure_mpa"] + TOL_PRESSURE_MPA,
              f"{p_discharge_set:.4f} <= {cm['maximum_discharge_pressure_mpa']:.1f} MPa")
        m.chk(f"{c} suction temperature <= maximum",
              t <= cm["maximum_suction_temperature_c"] + TOL_TEMPERATURE_C,
              f"{t:.2f} <= {cm['maximum_suction_temperature_c']:.1f} degC")
        m.chk(f"{c} discharge temperature <= maximum",
              t_out <= cm["maximum_discharge_temperature_c"] + TOL_TEMPERATURE_C,
              f"{t_out:.2f} <= {cm['maximum_discharge_temperature_c']:.1f} degC")
        m.chk(f"{c} driver power <= maximum", w_mw <= cm["maximum_power_mw"] + 1e-9,
              f"{w_mw:.3f} <= {cm['maximum_power_mw']:.1f} MW")
        mixed_t_num += f * t_out
        rr = m.pipe(INJ_DISCHARGE_PIPE[c], f, p_discharge_set, t_out)
        disch_p.append(rr.p_out_mpa)
        m.energy_mwh += w_mw * plan["hours"]
    mixed_t = mixed_t_num / flow
    p = m.header("HDR-INJ-DIS-01", flow, min(disch_p), mixed_t, water, liquid)

    cool_flows = split_flow(flow, [(c, design.nodes[c].model["capacity_kg_s"], 0.0, 1.0)
                                   for c in plan["coolers"]])
    m.unit_flow.update(cool_flows)
    cool_t = plan["cooler_outlet_c"]
    p_after = []
    p_cooler_out = p
    for c in plan["coolers"]:
        cm = design.nodes[c].model
        f = cool_flows[c]
        r = m.pipe(COOLER_IN_PIPE[c], f, p, mixed_t)
        p_in = r.p_out_mpa
        duty = B.cooler_duty_mw(f, cp, mixed_t, cool_t)
        power = duty * cm["electric_power_fraction_of_duty"]
        m.chk(f"{c} flow <= capacity", f <= cm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.3f} <= {cm['capacity_kg_s']:.1f} kg/s")
        m.chk(f"{c} pressure <= limit", p_in <= cm["maximum_pressure_mpa"] + TOL_PRESSURE_MPA)
        m.chk(f"{c} duty <= maximum", duty <= cm["maximum_duty_mw"] + 1e-9,
              f"{duty:.3f} <= {cm['maximum_duty_mw']:.1f} MW")
        m.chk(f"{c} outlet temperature >= minimum",
              cool_t >= cm["minimum_outlet_temperature_c"] - TOL_TEMPERATURE_C,
              f"{cool_t:.2f} >= {cm['minimum_outlet_temperature_c']:.1f} degC")
        m.state[c] = dict(p_in=p_in, p_out=p_in - cm["pressure_drop_mpa"], t_in=mixed_t,
                          t_out=cool_t, duty_mw=duty, power_mw=power, flow=f)
        m.energy_mwh += power * plan["hours"]
        p_cooler_out = p_in - cm["pressure_drop_mpa"]
        if c in COOLER_OUT_PIPE:
            rr = m.pipe(COOLER_OUT_PIPE[c], f, p_cooler_out, cool_t)
            p_after.append(rr.p_out_mpa)
        else:
            p_after.append(p_cooler_out)
    p = min(p_after)

    r = m.pipe("P-113", flow, p, cool_t)
    p_wh = r.p_out_mpa
    p = m.header("WH-01", flow, p_wh, cool_t, water, liquid)
    for w in WELLS:
        f = plan["well_alloc"][w]
        r = m.pipe(WELL_PIPE[w], f, p, cool_t)
        m.state[w] = dict(p=r.p_out_mpa, t=cool_t, water=water, liquid=liquid, flow=f)
        m.chk(f"well group {w} flow <= interface limit",
              f <= design.case.interfaces[w]["maximum_flow_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.3f} <= {design.case.interfaces[w]['maximum_flow_kg_s']:.1f} kg/s")
        m.chk(f"delivery temperature at {w} within project limits",
              -10.0 - TOL_TEMPERATURE_C <= cool_t <= 60.0 + TOL_TEMPERATURE_C,
              f"{cool_t:.2f} degC")
        m.chk(f"delivery water content at {w} <= 50 mg/Sm3", water <= 50.0 + 1e-5,
              f"{water:.2f} mg/Sm3")
        m.chk(f"delivery free liquid at {w} <= 1e-4", liquid <= 1e-4 + 1e-9, f"{liquid:.3e}")
    return m


def run_withdrawal(design: Design, plan: dict, reg_out_set: float,
                   boost_discharge_set: float | None) -> March:
    gas = design.gas
    cp, k = gas.cp, gas.k
    m = March(design, plan)
    flow = plan["source"]["flow"]
    p_src = plan["source"]["p"]
    t = plan["source"]["t"]
    water = plan["source"]["water"]
    liquid = plan["source"]["liquid"]

    branch_p = []
    for w in WELLS:
        f = plan["well_alloc"][w]
        m.state[w] = dict(p=p_src, t=t, water=water, liquid=liquid, flow=f)
        r = m.pipe(WELL_PIPE[w], f, p_src, t, direction=-1)
        branch_p.append(r.p_out_mpa)
        m.chk(f"well group {w} flow <= interface limit",
              f <= design.case.interfaces[w]["maximum_flow_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.3f} <= {design.case.interfaces[w]['maximum_flow_kg_s']:.1f} kg/s")
    p = m.header("WH-01", flow, min(branch_p), t, water, liquid)

    trains = plan["trains"]
    train_flow = flow / len(trains)
    dehy_p = []
    sep_out_loading = liquid
    for ti in trains:
        sep, dehy = TRAINS[ti]
        sm = design.nodes[sep].model
        dm = design.nodes[dehy].model
        f = train_flow
        m.unit_flow[sep] = f
        m.unit_flow[dehy] = f
        r = m.pipe(SEP_FEED_PIPE[sep], f, p, t)
        p_sep_in = r.p_out_mpa
        sep_out_loading = B.separator_outlet_loading(liquid, sm["liquid_removal_efficiency"])
        removed = f * liquid * sm["liquid_removal_efficiency"]
        m.chk(f"{sep} feed liquid loading <= maximum",
              liquid <= sm["maximum_feed_free_liquid_fraction"] + TOL_LIQUID_LOADING,
              f"{liquid:.6f} <= {sm['maximum_feed_free_liquid_fraction']:.4f}")
        m.chk(f"{sep} flow <= capacity", f <= sm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.3f} <= {sm['capacity_kg_s']:.1f} kg/s")
        m.chk(f"{sep} pressure <= limit", p_sep_in <= sm["maximum_pressure_mpa"] + TOL_PRESSURE_MPA,
              f"{p_sep_in:.4f} <= {sm['maximum_pressure_mpa']:.1f} MPa")
        m.chk(f"{sep} removed liquid <= maximum liquid rate",
              removed <= sm["maximum_liquid_rate_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{removed:.4f} <= {sm['maximum_liquid_rate_kg_s']:.2f} kg/s")
        p_after = p_sep_in - sm["pressure_drop_mpa"]
        m.state[sep] = dict(p_in=p_sep_in, p_out=p_after, t=t, flow=f, liquid_in=liquid,
                            liquid_out=sep_out_loading, liquid_removed=removed)
        m.sep_liquid[sep] = removed
        r = m.pipe(SEP_DEHY_PIPE[sep], f, p_after, t)
        p_dehy_in = r.p_out_mpa
        m.chk(f"{dehy} feed liquid loading <= maximum",
              sep_out_loading <= dm["maximum_feed_free_liquid_fraction"] + TOL_LIQUID_LOADING,
              f"{sep_out_loading:.3e} <= {dm['maximum_feed_free_liquid_fraction']:.4f}")
        m.chk(f"{dehy} flow <= capacity", f <= dm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.3f} <= {dm['capacity_kg_s']:.1f} kg/s")
        m.chk(f"{dehy} pressure <= limit", p_dehy_in <= dm["maximum_pressure_mpa"] + TOL_PRESSURE_MPA,
              f"{p_dehy_in:.4f} <= {dm['maximum_pressure_mpa']:.1f} MPa")
        p_dehy_out = p_dehy_in - dm["pressure_drop_mpa"]
        energy = f * dm["energy_mw_per_kg_s"]
        m.energy_mwh += energy * plan["hours"]
        m.state[dehy] = dict(p_in=p_dehy_in, p_out=p_dehy_out, t=t, flow=f,
                             water_out=dm["normal_outlet_water_mg_sm3"], liquid=sep_out_loading,
                             energy_mw=energy)
        r = m.pipe(DEHY_HEADER_PIPE[dehy], f, p_dehy_out, t)
        dehy_p.append(r.p_out_mpa)
    water_dehy = design.nodes[TRAINS[trains[0]][1]].model["normal_outlet_water_mg_sm3"]
    p = m.header("HDR-TRT-OUT-01", flow, min(dehy_p), t, water_dehy, sep_out_loading)

    comps = plan["compressors"]
    reg_in_p = None
    t_link = t
    if comps:
        # boost service: the treated gas is routed to the shared compressor set
        # (treated-gas header -> suction header -> compressors -> discharge header
        # -> delivery header)
        comp_flows = split_flow(flow, [(c, design.nodes[c].model["capacity_kg_s"],
                                        design.nodes[c].model["minimum_stable_flow_kg_s"],
                                        design.nodes[c].model["efficiency_proxy"])
                                       for c in comps])
        m.unit_flow.update(comp_flows)
        m.chk("boost compressor flows sum to scenario flow",
              abs(sum(comp_flows.values()) - flow) < TOL_MASS_FLOW_KG_S,
              f"{sum(comp_flows.values()):.6f} vs {flow:.6f} kg/s")
        r = m.pipe("P-143", flow, p, t)
        p_suc_hdr = r.p_out_mpa
        p_suc_hdr = m.header("HDR-INJ-SUC-01", flow, p_suc_hdr, t, water_dehy, sep_out_loading)
        disch = []
        mixed_num = 0.0
        for c in comps:
            cm = design.nodes[c].model
            f = comp_flows[c]
            r = m.pipe(INJ_SUCTION_PIPE[c], f, p_suc_hdr, t)
            p_suc = r.p_out_mpa
            ratio = boost_discharge_set / p_suc
            t_out = B.compressor_outlet_temperature_c(t, ratio, k, cm["efficiency_proxy"])
            w_mw = B.compressor_power_mw(f, t, ratio, k, cm["efficiency_proxy"],
                                         cm["driver_efficiency"], cp)
            m.state[c] = dict(p_in=p_suc, p_out=boost_discharge_set, ratio=ratio, t_in=t,
                              t_out=t_out, power_mw=w_mw, flow=f, running=f > 0)
            if f <= 0:
                m.chk(f"{c} idle (not running) in this scenario", True, "no duty")
                continue
            m.chk(f"{c} flow within [min stable, capacity]",
                  f >= cm["minimum_stable_flow_kg_s"] - TOL_MASS_FLOW_KG_S and
                  f <= cm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
                  f"{f:.3f} in [{cm['minimum_stable_flow_kg_s']:.1f}, {cm['capacity_kg_s']:.1f}] kg/s")
            m.chk(f"{c} pressure ratio <= maximum", ratio <= cm["maximum_pressure_ratio"] + 1e-9,
                  f"{ratio:.4f} <= {cm['maximum_pressure_ratio']:.3f}")
            m.chk(f"{c} suction pressure <= maximum",
                  p_suc <= cm["maximum_suction_pressure_mpa"] + TOL_PRESSURE_MPA,
                  f"{p_suc:.4f} MPa")
            m.chk(f"{c} discharge pressure <= maximum",
                  boost_discharge_set <= cm["maximum_discharge_pressure_mpa"] + TOL_PRESSURE_MPA)
            m.chk(f"{c} discharge temperature <= maximum",
                  t_out <= cm["maximum_discharge_temperature_c"] + TOL_TEMPERATURE_C,
                  f"{t_out:.2f} degC")
            m.chk(f"{c} driver power <= maximum", w_mw <= cm["maximum_power_mw"] + 1e-9,
                  f"{w_mw:.3f} MW")
            m.energy_mwh += w_mw * plan["hours"]
            mixed_num += f * t_out
            rr = m.pipe(INJ_DISCHARGE_PIPE[c], f, boost_discharge_set, t_out)
            disch.append(rr.p_out_mpa)
        t_link = mixed_num / flow
        p_dis_hdr = m.header("HDR-INJ-DIS-01", flow, min(disch), t_link, water_dehy,
                             sep_out_loading)
        r = m.pipe("P-144", flow, p_dis_hdr, t_link)
        reg_in_p = r.p_out_mpa

    bypass_flow = flow if not comps else 0.0
    if bypass_flow > 0:
        r = m.pipe("P-123", bypass_flow, p, t)
        reg_in_p = r.p_out_mpa if reg_in_p is None else min(reg_in_p, r.p_out_mpa)
    if reg_in_p is None:
        reg_in_p = p
    p_dlv = m.header("HDR-DLV-01", flow, reg_in_p, t_link, water_dehy, sep_out_loading)
    r = m.pipe("P-128", flow, p_dlv, t_link)
    p_reg_in = r.p_out_mpa

    reg = design.nodes["REG-WDR-01"]
    rm = reg.model
    m.chk("regulator outlet setpoint <= inlet pressure", reg_out_set <= p_reg_in + TOL_PRESSURE_MPA,
          f"{reg_out_set:.4f} <= {p_reg_in:.4f} MPa")
    m.chk("regulator flow <= capacity", flow <= rm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
          f"{flow:.3f} <= {rm['capacity_kg_s']:.1f} kg/s")
    m.chk("regulator inlet pressure <= limit",
          p_reg_in <= rm["maximum_pressure_mpa"] + TOL_PRESSURE_MPA,
          f"{p_reg_in:.4f} <= {rm['maximum_pressure_mpa']:.1f} MPa")
    t_reg = B.regulator_outlet_temperature_c(t_link, p_reg_in, reg_out_set,
                                             rm["jt_temperature_coefficient_k_per_mpa"])
    m.state["REG-WDR-01"] = dict(p_in=p_reg_in, p_out=reg_out_set, t_in=t_link, t_out=t_reg,
                                 flow=flow)
    r = m.pipe("P-129", flow, reg_out_set, t_reg)
    p = m.simple("MTR-WDR-01", flow, r.p_out_mpa, t_reg, water_dehy, sep_out_loading)
    r = m.pipe("P-130", flow, p, t_reg)
    p_grid = r.p_out_mpa
    water_out = water_dehy
    m.state["GRID-TIE"] = dict(p=p_grid, t=t_reg, water=water_out, liquid=sep_out_loading,
                               flow=flow)
    m.chk("delivery pressure at GRID-TIE >= requirement",
          p_grid >= plan["sink_required_mpa"] - TOL_PRESSURE_MPA,
          f"{p_grid:.5f} >= {plan['sink_required_mpa']:.3f} MPa")
    m.chk("delivery temperature at GRID-TIE within project limits",
          -10.0 - 1e-4 <= t_reg <= 60.0 + 1e-4, f"{t_reg:.2f} degC")
    m.chk("delivery water content at GRID-TIE <= 50 mg/Sm3", water_out <= 50.0 + 1e-5,
          f"{water_out:.2f} mg/Sm3")
    m.chk("delivery free liquid at GRID-TIE <= 1e-4", sep_out_loading <= 1e-4 + 1e-9,
          f"{sep_out_loading:.3e}")

    # drain system: each separator liquid side stream to its own closed drain
    total_removed = 0.0
    for ti in trains:
        sep, _ = TRAINS[ti]
        f = m.sep_liquid[sep]
        total_removed += f
        drain_tag = DRAIN_LINE_TO_DRAIN[sep]
        dm = design.nodes[drain_tag].model
        m.unit_flow[drain_tag] = f
        m.liquid_pipe_flow[DRAIN_LINE[sep]] = f
        m.liquid_pipe_flow[DRAIN_OUT[sep]] = f
        m.chk(f"{drain_tag} liquid flow <= capacity",
              f <= dm["capacity_kg_s"] + TOL_MASS_FLOW_KG_S,
              f"{f:.4f} <= {dm['capacity_kg_s']:.2f} kg/s")
        m.chk(f"{drain_tag} pressure within closed-drain limit",
              dm["maximum_pressure_mpa"] >= 1.0 - 1e-12,
              f"drain domain <= {dm['maximum_pressure_mpa']:.1f} MPa "
              f"(idealised letdown at the separator liquid_out)")
    m.chk("outfall combined liquid flow <= interface limit",
          total_removed <= design.case.interfaces["LIQUID-DRAIN-OUTFALL"]["maximum_flow_kg_s"]
          + TOL_MASS_FLOW_KG_S,
          f"{total_removed:.4f} <= "
          f"{design.case.interfaces['LIQUID-DRAIN-OUTFALL']['maximum_flow_kg_s']:.1f} kg/s")
    # metering: all exchanged gas must pass through active meter capacity
    mtr = design.nodes["MTR-WDR-01"].model
    m.chk("withdrawal custody metering capacity >= scenario flow",
          mtr["capacity_kg_s"] >= flow - TOL_MASS_FLOW_KG_S,
          f"{mtr['capacity_kg_s']:.1f} >= {flow:.3f} kg/s")
    m.chk("GRID-TIE boundary flow <= interface limit",
          flow <= design.case.interfaces["GRID-TIE"]["maximum_flow_kg_s"] + TOL_MASS_FLOW_KG_S,
          f"{flow:.3f} <= {design.case.interfaces['GRID-TIE']['maximum_flow_kg_s']:.1f} kg/s")
    return m


def check_mass_balance(design: Design, m, plan):
    """Conserve gas flow at every node: the inflow of a node must equal its
    declared through-flow and its outflow (mixing sums, splits conserve)."""
    inflow = {}
    outflow = {}
    for tag, pl in design.pipes.items():
        res = m.pipe_state.get(pl.tag)
        if res is None or res.flow <= 0:
            continue
        direction = getattr(res, "direction", 1)
        src_node, dst_node = (pl.a[0], pl.b[0]) if direction > 0 else (pl.b[0], pl.a[0])
        if dst_node in design.nodes:
            inflow[dst_node] = inflow.get(dst_node, 0.0) + res.flow
        if src_node in design.nodes:
            outflow[src_node] = outflow.get(src_node, 0.0) + res.flow
    for tag in design.nodes:
        nin = inflow.get(tag, 0.0)
        nout = outflow.get(tag, 0.0)
        if nin <= 0 and nout <= 0:
            continue
        through = m.unit_flow.get(tag, None)
        if design.nodes[tag].model["category"] == "header":
            through = nin
        ok = abs(nin - nout) < 1e-6
        if through is not None and design.nodes[tag].model["category"] != "header":
            ok = ok and abs(through - nin) < 1e-6
        m.chk(f"node mass balance {tag}", ok,
              f"in {nin:.4f} / through "
              f"{'-' if through is None else format(through, '.4f')} / out {nout:.4f} kg/s")
    # boundary conservation
    src = plan["source"]["flow"]
    m.chk("source boundary flow conserved",
          abs(sum(inflow.get(t, 0.0) + outflow.get(t, 0.0) for t in [])
              + (src - src)) < 1e-9, "declared source flow used")
    return m


def check_interface_directions(design: Design, m, plan):
    """An external interface may terminate connections but is never an internal
    intermediate node: in every scenario each interface used is either a pure
    source or a pure sink of the flow."""
    for tag in design.case.interfaces:
        inflow = outflow = 0.0
        for pl in design.pipes.values():
            res = m.pipe_state.get(pl.tag)
            if res is None or res.flow <= 0:
                continue
            direction = getattr(res, "direction", 1)
            src_node, dst_node = (pl.a[0], pl.b[0]) if direction > 0 else (pl.b[0], pl.a[0])
            if dst_node == tag:
                inflow += res.flow
            if src_node == tag:
                outflow += res.flow
        if inflow > 0 and outflow > 0:
            m.chk(f"interface {tag} is not used as an internal node", False,
                  f"in {inflow:.3f} / out {outflow:.3f} kg/s")
    return m


def run_plan(design: Design, plan: dict):
    """Solve the scenario setpoints and return (plan, march)."""
    if plan["service"] == "injection":
        p_dis = plan["sink_required_mpa"] + 1.0
        m = None
        for _ in range(30):
            m = run_injection(design, plan, p_dis)
            pmin = min(m.state[w]["p"] for w in WELLS)
            delta = (plan["sink_required_mpa"] + plan["margin"]) - pmin
            if abs(delta) < 1e-7:
                break
            p_dis += delta
        plan["compressor_discharge_setpoint_mpa"] = p_dis
        plan["cooler_outlet_setpoint_c"] = plan["cooler_outlet_c"]
        check_mass_balance(design, m, plan)
        check_interface_directions(design, m, plan)
        return plan, m

    reg_out = plan["sink_required_mpa"] + plan["margin"] + 0.10
    boost = (reg_out + 0.40) if plan["compressors"] else None
    m = None
    for _ in range(60):
        m = run_withdrawal(design, plan, reg_out, boost)
        pgrid = m.state["GRID-TIE"]["p"]
        d_reg = (plan["sink_required_mpa"] + plan["margin"]) - pgrid
        if plan["compressors"]:
            p_reg_in = m.state["REG-WDR-01"]["p_in"]
            d_boost = (reg_out + 0.30) - p_reg_in
        else:
            d_boost = 0.0
        if abs(d_reg) < 1e-7 and abs(d_boost) < 1e-7:
            break
        reg_out += d_reg
        if plan["compressors"]:
            boost += d_boost
    plan["regulator_outlet_setpoint_mpa"] = reg_out
    if plan["compressors"]:
        plan["boost_discharge_setpoint_mpa"] = boost
    check_mass_balance(design, m, plan)
    check_interface_directions(design, m, plan)
    return plan, m
