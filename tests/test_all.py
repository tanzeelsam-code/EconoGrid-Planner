"""
Test suite — Econometric & Energy Modeling Toolkit.

Tests all three analytical modules with sample data:
- Module 1: Regression engine, diagnostics, forecast, Excel export
- Module 2: Scenario engine, emissions, supply, Excel export
- Module 3: Financial engine, LCOE, cash flow, sensitivity, Excel export
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.data_utils import (
    generate_sample_regression_data,
    generate_sample_energy_balance,
    generate_sample_financial_data,
)
from config import OUTPUT_DIR


# ═══════════════════════════════════════════════════════════════════════
# MODULE 1 — REGRESSION ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestRegressionEngine:
    """Tests for the EViews-equivalent regression module."""

    def setup_method(self):
        """Load sample data before each test."""
        self.data = generate_sample_regression_data()

    def test_ols_log_log(self):
        """Test log-log OLS regression runs and produces coefficients."""
        from modules.regression.regression_engine import RegressionEngine

        engine = RegressionEngine()
        result = engine.fit(
            data=self.data,
            dependent_var="Electricity_Demand_GWh",
            independent_vars=["GDP_Billion_USD", "Population_Million", "Electricity_Price_USD_kWh"],
            model_type="log_log",
        )

        assert result is not None
        assert result.r_squared > 0.9, f"R² too low: {result.r_squared}"
        assert result.n_observations == 30
        assert len(result.coefficients) == 4  # 3 vars + constant
        assert result.model_type == "log_log"

        # Check elasticities are reasonable
        elasticities = engine.get_elasticities(result)
        assert len(elasticities) == 3
        print(f"✅ Log-log regression: R²={result.r_squared:.4f}")

    def test_ols_linear(self):
        """Test linear OLS regression."""
        from modules.regression.regression_engine import RegressionEngine

        engine = RegressionEngine()
        result = engine.fit(
            data=self.data,
            dependent_var="Electricity_Demand_GWh",
            independent_vars=["GDP_Billion_USD", "Population_Million"],
            model_type="linear",
        )

        assert result is not None
        assert result.r_squared > 0.8
        assert result.model_type == "linear"
        print(f"✅ Linear regression: R²={result.r_squared:.4f}")

    def test_ols_semi_log(self):
        """Test semi-log OLS regression."""
        from modules.regression.regression_engine import RegressionEngine

        engine = RegressionEngine()
        result = engine.fit(
            data=self.data,
            dependent_var="Electricity_Demand_GWh",
            independent_vars=["GDP_Billion_USD", "Population_Million"],
            model_type="semi_log",
        )

        assert result is not None
        assert result.model_type == "semi_log"
        print(f"✅ Semi-log regression: R²={result.r_squared:.4f}")

    def test_summary_text(self):
        """Test EViews-style text summary generation."""
        from modules.regression.regression_engine import RegressionEngine

        engine = RegressionEngine()
        engine.fit(
            data=self.data,
            dependent_var="Electricity_Demand_GWh",
            independent_vars=["GDP_Billion_USD", "Population_Million"],
            model_type="log_log",
        )

        summary = engine.summary_text()
        assert "R-squared" in summary
        assert "Durbin-Watson" in summary
        assert "Coefficient" in summary
        print("✅ EViews summary text generated")


class TestDiagnostics:
    """Tests for regression diagnostics."""

    def test_all_diagnostics(self):
        """Test full diagnostic suite runs without error."""
        from modules.regression.regression_engine import RegressionEngine
        from modules.regression.diagnostics import RegressionDiagnostics

        data = generate_sample_regression_data()
        engine = RegressionEngine()
        result = engine.fit(
            data=data,
            dependent_var="Electricity_Demand_GWh",
            independent_vars=["GDP_Billion_USD", "Population_Million"],
            model_type="log_log",
        )

        diagnostics = RegressionDiagnostics.run_all(result)
        assert "normality_test" in diagnostics
        assert "heteroskedasticity_test" in diagnostics
        assert "serial_correlation_test" in diagnostics
        assert "durbin_watson" in diagnostics
        assert "multicollinearity" in diagnostics

        # Summary table
        table = RegressionDiagnostics.summary_table(diagnostics)
        assert len(table) >= 3
        print(f"✅ Diagnostics complete: {len(diagnostics)} tests")


class TestForecastEngine:
    """Tests for the forecast engine."""

    def test_forecast_generation(self):
        """Test 30-year forecast generation."""
        from modules.regression.regression_engine import RegressionEngine
        from modules.regression.forecast_engine import ForecastEngine

        data = generate_sample_regression_data()
        reg = RegressionEngine()
        result = reg.fit(
            data=data,
            dependent_var="Electricity_Demand_GWh",
            independent_vars=["GDP_Billion_USD", "Population_Million"],
            model_type="log_log",
        )

        forecast = ForecastEngine()
        fc = forecast.generate_forecast(
            regression_result=result,
            original_data=data,
            forecast_years=30,
            growth_assumptions={
                "GDP_Billion_USD": 0.04,
                "Population_Million": 0.02,
            },
        )

        assert fc.forecast_table is not None
        assert len(fc.forecast_table) == 30
        assert fc.forecast_years == 30
        print(f"✅ 30-year forecast generated: {len(fc.forecast_table)} rows")


class TestRegressionExcelExport:
    """Tests for regression Excel export."""

    def test_export(self):
        """Test Excel workbook creation."""
        from modules.regression.regression_engine import RegressionEngine
        from modules.regression.diagnostics import RegressionDiagnostics
        from modules.regression.forecast_engine import ForecastEngine
        from modules.regression.excel_export import RegressionExcelExport

        data = generate_sample_regression_data()
        reg = RegressionEngine()
        result = reg.fit(data=data, dependent_var="Electricity_Demand_GWh",
                         independent_vars=["GDP_Billion_USD", "Population_Million"],
                         model_type="log_log")
        diagnostics = RegressionDiagnostics.run_all(result)
        fc_engine = ForecastEngine()
        fc = fc_engine.generate_forecast(result, data, 30,
                                          {"GDP_Billion_USD": 0.04, "Population_Million": 0.02})

        exporter = RegressionExcelExport(str(OUTPUT_DIR))
        path = exporter.export(result, diagnostics, fc)
        assert os.path.exists(path)
        print(f"✅ Regression Excel exported: {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════
# MODULE 2 — SCENARIO ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestLEAPModel:
    """Tests for the LEAP-equivalent model."""

    def setup_method(self):
        self.config = generate_sample_energy_balance()

    def test_base_year(self):
        from modules.scenario.leap_model import LEAPModel
        model = LEAPModel(self.config)
        summary = model.get_base_year_summary()
        assert summary["total_demand_pj"] > 0
        assert len(summary["demand_by_sector"]) == 5
        print(f"✅ Base year: {summary['total_demand_pj']:.2f} PJ")

    def test_scenarios_available(self):
        from modules.scenario.leap_model import LEAPModel
        model = LEAPModel(self.config)
        names = model.get_scenario_names()
        assert "BAU" in names
        assert "Low Carbon" in names
        assert "High Growth" in names
        print(f"✅ Scenarios: {names}")


class TestScenarioEngine:
    """Tests for the scenario engine."""

    def test_run_all_scenarios(self):
        from modules.scenario.leap_model import LEAPModel
        from modules.scenario.scenario_engine import ScenarioEngine

        model = LEAPModel(generate_sample_energy_balance())
        engine = ScenarioEngine(model)
        results = engine.run_all_scenarios()

        assert len(results) == 3
        comparison = engine.get_comparison_table()
        assert len(comparison) > 0
        summary = engine.get_scenario_summary()
        assert len(summary) == 3
        print(f"✅ All 3 scenarios complete: {list(results.keys())}")


class TestEmissionsEngine:
    """Tests for emissions calculations."""

    def test_emissions(self):
        from modules.scenario.leap_model import LEAPModel
        from modules.scenario.scenario_engine import ScenarioEngine
        from modules.scenario.emissions_engine import EmissionsEngine

        config = generate_sample_energy_balance()
        model = LEAPModel(config)
        engine = ScenarioEngine(model)
        results = engine.run_all_scenarios()

        em_engine = EmissionsEngine(config["emission_factors_kg_CO2_per_GJ"])
        gen_mix = config["supply"]["generation_mix_base_year"]

        for name, result in results.items():
            demand_em = em_engine.calculate_demand_emissions(result)
            supply_em = em_engine.calculate_supply_emissions(result, gen_mix)
            total = em_engine.get_total_emissions(demand_em, supply_em)
            assert len(total) > 0
            print(f"  ✅ {name}: {total['Total Emissions (Mt CO₂)'].iloc[-1]:.2f} Mt CO₂")


class TestScenarioExcelExport:
    """Tests for scenario Excel export."""

    def test_export(self):
        from modules.scenario.leap_model import LEAPModel
        from modules.scenario.scenario_engine import ScenarioEngine
        from modules.scenario.emissions_engine import EmissionsEngine
        from modules.scenario.excel_export import ScenarioExcelExport

        config = generate_sample_energy_balance()
        model = LEAPModel(config)
        engine = ScenarioEngine(model)
        results = engine.run_all_scenarios()
        comparison = engine.get_comparison_table()

        exporter = ScenarioExcelExport(str(OUTPUT_DIR))
        path = exporter.export(
            config=config,
            base_year_summary=model.get_base_year_summary(),
            scenario_results=results,
            demand_comparison=comparison,
        )
        assert os.path.exists(path)
        print(f"✅ Scenario Excel exported: {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════
# MODULE 3 — FINANCIAL ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestFinanceEngine:
    """Tests for the RETScreen-equivalent financial module."""

    def setup_method(self):
        self.project_data = generate_sample_financial_data()

    def test_full_analysis(self):
        from modules.financial.finance_engine import FinanceEngine
        engine = FinanceEngine(self.project_data)
        result = engine.run_analysis()

        assert result.lcoe > 0
        assert result.npv is not None
        assert result.cashflow_table is not None
        assert len(result.cashflow_table) == 26  # Year 0 + 25 years
        print(f"✅ LCOE={result.lcoe:.2f}, NPV={result.npv:,.0f}, FIRR={result.firr}, EIRR={result.eirr}")

    def test_payback(self):
        from modules.financial.finance_engine import FinanceEngine
        engine = FinanceEngine(self.project_data)
        result = engine.run_analysis()

        if result.payback_period:
            assert result.payback_period > 0
            assert result.payback_period < self.project_data["project_life_years"]
            print(f"✅ Payback: {result.payback_period:.1f} years")

    def test_bcr(self):
        from modules.financial.finance_engine import FinanceEngine
        engine = FinanceEngine(self.project_data)
        result = engine.run_analysis()

        assert result.benefit_cost_ratio > 0
        print(f"✅ B/C Ratio: {result.benefit_cost_ratio:.3f}")


class TestLCOECalculator:
    """Tests for standalone LCOE calculator."""

    def test_lcoe(self):
        from modules.financial.lcoe import LCOECalculator
        calc = LCOECalculator()
        result = calc.calculate(
            capex=45_000_000,
            annual_opex=650_000,
            annual_generation=96_360,
            project_life=25,
            discount_rate=0.08,
        )

        assert result.lcoe > 0
        assert result.lcoe < 200  # Reasonable for solar PV
        assert result.lcoe_capex_component + result.lcoe_opex_component == pytest.approx(result.lcoe, abs=0.1)
        print(f"✅ LCOE: ${result.lcoe:.2f}/MWh (CAPEX: ${result.lcoe_capex_component:.2f}, OPEX: ${result.lcoe_opex_component:.2f})")


class TestSensitivityAnalyzer:
    """Tests for sensitivity analysis."""

    def test_sensitivity(self):
        from modules.financial.sensitivity import SensitivityAnalyzer
        data = generate_sample_financial_data()
        analyzer = SensitivityAnalyzer(data)
        results = analyzer.run_sensitivity()

        assert "lcoe" in results
        assert "npv" in results
        assert "irr" in results
        assert len(results["npv"]) > 0

        tornado = analyzer.get_tornado_data(results)
        assert len(tornado) > 0
        print(f"✅ Sensitivity: {len(results['npv'])} parameters analyzed")


class TestFinancialExcelExport:
    """Tests for financial Excel export."""

    def test_export(self):
        from modules.financial.finance_engine import FinanceEngine
        from modules.financial.lcoe import LCOECalculator
        from modules.financial.sensitivity import SensitivityAnalyzer
        from modules.financial.excel_export import FinancialExcelExport

        data = generate_sample_financial_data()
        engine = FinanceEngine(data)
        result = engine.run_analysis()

        lcoe_calc = LCOECalculator()
        lcoe = lcoe_calc.calculate(data["capex_total_usd"], data["annual_opex_usd"],
                                    data["annual_generation_mwh"], data["project_life_years"],
                                    data["discount_rate"])

        sens = SensitivityAnalyzer(data)
        sens_results = sens.run_sensitivity()
        tornado = sens.get_tornado_data(sens_results)

        exporter = FinancialExcelExport(str(OUTPUT_DIR))
        path = exporter.export(result, lcoe, sens_results, tornado, data)
        assert os.path.exists(path)
        print(f"✅ Financial Excel exported: {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests for the Flask dashboard."""

    def test_app_creation(self):
        """Test Flask app creates successfully."""
        from dashboard.app import create_app
        app = create_app()
        assert app is not None
        print("✅ Flask app created")

    def test_health_endpoint(self):
        """Test health check endpoint."""
        from dashboard.app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        print("✅ Health endpoint OK")

    def test_index_page(self):
        """Test index page loads."""
        from dashboard.app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 200
        assert b"Econometric" in response.data
        print("✅ Index page loads")

    def test_module_pages(self):
        """Test all module pages load."""
        from dashboard.app import create_app
        app = create_app()
        client = app.test_client()

        for path in ["/regression", "/scenario", "/financial"]:
            response = client.get(path)
            assert response.status_code == 200, f"Failed: {path}"
            print(f"  ✅ {path} loads")

    def test_regression_api(self):
        """Test regression API endpoint."""
        from dashboard.app import create_app
        app = create_app()
        client = app.test_client()
        response = client.post("/api/regression/run",
                               json={},
                               content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        print("✅ Regression API returns success")

    def test_scenario_api(self):
        """Test scenario API endpoint."""
        from dashboard.app import create_app
        app = create_app()
        client = app.test_client()
        response = client.post("/api/scenario/run",
                               json={},
                               content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        print("✅ Scenario API returns success")

    def test_financial_api(self):
        """Test financial API endpoint."""
        from dashboard.app import create_app
        app = create_app()
        client = app.test_client()
        response = client.post("/api/financial/run",
                               json={},
                               content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        print("✅ Financial API returns success")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
