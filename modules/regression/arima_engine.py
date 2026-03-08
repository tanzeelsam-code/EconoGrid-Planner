"""
ARIMA / Time-Series Forecasting Engine.

Provides ARIMA, auto-order selection, and Holt-Winters ETS
as complementary forecasting methods to the OLS regression engine.
"""
import warnings
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

warnings.filterwarnings("ignore")

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.stattools import adfuller
    _HAS_SM = True
except ImportError:
    _HAS_SM = False


@dataclass
class ARIMAResult:
    model_type: str
    order: tuple
    seasonal_order: Optional[tuple]
    aic: float
    bic: float
    forecast_table: pd.DataFrame   # Year, Forecast, Lower_CI, Upper_CI
    forecast_years: int
    is_stationary: bool
    adf_pvalue: float
    residual_diagnostics: dict
    summary_text: str


class ARIMAEngine:
    """ARIMA / ETS forecasting for annual energy demand time series."""

    def _stationarity(self, s: pd.Series) -> Tuple[bool, float]:
        if not _HAS_SM:
            return True, 0.01
        try:
            p = float(adfuller(s.dropna())[1])
            return p < 0.05, p
        except Exception:
            return True, 0.05

    def _auto_order(self, s: pd.Series) -> Tuple[int, int, int]:
        is_stat, _ = self._stationarity(s)
        d, tmp = 0, s.copy()
        while not is_stat and d < 2:
            tmp = tmp.diff().dropna()
            is_stat, _ = self._stationarity(tmp)
            d += 1
        best_aic, best = np.inf, (1, d, 1)
        for p in range(4):
            for q in range(4):
                if p == q == 0:
                    continue
                try:
                    m = ARIMA(s, order=(p, d, q)).fit()
                    if m.aic < best_aic:
                        best_aic, best = m.aic, (p, d, q)
                except Exception:
                    pass
        return best

    def fit_arima(self, series: pd.Series, order: Optional[Tuple] = None,
                  forecast_years: int = 30, base_year: Optional[int] = None) -> ARIMAResult:
        if not _HAS_SM:
            return self._fallback(series, forecast_years, base_year)
        is_stat, adf_p = self._stationarity(series)
        if order is None:
            order = self._auto_order(series)
        base_year = base_year or 2023
        try:
            fitted = ARIMA(series, order=order).fit()
            fc_res = fitted.get_forecast(steps=forecast_years)
            fc_mean = fc_res.predicted_mean.values
            ci = fc_res.conf_int(alpha=0.05).values
            diag = {"mean_residual": float(fitted.resid.mean()),
                    "std_residual": float(fitted.resid.std())}
            try:
                from statsmodels.stats.diagnostic import acorr_ljungbox
                lb = acorr_ljungbox(fitted.resid, lags=[10], return_df=True)
                diag["ljung_box_pvalue"] = float(lb["lb_pvalue"].iloc[0])
            except Exception:
                pass
            summary = (f"ARIMA({order[0]},{order[1]},{order[2]})\n"
                       f"AIC: {fitted.aic:.4f}  BIC: {fitted.bic:.4f}\n"
                       f"ADF p-value: {adf_p:.4f}  Resid Std: {diag['std_residual']:.4f}")
            return ARIMAResult(
                model_type="ARIMA", order=order, seasonal_order=None,
                aic=float(fitted.aic), bic=float(fitted.bic),
                forecast_table=pd.DataFrame({
                    "Year": range(base_year, base_year + forecast_years),
                    "Forecast": fc_mean,
                    "Lower_CI": ci[:, 0],
                    "Upper_CI": ci[:, 1],
                }),
                forecast_years=forecast_years, is_stationary=is_stat,
                adf_pvalue=adf_p, residual_diagnostics=diag, summary_text=summary,
            )
        except Exception as e:
            return self._fallback(series, forecast_years, base_year, str(e))

    def fit_ets(self, series: pd.Series, forecast_years: int = 30,
                base_year: Optional[int] = None) -> ARIMAResult:
        if not _HAS_SM:
            return self._fallback(series, forecast_years, base_year)
        is_stat, adf_p = self._stationarity(series)
        base_year = base_year or 2023
        try:
            fitted = ExponentialSmoothing(series, trend="add",
                                          initialization_method="estimated").fit(optimized=True)
            fc_mean = fitted.forecast(forecast_years).values
            resid_std = float(fitted.resid.std())
            z = 1.96
            aic = float(getattr(fitted, "aic", 0))
            bic = float(getattr(fitted, "bic", 0))
            summary = (f"ETS (Holt-Winters additive trend)\n"
                       f"AIC: {aic:.4f}  BIC: {bic:.4f}\n"
                       f"Resid Std: {resid_std:.4f}")
            return ARIMAResult(
                model_type="ETS", order=(0, 0, 0), seasonal_order=None,
                aic=aic, bic=bic,
                forecast_table=pd.DataFrame({
                    "Year": range(base_year, base_year + forecast_years),
                    "Forecast": fc_mean,
                    "Lower_CI": fc_mean - z * resid_std,
                    "Upper_CI": fc_mean + z * resid_std,
                }),
                forecast_years=forecast_years, is_stationary=is_stat,
                adf_pvalue=adf_p,
                residual_diagnostics={"mean_residual": float(fitted.resid.mean()),
                                       "std_residual": resid_std},
                summary_text=summary,
            )
        except Exception as e:
            return self._fallback(series, forecast_years, base_year, str(e))

    def compare_models(self, series: pd.Series, forecast_years: int = 30,
                       base_year: Optional[int] = None) -> Dict[str, ARIMAResult]:
        return {
            "ARIMA": self.fit_arima(series, forecast_years=forecast_years, base_year=base_year),
            "ETS":   ARIMAEngine().fit_ets(series, forecast_years=forecast_years, base_year=base_year),
        }

    def _fallback(self, series: pd.Series, forecast_years: int,
                  base_year: Optional[int], msg: str = "") -> ARIMAResult:
        base_year = base_year or 2023
        n = len(series)
        x = np.arange(n)
        y = series.values.astype(float)
        m, b = np.polyfit(x, y, 1)
        resid_std = float(np.std(y - (m * x + b)))
        fc = m * np.arange(n, n + forecast_years) + b
        return ARIMAResult(
            model_type="Linear Trend (fallback)", order=(0, 1, 0), seasonal_order=None,
            aic=0.0, bic=0.0,
            forecast_table=pd.DataFrame({
                "Year": range(base_year, base_year + forecast_years),
                "Forecast": fc,
                "Lower_CI": fc - 1.96 * resid_std,
                "Upper_CI": fc + 1.96 * resid_std,
            }),
            forecast_years=forecast_years, is_stationary=False, adf_pvalue=1.0,
            residual_diagnostics={"mean_residual": 0.0, "std_residual": resid_std},
            summary_text=f"Linear trend fallback. {msg}",
        )
