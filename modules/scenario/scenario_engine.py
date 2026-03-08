"""
Scenario Engine — Multi-Scenario Energy Demand Projections.

Runs the LEAP model under multiple scenarios (BAU, Low Carbon,
High Growth, etc.) and produces comparative demand projection
tables and charts.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .leap_model import LEAPModel, SectorData, EnergyBalance


@dataclass
class ScenarioResult:
    """Container for a single scenario's projection results."""
    name: str
    description: str
    years: List[int]

    # Annual demand totals
    total_demand_by_year: pd.Series          # Year -> total PJ
    demand_by_sector_by_year: pd.DataFrame   # Year × Sector
    demand_by_fuel_by_year: pd.DataFrame     # Year × Fuel

    # Detailed sector-fuel matrices per year (select years)
    energy_balances: Dict[int, EnergyBalance]

    # Growth metrics
    cumulative_demand: float
    avg_annual_growth_rate: float


class ScenarioEngine:
    """
    Multi-scenario energy demand projection engine.

    Takes a LEAPModel and runs it under each defined scenario,
    producing comparative tables and visualizable data.
    """

    def __init__(self, leap_model: LEAPModel):
        """
        Initialize with a configured LEAP model.

        Args:
            leap_model: Initialized LEAPModel instance.
        """
        self.model = leap_model
        self.results: Dict[str, ScenarioResult] = {}

    def run_scenario(self, scenario_name: str) -> ScenarioResult:
        """
        Run a single scenario projection.

        Args:
            scenario_name: Name of the scenario (must exist in model config).

        Returns:
            ScenarioResult with full projection data.

        Raises:
            ValueError: If scenario not found.
        """
        scenarios = self.model.config.get("scenarios", {})
        if scenario_name not in scenarios:
            raise ValueError(
                f"Scenario '{scenario_name}' not found. "
                f"Available: {list(scenarios.keys())}"
            )

        scenario_cfg = scenarios[scenario_name]
        horizon = self.model.projection_horizon
        base_year = self.model.base_year
        years = list(range(base_year, base_year + horizon + 1))

        # ── Project each sector ────────────────────────────────────────────
        sector_projections: Dict[str, List[SectorData]] = {}

        for sector_name, base_sector in self.model.base_sectors.items():
            activity_growth = scenario_cfg["activity_growth"].get(sector_name, 0.02)
            intensity_change = scenario_cfg["intensity_change"].get(sector_name, -0.005)
            fuel_switching = scenario_cfg.get("fuel_switching", {}).get(sector_name)

            projected = self.model.project_sector(
                sector=base_sector,
                years_forward=horizon,
                activity_growth=activity_growth,
                intensity_change=intensity_change,
                fuel_switching=fuel_switching,
            )
            sector_projections[sector_name] = projected

        # ── Build annual energy balances ───────────────────────────────────
        energy_balances: Dict[int, EnergyBalance] = {}

        # Base year
        energy_balances[base_year] = self.model.base_balance

        # Projected years
        for t in range(horizon):
            year = base_year + t + 1
            year_sectors = {}
            for sector_name, projections in sector_projections.items():
                year_sectors[sector_name] = projections[t]

            balance = EnergyBalance(year=year, sectors=year_sectors)
            balance.compute()
            energy_balances[year] = balance

        # ── Build summary tables ───────────────────────────────────────────
        demand_by_sector_data = {}
        demand_by_fuel_data = {}
        total_demand = {}

        for year in years:
            balance = energy_balances[year]
            total_demand[year] = balance.total_demand
            demand_by_sector_data[year] = balance.demand_by_sector
            demand_by_fuel_data[year] = balance.demand_by_fuel

        total_series = pd.Series(total_demand, name="Total Demand (PJ)")
        sector_df = pd.DataFrame(demand_by_sector_data).T
        sector_df.index.name = "Year"
        fuel_df = pd.DataFrame(demand_by_fuel_data).T.fillna(0.0)
        fuel_df.index.name = "Year"

        # Growth metrics
        cumulative = total_series.sum()
        if len(total_series) > 1:
            first_val = total_series.iloc[0]
            last_val = total_series.iloc[-1]
            n_years = len(total_series) - 1
            if first_val > 0:
                avg_growth = (last_val / first_val) ** (1 / n_years) - 1
            else:
                avg_growth = 0.0
        else:
            avg_growth = 0.0

        result = ScenarioResult(
            name=scenario_name,
            description=scenario_cfg.get("description", ""),
            years=years,
            total_demand_by_year=total_series,
            demand_by_sector_by_year=sector_df,
            demand_by_fuel_by_year=fuel_df,
            energy_balances=energy_balances,
            cumulative_demand=cumulative,
            avg_annual_growth_rate=avg_growth,
        )

        self.results[scenario_name] = result
        return result

    def run_all_scenarios(self) -> Dict[str, ScenarioResult]:
        """
        Run all defined scenarios.

        Returns:
            Dictionary of {scenario_name: ScenarioResult}.
        """
        for name in self.model.get_scenario_names():
            self.run_scenario(name)
        return self.results

    def get_comparison_table(self) -> pd.DataFrame:
        """
        Build a scenario comparison table of total demand by year.

        Returns:
            DataFrame with Year index and one column per scenario.
        """
        if not self.results:
            raise ValueError("No scenarios have been run yet.")

        comparison = pd.DataFrame()
        for name, result in self.results.items():
            comparison[name] = result.total_demand_by_year

        comparison.index.name = "Year"
        return comparison.round(2)

    def get_scenario_summary(self) -> pd.DataFrame:
        """
        High-level summary metrics for each scenario.

        Returns:
            DataFrame with scenario names as index.
        """
        rows = []
        for name, result in self.results.items():
            rows.append({
                "Scenario": name,
                "Description": result.description,
                "Base Year Demand (PJ)": round(result.total_demand_by_year.iloc[0], 2),
                "Final Year Demand (PJ)": round(result.total_demand_by_year.iloc[-1], 2),
                "Cumulative Demand (PJ)": round(result.cumulative_demand, 2),
                "Avg. Annual Growth (%)": round(result.avg_annual_growth_rate * 100, 2),
            })
        return pd.DataFrame(rows).set_index("Scenario")
