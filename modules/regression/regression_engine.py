"""
Regression Engine — EViews-Equivalent OLS Estimation Module.

Provides OLS regression with support for linear, log-log, and semi-log
model specifications. Produces EViews-style coefficient tables with
standard errors, t-statistics, p-values, and comprehensive model
diagnostics.

Uses statsmodels as the estimation backend.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RegressionResult:
    """Container for regression estimation results."""
    model_type: str
    dependent_var: str
    independent_vars: List[str]
    equation_title: str
    sample_period: str
    n_observations: int
    estimation_method: str
    run_timestamp: str

    # Coefficient table
    coefficients: pd.DataFrame       # Variable, Coeff, StdErr, tStat, Prob

    # Model statistics
    r_squared: float
    adj_r_squared: float
    f_statistic: float
    prob_f_statistic: float
    durbin_watson: float
    aic: float
    bic: float
    log_likelihood: float
    se_regression: float
    sum_squared_resid: float
    mean_dependent: float
    sd_dependent: float

    # Confidence intervals
    conf_intervals: pd.DataFrame

    # Residuals
    residuals: pd.Series
    fitted_values: pd.Series

    # Underlying statsmodels result (for advanced diagnostics)
    raw_result: Any = field(repr=False, default=None)


class RegressionEngine:
    """
    EViews-equivalent OLS regression engine.

    Supports:
    - Linear: Y = a + b1*X1 + b2*X2 + ...
    - Log-Log: ln(Y) = a + b1*ln(X1) + b2*ln(X2) + ...
    - Semi-Log: ln(Y) = a + b1*X1 + b2*X2 + ...

    In log-log specification, coefficients are interpreted as elasticities.
    """

    VALID_MODEL_TYPES = ["linear", "log_log", "semi_log"]

    def __init__(self):
        """Initialize the regression engine."""
        self._last_result: Optional[RegressionResult] = None

    @property
    def last_result(self) -> Optional[RegressionResult]:
        """Access the most recent regression result."""
        return self._last_result

    def fit(
        self,
        data: pd.DataFrame,
        dependent_var: str,
        independent_vars: List[str],
        model_type: str = "log_log",
        add_constant: bool = True,
        equation_title: Optional[str] = None,
        confidence_level: float = 0.95
    ) -> RegressionResult:
        """
        Estimate an OLS regression model.

        Args:
            data: DataFrame with all variables.
            dependent_var: Name of the dependent (Y) variable.
            independent_vars: Names of independent (X) variables.
            model_type: One of "linear", "log_log", "semi_log".
            add_constant: Whether to include an intercept term.
            equation_title: Custom title for the equation.
            confidence_level: Confidence level for intervals (default 0.95).

        Returns:
            RegressionResult containing all estimation outputs.

        Raises:
            ValueError: If model_type is invalid or required columns missing.
        """
        # ── Validate inputs ────────────────────────────────────────────────
        if model_type not in self.VALID_MODEL_TYPES:
            raise ValueError(
                f"Invalid model_type '{model_type}'. "
                f"Must be one of: {self.VALID_MODEL_TYPES}"
            )

        all_vars = [dependent_var] + independent_vars
        missing = set(all_vars) - set(data.columns)
        if missing:
            raise ValueError(f"Variables not found in data: {missing}")

        # ── Prepare working data ───────────────────────────────────────────
        df = data[all_vars].dropna().copy()

        if len(df) < len(independent_vars) + 2:
            raise ValueError(
                f"Insufficient observations ({len(df)}) for "
                f"{len(independent_vars)} independent variables."
            )

        # Determine sample period
        if "Year" in data.columns:
            years = data.loc[df.index, "Year"]
            sample_period = f"{int(years.min())} – {int(years.max())}"
        elif hasattr(df.index, 'year'):
            sample_period = f"{df.index.min()} – {df.index.max()}"
        else:
            sample_period = f"Obs 1 – {len(df)}"

        # ── Apply transformations ──────────────────────────────────────────
        y_label = dependent_var
        x_labels = list(independent_vars)

        if model_type == "log_log":
            # Check for non-positive values
            for var in all_vars:
                if (df[var] <= 0).any():
                    raise ValueError(
                        f"Log transformation failed: '{var}' contains "
                        f"non-positive values."
                    )
            y = np.log(df[dependent_var])
            X = np.log(df[independent_vars])
            y_label = f"LOG({dependent_var})"
            x_labels = [f"LOG({v})" for v in independent_vars]

        elif model_type == "semi_log":
            if (df[dependent_var] <= 0).any():
                raise ValueError(
                    f"Log transformation failed: '{dependent_var}' contains "
                    f"non-positive values."
                )
            y = np.log(df[dependent_var])
            X = df[independent_vars].copy()
            y_label = f"LOG({dependent_var})"

        else:  # linear
            y = df[dependent_var].copy()
            X = df[independent_vars].copy()

        # ── Add constant term ──────────────────────────────────────────────
        if add_constant:
            X = sm.add_constant(X)
            x_labels_full = ["C (Intercept)"] + x_labels
        else:
            x_labels_full = x_labels

        # ── Estimate OLS ───────────────────────────────────────────────────
        model = sm.OLS(y, X)
        result = model.fit()

        # ── Build coefficient table ────────────────────────────────────────
        coeff_data = {
            "Variable": x_labels_full,
            "Coefficient": result.params.values,
            "Std. Error": result.bse.values,
            "t-Statistic": result.tvalues.values,
            "Prob.": result.pvalues.values,
        }
        coeff_df = pd.DataFrame(coeff_data)
        coeff_df = coeff_df.round(6)

        # ── Confidence intervals ───────────────────────────────────────────
        alpha = 1 - confidence_level
        ci = result.conf_int(alpha=alpha)
        ci_df = pd.DataFrame({
            "Variable": x_labels_full,
            f"Lower {confidence_level*100:.0f}%": ci.iloc[:, 0].values,
            f"Upper {confidence_level*100:.0f}%": ci.iloc[:, 1].values,
        })

        # ── Build result object ────────────────────────────────────────────
        if equation_title is None:
            equation_title = (
                f"Equation: {y_label} = f({', '.join(x_labels)})"
            )

        reg_result = RegressionResult(
            model_type=model_type,
            dependent_var=y_label,
            independent_vars=x_labels,
            equation_title=equation_title,
            sample_period=sample_period,
            n_observations=int(result.nobs),
            estimation_method="Least Squares",
            run_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            coefficients=coeff_df,

            r_squared=round(result.rsquared, 6),
            adj_r_squared=round(result.rsquared_adj, 6),
            f_statistic=round(result.fvalue, 4),
            prob_f_statistic=round(result.f_pvalue, 6),
            durbin_watson=round(float(sm.stats.durbin_watson(result.resid)), 4),
            aic=round(result.aic, 4),
            bic=round(result.bic, 4),
            log_likelihood=round(result.llf, 4),
            se_regression=round(np.sqrt(result.mse_resid), 6),
            sum_squared_resid=round(result.ssr, 6),
            mean_dependent=round(float(y.mean()), 6),
            sd_dependent=round(float(y.std()), 6),

            conf_intervals=ci_df,
            residuals=result.resid,
            fitted_values=result.fittedvalues,
            raw_result=result,
        )

        self._last_result = reg_result
        return reg_result

    def get_elasticities(self, result: Optional[RegressionResult] = None) -> Dict[str, float]:
        """
        Extract elasticity estimates from a log-log regression.

        For log-log models, the coefficients are direct elasticities.
        For other model types, returns coefficients with a note.

        Args:
            result: RegressionResult to extract from. Uses last result if None.

        Returns:
            Dictionary of {variable: elasticity}.
        """
        if result is None:
            result = self._last_result
        if result is None:
            raise ValueError("No regression result available.")

        elasticities = {}
        for _, row in result.coefficients.iterrows():
            if row["Variable"] != "C (Intercept)":
                elasticities[row["Variable"]] = row["Coefficient"]

        return elasticities

    def predict(
        self,
        result: RegressionResult,
        data: pd.DataFrame,
        confidence_level: float = 0.95
    ) -> pd.DataFrame:
        """
        Predict on new data supplied in the original variable space.

        Args:
            result: Previously estimated regression result.
            data: DataFrame containing the original independent variables.
            confidence_level: Interval coverage for predictions.

        Returns:
            DataFrame with predicted values and confidence bounds.
        """
        original_var_names = [
            var.replace("LOG(", "").replace(")", "")
            for var in result.independent_vars
        ]
        missing = set(original_var_names) - set(data.columns)
        if missing:
            raise ValueError(f"Prediction data is missing variables: {sorted(missing)}")

        X = data[original_var_names].copy()
        if result.model_type == "log_log":
            if (X <= 0).any().any():
                raise ValueError("Prediction data contains non-positive values for log-log model.")
            X = np.log(X)
        if result.model_type == "semi_log":
            X = X.copy()

        if result.coefficients["Variable"].iloc[0] == "C (Intercept)":
            X = sm.add_constant(X, has_constant="add")

        prediction = result.raw_result.get_prediction(X)
        pred_summary = prediction.summary_frame(alpha=1 - confidence_level)

        mean = pred_summary["mean"]
        lower = pred_summary["mean_ci_lower"]
        upper = pred_summary["mean_ci_upper"]

        if result.model_type in ["log_log", "semi_log"]:
            mean = np.exp(mean)
            lower = np.exp(lower)
            upper = np.exp(upper)

        dep_var_clean = result.dependent_var.replace("LOG(", "").replace(")", "")
        return pd.DataFrame({
            "Predicted": mean.round(4),
            f"{dep_var_clean} (Predicted)": mean.round(4),
            f"Lower {confidence_level*100:.0f}%": lower.round(4),
            f"Upper {confidence_level*100:.0f}%": upper.round(4),
        }, index=data.index)

    def summary_text(self, result: Optional[RegressionResult] = None) -> str:
        """
        Generate an EViews-style text summary.

        Args:
            result: RegressionResult to summarize. Uses last result if None.

        Returns:
            Formatted text string.
        """
        if result is None:
            result = self._last_result
        if result is None:
            return "No regression result available."

        lines = []
        lines.append("=" * 72)
        lines.append(f"Dependent Variable: {result.dependent_var}")
        lines.append(f"Method: {result.estimation_method}")
        lines.append(f"Date: {result.run_timestamp}")
        lines.append(f"Sample: {result.sample_period}")
        lines.append(f"Included observations: {result.n_observations}")
        lines.append(f"Model specification: {result.model_type}")
        lines.append("=" * 72)
        lines.append("")

        # Coefficient table
        header = f"{'Variable':<20} {'Coefficient':>12} {'Std. Error':>12} {'t-Statistic':>12} {'Prob.':>10}"
        lines.append(header)
        lines.append("-" * 72)
        for _, row in result.coefficients.iterrows():
            lines.append(
                f"{row['Variable']:<20} "
                f"{row['Coefficient']:>12.6f} "
                f"{row['Std. Error']:>12.6f} "
                f"{row['t-Statistic']:>12.4f} "
                f"{row['Prob.']:>10.4f}"
            )
        lines.append("-" * 72)
        lines.append("")

        # Model statistics
        lines.append(f"R-squared:           {result.r_squared:>12.6f}    "
                      f"Mean dependent var:  {result.mean_dependent:>12.6f}")
        lines.append(f"Adjusted R-squared:  {result.adj_r_squared:>12.6f}    "
                      f"S.D. dependent var:  {result.sd_dependent:>12.6f}")
        lines.append(f"S.E. of regression:  {result.se_regression:>12.6f}    "
                      f"Akaike info crit.:   {result.aic:>12.4f}")
        lines.append(f"Sum squared resid:   {result.sum_squared_resid:>12.6f}    "
                      f"Schwarz criterion:   {result.bic:>12.4f}")
        lines.append(f"Log likelihood:      {result.log_likelihood:>12.4f}    "
                      f"Durbin-Watson stat:  {result.durbin_watson:>12.4f}")
        lines.append(f"F-statistic:         {result.f_statistic:>12.4f}    ")
        lines.append(f"Prob(F-statistic):   {result.prob_f_statistic:>12.6f}")
        lines.append("=" * 72)

        return "\n".join(lines)
