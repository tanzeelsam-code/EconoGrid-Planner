"""
Advanced Test Suite — EconoGrid Planner v2.0

Tests for new modules:
  - Monte Carlo (modules/financial/monte_carlo.py)
  - ARIMA/ETS   (modules/regression/arima_engine.py)
  - RE Targets  (modules/scenario/renewable_targets.py)
  - Validation  (utils/validation.py)
  - Cache       (utils/cache.py)
  - Advanced routes (/api/advanced/*)
"""
import os
import sys
import time
import tempfile
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.data_utils import (
    generate_sample_regression_data,
    generate_sample_energy_balance,
    generate_sample_financial_data,
)
from config import OUTPUT_DIR


# ═══════════════════════════════════════════════════════════════════════
# MONTE CARLO
# ═══════════════════════════════════════════════════════════════════════

class TestMonteCarlo:

    def setup_method(self):
        self.data = generate_sample_financial_data()

    def test_runs(self):
        from modules.financial.monte_carlo import MonteCarloSimulator
        r = MonteCarloSimulator(self.data, n_simulations=300, seed=42).run()
        assert r.n_simulations > 0
        assert len(r.npv_distribution) > 0
        print(f"✅ Monte Carlo: {r.n_simulations} simulations")

    def test_percentiles_ordered(self):
        from modules.financial.monte_carlo import MonteCarloSimulator
        r = MonteCarloSimulator(self.data, n_simulations=300, seed=42).run()
        assert r.npv_p10 <= r.npv_p50 <= r.npv_p90
        assert r.lcoe_p10 <= r.lcoe_p50 <= r.lcoe_p90
        print(f"✅ NPV P10/P50/P90: {r.npv_p10:,.0f} / {r.npv_p50:,.0f} / {r.npv_p90:,.0f}")

    def test_prob_positive_npv(self):
        from modules.financial.monte_carlo import MonteCarloSimulator
        r = MonteCarloSimulator(self.data, n_simulations=300, seed=42).run()
        assert 0.0 <= r.prob_positive_npv <= 1.0
        print(f"✅ Prob(NPV>0): {r.prob_positive_npv*100:.1f}%")

    def test_param_correlations(self):
        from modules.financial.monte_carlo import MonteCarloSimulator
        r = MonteCarloSimulator(self.data, n_simulations=300, seed=42).run()
        for name, c in r.param_correlations.items():
            assert -1.0 <= c <= 1.0, f"Correlation out of range: {name}={c}"
        print(f"✅ Correlations: {r.param_correlations}")

    def test_histogram_structure(self):
        from modules.financial.monte_carlo import MonteCarloSimulator
        r = MonteCarloSimulator(self.data, n_simulations=300, seed=42).run()
        for metric in ["npv", "irr", "lcoe"]:
            h = r.histogram_data[metric]
            assert "counts" in h and "edges" in h and "mean" in h
            assert len(h["edges"]) == len(h["counts"]) + 1
        print("✅ Histogram structure OK")

    def test_reproducible(self):
        from modules.financial.monte_carlo import MonteCarloSimulator
        r1 = MonteCarloSimulator(self.data, n_simulations=100, seed=7).run()
        r2 = MonteCarloSimulator(self.data, n_simulations=100, seed=7).run()
        assert r1.npv_p50 == r2.npv_p50
        print("✅ Reproducible with same seed")


# ═══════════════════════════════════════════════════════════════════════
# ARIMA ENGINE
# ═══════════════════════════════════════════════════════════════════════

class TestARIMAEngine:

    def setup_method(self):
        df = generate_sample_regression_data()
        self.series = pd.Series(df["Electricity_Demand_GWh"].values)

    def test_arima_fit(self):
        from modules.regression.arima_engine import ARIMAEngine
        r = ARIMAEngine().fit_arima(self.series, forecast_years=10, base_year=2023)
        assert r is not None
        assert len(r.forecast_table) == 10
        assert {"Year", "Forecast", "Lower_CI", "Upper_CI"}.issubset(r.forecast_table.columns)
        print(f"✅ ARIMA({r.order}): AIC={r.aic:.2f}")

    def test_ets_fit(self):
        from modules.regression.arima_engine import ARIMAEngine
        r = ARIMAEngine().fit_ets(self.series, forecast_years=10, base_year=2023)
        assert len(r.forecast_table) == 10
        print(f"✅ ETS: AIC={r.aic:.2f}")

    def test_ci_ordering(self):
        from modules.regression.arima_engine import ARIMAEngine
        r = ARIMAEngine().fit_arima(self.series, forecast_years=10, base_year=2023)
        for _, row in r.forecast_table.iterrows():
            assert row["Lower_CI"] <= row["Upper_CI"]
        print("✅ CI ordering correct")

    def test_compare_models(self):
        from modules.regression.arima_engine import ARIMAEngine
        results = ARIMAEngine().compare_models(self.series, forecast_years=5, base_year=2023)
        assert "ARIMA" in results and "ETS" in results
        print(f"✅ compare_models: {list(results.keys())}")

    def test_stationarity(self):
        from modules.regression.arima_engine import ARIMAEngine
        is_stat, pval = ARIMAEngine()._stationarity(self.series)
        assert isinstance(is_stat, bool)
        assert 0.0 <= pval <= 1.0
        print(f"✅ Stationarity ADF p={pval:.4f}")

    def test_summary_nonempty(self):
        from modules.regression.arima_engine import ARIMAEngine
        r = ARIMAEngine().fit_arima(self.series, forecast_years=5, base_year=2023)
        assert len(r.summary_text) > 20
        print("✅ Summary text generated")


