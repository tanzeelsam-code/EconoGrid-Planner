"""
Emissions Engine — CO₂ Accounting for Energy Scenarios.

Calculates greenhouse gas emissions from energy consumption
using standard emission factors (IPCC-based). Supports both
demand-side and supply/transformation-side emissions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from .scenario_engine import ScenarioResult


class EmissionsEngine:
    """
    CO₂ emissions calculator for energy scenarios.

    Computes emissions from:
    1. Direct combustion in demand sectors (non-electricity fuels)
    2. Power generation in the transformation sector

    Emission factors are in kg CO₂ per GJ.
    Output is in Mt CO₂ (million tonnes).
    """

    # Conversion: PJ × (kg CO₂/GJ) = Mt CO₂ × 1e6 → factor = 1e-3
    PJ_TO_MT_FACTOR = 1e-3  # PJ * (kg/GJ) * 1e-3 = kt; /1e3 = Mt

    def __init__(self, emission_factors: Dict[str, float]):
        """
        Initialize with emission factors.

        Args:
            emission_factors: Dict of {fuel: kg_CO2_per_GJ}.
        """
        self.emission_factors = emission_factors

    def calculate_demand_emissions(
        self,
        scenario_result: ScenarioResult
    ) -> pd.DataFrame:
        """
        Calculate demand-side emissions by fuel and year.

        Excludes electricity (accounted in transformation sector).

        Args:
            scenario_result: Completed ScenarioResult.

        Returns:
            DataFrame with Year index and fuel columns (Mt CO₂).
        """
        fuel_demand = scenario_result.demand_by_fuel_by_year.copy()

        emissions_data = {}
        for fuel in fuel_demand.columns:
            ef = self.emission_factors.get(fuel, 0.0)
            # PJ × (kg CO₂/GJ) = Gt CO₂ × 1e6... we need Mt
            # 1 PJ = 1e6 GJ → emissions = PJ × 1e6 GJ/PJ × ef kg/GJ = ef × 1e6 kg = ef × 1e3 t = ef × 1 kt
            # So: PJ × ef × 1e-3 = Mt CO₂
            emissions_data[fuel] = fuel_demand[fuel] * ef * self.PJ_TO_MT_FACTOR

        emissions_df = pd.DataFrame(emissions_data)
        emissions_df["Total"] = emissions_df.sum(axis=1)
        emissions_df.index.name = "Year"

        return emissions_df.round(4)

    def calculate_supply_emissions(
        self,
        scenario_result: ScenarioResult,
        generation_mix: Dict[str, float],
        generation_emission_factors: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        Calculate supply-side (power generation) emissions.

        Args:
            scenario_result: Completed ScenarioResult.
            generation_mix: Dict of {source: share} for generation.
            generation_emission_factors: Emission factors for generation fuels.

        Returns:
            DataFrame with Year index and generation source columns (Mt CO₂).
        """
        if generation_emission_factors is None:
            generation_emission_factors = {
                "Coal": 94.6,
                "Natural Gas": 56.1,
                "Oil Products": 73.3,
                "Hydro": 0.0,
                "Solar": 0.0,
                "Wind": 0.0,
                "Nuclear": 0.0,
            }

        # Total electricity demand by year
        fuel_demand = scenario_result.demand_by_fuel_by_year
        if "Electricity" in fuel_demand.columns:
            elec_demand = fuel_demand["Electricity"]
        else:
            elec_demand = pd.Series(0.0, index=fuel_demand.index)

        emissions_data = {}
        for source, share in generation_mix.items():
            ef = generation_emission_factors.get(source, 0.0)
            # Generation from this source = electricity demand × share / efficiency
            # Assume average efficiency ~0.35 for thermal, 1.0 for renewables
            if ef > 0:
                efficiency = 0.35  # Thermal generation efficiency
            else:
                efficiency = 1.0

            generation_pj = elec_demand * share / efficiency
            emissions_data[source] = generation_pj * ef * self.PJ_TO_MT_FACTOR

        supply_emissions = pd.DataFrame(emissions_data)
        supply_emissions["Total Supply"] = supply_emissions.sum(axis=1)
        supply_emissions.index.name = "Year"

        return supply_emissions.round(4)

    def get_total_emissions(
        self,
        demand_emissions: pd.DataFrame,
        supply_emissions: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Combine demand and supply emissions into total emissions table.

        Args:
            demand_emissions: From calculate_demand_emissions().
            supply_emissions: From calculate_supply_emissions().

        Returns:
            DataFrame with demand total, supply total, and grand total.
        """
        total = pd.DataFrame({
            "Demand-Side Emissions (Mt CO₂)": demand_emissions["Total"],
            "Supply-Side Emissions (Mt CO₂)": supply_emissions["Total Supply"],
        })
        total["Total Emissions (Mt CO₂)"] = total.sum(axis=1)
        total.index.name = "Year"

        return total.round(4)

    def compare_scenario_emissions(
        self,
        scenario_emissions: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Compare total emissions across scenarios.

        Args:
            scenario_emissions: Dict of {scenario_name: total_emissions_df}.

        Returns:
            DataFrame with Year index and one column per scenario.
        """
        comparison = pd.DataFrame()
        for name, emissions_df in scenario_emissions.items():
            comparison[name] = emissions_df["Total Emissions (Mt CO₂)"]

        comparison.index.name = "Year"
        return comparison.round(4)
