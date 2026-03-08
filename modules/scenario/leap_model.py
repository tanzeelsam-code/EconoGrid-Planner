"""
LEAP Model — Energy Balance Framework.

Implements a bottom-up energy accounting model similar to LEAP.
Energy demand is computed as:
    Energy = Activity Level × Energy Intensity

The model supports multiple sectors, fuels, and a base-year
calibration framework that is projected forward using scenario
assumptions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SectorData:
    """Data container for a single sector."""
    name: str
    activity_level: float          # Base year activity level
    activity_unit: str             # e.g., "million households"
    energy_intensity: float        # Energy per unit of activity
    intensity_unit: str            # e.g., "GJ/household"
    fuel_shares: Dict[str, float]  # Fuel name -> share (must sum to ~1.0)

    @property
    def total_energy(self) -> float:
        """Total energy consumption in the base year (PJ)."""
        raw = self.activity_level * self.energy_intensity
        # Convert to PJ if intensity is in GJ or MJ
        if "GJ" in self.intensity_unit:
            return raw / 1000.0  # GJ -> PJ (via million * GJ = PJ)
        elif "MJ" in self.intensity_unit:
            return raw / 1e6  # MJ -> PJ (via million * MJ)
        elif "PJ" in self.intensity_unit:
            return raw
        return raw  # Assume PJ

    def energy_by_fuel(self) -> Dict[str, float]:
        """Energy consumption by fuel type in PJ."""
        total = self.total_energy
        return {fuel: total * share for fuel, share in self.fuel_shares.items()}


@dataclass
class EnergyBalance:
    """Complete energy balance for a given year."""
    year: int
    sectors: Dict[str, SectorData]
    total_demand: float = 0.0
    demand_by_sector: Dict[str, float] = field(default_factory=dict)
    demand_by_fuel: Dict[str, float] = field(default_factory=dict)
    demand_matrix: Optional[pd.DataFrame] = None  # Sector × Fuel

    def compute(self) -> None:
        """Compute the full energy balance."""
        # Demand by sector
        self.demand_by_sector = {
            name: sector.total_energy
            for name, sector in self.sectors.items()
        }
        self.total_demand = sum(self.demand_by_sector.values())

        # Demand by fuel (aggregate across sectors)
        self.demand_by_fuel = {}
        for sector in self.sectors.values():
            for fuel, energy in sector.energy_by_fuel().items():
                self.demand_by_fuel[fuel] = (
                    self.demand_by_fuel.get(fuel, 0.0) + energy
                )

        # Demand matrix (sector × fuel)
        rows = {}
        for name, sector in self.sectors.items():
            rows[name] = sector.energy_by_fuel()
        self.demand_matrix = pd.DataFrame(rows).T.fillna(0.0)
        self.demand_matrix.loc["TOTAL"] = self.demand_matrix.sum()


class LEAPModel:
    """
    LEAP-equivalent energy planning model.

    Implements a bottom-up accounting framework that projects
    energy demand by sector and fuel over a multi-year horizon,
    based on activity growth, intensity changes, and fuel switching
    assumptions.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LEAP model with configuration data.

        Args:
            config: Dictionary with base_year, sectors, scenarios, supply, etc.
                    See data_utils.generate_sample_energy_balance() for schema.
        """
        self.config = config
        self.base_year = config["base_year"]
        self.projection_horizon = config.get("projection_horizon", 30)
        self.emission_factors = config.get("emission_factors_kg_CO2_per_GJ", {})
        self.supply_config = config.get("supply", {})

        # Build base year sectors
        self.base_sectors: Dict[str, SectorData] = {}
        for name, params in config["sectors"].items():
            self.base_sectors[name] = SectorData(
                name=name,
                activity_level=params["activity_level"],
                activity_unit=params["activity_unit"],
                energy_intensity=params["energy_intensity"],
                intensity_unit=params["intensity_unit"],
                fuel_shares=params["fuel_shares"],
            )

        # Compute and store base year balance
        self.base_balance = EnergyBalance(
            year=self.base_year,
            sectors=self.base_sectors,
        )
        self.base_balance.compute()

    def get_base_year_summary(self) -> Dict[str, Any]:
        """Return a summary of the base year energy balance."""
        balance = self.base_balance
        return {
            "year": balance.year,
            "total_demand_pj": round(balance.total_demand, 2),
            "demand_by_sector": {
                k: round(v, 2) for k, v in balance.demand_by_sector.items()
            },
            "demand_by_fuel": {
                k: round(v, 2) for k, v in balance.demand_by_fuel.items()
            },
            "demand_matrix": balance.demand_matrix.round(2),
        }

    def project_sector(
        self,
        sector: SectorData,
        years_forward: int,
        activity_growth: float,
        intensity_change: float,
        fuel_switching: Optional[Dict[str, Any]] = None
    ) -> List[SectorData]:
        """
        Project a sector forward by N years.

        Args:
            sector: Base year sector data.
            years_forward: Number of years to project.
            activity_growth: Annual growth rate of activity level.
            intensity_change: Annual change rate in energy intensity (negative = improvement).
            fuel_switching: Optional dict with "target_fuel" and "shift_per_year".

        Returns:
            List of SectorData objects, one per year.
        """
        projections = []
        current_shares = dict(sector.fuel_shares)

        for t in range(1, years_forward + 1):
            # Project activity and intensity
            new_activity = sector.activity_level * ((1 + activity_growth) ** t)
            new_intensity = sector.energy_intensity * ((1 + intensity_change) ** t)

            # Apply fuel switching if specified
            new_shares = dict(current_shares)
            if fuel_switching:
                target = fuel_switching.get("target_fuel")
                shift = fuel_switching.get("shift_per_year", 0.0)
                if target and target in new_shares:
                    # Shift from all other fuels toward target
                    other_fuels = [f for f in new_shares if f != target]
                    total_shift = min(shift, sum(new_shares[f] for f in other_fuels))

                    for f in other_fuels:
                        proportion = new_shares[f] / sum(
                            new_shares[of] for of in other_fuels
                        ) if sum(new_shares[of] for of in other_fuels) > 0 else 0
                        reduction = total_shift * proportion
                        new_shares[f] = max(0, new_shares[f] - reduction)

                    new_shares[target] = min(1.0, new_shares[target] + total_shift)

                    # Normalize shares
                    total_share = sum(new_shares.values())
                    if total_share > 0:
                        new_shares = {k: v / total_share for k, v in new_shares.items()}

            projected = SectorData(
                name=sector.name,
                activity_level=new_activity,
                activity_unit=sector.activity_unit,
                energy_intensity=new_intensity,
                intensity_unit=sector.intensity_unit,
                fuel_shares=new_shares,
            )
            projections.append(projected)

            # Update current shares for next iteration (cumulative switching)
            current_shares = dict(new_shares)

        return projections

    def get_scenario_names(self) -> List[str]:
        """Return available scenario names."""
        return list(self.config.get("scenarios", {}).keys())
