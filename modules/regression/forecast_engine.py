"""
Forecast Engine — EViews-Equivalent Projection Module.

Generates multi-year demand forecasts based on estimated regression
coefficients and user-supplied growth assumptions for independent
variables. Supports scenario-linked forecasting.
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .regression_engine import RegressionResult


@dataclass
class ForecastResult:
    """Container for forecast outputs."""
    forecast_table: pd.DataFrame    # Year, Predicted Y, Confidence bounds
    assumptions_table: pd.DataFrame  # Year, X1, X2, ... assumed values
    model_type: str
    dependent_var: str
    forecast_years: int
    base_year: int
    scenario_name: str


class ForecastEngine:
    """
    Multi-year econometric forecast engine.

    Uses estimated regression coefficients to project the dependent
    variable forward based on assumed growth paths for independent
    variables. Supports multiple scenarios.
    """

    def __init__(self):
        """Initialize the forecast engine."""
        self._forecasts: Dict[str, ForecastResult] = {}

    @property
    def forecasts(self) -> Dict[str, ForecastResult]:
        """Access all computed forecasts by scenario name."""
        return self._forecasts

    def generate_forecast(
        self,
        regression_result: RegressionResult,
        original_data: pd.DataFrame,
        forecast_years: int = 30,
        growth_assumptions: Optional[Dict[str, float]] = None,
        scenario_name: str = "Base Forecast",
        confidence_level: float = 0.95
    ) -> ForecastResult:
        """
        Generate a multi-year forecast.

        Args:
            regression_result: Fitted RegressionResult.
            original_data: Original dataset with historical values.
            forecast_years: Number of years to project forward.
            growth_assumptions: Dict of {variable_name: annual_growth_rate}.
                Growth rates are applied to the ORIGINAL (untransformed) variables.
                Example: {"GDP_Billion_USD": 0.04} means 4% annual GDP growth.
            scenario_name: Name for this forecast scenario.
            confidence_level: Confidence level for prediction intervals.

        Returns:
            ForecastResult with forecast and assumption tables.
        """
        model_type = regression_result.model_type
        coeff_df = regression_result.coefficients
        raw_result = regression_result.raw_result

        # ── Determine base year and variable names ─────────────────────────
        if "Year" in original_data.columns:
            base_year = int(original_data["Year"].max())
        else:
            base_year = len(original_data) + 1992  # Fallback

        # Map transformed variable names back to original column names
        original_var_names = []
        for var in regression_result.independent_vars:
            # Strip LOG() wrapper if present
            clean = var.replace("LOG(", "").replace(")", "")
            original_var_names.append(clean)

        # ── Get last observed values ───────────────────────────────────────
        last_values = {}
        for orig_name in original_var_names:
            if orig_name in original_data.columns:
                last_values[orig_name] = float(
                    original_data[orig_name].dropna().iloc[-1]
                )
            else:
                raise ValueError(
                    f"Variable '{orig_name}' not found in original data."
                )

        # ── Set default growth assumptions ─────────────────────────────────
        if growth_assumptions is None:
            growth_assumptions = {var: 0.03 for var in original_var_names}

        # ── Project independent variables forward ──────────────────────────
        forecast_data = []
        for t in range(1, forecast_years + 1):
            year = base_year + t
            row = {"Year": year}
            for var_name in original_var_names:
                growth = growth_assumptions.get(var_name, 0.02)
                projected = last_values[var_name] * ((1 + growth) ** t)
                row[var_name] = projected
            forecast_data.append(row)

        assumptions_df = pd.DataFrame(forecast_data)

        # ── Compute predicted dependent variable ───────────────────────────
        coefficients = coeff_df["Coefficient"].values
        has_constant = coeff_df["Variable"].iloc[0] == "C (Intercept)"

        predictions = []
        prediction_intervals_lower = []
        prediction_intervals_upper = []

        for _, row in assumptions_df.iterrows():
            # Get X values in the correct transformation
            x_values = []
            for orig_name in original_var_names:
                val = row[orig_name]
                if model_type == "log_log":
                    val = np.log(val)
                x_values.append(val)

            # Add constant
            if has_constant:
                x_all = [1.0] + x_values
            else:
                x_all = x_values

            # Predicted value (in transformed space)
            y_pred_transformed = np.dot(coefficients, x_all)

            # Convert back to original scale
            if model_type in ["log_log", "semi_log"]:
                y_pred = np.exp(y_pred_transformed)
            else:
                y_pred = y_pred_transformed

            predictions.append(y_pred)

            # Approximate prediction intervals using SE of regression
            se = regression_result.se_regression
            z = 1.96 if confidence_level == 0.95 else 1.645

            if model_type in ["log_log", "semi_log"]:
                lower = np.exp(y_pred_transformed - z * se)
                upper = np.exp(y_pred_transformed + z * se)
            else:
                lower = y_pred_transformed - z * se
                upper = y_pred_transformed + z * se

            prediction_intervals_lower.append(lower)
            prediction_intervals_upper.append(upper)

        # ── Build forecast table ───────────────────────────────────────────
        dep_var_clean = regression_result.dependent_var.replace("LOG(", "").replace(")", "")
        forecast_df = pd.DataFrame({
            "Year": assumptions_df["Year"].astype(int),
            f"{dep_var_clean} (Forecast)": np.round(predictions, 2),
            f"Lower {confidence_level*100:.0f}%": np.round(
                prediction_intervals_lower, 2
            ),
            f"Upper {confidence_level*100:.0f}%": np.round(
                prediction_intervals_upper, 2
            ),
        })

        # Round assumptions table
        for col in assumptions_df.columns:
            if col != "Year":
                assumptions_df[col] = assumptions_df[col].round(4)

        result = ForecastResult(
            forecast_table=forecast_df,
            assumptions_table=assumptions_df,
            model_type=model_type,
            dependent_var=dep_var_clean,
            forecast_years=forecast_years,
            base_year=base_year,
            scenario_name=scenario_name,
        )

        self._forecasts[scenario_name] = result
        return result

    def compare_scenarios(self) -> Optional[pd.DataFrame]:
        """
        Compare forecast results across all computed scenarios.

        Returns:
            DataFrame with Year and one column per scenario, or None.
        """
        if not self._forecasts:
            return None

        dfs = []
        for name, result in self._forecasts.items():
            col_name = [c for c in result.forecast_table.columns if "Forecast" in c][0]
            df = result.forecast_table[["Year", col_name]].copy()
            df = df.rename(columns={col_name: name})
            dfs.append(df)

        # Merge all on Year
        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.merge(df, on="Year", how="outer")

        return merged
