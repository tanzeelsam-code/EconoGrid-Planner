"""
Supply & Transformation — Power Generation Mix Modeling.

Models the supply side of the energy system including:
- Generation capacity by source
- Generation mix evolution over time
- Transformation efficiency and losses
- Supply-side scenario comparisons
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional


class SupplyTransformation:
    """
    Supply-side energy transformation model.

    Models the power generation mix, transformation efficiency,
    and transmission/distribution losses.
    """

    def __init__(self, supply_config: Dict[str, Any]):
        """
        Initialize with supply configuration.

        Args:
            supply_config: Dict with generation_mix_base_year,
                          transformation_efficiency, transmission_losses.
        """
        self.base_mix = supply_config.get("generation_mix_base_year", {})
        self.efficiency = supply_config.get("transformation_efficiency", 0.35)
        self.losses = supply_config.get("transmission_losses", 0.08)

    def project_generation_mix(
        self,
        years: int,
        scenario: str = "BAU",
        renewable_growth: float = 0.02,
        coal_reduction: float = 0.01
    ) -> pd.DataFrame:
        """
        Project the generation mix evolution over time.

        Args:
            years: Number of years to project.
            scenario: Scenario name for labeling.
            renewable_growth: Annual increase in renewables share.
            coal_reduction: Annual decrease in coal share.

        Returns:
            DataFrame with Year index and source columns (shares).
        """
        mix_data = []
        current_mix = dict(self.base_mix)

        # Categorize sources
        renewables = ["Solar", "Wind", "Hydro"]
        fossil = ["Coal", "Natural Gas", "Oil Products"]

        for t in range(years + 1):
            row = {"Year_Offset": t}
            row.update(current_mix)
            mix_data.append(row)

            if t < years:
                # Reduce coal
                coal_shift = min(coal_reduction, current_mix.get("Coal", 0))
                current_mix["Coal"] = max(0, current_mix.get("Coal", 0) - coal_shift)

                # Increase renewables proportionally
                ren_total = sum(current_mix.get(r, 0) for r in renewables)
                for r in renewables:
                    if ren_total > 0:
                        share = current_mix.get(r, 0) / ren_total
                    else:
                        share = 1.0 / len(renewables)
                    current_mix[r] = current_mix.get(r, 0) + coal_shift * share

                # Also add small growth to renewables from gas
                gas_shift = min(renewable_growth * 0.3, current_mix.get("Natural Gas", 0))
                current_mix["Natural Gas"] = max(
                    0, current_mix.get("Natural Gas", 0) - gas_shift
                )
                for r in renewables:
                    if ren_total > 0:
                        share = current_mix.get(r, 0) / max(ren_total, 0.01)
                    else:
                        share = 1.0 / len(renewables)
                    current_mix[r] = current_mix.get(r, 0) + gas_shift * share

                # Normalize
                total = sum(current_mix.values())
                if total > 0:
                    current_mix = {k: v / total for k, v in current_mix.items()}

        df = pd.DataFrame(mix_data)
        df = df.set_index("Year_Offset")
        return df.round(4)

    def calculate_generation_requirements(
        self,
        electricity_demand_pj: pd.Series,
    ) -> pd.DataFrame:
        """
        Calculate total generation requirements accounting for
        transformation efficiency and transmission losses.

        Args:
            electricity_demand_pj: Series of electricity demand by year (PJ).

        Returns:
            DataFrame with demand, gross generation, and losses.
        """
        gross_generation = electricity_demand_pj / (1 - self.losses)
        primary_energy = gross_generation / self.efficiency
        losses_pj = gross_generation - electricity_demand_pj

        df = pd.DataFrame({
            "Electricity Demand (PJ)": electricity_demand_pj,
            "Gross Generation (PJ)": gross_generation,
            "T&D Losses (PJ)": losses_pj,
            "Primary Energy Input (PJ)": primary_energy,
            "Efficiency (%)": self.efficiency * 100,
            "Loss Rate (%)": self.losses * 100,
        })

        return df.round(2)

    def get_generation_by_source(
        self,
        gross_generation: pd.Series,
        mix_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute generation by source in absolute terms (PJ).

        Args:
            gross_generation: Total gross generation by year.
            mix_df: Generation mix shares by year.

        Returns:
            DataFrame of generation by source in PJ.
        """
        result = pd.DataFrame(index=mix_df.index)
        for col in mix_df.columns:
            # Align indices
            gen_values = gross_generation.values[:len(mix_df)]
            result[col] = mix_df[col].values * gen_values

        result.index.name = "Year_Offset"
        return result.round(2)
