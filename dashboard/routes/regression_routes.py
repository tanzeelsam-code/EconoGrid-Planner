"""
Regression Routes — API endpoints for Module 1.

Handles running regression analysis, generating forecasts,
and downloading Excel outputs via the dashboard.
"""

import os
import sys
import json
import traceback
import pandas as pd
from flask import Blueprint, request, jsonify, send_file, current_app
import plotly.graph_objects as go
import plotly.utils

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.regression.regression_engine import RegressionEngine
from modules.regression.diagnostics import RegressionDiagnostics
from modules.regression.forecast_engine import ForecastEngine
from modules.regression.excel_export import RegressionExcelExport
from utils.data_utils import generate_sample_regression_data

regression_bp = Blueprint("regression", __name__)


@regression_bp.route("/run", methods=["POST"])
def run_regression():
    """Run OLS regression with provided or sample data."""
    try:
        # Get parameters from request
        params = request.get_json(silent=True) or {}
        model_type = params.get("model_type", "log_log")
        dependent_var = params.get("dependent_var", "Electricity_Demand_GWh")
        independent_vars = params.get("independent_vars", [
            "GDP_Billion_USD", "Population_Million", "Electricity_Price_USD_kWh"
        ])

        # Load data
        if "data" in params:
            df = pd.DataFrame(params["data"])
        else:
            df = generate_sample_regression_data()

        # Run regression
        engine = RegressionEngine()
        result = engine.fit(
            data=df,
            dependent_var=dependent_var,
            independent_vars=independent_vars,
            model_type=model_type,
        )

        # Run diagnostics
        diagnostics = RegressionDiagnostics.run_all(result)
        diag_table = RegressionDiagnostics.summary_table(diagnostics)

        # Generate forecast
        forecast_engine = ForecastEngine()
        growth = params.get("growth_assumptions", {
            "GDP_Billion_USD": 0.04,
            "Population_Million": 0.02,
            "Electricity_Price_USD_kWh": 0.01,
        })

        forecast = forecast_engine.generate_forecast(
            regression_result=result,
            original_data=df,
            forecast_years=30,
            growth_assumptions=growth,
            scenario_name="Base Forecast"
        )

        # Build charts
        charts = _build_regression_charts(result, forecast, df)

        # Export to Excel
        exporter = RegressionExcelExport(current_app.config["OUTPUT_DIR"])
        excel_path = exporter.export(
            regression_result=result,
            diagnostics=diagnostics,
            forecast_result=forecast,
        )

        return jsonify({
            "status": "success",
            "summary_text": engine.summary_text(result),
            "coefficients": result.coefficients.to_dict(orient="records"),
            "model_stats": {
                "R-squared": result.r_squared,
                "Adjusted R-squared": result.adj_r_squared,
                "F-statistic": result.f_statistic,
                "Prob(F-statistic)": result.prob_f_statistic,
                "Durbin-Watson": result.durbin_watson,
                "AIC": result.aic,
                "BIC": result.bic,
            },
            "diagnostics": diag_table.to_dict(orient="records"),
            "forecast": forecast.forecast_table.to_dict(orient="records"),
            "elasticities": engine.get_elasticities(result),
            "charts": charts,
            "excel_file": os.path.basename(excel_path),
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 400


@regression_bp.route("/download/<filename>")
def download_regression(filename):
    """Download regression Excel output."""
    filepath = os.path.join(current_app.config["OUTPUT_DIR"], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


def _build_regression_charts(result, forecast, original_data):
    """Build Plotly chart JSON for the dashboard."""
    charts = {}

    # Forecast chart
    fig = go.Figure()
    forecast_df = forecast.forecast_table
    col = [c for c in forecast_df.columns if "Forecast" in c][0]

    # Historical data
    dep_var_clean = result.dependent_var.replace("LOG(", "").replace(")", "")
    if dep_var_clean in original_data.columns and "Year" in original_data.columns:
        fig.add_trace(go.Scatter(
            x=original_data["Year"].tolist(),
            y=original_data[dep_var_clean].tolist(),
            name="Historical",
            mode="lines+markers",
            line=dict(color="#4FC3F7", width=2),
            marker=dict(size=5)
        ))

    fig.add_trace(go.Scatter(
        x=forecast_df["Year"].tolist(),
        y=forecast_df[col].tolist(),
        name="Forecast",
        mode="lines",
        line=dict(color="#FF7043", width=2, dash="dash")
    ))

    # Confidence bands
    lower_col = [c for c in forecast_df.columns if "Lower" in c]
    upper_col = [c for c in forecast_df.columns if "Upper" in c]
    if lower_col and upper_col:
        fig.add_trace(go.Scatter(
            x=forecast_df["Year"].tolist() + forecast_df["Year"].tolist()[::-1],
            y=forecast_df[upper_col[0]].tolist() + forecast_df[lower_col[0]].tolist()[::-1],
            fill="toself",
            fillcolor="rgba(255,112,67,0.15)",
            line=dict(color="rgba(255,112,67,0)"),
            name="95% Confidence",
            showlegend=True
        ))

    fig.update_layout(
        template="plotly_dark",
        title="Demand Forecast",
        xaxis_title="Year",
        yaxis_title=dep_var_clean,
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["forecast"] = json.loads(json.dumps(fig.to_dict(), cls=plotly.utils.PlotlyJSONEncoder))

    # Residuals chart
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        y=result.residuals.tolist(),
        mode="markers+lines",
        name="Residuals",
        line=dict(color="#66BB6A"),
        marker=dict(size=5)
    ))
    fig2.add_hline(y=0, line_dash="dash", line_color="#ef5350")
    fig2.update_layout(
        template="plotly_dark",
        title="Residual Plot",
        xaxis_title="Observation",
        yaxis_title="Residual",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["residuals"] = json.loads(json.dumps(fig2.to_dict(), cls=plotly.utils.PlotlyJSONEncoder))

    return charts
