"""
Financial Excel Export — RETScreen-Style Workbook Output.

Creates a professionally formatted financial screening workbook:
1. Financial Summary — key metrics
2. Project Assumptions — all input parameters
3. Cash Flow — annual cash flow table
4. LCOE Analysis — levelized cost breakdown
5. Sensitivity — parameter sensitivity matrices
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.excel_utils import ExcelFormatter
from config import OUTPUT_DIR, EXCEL_STYLES
from .finance_engine import FinancialResult
from .lcoe import LCOEResult


class FinancialExcelExport:
    """
    Export financial analysis to a RETScreen-style Excel workbook.
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or str(OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)

    def export(
        self,
        result: FinancialResult,
        lcoe_result: Optional[LCOEResult] = None,
        sensitivity_results: Optional[Dict[str, pd.DataFrame]] = None,
        tornado_data: Optional[pd.DataFrame] = None,
        project_data: Optional[Dict[str, Any]] = None,
        filename: str = "financial_output.xlsx"
    ) -> str:
        """
        Export all financial outputs to Excel.

        Returns:
            Path to saved workbook.
        """
        formatter = ExcelFormatter(title="Financial Screening Workbook")

        # Sheet 1: Financial Summary
        self._write_summary(formatter, result)

        # Sheet 2: Project Assumptions
        if project_data:
            self._write_assumptions(formatter, project_data)

        # Sheet 3: Cash Flow
        self._write_cashflow(formatter, result)

        # Sheet 4: LCOE
        if lcoe_result:
            self._write_lcoe(formatter, lcoe_result)

        # Sheet 5: Sensitivity
        if sensitivity_results:
            self._write_sensitivity(formatter, sensitivity_results, tornado_data)

        filepath = os.path.join(self.output_dir, filename)
        return formatter.save(filepath)

    def _write_summary(self, formatter: ExcelFormatter, result: FinancialResult) -> None:
        """Write the financial summary sheet (primary output page)."""
        ws = formatter.add_sheet("Financial Summary")

        row = formatter.write_title_block(
            ws,
            title="Financial Screening Summary",
            subtitle=f"{result.project_name} — {result.technology}",
            span=4
        )

        # Key metrics with conditional coloring
        row = formatter.write_key_value_block(
            ws, result.summary, start_row=row, start_col=1,
            title="Project Assessment"
        )

        # Highlight NPV
        for r in range(1, row):
            cell = ws.cell(row=r, column=1)
            if cell.value and "NPV" in str(cell.value):
                val_cell = ws.cell(row=r, column=2)
                try:
                    npv_val = result.npv
                    formatter.apply_conditional_fill(ws, r, 2, npv_val, positive_good=True)
                except:
                    pass

        formatter.auto_fit_columns(ws)

    def _write_assumptions(self, formatter: ExcelFormatter, project_data: Dict[str, Any]) -> None:
        """Write project assumptions sheet."""
        ws = formatter.add_sheet("Assumptions")

        row = formatter.write_title_block(
            ws, "Project Assumptions",
            subtitle="Input parameters for financial analysis",
            span=4
        )

        # General assumptions
        general = {
            "Project Name": project_data.get("project_name"),
            "Technology": project_data.get("technology"),
            "Capacity (MW)": project_data.get("capacity_mw"),
            "Capacity Factor": f"{project_data.get('capacity_factor', 0):.1%}",
            "Annual Generation (MWh)": f"{project_data.get('annual_generation_mwh', 0):,.0f}",
            "Project Life (years)": project_data.get("project_life_years"),
        }
        row = formatter.write_key_value_block(
            ws, general, start_row=row, title="General"
        )

        # Cost assumptions
        costs = {
            "Total CAPEX (USD)": f"${project_data.get('capex_total_usd', 0):,.0f}",
            "Annual OPEX (USD)": f"${project_data.get('annual_opex_usd', 0):,.0f}",
        }
        # Add CAPEX breakdown
        breakdown = project_data.get("capex_breakdown", {})
        for item, value in breakdown.items():
            costs[f"  {item}"] = f"${value:,.0f}"

        row = formatter.write_key_value_block(
            ws, costs, start_row=row, title="Cost Parameters"
        )

        # Financial assumptions
        financial = {
            "Discount Rate": f"{project_data.get('discount_rate', 0):.1%}",
            "Inflation Rate": f"{project_data.get('inflation_rate', 0):.1%}",
            "Degradation Rate": f"{project_data.get('degradation_rate', 0):.2%}",
            "Electricity Price (USD/MWh)": f"${project_data.get('electricity_price_usd_mwh', 0):.2f}",
            "Price Escalation": f"{project_data.get('price_escalation_rate', 0):.1%}",
            "Debt Fraction": f"{project_data.get('debt_fraction', 0):.0%}",
            "Debt Interest Rate": f"{project_data.get('debt_interest_rate', 0):.1%}",
            "Debt Term (years)": project_data.get("debt_term_years"),
            "Tax Rate": f"{project_data.get('tax_rate', 0):.0%}",
        }
        row = formatter.write_key_value_block(
            ws, financial, start_row=row, title="Financial Parameters"
        )

        formatter.auto_fit_columns(ws)

    def _write_cashflow(self, formatter: ExcelFormatter, result: FinancialResult) -> None:
        """Write annual cash flow sheet."""
        ws = formatter.add_sheet("Cash Flow")

        row = formatter.write_title_block(
            ws, "Annual Cash Flow Analysis",
            subtitle=f"{result.project_name} — {result.project_life} year projection",
            span=len(result.cashflow_table.columns)
        )

        row = formatter.write_dataframe(
            ws, result.cashflow_table, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        formatter.auto_fit_columns(ws)

    def _write_lcoe(self, formatter: ExcelFormatter, lcoe_result: LCOEResult) -> None:
        """Write LCOE analysis sheet."""
        ws = formatter.add_sheet("LCOE Analysis")

        row = formatter.write_title_block(
            ws, "Levelized Cost of Electricity (LCOE)",
            subtitle="LCOE = PV(Total Costs) / PV(Total Generation)",
            span=4
        )

        lcoe_data = {
            "LCOE (USD/MWh)": f"${lcoe_result.lcoe:.2f}",
            "": "",
            "PV of Total Costs (USD)": f"${lcoe_result.pv_total_costs:,.0f}",
            "PV of CAPEX (USD)": f"${lcoe_result.pv_capex:,.0f}",
            "PV of OPEX (USD)": f"${lcoe_result.pv_opex:,.0f}",
            " ": "",
            "PV of Total Generation (MWh)": f"{lcoe_result.pv_generation:,.0f}",
            "  ": "",
            "LCOE — CAPEX Component (USD/MWh)": f"${lcoe_result.lcoe_capex_component:.2f}",
            "LCOE — OPEX Component (USD/MWh)": f"${lcoe_result.lcoe_opex_component:.2f}",
        }

        row = formatter.write_key_value_block(
            ws, lcoe_data, start_row=row, title="LCOE Breakdown"
        )

        formatter.auto_fit_columns(ws)

    def _write_sensitivity(
        self,
        formatter: ExcelFormatter,
        sensitivity_results: Dict[str, pd.DataFrame],
        tornado_data: Optional[pd.DataFrame]
    ) -> None:
        """Write sensitivity analysis sheets."""
        for metric, df in sensitivity_results.items():
            sheet_name = f"Sensitivity {metric.upper()}"[:31]
            ws = formatter.add_sheet(sheet_name)

            row = formatter.write_title_block(
                ws, f"Sensitivity Analysis — {metric.upper()}",
                subtitle="One-at-a-time parameter variation impact",
                span=len(df.columns) + 1
            )

            row = formatter.write_dataframe(
                ws, df, start_row=row, include_index=True,
                number_format=EXCEL_STYLES["number_format_dec2"]
            )

            formatter.auto_fit_columns(ws)

        # Tornado data
        if tornado_data is not None:
            ws = formatter.add_sheet("Tornado Data")
            row = formatter.write_title_block(
                ws, "Tornado Chart Data — NPV Sensitivity",
                span=5
            )
            formatter.write_dataframe(
                ws, tornado_data, start_row=row, include_index=False,
                number_format=EXCEL_STYLES["number_format_dec2"]
            )
            formatter.auto_fit_columns(ws)
