"""
Scenario Excel Export — LEAP-Style Energy Planning Workbook.

Produces a professionally formatted Excel workbook with multiple
sheets for base year data, scenario assumptions, demand results,
supply/transformation, emissions, and scenario comparisons.
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.excel_utils import ExcelFormatter
from config import OUTPUT_DIR, EXCEL_STYLES
from .scenario_engine import ScenarioResult


class ScenarioExcelExport:
    """
    Export LEAP-style scenario analysis results to Excel.

    Sheets produced:
    1. Base Year — energy balance
    2. Assumptions — scenario parameters
    3. Demand by Sector — for each scenario
    4. Demand by Fuel — for each scenario
    5. Supply/Transformation — generation mix
    6. Emissions — CO₂ by scenario
    7. Scenario Comparison — demand and emissions comparison
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or str(OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)

    def export(
        self,
        config: Dict[str, Any],
        base_year_summary: Dict[str, Any],
        scenario_results: Dict[str, ScenarioResult],
        demand_comparison: Optional[pd.DataFrame] = None,
        emissions_data: Optional[Dict[str, pd.DataFrame]] = None,
        emissions_comparison: Optional[pd.DataFrame] = None,
        supply_data: Optional[Dict[str, pd.DataFrame]] = None,
        filename: str = "scenario_output.xlsx"
    ) -> str:
        """
        Export all scenario outputs to Excel.

        Returns:
            Path to saved workbook.
        """
        formatter = ExcelFormatter(title="Energy Scenario Analysis")

        # Sheet 1: Base Year
        self._write_base_year(formatter, base_year_summary, config)

        # Sheet 2: Assumptions
        self._write_assumptions(formatter, config)

        # Sheet 3-N: Scenario details
        for name, result in scenario_results.items():
            self._write_scenario_detail(formatter, result, name)

        # Demand comparison
        if demand_comparison is not None:
            self._write_comparison(
                formatter, demand_comparison,
                "Demand Comparison",
                "Total Energy Demand (PJ) — Scenario Comparison"
            )

        # Emissions
        if emissions_comparison is not None:
            self._write_comparison(
                formatter, emissions_comparison,
                "Emissions Comparison",
                "Total CO₂ Emissions (Mt) — Scenario Comparison"
            )

        # Detailed emissions per scenario
        if emissions_data:
            for name, em_df in emissions_data.items():
                sheet_name = f"Emissions {name}"[:31]
                ws = formatter.add_sheet(sheet_name)
                row = formatter.write_title_block(
                    ws, f"Emissions — {name}",
                    subtitle="Demand + Supply CO₂ emissions",
                    span=len(em_df.columns)
                )
                formatter.write_dataframe(
                    ws, em_df, start_row=row,
                    number_format=EXCEL_STYLES["number_format_dec2"]
                )
                formatter.auto_fit_columns(ws)

        filepath = os.path.join(self.output_dir, filename)
        return formatter.save(filepath)

    def _write_base_year(
        self,
        formatter: ExcelFormatter,
        summary: Dict[str, Any],
        config: Dict[str, Any]
    ) -> None:
        ws = formatter.add_sheet("Base Year")

        row = formatter.write_title_block(
            ws, "Base Year Energy Balance",
            subtitle=f"Year: {summary['year']}",
            span=6
        )

        # Total demand
        info = {"Total Energy Demand (PJ)": summary["total_demand_pj"]}
        row = formatter.write_key_value_block(
            ws, info, start_row=row,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        # Demand by sector
        sector_df = pd.DataFrame(
            list(summary["demand_by_sector"].items()),
            columns=["Sector", "Demand (PJ)"]
        )
        row = formatter.write_dataframe(
            ws, sector_df, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        # Demand by fuel
        fuel_df = pd.DataFrame(
            list(summary["demand_by_fuel"].items()),
            columns=["Fuel", "Demand (PJ)"]
        )
        row = formatter.write_dataframe(
            ws, fuel_df, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        # Demand matrix
        if summary.get("demand_matrix") is not None:
            row = formatter.write_dataframe(
                ws, summary["demand_matrix"], start_row=row,
                include_index=True,
                number_format=EXCEL_STYLES["number_format_dec2"]
            )

        formatter.auto_fit_columns(ws)

    def _write_assumptions(
        self,
        formatter: ExcelFormatter,
        config: Dict[str, Any]
    ) -> None:
        ws = formatter.add_sheet("Assumptions")

        row = formatter.write_title_block(
            ws, "Scenario Assumptions",
            subtitle="Growth rates, intensity changes, and fuel switching parameters",
            span=6
        )

        scenarios = config.get("scenarios", {})
        for scenario_name, params in scenarios.items():
            info = {"Scenario": scenario_name, "Description": params.get("description", "")}
            row = formatter.write_key_value_block(ws, info, start_row=row, title=scenario_name)

            # Activity growth
            growth_df = pd.DataFrame(
                list(params.get("activity_growth", {}).items()),
                columns=["Sector", "Annual Growth Rate"]
            )
            row = formatter.write_dataframe(
                ws, growth_df, start_row=row, include_index=False,
                number_format=EXCEL_STYLES["number_format_pct"]
            )

            # Intensity change
            intensity_df = pd.DataFrame(
                list(params.get("intensity_change", {}).items()),
                columns=["Sector", "Annual Intensity Change"]
            )
            row = formatter.write_dataframe(
                ws, intensity_df, start_row=row, include_index=False,
                number_format=EXCEL_STYLES["number_format_pct"]
            )

        formatter.auto_fit_columns(ws)

    def _write_scenario_detail(
        self,
        formatter: ExcelFormatter,
        result: ScenarioResult,
        name: str
    ) -> None:
        sheet_name = f"Demand {name}"[:31]
        ws = formatter.add_sheet(sheet_name)

        row = formatter.write_title_block(
            ws, f"Energy Demand — {name}",
            subtitle=result.description,
            span=max(len(result.demand_by_sector_by_year.columns), 4)
        )

        # Summary stats
        stats = {
            "Base Year Demand (PJ)": round(result.total_demand_by_year.iloc[0], 2),
            "Final Year Demand (PJ)": round(result.total_demand_by_year.iloc[-1], 2),
            "Avg Annual Growth": f"{result.avg_annual_growth_rate*100:.2f}%"
        }
        row = formatter.write_key_value_block(ws, stats, start_row=row)

        # Demand by sector (show every 5th year)
        sector_display = result.demand_by_sector_by_year.iloc[::5].round(2)
        row = formatter.write_dataframe(
            ws, sector_display, start_row=row,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        # Demand by fuel (show every 5th year)
        fuel_display = result.demand_by_fuel_by_year.iloc[::5].round(2)
        row = formatter.write_dataframe(
            ws, fuel_display, start_row=row,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        formatter.auto_fit_columns(ws)

    def _write_comparison(
        self,
        formatter: ExcelFormatter,
        comparison_df: pd.DataFrame,
        sheet_name: str,
        title: str
    ) -> None:
        ws = formatter.add_sheet(sheet_name[:31])

        row = formatter.write_title_block(
            ws, title,
            span=len(comparison_df.columns) + 1
        )

        # Show every 5th year
        display = comparison_df.iloc[::5].round(2)
        formatter.write_dataframe(
            ws, display, start_row=row,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        formatter.auto_fit_columns(ws)
