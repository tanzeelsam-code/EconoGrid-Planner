"""
Scenario Routes — API endpoints for Module 2.

Handles running LEAP-style scenario analysis, emissions calculations,
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
from modules.scenario.leap_model import LEAPModel
from modules.scenario.scenario_engine import ScenarioEngine
from modules.scenario.emissions_engine import EmissionsEngine
from modules.scenario.supply_transformation import SupplyTransformation
from modules.scenario.excel_export import ScenarioExcelExport
from utils.data_utils import generate_sample_energy_balance

scenario_bp = Blueprint("scenario", __name__)


@scenario_bp.route("/run", methods=["POST"])
def run_scenario():
    """Run full scenario analysis."""
    try:
        params = request.get_json(silent=True) or {}
        config = params.get("config", generate_sample_energy_balance())

        # Override planning parameters from UI
        if "base_year" in params:
            config["base_year"] = int(params["base_year"])
        if "projection_horizon" in params:
            config["projection_horizon"] = int(params["projection_horizon"])

        # Build config from direct GWh sector demands if provided
        sector_demands = params.get("sector_demands")
        if sector_demands and len(sector_demands) > 0:
            GWH_TO_PJ = 0.0036  # 1 GWh = 0.0036 PJ

            # Build sectors dict from GWh inputs
            sectors_config = {}
            bau_activity = {}
            low_activity = {}
            high_activity = {}

            for sd in sector_demands:
                name = sd["sector"]
                demand_pj = sd["demand_gwh"] * GWH_TO_PJ

                # Use activity=1, intensity=demand_pj so Activity×Intensity = demand_pj
                sectors_config[name] = {
                    "activity_level": 1.0,
                    "activity_unit": "index",
                    "energy_intensity": demand_pj * 1000,  # Will be /1000 via GJ conversion
                    "intensity_unit": "GJ/index",
                    "fuel_shares": {"Electricity": 1.0},
                }

                bau_activity[name] = sd.get("bau_growth", 0.03)
                low_activity[name] = sd.get("low_carbon_growth", 0.02)
                high_activity[name] = sd.get("high_growth", 0.05)

            config["sectors"] = sectors_config
            config["scenarios"] = {
                "BAU": {
                    "description": "Business As Usual",
                    "activity_growth": bau_activity,
                    "intensity_change": {s: -0.005 for s in bau_activity},
                    "fuel_switching": {},
                },
                "Low Carbon": {
                    "description": "Aggressive efficiency & renewables",
                    "activity_growth": low_activity,
                    "intensity_change": {s: -0.015 for s in low_activity},
                    "fuel_switching": {},
                },
                "High Growth": {
                    "description": "Accelerated economic growth",
                    "activity_growth": high_activity,
                    "intensity_change": {s: -0.003 for s in high_activity},
                    "fuel_switching": {},
                },
            }

        population_million = params.get("population_million")
        population_growth_rate = params.get("population_growth_rate", 0.02)

        # Initialize model
        model = LEAPModel(config)
        base_summary = model.get_base_year_summary()

        # Run all scenarios
        engine = ScenarioEngine(model)
        results = engine.run_all_scenarios()

        # Scenario comparison
        comparison = engine.get_comparison_table()
        scenario_summary = engine.get_scenario_summary()

        # ── Convert PJ → GWh for display (1 PJ = 277.778 GWh) ──
        PJ_TO_GWH = 277.778

        # Emissions
        emission_factors = config.get("emission_factors_kg_CO2_per_GJ", {})
        emissions_engine = EmissionsEngine(emission_factors)
        gen_mix = config.get("supply", {}).get("generation_mix_base_year", {})

        emissions_data = {}
        scenario_emissions = {}
        for name, result in results.items():
            demand_em = emissions_engine.calculate_demand_emissions(result)
            supply_em = emissions_engine.calculate_supply_emissions(result, gen_mix)
            total_em = emissions_engine.get_total_emissions(demand_em, supply_em)
            emissions_data[name] = total_em
            scenario_emissions[name] = total_em

        emissions_comparison = emissions_engine.compare_scenario_emissions(scenario_emissions)

        # Convert comparison table to GWh
        comparison_gwh = comparison * PJ_TO_GWH

        # Build charts (pass GWh data)
        charts = _build_scenario_charts(comparison_gwh, emissions_comparison, results, PJ_TO_GWH)

        # Export Excel
        exporter = ScenarioExcelExport(current_app.config["OUTPUT_DIR"])

        base_export = dict(base_summary)
        if base_export.get("demand_matrix") is not None:
            base_export["demand_matrix"] = base_summary["demand_matrix"]

        excel_path = exporter.export(
            config=config,
            base_year_summary=base_export,
            scenario_results=results,
            demand_comparison=comparison,
            emissions_data=emissions_data,
            emissions_comparison=emissions_comparison,
        )

        # Serialize (GWh for demand values)
        comparison_gwh_json = comparison_gwh.round(2).reset_index().to_dict(orient="records")
        emissions_json = emissions_comparison.reset_index().to_dict(orient="records")

        # Convert scenario summary to GWh
        summary_df = scenario_summary.reset_index()
        for col in ["Base Year Demand (PJ)", "Final Year Demand (PJ)"]:
            if col in summary_df.columns:
                new_col = col.replace("(PJ)", "(GWh)")
                summary_df[new_col] = (summary_df[col] * PJ_TO_GWH).round(2)
                summary_df.drop(columns=[col], inplace=True)
        if "Cumulative Demand (PJ)" in summary_df.columns:
            summary_df.drop(columns=["Cumulative Demand (PJ)"], inplace=True)
        summary_json = summary_df.to_dict(orient="records")

        # Build base year response in GWh
        total_gwh = round(base_summary["total_demand_pj"] * PJ_TO_GWH, 2)
        base_year_response = {
            "year": base_summary["year"],
            "total_demand_gwh": total_gwh,
            "demand_by_sector": {
                k: round(v * PJ_TO_GWH, 2)
                for k, v in base_summary["demand_by_sector"].items()
            },
            "demand_by_fuel": {
                k: round(v * PJ_TO_GWH, 2)
                for k, v in base_summary["demand_by_fuel"].items()
            },
        }

        # ── MW Peak Demand (seasonal load factors) ──
        summer_lf = params.get("summer_load_factor", 0.60)
        winter_lf = params.get("winter_load_factor", 0.45)
        reserve_margin = params.get("reserve_margin", 0.15)

        # Peak MW = GWh × 1000 / (8760 × Load Factor)
        summer_peak_mw = round(total_gwh * 1000 / (8760 * summer_lf), 0)
        winter_peak_mw = round(total_gwh * 1000 / (8760 * winter_lf), 0)
        system_peak_mw = max(summer_peak_mw, winter_peak_mw)
        required_capacity_mw = round(system_peak_mw * (1 + reserve_margin), 0)

        base_year_response["summer_peak_mw"] = int(summer_peak_mw)
        base_year_response["winter_peak_mw"] = int(winter_peak_mw)
        base_year_response["required_capacity_mw"] = int(required_capacity_mw)

        # Add per-capita kWh if population provided
        if population_million:
            per_capita_kwh = (total_gwh * 1000) / population_million  # GWh->kWh / million
            base_year_response["population_million"] = population_million
            base_year_response["per_capita_kwh"] = round(per_capita_kwh, 2)

        return jsonify({
            "status": "success",
            "base_year": base_year_response,
            "scenario_summary": summary_json,
            "demand_comparison": comparison_gwh_json,
            "emissions_comparison": emissions_json,
            "charts": charts,
            "excel_file": os.path.basename(excel_path),
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 400


@scenario_bp.route("/download/<filename>")
def download_scenario(filename):
    """Download scenario Excel output."""
    filepath = os.path.join(current_app.config["OUTPUT_DIR"], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


def _build_scenario_charts(comparison_gwh, emissions_comparison, results, pj_to_gwh):
    """Build Plotly chart JSON for the scenario dashboard (GWh units)."""
    charts = {}

    # Demand comparison (already in GWh)
    fig = go.Figure()
    colors = ["#4FC3F7", "#FF7043", "#66BB6A", "#AB47BC", "#FFA726"]
    for i, col in enumerate(comparison_gwh.columns):
        fig.add_trace(go.Scatter(
            x=comparison_gwh.index.tolist(),
            y=comparison_gwh[col].round(2).tolist(),
            name=col,
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    fig.update_layout(
        template="plotly_dark",
        title="Total Energy Demand by Scenario",
        xaxis_title="Year",
        yaxis_title="Energy Demand (GWh)",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["demand_comparison"] = json.loads(
        json.dumps(fig.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    )

    # Emissions comparison
    fig2 = go.Figure()
    for i, col in enumerate(emissions_comparison.columns):
        fig2.add_trace(go.Scatter(
            x=emissions_comparison.index.tolist(),
            y=emissions_comparison[col].tolist(),
            name=col,
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    fig2.update_layout(
        template="plotly_dark",
        title="CO₂ Emissions by Scenario",
        xaxis_title="Year",
        yaxis_title="Emissions (Mt CO₂)",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["emissions_comparison"] = json.loads(
        json.dumps(fig2.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    )

    # Sector breakdown for first scenario (convert to GWh)
    first_name = list(results.keys())[0]
    first_result = results[first_name]
    sector_df = first_result.demand_by_sector_by_year * pj_to_gwh

    fig3 = go.Figure()
    for i, col in enumerate(sector_df.columns):
        fig3.add_trace(go.Scatter(
            x=sector_df.index.tolist(),
            y=sector_df[col].round(2).tolist(),
            name=col,
            mode="lines",
            stackgroup="one",
        ))

    fig3.update_layout(
        template="plotly_dark",
        title=f"Demand by Sector — {first_name}",
        xaxis_title="Year",
        yaxis_title="Energy Demand (GWh)",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#e0e0e0"),
    )
    charts["sector_breakdown"] = json.loads(
        json.dumps(fig3.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    )

    return charts
