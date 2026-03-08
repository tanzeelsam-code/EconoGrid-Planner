"""
Regression Excel Export — EViews-Style Workbook Output.

Creates a professionally formatted Excel workbook that emulates
the reporting style of EViews regression output, including:
- Regression summary sheet
- Diagnostics sheet
- Forecast sheet
- Forecast assumptions sheet
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.excel_utils import ExcelFormatter
from config import OUTPUT_DIR, EXCEL_STYLES
from .regression_engine import RegressionResult
from .forecast_engine import ForecastResult


class RegressionExcelExport:
    """
    Export regression results to a professionally formatted Excel workbook.

    Produces an EViews-style workbook with multiple sheets:
    1. Regression Summary — coefficient table + model statistics
    2. Diagnostics — test results and residual analysis
    3. Forecast — projected values with confidence intervals
    4. Assumptions — forecast driver assumptions
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the exporter.

        Args:
            output_dir: Directory for output files. Defaults to config OUTPUT_DIR.
        """
        self.output_dir = output_dir or str(OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)

    def export(
        self,
        regression_result: RegressionResult,
        diagnostics: Optional[Dict[str, Any]] = None,
        forecast_result: Optional[ForecastResult] = None,
        comparison_df: Optional[pd.DataFrame] = None,
        filename: str = "regression_output.xlsx"
    ) -> str:
        """
        Export all regression outputs to Excel.

        Args:
            regression_result: Fitted regression result.
            diagnostics: Diagnostic test results dictionary.
            forecast_result: Forecast output (optional).
            comparison_df: Scenario comparison DataFrame (optional).
            filename: Output filename.

        Returns:
            Absolute path to saved workbook.
        """
        formatter = ExcelFormatter(title="Regression Analysis Output")

        # ── Sheet 1: Regression Summary ────────────────────────────────────
        self._write_regression_summary(formatter, regression_result)

        # ── Sheet 2: Diagnostics ───────────────────────────────────────────
        if diagnostics:
            self._write_diagnostics(formatter, regression_result, diagnostics)

        # ── Sheet 3: Confidence Intervals ──────────────────────────────────
        self._write_confidence_intervals(formatter, regression_result)

        # ── Sheet 4: Forecast ──────────────────────────────────────────────
        if forecast_result:
            self._write_forecast(formatter, forecast_result)

        # ── Sheet 5: Scenario Comparison ───────────────────────────────────
        if comparison_df is not None:
            self._write_scenario_comparison(formatter, comparison_df)

        # ── Save ───────────────────────────────────────────────────────────
        filepath = os.path.join(self.output_dir, filename)
        return formatter.save(filepath)

    def _write_regression_summary(
        self,
        formatter: ExcelFormatter,
        result: RegressionResult
    ) -> None:
        """Write the main regression summary sheet (EViews-style)."""
        ws = formatter.add_sheet("Regression Summary")

        # Title block
        row = formatter.write_title_block(
            ws,
            title="OLS Regression Results",
            subtitle=result.equation_title,
            span=5
        )

        # Header info block
        info = {
            "Dependent Variable": result.dependent_var,
            "Method": result.estimation_method,
            "Model Specification": result.model_type.replace("_", "-").title(),
            "Date/Time": result.run_timestamp,
            "Sample": result.sample_period,
            "Included Observations": result.n_observations,
        }
        row = formatter.write_key_value_block(
            ws, info, start_row=row, start_col=1,
            title="Estimation Details"
        )

        # Coefficient table
        row = formatter.write_dataframe(
            ws, result.coefficients, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec4"]
        )

        # Model statistics — two-column layout
        stats_left = {
            "R-squared": result.r_squared,
            "Adjusted R-squared": result.adj_r_squared,
            "S.E. of regression": result.se_regression,
            "Sum squared resid": result.sum_squared_resid,
            "Log likelihood": result.log_likelihood,
            "F-statistic": result.f_statistic,
            "Prob(F-statistic)": result.prob_f_statistic,
        }
        row_left = formatter.write_key_value_block(
            ws, stats_left, start_row=row, start_col=1,
            title="Model Statistics",
            number_format=EXCEL_STYLES["number_format_dec4"]
        )

        stats_right = {
            "Mean dependent var": result.mean_dependent,
            "S.D. dependent var": result.sd_dependent,
            "Akaike info criterion": result.aic,
            "Schwarz criterion (BIC)": result.bic,
            "Durbin-Watson stat": result.durbin_watson,
        }
        formatter.write_key_value_block(
            ws, stats_right, start_row=row, start_col=4,
            title="Additional Statistics",
            number_format=EXCEL_STYLES["number_format_dec4"]
        )

        formatter.auto_fit_columns(ws)

    def _write_diagnostics(
        self,
        formatter: ExcelFormatter,
        result: RegressionResult,
        diagnostics: Dict[str, Any]
    ) -> None:
        """Write the diagnostics sheet."""
        ws = formatter.add_sheet("Diagnostics")

        row = formatter.write_title_block(
            ws,
            title="Regression Diagnostics",
            subtitle="Post-estimation statistical tests",
            span=4
        )

        # Residual summary
        resid_summary = diagnostics.get("residual_summary", {})
        row = formatter.write_key_value_block(
            ws, resid_summary, start_row=row, start_col=1,
            title="Residual Summary Statistics",
            number_format=EXCEL_STYLES["number_format_dec4"]
        )

        # Diagnostic tests table
        from .diagnostics import RegressionDiagnostics
        diag_df = RegressionDiagnostics.summary_table(diagnostics)
        row = formatter.write_dataframe(
            ws, diag_df, start_row=row, include_index=False
        )

        # VIF table if available
        vif_data = diagnostics.get("multicollinearity", {})
        if "results" in vif_data and vif_data["results"]:
            vif_df = pd.DataFrame(vif_data["results"])
            row = formatter.write_dataframe(
                ws, vif_df, start_row=row, include_index=False,
                number_format=EXCEL_STYLES["number_format_dec4"]
            )

        formatter.auto_fit_columns(ws)

    def _write_confidence_intervals(
        self,
        formatter: ExcelFormatter,
        result: RegressionResult
    ) -> None:
        """Write confidence intervals sheet."""
        ws = formatter.add_sheet("Confidence Intervals")

        row = formatter.write_title_block(
            ws,
            title="Coefficient Confidence Intervals",
            subtitle=result.equation_title,
            span=3
        )

        row = formatter.write_dataframe(
            ws, result.conf_intervals, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec4"]
        )

        formatter.auto_fit_columns(ws)

    def _write_forecast(
        self,
        formatter: ExcelFormatter,
        forecast: ForecastResult
    ) -> None:
        """Write forecast sheet with projections and assumptions."""
        # Forecast values
        ws = formatter.add_sheet("Forecast")

        row = formatter.write_title_block(
            ws,
            title=f"Demand Forecast — {forecast.scenario_name}",
            subtitle=f"Base year: {forecast.base_year} | "
                     f"Horizon: {forecast.forecast_years} years | "
                     f"Model: {forecast.model_type}",
            span=4
        )

        row = formatter.write_dataframe(
            ws, forecast.forecast_table, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        # Assumptions table
        ws2 = formatter.add_sheet("Forecast Assumptions")

        row2 = formatter.write_title_block(
            ws2,
            title="Forecast Assumptions",
            subtitle=f"Scenario: {forecast.scenario_name}",
            span=len(forecast.assumptions_table.columns)
        )

        row2 = formatter.write_dataframe(
            ws2, forecast.assumptions_table, start_row=row2, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec4"]
        )

        formatter.auto_fit_columns(ws)
        formatter.auto_fit_columns(ws2)

    def _write_scenario_comparison(
        self,
        formatter: ExcelFormatter,
        comparison_df: pd.DataFrame
    ) -> None:
        """Write scenario comparison sheet."""
        ws = formatter.add_sheet("Scenario Comparison")

        row = formatter.write_title_block(
            ws,
            title="Forecast Scenario Comparison",
            subtitle="Demand projections under different growth assumptions",
            span=len(comparison_df.columns)
        )

        row = formatter.write_dataframe(
            ws, comparison_df, start_row=row, include_index=False,
            number_format=EXCEL_STYLES["number_format_dec2"]
        )

        formatter.auto_fit_columns(ws)
