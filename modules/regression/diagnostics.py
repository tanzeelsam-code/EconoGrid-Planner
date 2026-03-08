"""
Regression Diagnostics — Statistical Tests and Residual Analysis.

Provides post-estimation diagnostic checks analogous to EViews:
- Normality test (Jarque-Bera)
- Heteroskedasticity test (Breusch-Pagan)
- Serial correlation test (Breusch-Godfrey / LM)
- Multicollinearity check (VIF)
- Residual summary statistics
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import (
    het_breuschpagan,
    acorr_breusch_godfrey,
)
from statsmodels.stats.stattools import jarque_bera
from statsmodels.stats.outliers_influence import variance_inflation_factor
from typing import Dict, Any, Optional
from .regression_engine import RegressionResult


class RegressionDiagnostics:
    """
    Post-estimation diagnostics for OLS regression.

    Runs a battery of standard tests and produces a diagnostic
    summary table similar to EViews' equation diagnostics panel.
    """

    @staticmethod
    def run_all(result: RegressionResult) -> Dict[str, Any]:
        """
        Run all diagnostic tests on a regression result.

        Args:
            result: RegressionResult from the regression engine.

        Returns:
            Dictionary with all diagnostic test results.
        """
        diagnostics = {}

        # ── Residual summary ───────────────────────────────────────────────
        resid = result.residuals
        diagnostics["residual_summary"] = {
            "Mean": round(float(resid.mean()), 8),
            "Median": round(float(resid.median()), 8),
            "Std. Dev.": round(float(resid.std()), 6),
            "Skewness": round(float(resid.skew()), 6),
            "Kurtosis": round(float(resid.kurtosis() + 3), 6),  # Excess -> normal
            "Min": round(float(resid.min()), 6),
            "Max": round(float(resid.max()), 6),
        }

        # ── Jarque-Bera normality test ─────────────────────────────────────
        jb_stat, jb_pvalue, jb_skew, jb_kurtosis = jarque_bera(resid)
        diagnostics["normality_test"] = {
            "test": "Jarque-Bera",
            "statistic": round(float(jb_stat), 4),
            "p_value": round(float(jb_pvalue), 6),
            "conclusion": "Normal" if jb_pvalue > 0.05 else "Non-normal (reject H0)",
            "skewness": round(float(jb_skew), 6),
            "kurtosis": round(float(jb_kurtosis), 6),
        }

        # ── Breusch-Pagan heteroskedasticity test ──────────────────────────
        try:
            raw = result.raw_result
            bp_stat, bp_pvalue, bp_fstat, bp_fpvalue = het_breuschpagan(
                raw.resid, raw.model.exog
            )
            diagnostics["heteroskedasticity_test"] = {
                "test": "Breusch-Pagan",
                "LM_statistic": round(float(bp_stat), 4),
                "LM_p_value": round(float(bp_pvalue), 6),
                "F_statistic": round(float(bp_fstat), 4),
                "F_p_value": round(float(bp_fpvalue), 6),
                "conclusion": (
                    "Homoskedastic" if bp_pvalue > 0.05
                    else "Heteroskedastic (reject H0)"
                ),
            }
        except Exception as e:
            diagnostics["heteroskedasticity_test"] = {
                "test": "Breusch-Pagan",
                "error": str(e),
            }

        # ── Breusch-Godfrey serial correlation test (lag=2) ────────────────
        try:
            raw = result.raw_result
            bg_result = acorr_breusch_godfrey(raw, nlags=2)
            bg_stat, bg_pvalue = bg_result[0], bg_result[1]
            diagnostics["serial_correlation_test"] = {
                "test": "Breusch-Godfrey LM",
                "lags": 2,
                "LM_statistic": round(float(bg_stat), 4),
                "p_value": round(float(bg_pvalue), 6),
                "conclusion": (
                    "No serial correlation" if bg_pvalue > 0.05
                    else "Serial correlation detected"
                ),
            }
        except Exception as e:
            diagnostics["serial_correlation_test"] = {
                "test": "Breusch-Godfrey LM",
                "error": str(e),
            }

        # ── Durbin-Watson ──────────────────────────────────────────────────
        diagnostics["durbin_watson"] = {
            "statistic": result.durbin_watson,
            "interpretation": RegressionDiagnostics._interpret_dw(
                result.durbin_watson
            ),
        }

        # ── VIF for multicollinearity ──────────────────────────────────────
        try:
            raw = result.raw_result
            exog = raw.model.exog
            # Skip constant column (index 0) for VIF
            vif_data = []
            start_idx = 1 if "const" in raw.model.exog_names or \
                            raw.model.exog_names[0] == "const" else 0

            for i in range(start_idx, exog.shape[1]):
                vif_val = variance_inflation_factor(exog, i)
                vif_data.append({
                    "Variable": raw.model.exog_names[i],
                    "VIF": round(float(vif_val), 4),
                    "Tolerance": round(1.0 / float(vif_val), 4) if vif_val > 0 else 0,
                })

            diagnostics["multicollinearity"] = {
                "test": "Variance Inflation Factor",
                "results": vif_data,
                "warning": any(v["VIF"] > 10 for v in vif_data),
            }
        except Exception as e:
            diagnostics["multicollinearity"] = {
                "test": "VIF",
                "error": str(e),
            }

        # ── Model information criteria ─────────────────────────────────────
        diagnostics["information_criteria"] = {
            "AIC": result.aic,
            "BIC (Schwarz)": result.bic,
            "Log-Likelihood": result.log_likelihood,
        }

        return diagnostics

    @staticmethod
    def _interpret_dw(dw: float) -> str:
        """Interpret Durbin-Watson statistic value."""
        if dw < 1.0:
            return "Strong positive autocorrelation"
        elif dw < 1.5:
            return "Possible positive autocorrelation"
        elif dw <= 2.5:
            return "No significant autocorrelation"
        elif dw <= 3.0:
            return "Possible negative autocorrelation"
        else:
            return "Strong negative autocorrelation"

    @staticmethod
    def summary_table(diagnostics: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert diagnostic results into a summary DataFrame.

        Args:
            diagnostics: Output from run_all().

        Returns:
            DataFrame with test names, statistics, p-values, and conclusions.
        """
        rows = []

        # Normality
        norm = diagnostics.get("normality_test", {})
        if "error" not in norm:
            rows.append({
                "Test": "Jarque-Bera Normality",
                "Statistic": norm.get("statistic"),
                "P-Value": norm.get("p_value"),
                "Conclusion": norm.get("conclusion"),
            })

        # Heteroskedasticity
        het = diagnostics.get("heteroskedasticity_test", {})
        if "error" not in het:
            rows.append({
                "Test": "Breusch-Pagan (Heteroskedasticity)",
                "Statistic": het.get("LM_statistic"),
                "P-Value": het.get("LM_p_value"),
                "Conclusion": het.get("conclusion"),
            })

        # Serial correlation
        sc = diagnostics.get("serial_correlation_test", {})
        if "error" not in sc:
            rows.append({
                "Test": "Breusch-Godfrey LM (Serial Corr.)",
                "Statistic": sc.get("LM_statistic"),
                "P-Value": sc.get("p_value"),
                "Conclusion": sc.get("conclusion"),
            })

        # Durbin-Watson
        dw = diagnostics.get("durbin_watson", {})
        rows.append({
            "Test": "Durbin-Watson",
            "Statistic": dw.get("statistic"),
            "P-Value": "—",
            "Conclusion": dw.get("interpretation"),
        })

        return pd.DataFrame(rows)
