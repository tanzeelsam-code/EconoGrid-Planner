"""
Renewable Energy Target Tracking & Technology Cost Learning Curves.

Tracks progress toward RE targets and models technology cost
trajectories using Wright's Law learning curves.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# IRENA-inspired learning rate parameters
TECH_PARAMS = {
    "Solar PV":       {"base_cost": 1100, "lr": 0.20, "floor": 200,  "cf": 0.20},
    "Onshore Wind":   {"base_cost": 1400, "lr": 0.12, "floor": 700,  "cf": 0.30},
    "Offshore Wind":  {"base_cost": 3200, "lr": 0.15, "floor": 1200, "cf": 0.38},
    "Battery Storage":{"base_cost": 280,  "lr": 0.18, "floor": 60,   "cf": 0.90},
    "Geothermal":     {"base_cost": 3500, "lr": 0.05, "floor": 2500, "cf": 0.80},
    "Hydropower":     {"base_cost": 1800, "lr": 0.03, "floor": 1500, "cf": 0.45},
}

DEFAULT_TARGETS = {
    "BAU":         {"2030": 25.0, "2050": 40.0},
    "Low Carbon":  {"2030": 45.0, "2050": 80.0},
    "High Growth": {"2030": 35.0, "2050": 60.0},
}


@dataclass
class TechCostProjection:
    technology: str
    base_year: int
    projection_years: List[int]
    costs: List[float]
    lcoe_trend: List[float]


@dataclass
class RenewableTargetResult:
    scenario: str
    base_year: int
    target_year: int
    target_pct: float
    annual_share_table: pd.DataFrame
    tech_cost_projections: Dict[str, TechCostProjection]
    on_track: bool
    gap_at_target: float
    cumulative_investment_musd: float
    avoided_emissions_mt: float
    policy_gap_analysis: Dict


class RenewableTargetTracker:
    """
    Tracks RE deployment and models technology cost learning curves.
    """

    def __init__(self, base_year: int = 2022, baseline_re_share_pct: float = 18.0,
                 total_capacity_gw: float = 5.0, annual_demand_twh: float = 50.0):
        self.base_year = base_year
        self.baseline_re = baseline_re_share_pct
        self.total_cap_gw = total_capacity_gw
        self.demand_twh = annual_demand_twh

    def _learning_cost(self, tech: str, cum_gw: float) -> float:
        p = TECH_PARAMS.get(tech, {})
        if not p:
            return 1000.0
        doublings = np.log2(max(cum_gw, 0.1) / 1.0)
        return max(p["base_cost"] * (1 - p["lr"]) ** doublings, p["floor"])

    def _lcoe(self, capex_kw: float, cf: float, dr: float = 0.08, life: int = 25) -> float:
        if cf <= 0:
            return 999.0
        crf = dr * (1 + dr) ** life / ((1 + dr) ** life - 1)
        return (capex_kw * 1000 * (crf + 0.015)) / (cf * 8760)  # $/MWh

    def project_tech_costs(self, technology: str, horizon: int = 30,
                           annual_deploy_gw: float = 0.3) -> TechCostProjection:
        years, costs, lcoes = [], [], []
        cum = max(annual_deploy_gw, 0.1)
        cf = TECH_PARAMS.get(technology, {}).get("cf", 0.25)
        for i in range(horizon):
            yr = self.base_year + i
            c = self._learning_cost(technology, cum)
            costs.append(round(c, 1))
            lcoes.append(round(self._lcoe(c, cf), 2))
            years.append(yr)
            cum += annual_deploy_gw
        return TechCostProjection(technology, self.base_year, years, costs, lcoes)

    def track_targets(self, scenario: str, target_year: int = 2050,
                      custom_target_pct: Optional[float] = None,
                      demand_growth_rate: float = 0.03) -> RenewableTargetResult:
        tgt_map = DEFAULT_TARGETS.get(scenario, DEFAULT_TARGETS["BAU"])
        target_pct = custom_target_pct or tgt_map.get(str(target_year), 40.0)
        horizon = target_year - self.base_year + 1
        years = list(range(self.base_year, target_year + 1))
        re_shares = np.linspace(self.baseline_re, target_pct, horizon)
        demands = [self.demand_twh * (1 + demand_growth_rate) ** i for i in range(horizon)]
        avg_cf = 0.25
        re_cap = [(re_shares[i] / 100 * demands[i] * 1e6) / (avg_cf * 8760) for i in range(horizon)]
        additions = [max(0, re_cap[i] - re_cap[i - 1]) if i > 0 else 0 for i in range(horizon)]
        investments = [additions[i] * 1e3 * 1200 * (0.98 ** i) / 1e6 for i in range(horizon)]
        table = pd.DataFrame({
            "Year": years,
            "Renewable_Share_Pct": np.round(re_shares, 2),
            "RE_Capacity_GW": np.round(re_cap, 3),
            "New_Additions_GW": np.round(additions, 3),
            "Annual_Investment_MUSD": np.round(investments, 1),
            "Total_Demand_TWh": np.round(demands, 2),
        })
        cum_inv = float(table["Annual_Investment_MUSD"].sum())
        avoided = sum(re_shares[i] / 100 * demands[i] for i in range(horizon)) * 820 / 1e9 * 1e12 / 1e9
        on_track = float(re_shares[-1]) >= target_pct * 0.95
        gap = float(re_shares[-1]) - target_pct
        depl = 0.3 if scenario == "Low Carbon" else 0.15
        tech_costs = {t: self.project_tech_costs(t, min(horizon, 30), depl)
                      for t in ["Solar PV", "Onshore Wind", "Battery Storage"]}
        return RenewableTargetResult(
            scenario=scenario, base_year=self.base_year,
            target_year=target_year, target_pct=target_pct,
            annual_share_table=table, tech_cost_projections=tech_costs,
            on_track=on_track, gap_at_target=gap,
            cumulative_investment_musd=cum_inv, avoided_emissions_mt=avoided,
            policy_gap_analysis={
                "target_pct": target_pct,
                "projected_pct": round(float(re_shares[-1]), 2),
                "gap_pct": round(gap, 2),
                "on_track": on_track,
            },
        )

    def compare_scenarios(self, target_year: int = 2050) -> pd.DataFrame:
        rows = []
        for s in ["BAU", "Low Carbon", "High Growth"]:
            r = self.track_targets(s, target_year)
            rows.append({
                "Scenario": s,
                "Target_%": r.target_pct,
                "Projected_%": r.policy_gap_analysis["projected_pct"],
                "On_Track": r.on_track,
                "Gap_%": round(r.gap_at_target, 2),
                "Investment_BUSD": round(r.cumulative_investment_musd / 1000, 2),
                "Avoided_Emissions_Mt": round(r.avoided_emissions_mt, 1),
            })
        return pd.DataFrame(rows)
