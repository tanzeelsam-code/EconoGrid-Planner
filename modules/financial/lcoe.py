"""
LCOE Calculator — Levelized Cost of Electricity.

Standalone LCOE computation with detailed cost breakdown.
LCOE = PV(Lifecycle Costs) / PV(Lifecycle Generation)
"""

import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LCOEResult:
    """LCOE calculation result container."""
    lcoe: float                    # USD/MWh
    pv_total_costs: float         # USD
    pv_generation: float          # MWh
    pv_capex: float
    pv_opex: float
    unit: str = "USD/MWh"

    # Breakdown
    lcoe_capex_component: float = 0.0
    lcoe_opex_component: float = 0.0


class LCOECalculator:
    """
    Levelized Cost of Electricity calculator.

    Implements the standard LCOE formula:
    LCOE = Σ(Ct / (1+r)^t) / Σ(Et / (1+r)^t)

    Where:
    - Ct = costs in year t (CAPEX in year 0, OPEX thereafter)
    - Et = electricity generation in year t
    - r = discount rate
    """

    def calculate(
        self,
        capex: float,
        annual_opex: float,
        annual_generation: float,
        project_life: int,
        discount_rate: float,
        inflation_rate: float = 0.02,
        degradation_rate: float = 0.005
    ) -> LCOEResult:
        """
        Calculate LCOE.

        Args:
            capex: Total capital expenditure (USD).
            annual_opex: Base year O&M cost (USD/year).
            annual_generation: Base year electricity output (MWh/year).
            project_life: Project lifetime in years.
            discount_rate: Real discount rate.
            inflation_rate: Annual OPEX escalation.
            degradation_rate: Annual generation degradation.

        Returns:
            LCOEResult with detailed breakdown.
        """
        pv_capex = capex
        pv_opex = 0.0
        pv_generation = 0.0

        for year in range(1, project_life + 1):
            df = (1 + discount_rate) ** year

            # OPEX with inflation
            opex_t = annual_opex * (1 + inflation_rate) ** (year - 1)
            pv_opex += opex_t / df

            # Generation with degradation
            gen_t = annual_generation * (1 - degradation_rate) ** (year - 1)
            pv_generation += gen_t / df

        pv_total = pv_capex + pv_opex
        lcoe = pv_total / pv_generation if pv_generation > 0 else float('inf')

        # Component breakdown
        lcoe_capex = pv_capex / pv_generation if pv_generation > 0 else 0
        lcoe_opex = pv_opex / pv_generation if pv_generation > 0 else 0

        return LCOEResult(
            lcoe=round(lcoe, 2),
            pv_total_costs=round(pv_total, 2),
            pv_generation=round(pv_generation, 2),
            pv_capex=round(pv_capex, 2),
            pv_opex=round(pv_opex, 2),
            lcoe_capex_component=round(lcoe_capex, 2),
            lcoe_opex_component=round(lcoe_opex, 2),
        )

    def compare_technologies(
        self,
        projects: Dict[str, Dict[str, Any]]
    ) -> Dict[str, LCOEResult]:
        """
        Compare LCOE across multiple project configurations.

        Args:
            projects: Dict of {name: {capex, annual_opex, ...}}.

        Returns:
            Dict of {name: LCOEResult}.
        """
        results = {}
        for name, params in projects.items():
            results[name] = self.calculate(**params)
        return results
