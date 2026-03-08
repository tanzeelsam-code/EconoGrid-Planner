"""
Financial Routes — API endpoints for Module 3.

Handles running RETScreen-style financial analysis, sensitivity,
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
from modules.financial.finance_engine import FinanceEngine
from modules.financial.lcoe import LCOECalculator
from modules.financial.cashflow import CashFlowAnalyzer
from modules.financial.sensitivity import SensitivityAnalyzer
from modules.financial.excel_export import FinancialExcelExport
from utils.data_utils import generate_sample_financial_data

financial_bp = Blueprint("financial", __name__)


@financial_bp.route("/run", methods=["POST"])
def run_financial():
    """Run full financial analysis."""
    try:
        params = request.get_json(silent=True) or {}
        project_data = params.get("project_data", generate_sample_financial_data())

        # Run main analysis
        engine = FinanceEngine(project_data)
        result = engine.run_analysis()

        # LCOE detailed
        lcoe_calc = LCOECalculator()
        lcoe_result = lcoe_calc.calculate(
            capex=project_data.get("capex_total_usd", 0),
            annual_opex=project_data.get("annual_opex_usd", 0),
            annual_generation=project_data.get("annual_generation_mwh", 0),
            project_life=project_data.get("project_life_years", 25),
            discount_rate=project_data.get("discount_rate", 0.08),
            inflation_rate=project_data.get("inflation_rate", 0.02),
            degradation_rate=project_data.get("degradation_rate", 0.005),
        )

        # Cash flow analysis
        cf_summary = CashFlowAnalyzer.get_annual_summary(result)
        profitability = CashFlowAnalyzer.get_profitability_metrics(result)
        chart_data = CashFlowAnalyzer.get_chart_data(result)

        # Sensitivity analysis
        sensitivity = SensitivityAnalyzer(project_data)
        sens_results = sensitivity.run_sensitivity()
        tornado = sensitivity.get_tornado_data(sens_results, "npv")

        # Build charts
        charts = _build_financial_charts(result, chart_data, tornado)

        # Export Excel
        exporter = FinancialExcelExport(current_app.config["OUTPUT_DIR"])
        excel_path = exporter.export(
            result=result,
            lcoe_result=lcoe_result,
            sensitivity_results=sens_results,
            tornado_data=tornado,
            project_data=project_data,
        )

        # NaN-safe serialization helper (NaN is invalid JSON)
        import math

        def nan_safe(obj):
            """Replace NaN/Inf with None for JSON compatibility."""
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if isinstance(obj, dict):
                return {k: nan_safe(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [nan_safe(v) for v in obj]
            return obj

        # Serialize sensitivity data safely
        sens_npv = sens_results["npv"].reset_index().rename(
            columns={"index": "Parameter"}
        ).to_dict(orient="records")

        return jsonify(nan_safe({
            "status": "success",
            "summary": result.summary,
            "lcoe": {
                "value": lcoe_result.lcoe,
                "capex_component": lcoe_result.lcoe_capex_component,
                "opex_component": lcoe_result.lcoe_opex_component,
                "pv_total_costs": lcoe_result.pv_total_costs,
                "pv_generation": lcoe_result.pv_generation,
            },
            "profitability": profitability,
            "cashflow_summary": cf_summary.to_dict(orient="records"),
            "sensitivity_npv": sens_npv,
            "tornado": tornado.to_dict(orient="records"),
            "charts": charts,
            "excel_file": os.path.basename(excel_path),
        }))

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 400


@financial_bp.route("/download/<filename>")
def download_financial(filename):
    """Download financial Excel output."""
    filepath = os.path.join(current_app.config["OUTPUT_DIR"], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


def _build_financial_charts(result, chart_data, tornado):
    """Build Plotly chart JSON for the financial dashboard."""
    charts = {}

    # Cumulative cash flow
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart_data["cumulative_cashflow"]["years"],
        y=chart_data["cumulative_cashflow"]["values"],
        name="Cumulative Cash Flow",
        mode="lines",
        line=dict(color="#4FC3F7", width=2),
        fill="tozeroy",
        fillcolor="rgba(79,195,247,0.15)"
    ))
    fig.add_trace(go.Scatter(
        x=chart_data["cumulative_discounted"]["years"],
        y=chart_data["cumulative_discounted"]["values"],
        name="Cumulative Discounted CF",
        mode="lines",
        line=dict(color="#FF7043", width=2, dash="dash"),
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.update_layout(
        template="plotly_dark",
        title="Cumulative Cash Flow",
        xaxis_title="Year",
        yaxis_title="USD",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["cumulative_cashflow"] = json.loads(
        json.dumps(fig.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    )

    # Annual cash flow bar chart
    fig2 = go.Figure()
    years = chart_data["annual_cashflow"]["years"]
    values = chart_data["annual_cashflow"]["values"]
    colors_bar = ["#ef5350" if v < 0 else "#66BB6A" for v in values]
    fig2.add_trace(go.Bar(
        x=years, y=values,
        name="Net Cash Flow",
        marker_color=colors_bar,
    ))
    fig2.update_layout(
        template="plotly_dark",
        title="Annual Net Cash Flow",
        xaxis_title="Year",
        yaxis_title="USD",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["annual_cashflow"] = json.loads(
        json.dumps(fig2.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    )

    # Revenue vs Cost
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=chart_data["revenue_vs_cost"]["years"],
        y=chart_data["revenue_vs_cost"]["revenue"],
        name="Revenue",
        line=dict(color="#66BB6A", width=2),
    ))
    fig3.add_trace(go.Scatter(
        x=chart_data["revenue_vs_cost"]["years"],
        y=chart_data["revenue_vs_cost"]["costs"],
        name="Total Costs",
        line=dict(color="#ef5350", width=2),
    ))
    fig3.update_layout(
        template="plotly_dark",
        title="Revenue vs. Total Costs",
        xaxis_title="Year",
        yaxis_title="USD/year",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["revenue_vs_cost"] = json.loads(
        json.dumps(fig3.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    )

    # Tornado chart for NPV sensitivity
    if not tornado.empty:
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            y=tornado["Parameter"].tolist(),
            x=(tornado["Max"] - tornado["Base"]).tolist(),
            name="Upside",
            orientation="h",
            marker_color="#66BB6A",
            base=tornado["Base"].tolist(),
        ))
        fig4.add_trace(go.Bar(
            y=tornado["Parameter"].tolist(),
            x=(tornado["Min"] - tornado["Base"]).tolist(),
            name="Downside",
            orientation="h",
            marker_color="#ef5350",
            base=tornado["Base"].tolist(),
        ))
        fig4.update_layout(
            template="plotly_dark",
            title="NPV Sensitivity (Tornado)",
            xaxis_title="NPV (USD)",
            barmode="overlay",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#16213e",
            font=dict(color="#e0e0e0"),
        )
        charts["tornado"] = json.loads(
            json.dumps(fig4.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
        )

    return charts
