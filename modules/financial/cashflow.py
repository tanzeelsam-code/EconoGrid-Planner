"""
Cash Flow Analyzer — Annual and Cumulative Cash Flow Analysis.

Provides detailed annual cash flow decomposition with present
value calculations and project viability metrics.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from .finance_engine import FinancialResult


class CashFlowAnalyzer:
    """
    Cash flow analysis and reporting engine.

    Generates structured cash flow summaries and annual
    decompositions suitable for financial reporting.
    """

    @staticmethod
    def get_annual_summary(result: FinancialResult) -> pd.DataFrame:
        """
        Get a condensed annual cash flow summary.

        Args:
            result: FinancialResult from finance engine.

        Returns:
            DataFrame with key cash flow columns for reporting.
        """
        cf = result.cashflow_table.copy()
        summary = cf[[
            "Year", "Revenue", "OPEX", "Debt Service", "Project Tax",
            "Net Cash Flow", "Cumulative Cash Flow",
            "Discounted CF", "Cumulative Discounted CF"
        ]].copy()

        return summary

    @staticmethod
    def get_yearly_breakdown(
        result: FinancialResult,
        years: Optional[list] = None
    ) -> pd.DataFrame:
        """
        Get detailed breakdown for selected years.

        Args:
            result: FinancialResult.
            years: List of years to include. Default: every 5th year.

        Returns:
            DataFrame with full column detail for selected years.
        """
        cf = result.cashflow_table.copy()

        if years is None:
            # Every 5th year plus first and last
            years = [0, 1, 5, 10, 15, 20, 25]
            years = [y for y in years if y <= result.project_life]

        return cf[cf["Year"].isin(years)].reset_index(drop=True)

    @staticmethod
    def get_profitability_metrics(result: FinancialResult) -> Dict[str, Any]:
        """
        Extract key profitability metrics.

        Args:
            result: FinancialResult.

        Returns:
            Dictionary of profitability metrics.
        """
        cf = result.cashflow_table

        # Total lifetime revenue
        total_revenue = cf.loc[cf["Year"] > 0, "Revenue"].sum()
        total_costs = cf.loc[cf["Year"] > 0, "Project Cost Basis"].sum() + result.capex
        total_generation = cf.loc[cf["Year"] > 0, "Generation (MWh)"].sum()
        total_net_cf = cf["Net Cash Flow"].sum()

        return {
            "Total Lifetime Revenue (USD)": round(total_revenue, 2),
            "Total Lifetime Costs (USD)": round(total_costs, 2),
            "Total Net Cash Flow (USD)": round(total_net_cf, 2),
            "Total Generation (MWh)": round(total_generation, 0),
            "Average Annual Revenue (USD)": round(
                total_revenue / result.project_life, 2
            ),
            "Average Annual Net CF (USD)": round(
                total_net_cf / (result.project_life + 1), 2
            ),
            "Revenue per MWh (avg)": round(
                total_revenue / total_generation if total_generation > 0 else 0, 2
            ),
            "Cost per MWh (avg)": round(
                total_costs / total_generation if total_generation > 0 else 0, 2
            ),
        }

    @staticmethod
    def get_chart_data(result: FinancialResult) -> Dict[str, Any]:
        """
        Prepare data structures for Plotly charts.

        Returns:
            Dict with 'annual_cashflow', 'cumulative_cashflow',
            'revenue_vs_cost', and 'generation' chart data.
        """
        cf = result.cashflow_table
        years = cf["Year"].tolist()

        return {
            "annual_cashflow": {
                "years": years,
                "values": cf["Net Cash Flow"].tolist(),
            },
            "cumulative_cashflow": {
                "years": years,
                "values": cf["Cumulative Cash Flow"].tolist(),
            },
            "cumulative_discounted": {
                "years": years,
                "values": cf["Cumulative Discounted CF"].tolist(),
            },
            "revenue_vs_cost": {
                "years": years[1:],  # Exclude year 0
                "revenue": cf.loc[cf["Year"] > 0, "Revenue"].tolist(),
                "costs": cf.loc[cf["Year"] > 0, "Total Costs"].tolist(),
            },
            "generation": {
                "years": years[1:],
                "mwh": cf.loc[cf["Year"] > 0, "Generation (MWh)"].tolist(),
            },
        }