# ═══════════════════════════════════════════════════════════════════════
# RENEWABLE TARGETS
# ═══════════════════════════════════════════════════════════════════════

class TestRenewableTargets:

    def setup_method(self):
        from modules.scenario.renewable_targets import RenewableTargetTracker
        self.tracker = RenewableTargetTracker(baseline_re_share_pct=18.0,
                                              total_capacity_gw=5.0,
                                              annual_demand_twh=50.0)

    def test_track_bau(self):
        r = self.tracker.track_targets("BAU", 2050)
        assert r.scenario == "BAU" and r.target_year == 2050
        assert len(r.annual_share_table) > 0
        print(f"✅ BAU: {r.target_pct}% by 2050, on_track={r.on_track}")

    def test_low_carbon_high_target(self):
        r = self.tracker.track_targets("Low Carbon", 2050)
        assert r.target_pct >= 50.0
        print(f"✅ Low Carbon: {r.target_pct}% target")

    def test_table_structure(self):
        r = self.tracker.track_targets("BAU", 2050)
        required = {"Year", "Renewable_Share_Pct", "RE_Capacity_GW", "Annual_Investment_MUSD"}
        assert required.issubset(r.annual_share_table.columns)
        assert r.annual_share_table["Renewable_Share_Pct"].between(0, 100).all()
        print("✅ Annual table structure OK")

    def test_avoided_emissions(self):
        r = self.tracker.track_targets("Low Carbon", 2050)
        assert r.avoided_emissions_mt > 0
        print(f"✅ Avoided: {r.avoided_emissions_mt:.1f} Mt CO₂")

    def test_tech_costs_decline(self):
        r = self.tracker.track_targets("BAU", 2050)
        for tech, proj in r.tech_cost_projections.items():
            assert proj.costs[0] >= proj.costs[-1], f"{tech} costs should decline"
        print(f"✅ Tech costs decline: {list(r.tech_cost_projections.keys())}")

    def test_compare_scenarios(self):
        df = self.tracker.compare_scenarios(2050)
        assert len(df) == 3
        assert set(df["Scenario"]) == {"BAU", "Low Carbon", "High Growth"}
        print(f"✅ Scenario comparison:\n{df.to_string(index=False)}")


# ═══════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════

class TestValidation:

    def test_financial_valid(self):
        from utils.validation import FinancialInputValidator
        cleaned, warns = FinancialInputValidator.validate({"discount_rate": 0.08})
        assert cleaned["discount_rate"] == 0.08
        print(f"✅ Financial valid: warnings={warns}")

    def test_financial_invalid_rate(self):
        from utils.validation import FinancialInputValidator, ValidationError
        with pytest.raises(ValidationError):
            FinancialInputValidator.validate({"discount_rate": 5.0})
        print("✅ ValidationError for discount_rate=5.0")

    def test_regression_valid(self):
        from utils.validation import RegressionInputValidator
        cleaned, _ = RegressionInputValidator.validate({"model_type": "log_log"})
        assert cleaned["model_type"] == "log_log"
        print("✅ Regression validation OK")

    def test_regression_bad_model(self):
        from utils.validation import RegressionInputValidator, ValidationError
        with pytest.raises(ValidationError):
            RegressionInputValidator.validate({"model_type": "random_forest"})
        print("✅ ValidationError for unsupported model_type")

    def test_scenario_valid(self):
        from utils.validation import ScenarioInputValidator
        cleaned, _ = ScenarioInputValidator.validate({"base_year": 2022})
        assert cleaned["base_year"] == 2022
        print("✅ Scenario validation OK")

    def test_upload_filename(self):
        from utils.validation import UploadValidator
        ok, _ = UploadValidator.validate_filename("data.csv")
        assert ok
        bad, _ = UploadValidator.validate_filename("file;rm.csv")
        assert not bad
        print("✅ Filename validation OK")

    def test_upload_size(self):
        from utils.validation import UploadValidator
        ok, _ = UploadValidator.validate_dataframe_size(100, 10)
        assert ok
        bad, _ = UploadValidator.validate_dataframe_size(0, 5)
        assert not bad
        print("✅ DataFrame size validation OK")


