"""
Advanced API Routes — EconoGrid Planner v2.

New endpoints:
  POST /api/advanced/monte-carlo        — Monte Carlo risk simulation
  POST /api/advanced/arima              — ARIMA / ETS time-series forecast
  POST /api/advanced/renewable-targets  — RE target tracking & tech costs
  POST /api/advanced/report/financial   — HTML financial report (download)
  POST /api/advanced/report/regression  — HTML regression report (download)
  POST /api/advanced/report/scenario    — HTML scenario report (download)
  GET  /api/advanced/cache/stats        — Cache statistics
  POST /api/advanced/cache/clear        — Clear cache
  GET  /api/advanced/history            — Analysis run history
  POST /api/advanced/history/clear      — Clear history
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from flask import Blueprint, current_app, jsonify, request, send_file

advanced_bp = Blueprint("advanced", __name__)


# ── Monte Carlo ────────────────────────────────────────────────────────────────

@advanced_bp.route("/monte-carlo", methods=["POST"])
def run_monte_carlo():
    try:
        from modules.financial.monte_carlo import MonteCarloSimulator
        from utils.data_utils import generate_sample_financial_data
        from utils.cache import get_cache, get_history

        data = request.get_json(silent=True) or {}
        params = generate_sample_financial_data()
        params.update(data)
        n_sim = int(data.get("n_simulations", 5000))
        seed  = int(data.get("seed", 42))

        cache = get_cache()
        ck = {**{k: v for k, v in params.items() if not callable(v)},
              "n_simulations": n_sim, "seed": seed}
        cached = cache.get("monte_carlo", ck)
        if cached:
            return jsonify({**cached, "cached": True})

        t0 = time.time()
        r = MonteCarloSimulator(params, n_simulations=n_sim, seed=seed).run()
        dur = round(time.time() - t0, 2)

        resp = {
            "status": "success",
            "n_simulations": r.n_simulations,
            "npv":  {"p10": round(r.npv_p10), "p50": round(r.npv_p50),
                     "p90": round(r.npv_p90), "histogram": r.histogram_data["npv"]},
            "irr":  {"p10": round(r.irr_p10*100,2), "p50": round(r.irr_p50*100,2),
                     "p90": round(r.irr_p90*100,2), "histogram": r.histogram_data["irr"]},
            "lcoe": {"p10": round(r.lcoe_p10,2), "p50": round(r.lcoe_p50,2),
                     "p90": round(r.lcoe_p90,2), "histogram": r.histogram_data["lcoe"]},
            "prob_positive_npv_pct": round(r.prob_positive_npv * 100, 1),
            "param_correlations": r.param_correlations,
            "duration_seconds": dur,
            "cached": False,
        }
        cache.set("monte_carlo", ck, resp)
        get_history().record("financial", {"module": "monte_carlo", "n_sim": n_sim},
                             {"prob_positive_npv": resp["prob_positive_npv_pct"]}, dur, True)
        return jsonify(resp)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ── ARIMA ──────────────────────────────────────────────────────────────────────

@advanced_bp.route("/arima", methods=["POST"])
def run_arima():
    try:
        import pandas as pd
        from modules.regression.arima_engine import ARIMAEngine
        from utils.cache import get_cache, get_history

        data = request.get_json(silent=True) or {}
        series_data   = data.get("series")
        base_year     = int(data.get("base_year", 2022))
        forecast_years= int(data.get("forecast_years", 30))
        method        = data.get("method", "arima").lower()
        order         = data.get("order")
        if order:
            order = tuple(int(x) for x in order[:3])

        if not series_data:
            from utils.data_utils import generate_sample_regression_data
            df = generate_sample_regression_data()
            series_data = df["Electricity_Demand_GWh"].tolist()
            base_year   = int(df["Year"].max()) + 1

        series = pd.Series(series_data, name="demand")
        cache = get_cache()
        ck = {"series_len": len(series_data), "method": method,
              "forecast_years": forecast_years, "base_year": base_year}
        cached = cache.get("arima", ck)
        if cached:
            return jsonify({**cached, "cached": True})

        t0 = time.time()
        engine = ARIMAEngine()

        if method == "compare":
            results = engine.compare_models(series, forecast_years, base_year)
            resp = {"status": "success", "method": "compare", "results": {
                name: {"model_type": r.model_type, "aic": round(r.aic, 2),
                       "bic": round(r.bic, 2), "is_stationary": r.is_stationary,
                       "adf_pvalue": round(r.adf_pvalue, 4),
                       "forecast": r.forecast_table.to_dict(orient="records"),
                       "summary": r.summary_text}
                for name, r in results.items()
            }, "duration_seconds": round(time.time()-t0,2), "cached": False}
        elif method == "ets":
            r = engine.fit_ets(series, forecast_years, base_year)
            resp = {"status": "success", "method": "ets", "model_type": r.model_type,
                    "aic": round(r.aic,2), "forecast": r.forecast_table.to_dict(orient="records"),
                    "summary": r.summary_text,
                    "duration_seconds": round(time.time()-t0,2), "cached": False}
        else:
            r = engine.fit_arima(series, order=order, forecast_years=forecast_years, base_year=base_year)
            resp = {"status": "success", "method": "arima", "model_type": r.model_type,
                    "order": list(r.order), "aic": round(r.aic,2), "bic": round(r.bic,2),
                    "is_stationary": r.is_stationary, "adf_pvalue": round(r.adf_pvalue,4),
                    "forecast": r.forecast_table.to_dict(orient="records"),
                    "summary": r.summary_text,
                    "duration_seconds": round(time.time()-t0,2), "cached": False}

        cache.set("arima", ck, resp)
        get_history().record("regression", {"module": "arima", "method": method},
                             {"aic": resp.get("aic", 0)}, time.time()-t0, True)
        return jsonify(resp)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ── Renewable Targets ──────────────────────────────────────────────────────────

@advanced_bp.route("/renewable-targets", methods=["POST"])
def run_renewable_targets():
    try:
        from modules.scenario.renewable_targets import RenewableTargetTracker
        from utils.cache import get_history

        data = request.get_json(silent=True) or {}
        scenario     = data.get("scenario", "all")
        target_year  = int(data.get("target_year", 2050))
        baseline_re  = float(data.get("baseline_re_share_pct", 18.0))
        total_cap    = float(data.get("total_capacity_gw", 5.0))
        custom_tgt   = data.get("custom_target_pct")
        if custom_tgt:
            custom_tgt = float(custom_tgt)

        t0 = time.time()
        tracker = RenewableTargetTracker(baseline_re_share_pct=baseline_re,
                                         total_capacity_gw=total_cap)

        def _fmt_result(r):
            return {
                "on_track": r.on_track,
                "gap_pct": round(r.gap_at_target, 2),
                "cumulative_investment_busd": round(r.cumulative_investment_musd / 1000, 2),
                "avoided_emissions_mt": round(r.avoided_emissions_mt, 1),
                "annual_table": r.annual_share_table.to_dict(orient="records"),
                "tech_costs": {t: {"years": p.projection_years, "costs_usd_kw": p.costs,
                                   "lcoe_usd_mwh": p.lcoe_trend}
                               for t, p in r.tech_cost_projections.items()},
                "policy_gap": r.policy_gap_analysis,
            }

        if scenario == "all":
            resp = {
                "status": "success", "target_year": target_year,
                "comparison": tracker.compare_scenarios(target_year).to_dict(orient="records"),
                "scenarios": {s: _fmt_result(tracker.track_targets(s, target_year, custom_tgt))
                              for s in ["BAU", "Low Carbon", "High Growth"]},
                "duration_seconds": round(time.time()-t0, 2),
            }
        else:
            r = tracker.track_targets(scenario, target_year, custom_tgt)
            resp = {"status": "success", "scenario": scenario,
                    **_fmt_result(r), "target_year": target_year, "target_pct": r.target_pct,
                    "duration_seconds": round(time.time()-t0, 2)}

        get_history().record("scenario", {"module": "renewable_targets", "scenario": scenario},
                             {"target_year": target_year}, time.time()-t0, True)
        return jsonify(resp)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ── HTML Reports ───────────────────────────────────────────────────────────────

@advanced_bp.route("/report/financial", methods=["POST"])
def report_financial():
    try:
        from modules.financial.finance_engine import FinanceEngine
        from modules.financial.sensitivity import SensitivityAnalyzer
        from utils.report_generator import ProjectReportGenerator
        from utils.data_utils import generate_sample_financial_data
        from utils.project_store import ProjectStore

        data = request.get_json(silent=True) or {}
        project_data = generate_sample_financial_data()
        project_data.update(data)
        result = FinanceEngine(project_data).run_analysis()
        sens   = SensitivityAnalyzer(project_data).run_sensitivity()

        # Build a synthetic project dict for the report generator
        project = {
            "project_id": "adhoc_financial",
            "project_name": project_data.get("project_name", "Financial Analysis"),
            "module": "financial",
            "inputs": project_data,
            "results": {
                "summary": {
                    "LCOE ($/MWh)": round(result.lcoe, 2),
                    "Project NPV (USD)": round(result.npv or 0),
                    "Project IRR": result.firr,
                    "Payback Period (yrs)": result.payback_period,
                    "Minimum DSCR": result.min_dscr,
                }
            },
        }
        output_dir = current_app.config.get("OUTPUT_DIR", "outputs")
        reporter = ProjectReportGenerator(output_dir)
        path = reporter.generate(project)
        return send_file(str(path), as_attachment=True,
                         download_name=os.path.basename(path), mimetype="application/pdf")
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@advanced_bp.route("/report/regression", methods=["POST"])
def report_regression():
    try:
        from modules.regression.regression_engine import RegressionEngine
        from modules.regression.diagnostics import RegressionDiagnostics
        from modules.regression.forecast_engine import ForecastEngine
        from utils.report_generator import ProjectReportGenerator
        from utils.data_utils import generate_sample_regression_data

        data   = request.get_json(silent=True) or {}
        df     = generate_sample_regression_data()
        mt     = data.get("model_type", "log_log")
        engine = RegressionEngine()
        result = engine.fit(df, "Electricity_Demand_GWh",
                            ["GDP_Billion_USD", "Population_Million"], mt)
        diag   = RegressionDiagnostics.run_all(result)
        fc     = ForecastEngine().generate_forecast(result, df, 30,
                                                    {"GDP_Billion_USD": 0.04,
                                                     "Population_Million": 0.02})
        project = {
            "project_id": "adhoc_regression",
            "project_name": f"Regression ({mt})",
            "module": "regression",
            "inputs": {"model_type": mt},
            "results": {"summary": {"R²": round(result.r_squared, 4),
                                    "Adj R²": round(result.adj_r_squared, 4),
                                    "Durbin-Watson": round(result.durbin_watson, 3)}},
        }
        output_dir = current_app.config.get("OUTPUT_DIR", "outputs")
        path = ProjectReportGenerator(output_dir).generate(project)
        return send_file(str(path), as_attachment=True,
                         download_name=os.path.basename(path), mimetype="application/pdf")
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@advanced_bp.route("/report/scenario", methods=["POST"])
def report_scenario():
    try:
        from modules.scenario.leap_model import LEAPModel
        from modules.scenario.scenario_engine import ScenarioEngine
        from utils.report_generator import ProjectReportGenerator
        from utils.data_utils import generate_sample_energy_balance

        config  = generate_sample_energy_balance()
        model   = LEAPModel(config)
        engine  = ScenarioEngine(model)
        results = engine.run_all_scenarios()
        base    = model.get_base_year_summary()
        project = {
            "project_id": "adhoc_scenario",
            "project_name": "Scenario Analysis",
            "module": "scenario",
            "inputs": {},
            "results": {"summary": {"Total Demand (PJ)": round(base["total_demand_pj"], 2),
                                    "Scenarios": len(results)}},
        }
        output_dir = current_app.config.get("OUTPUT_DIR", "outputs")
        path = ProjectReportGenerator(output_dir).generate(project)
        return send_file(str(path), as_attachment=True,
                         download_name=os.path.basename(path), mimetype="application/pdf")
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ── Cache ──────────────────────────────────────────────────────────────────────

@advanced_bp.route("/cache/stats", methods=["GET"])
def cache_stats():
    try:
        from utils.cache import get_cache
        return jsonify({"status": "success", "cache": get_cache().get_stats()})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@advanced_bp.route("/cache/clear", methods=["POST"])
def cache_clear():
    try:
        from utils.cache import get_cache
        module = (request.get_json(silent=True) or {}).get("module")
        get_cache().invalidate(module)
        return jsonify({"status": "success",
                        "message": f"Cache cleared{' for ' + module if module else ''}"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ── History ────────────────────────────────────────────────────────────────────

@advanced_bp.route("/history", methods=["GET"])
def get_history_route():
    try:
        from utils.cache import get_history
        module = request.args.get("module")
        limit  = int(request.args.get("limit", 20))
        h = get_history()
        return jsonify({"status": "success",
                        "history": h.get_recent(module, limit),
                        "stats": h.get_stats()})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@advanced_bp.route("/history/clear", methods=["POST"])
def clear_history_route():
    try:
        from utils.cache import get_history
        module = (request.get_json(silent=True) or {}).get("module")
        get_history().clear(module)
        return jsonify({"status": "success", "message": "History cleared"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
