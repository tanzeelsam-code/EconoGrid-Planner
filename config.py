"""
Global Configuration for EconoGrid Planner.

Centralizes all default parameters, paths, and shared constants
used across the three analytical modules and the dashboard.
"""

import os
from pathlib import Path

# ── Project Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR = BASE_DIR / "uploads"

# Ensure output/upload directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# ── Flask Settings ─────────────────────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5001
FLASK_DEBUG = True
SECRET_KEY = os.environ.get("SECRET_KEY", "econometric-toolkit-dev-key-2024")

# ── Module 1: Regression Defaults ─────────────────────────────────────────────
REGRESSION_DEFAULTS = {
    "model_type": "log_log",          # "linear", "log_log", "semi_log"
    "confidence_level": 0.95,
    "forecast_years": 30,
    "missing_data_strategy": "drop",  # "drop" or "interpolate"
}

# ── Module 2: Scenario/LEAP Defaults ──────────────────────────────────────────
SCENARIO_DEFAULTS = {
    "base_year": 2022,
    "projection_horizon": 30,         # years from base year
    "sectors": ["Residential", "Commercial", "Industrial", "Agriculture", "Transport"],
    "fuels": ["Electricity", "Natural Gas", "Oil Products", "Coal", "Renewables"],
    "default_scenarios": ["BAU", "Low Carbon", "High Growth"],
}

# Standard CO₂ emission factors (kg CO₂ per GJ)
# Source: IPCC Guidelines for National Greenhouse Gas Inventories
EMISSION_FACTORS = {
    "Electricity": 0.0,       # Accounted in transformation sector
    "Natural Gas": 56.1,
    "Oil Products": 73.3,
    "Coal": 94.6,
    "Renewables": 0.0,
}

# ── Module 3: Financial/RETScreen Defaults ─────────────────────────────────────
FINANCIAL_DEFAULTS = {
    "project_life": 25,               # years
    "discount_rate": 0.08,            # 8%
    "inflation_rate": 0.02,           # 2%
    "degradation_rate": 0.005,        # 0.5% per year
    "tax_rate": 0.0,                  # 0% default
    "debt_fraction": 0.70,            # 70% debt
    "debt_interest_rate": 0.06,       # 6%
    "debt_term": 15,                  # years
}

# ── Excel Styling Constants ────────────────────────────────────────────────────
EXCEL_STYLES = {
    "header_fill": "1F4E79",          # Dark blue
    "header_font_color": "FFFFFF",
    "subheader_fill": "2E75B6",       # Medium blue
    "accent_fill": "D6E4F0",          # Light blue
    "positive_fill": "C6EFCE",        # Green for positive values
    "negative_fill": "FFC7CE",        # Red for negative values
    "border_color": "4472C4",
    "title_font_size": 14,
    "header_font_size": 11,
    "body_font_size": 10,
    "number_format_pct": "0.00%",
    "number_format_dec2": "#,##0.00",
    "number_format_dec4": "0.0000",
    "number_format_int": "#,##0",
    "number_format_currency": "$#,##0.00",
}
