"""
Upload Routes — CSV/Excel file upload handling.

Handles file uploads for all three modules, parsing CSV and Excel
files into DataFrames for analysis.
"""

import os
import sys
import json
import traceback
import pandas as pd
from flask import Blueprint, request, jsonify, current_app

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route("/parse", methods=["POST"])
def parse_upload():
    """
    Parse an uploaded CSV/Excel file and return its contents as JSON.

    Returns column names, row count, data preview, and full data.
    """
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({
                "status": "error",
                "message": "Invalid file type. Upload CSV or Excel (.xlsx, .xls)"
            }), 400

        # Save temporarily
        upload_dir = current_app.config["UPLOAD_DIR"]
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        file.save(filepath)

        # Parse file
        ext = file.filename.rsplit('.', 1)[1].lower()
        sheet_name = request.form.get("sheet_name", 0)

        if ext == "csv":
            df = pd.read_csv(filepath)
        else:
            # Try to read specific sheet, fall back to first
            try:
                if isinstance(sheet_name, str) and sheet_name.isdigit():
                    sheet_name = int(sheet_name)
                df = pd.read_excel(filepath, sheet_name=sheet_name)
            except Exception:
                df = pd.read_excel(filepath, sheet_name=0)

            # Also get sheet names for user
            xls = pd.ExcelFile(filepath)
            sheet_names = xls.sheet_names
        
        # Get sheet names if Excel
        sheets = []
        if ext in ("xlsx", "xls"):
            try:
                xls = pd.ExcelFile(filepath)
                sheets = xls.sheet_names
            except:
                pass

        # Clean up
        os.remove(filepath)

        # Detect numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        all_cols = df.columns.tolist()

        return jsonify({
            "status": "success",
            "filename": file.filename,
            "rows": len(df),
            "columns": all_cols,
            "numeric_columns": numeric_cols,
            "sheets": sheets,
            "preview": df.head(10).to_dict(orient="records"),
            "data": df.to_dict(orient="records"),
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 400


@upload_bp.route("/template/<module>", methods=["GET"])
def download_template(module):
    """
    Download a sample CSV template for a module.
    """
    try:
        if module == "regression":
            df = _regression_template()
        elif module == "scenario":
            df = _scenario_template()
        elif module == "financial":
            df = _financial_template()
        else:
            return jsonify({"error": "Unknown module"}), 404

        # Save to temp
        upload_dir = current_app.config["UPLOAD_DIR"]
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, f"{module}_template.csv")
        df.to_csv(filepath, index=False)

        from flask import send_file
        return send_file(filepath, as_attachment=True,
                         download_name=f"{module}_template.csv")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _regression_template():
    """Sample regression data template."""
    import numpy as np
    years = list(range(1993, 2023))
    np.random.seed(42)
    return pd.DataFrame({
        "Year": years,
        "Electricity_Demand_GWh": [round(20 + i * 2.5 + np.random.normal(0, 1.5), 2) for i in range(len(years))],
        "GDP_Billion_USD": [round(10 + i * 1.8 + np.random.normal(0, 0.5), 2) for i in range(len(years))],
        "Population_Million": [round(5 + i * 0.15, 2) for i in range(len(years))],
        "Electricity_Price_USD_kWh": [round(0.08 + i * 0.001 + np.random.normal(0, 0.002), 4) for i in range(len(years))],
    })


def _scenario_template():
    """Sample scenario energy balance template (sector-fuel matrix)."""
    sectors = ["Residential", "Commercial", "Industrial", "Agriculture", "Transport"]
    fuels = ["Electricity", "Natural Gas", "Oil Products", "Coal", "Renewables"]
    rows = []
    for sector in sectors:
        for fuel in fuels:
            rows.append({
                "Sector": sector,
                "Fuel": fuel,
                "Base_Year_Demand_PJ": round(5 + hash(sector + fuel) % 20, 2),
                "Activity_Growth_Rate": 0.03,
                "Intensity_Change_Rate": -0.01,
            })
    return pd.DataFrame(rows)


def _financial_template():
    """Sample financial project data template."""
    return pd.DataFrame([{
        "project_name": "My Solar PV Project",
        "technology": "Solar PV",
        "capacity_mw": 50,
        "capacity_factor": 0.22,
        "capex_total_usd": 45000000,
        "annual_opex_usd": 650000,
        "project_life_years": 25,
        "discount_rate": 0.08,
        "inflation_rate": 0.02,
        "degradation_rate": 0.005,
        "electricity_price_usd_mwh": 65,
        "price_escalation_rate": 0.015,
        "debt_fraction": 0.70,
        "debt_interest_rate": 0.06,
        "debt_term_years": 15,
        "tax_rate": 0.20,
    }])