# ═══════════════════════════════════════════════════════════════════════
# CACHE & HISTORY
# ═══════════════════════════════════════════════════════════════════════

class TestCacheAndHistory:

    def test_set_get(self):
        from utils.cache import AnalysisCache
        c = AnalysisCache(10)
        c.set("regression", {"a": 1}, {"result": 42})
        assert c.get("regression", {"a": 1})["result"] == 42
        print("✅ Cache set/get OK")

    def test_miss(self):
        from utils.cache import AnalysisCache
        assert AnalysisCache().get("regression", {"x": "unknown"}) is None
        print("✅ Cache miss returns None")

    def test_expiry(self):
        from utils.cache import AnalysisCache
        c = AnalysisCache()
        c.set("financial", {"t": 1}, {"v": 1}, ttl=0.01)
        time.sleep(0.05)
        assert c.get("financial", {"t": 1}) is None
        print("✅ Cache TTL expiry OK")

    def test_invalidate_module(self):
        from utils.cache import AnalysisCache
        c = AnalysisCache()
        c.set("regression", {"a": 1}, {"x": 1})
        c.set("financial",  {"b": 2}, {"y": 2})
        c.invalidate("regression")
        assert c.get("regression", {"a": 1}) is None
        assert c.get("financial",  {"b": 2}) is not None
        print("✅ Module invalidation OK")

    def test_stats(self):
        from utils.cache import AnalysisCache
        c = AnalysisCache()
        c.set("scenario", {"p": 1}, True)
        c.get("scenario", {"p": 1})
        c.get("scenario", {"p": 2})
        s = c.get_stats()
        assert s["hits"] >= 1 and s["misses"] >= 1
        print(f"✅ Cache stats: {s}")

    def test_history_record(self):
        from utils.cache import AnalysisHistoryManager
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            hf = f.name
        try:
            h = AnalysisHistoryManager(hf)
            rid = h.record("regression", {"m": "log_log"}, {"r2": 0.95}, 1.0, True)
            recs = h.get_recent("regression", 5)
            assert len(recs) >= 1 and recs[0]["module"] == "regression"
            print(f"✅ History record: id={rid}")
        finally:
            os.unlink(hf)

    def test_history_stats(self):
        from utils.cache import AnalysisHistoryManager
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            hf = f.name
        try:
            h = AnalysisHistoryManager(hf)
            h.record("financial",  {}, {}, 2.0, True)
            h.record("financial",  {}, {}, 0.5, False, "err")
            h.record("regression", {}, {}, 1.0, True)
            s = h.get_stats()
            assert s["total_runs"] == 3
            assert s["by_module"]["financial"]["count"] == 2
            print(f"✅ History stats: {s}")
        finally:
            os.unlink(hf)


# ═══════════════════════════════════════════════════════════════════════
# ADVANCED ROUTES INTEGRATION
# ═══════════════════════════════════════════════════════════════════════

class TestAdvancedRoutes:

    def setup_method(self):
        from dashboard.app import create_app
        self.client = create_app().test_client()

    def test_monte_carlo(self):
        r = self.client.post("/api/advanced/monte-carlo",
                             json={"n_simulations": 200},
                             content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "success" and "npv" in d and "prob_positive_npv_pct" in d
        print(f"✅ /api/advanced/monte-carlo P50 NPV={d['npv']['p50']:,.0f}")

    def test_arima(self):
        r = self.client.post("/api/advanced/arima",
                             json={"forecast_years": 10},
                             content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "success" and len(d["forecast"]) == 10
        print(f"✅ /api/advanced/arima: {len(d['forecast'])} rows")

    def test_renewable_targets(self):
        r = self.client.post("/api/advanced/renewable-targets",
                             json={"target_year": 2050},
                             content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "success" and "scenarios" in d
        print(f"✅ /api/advanced/renewable-targets: {list(d['scenarios'].keys())}")

    def test_cache_stats(self):
        r = self.client.get("/api/advanced/cache/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "success" and "cache" in d
        print(f"✅ /api/advanced/cache/stats OK")

    def test_history(self):
        r = self.client.get("/api/advanced/history?limit=5")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "success" and "history" in d and "stats" in d
        print(f"✅ /api/advanced/history OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
