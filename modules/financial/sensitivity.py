"""
Sensitivity Analyzer — Parameter Sensitivity for Financial Metrics.

Performs one-at-a-time (OAT) sensitivity analysis on key project
parameters, computing impact on LCOE, NPV, and IRR.
Produces sensitivity matrices suitable for tornado charts.
"""

import numpy as np
import pandas as pd
import numpy_financial as npf
from typing import Dict, Any, Optional, List
from copy import deepcopy
from .finance_engine import FinanceEngine


class SensitivityAnalyzer:
    """
    Financial sensitivity analysis engine.

    Performs OAT sensitivity analysis by varying one parameter
    at a time and measuring the impact on key metrics.
    """

    DEFAULT_PARAMETERS = {
        "capex_total_usd": {
            "label": "CAPEX",
            "variations": [-0.20, -0.10, 0.0, 0.10, 0.20],
            "type": "multiplicative"
        },
        "discount_rate": {
            "label": "Discount Rate",
            "variations": [0.05, 0.06, 0.08, 0.10, 0.12],
            "type": "absolute"
        },
        "electricity_price_usd_mwh": {
            "label": "Electricity Price",
            "variations": [45, 55, 65, 75, 85],
            "type": "absolute"
        },
        "capacity_factor": {
            "label": "Capacity Factor",
            "variations": [0.18, 0.20, 0.22, 0.24, 0.26],
            "type": "absolute_with_gen"
        },
        "annual_opex_usd": {
            "label": "Annual OPEX",
            "variations": [-0.20, -0.10, 0.0, 0.10, 0.20],
            "type": "multiplicative"
        },
    }

    def __init__(self, base_project_data: Dict[str, Any]):
        """
        Initialize with base project data.

        Args:
            base_project_data: Original project parameters.
        """
        self.base_data = deepcopy(base_project_data)

    def run_sensitivity(
        self,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Run OAT sensitivity analysis.

        Args:
            parameters: Custom parameter definitions. Uses defaults if None.

        Returns:
            Dict with keys 'lcoe', 'npv', 'irr' — each a DataFrame
            with parameter variations as rows and the metric values.
        """
        if parameters is None:
            parameters = self.DEFAULT_PARAMETERS

        lcoe_results = {}
        npv_results = {}
        irr_results = {}
        eirr_results = {}

        for param_key, param_config in parameters.items():
            label = param_config["label"]
            variations = param_config["variations"]
            var_type = param_config["type"]

            lcoe_row = {}
            npv_row = {}
            irr_row = {}
            eirr_row = {}

            for variation in variations:
                # Create modified project data
                modified_data = deepcopy(self.base_data)

                if var_type == "multiplicative":
                    base_val = modified_data.get(param_key, 0)
                    modified_data[param_key] = base_val * (1 + variation)
                    var_label = f"{variation:+.0%}"
                elif var_type == "absolute":
                    modified_data[param_key] = variation
                    var_label = str(variation)
                elif var_type == "absolute_with_gen":
                    modified_data[param_key] = variation
                    # Recalculate annual generation
                    capacity = modified_data.get("capacity_mw", 50)
                    modified_data["annual_generation_mwh"] = capacity * variation * 8760
                    var_label = str(variation)
                else:
                    modified_data[param_key] = variation
                    var_label = str(variation)

                # Run analysis
                try:
                    engine = FinanceEngine(modified_data)
                    result = engine.run_analysis()
                    lcoe_row[var_label] = result.lcoe
                    npv_row[var_label] = result.npv
                    irr_row[var_label] = result.firr if result.firr is not None else float('nan')
                    eirr_row[var_label] = result.eirr if result.eirr is not None else float('nan')
                except Exception:
                    lcoe_row[var_label] = float('nan')
                    npv_row[var_label] = float('nan')
                    irr_row[var_label] = float('nan')
                    eirr_row[var_label] = float('nan')

            lcoe_results[label] = lcoe_row
            npv_results[label] = npv_row
            irr_results[label] = irr_row
            eirr_results[label] = eirr_row

        return {
            "lcoe": pd.DataFrame(lcoe_results).T,
            "npv": pd.DataFrame(npv_results).T,
            "irr": pd.DataFrame(irr_results).T,
            "eirr": pd.DataFrame(eirr_results).T,
        }

    def get_tornado_data(
        self,
        sensitivity_results: Dict[str, pd.DataFrame],
        metric: str = "npv"
    ) -> pd.DataFrame:
        """
        Prepare tornado chart data for a specific metric.

        Shows the range (min to max) for each parameter.

        Args:
            sensitivity_results: Output from run_sensitivity().
            metric: One of 'lcoe', 'npv', 'irr'.

        Returns:
            DataFrame with Parameter, Min, Max, Range, Base columns.
        """
        df = sensitivity_results[metric]
        rows = []

        for param in df.index:
            values = df.loc[param].dropna().values.astype(float)
            if len(values) > 0:
                rows.append({
                    "Parameter": param,
                    "Min": round(float(np.nanmin(values)), 2),
                    "Max": round(float(np.nanmax(values)), 2),
                    "Range": round(float(np.nanmax(values) - np.nanmin(values)), 2),
                    "Base": round(float(np.nanmedian(values)), 2),
                })

        result = pd.DataFrame(rows)
        result = result.sort_values("Range", ascending=True).reset_index(drop=True)
        return result
