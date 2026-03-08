"""
Data Utilities — Shared Data Loading and Validation.

Provides common functions for loading CSV/JSON data, validating
DataFrames, and handling missing values across all modules.
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# Add parent directory to path for config import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import DATA_DIR


def load_csv_data(
    filepath: str,
    required_columns: Optional[List[str]] = None,
    date_column: Optional[str] = None,
    index_column: Optional[str] = None
) -> pd.DataFrame:
    """
    Load CSV data with validation.

    Args:
        filepath: Path to CSV file.
        required_columns: Columns that must be present.
        date_column: Column to parse as datetime.
        index_column: Column to set as index.

    Returns:
        Validated DataFrame.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If required columns are missing.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    parse_dates = [date_column] if date_column else False
    df = pd.read_csv(filepath, parse_dates=parse_dates)

    # Validate required columns
    if required_columns:
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    # Set index
    if index_column and index_column in df.columns:
        df = df.set_index(index_column)

    return df


def load_json_data(filepath: str) -> Dict[str, Any]:
    """
    Load JSON configuration/data file.

    Args:
        filepath: Path to JSON file.

    Returns:
        Parsed dictionary.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    with open(filepath, 'r') as f:
        return json.load(f)


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: Optional[List[str]] = None,
    numeric_columns: Optional[List[str]] = None,
    min_rows: int = 3
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate and clean a DataFrame for analysis.

    Args:
        df: Input DataFrame.
        required_columns: Columns that must exist.
        numeric_columns: Columns that must be numeric.
        min_rows: Minimum number of valid rows required.

    Returns:
        Tuple of (cleaned DataFrame, list of warning messages).

    Raises:
        ValueError: If validation fails critically.
    """
    warnings = []

    # Check required columns
    if required_columns:
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    # Coerce numeric columns
    if numeric_columns:
        for col in numeric_columns:
            if col in df.columns:
                original_nulls = df[col].isna().sum()
                df[col] = pd.to_numeric(df[col], errors='coerce')
                new_nulls = df[col].isna().sum()
                if new_nulls > original_nulls:
                    non_numeric = new_nulls - original_nulls
                    warnings.append(
                        f"Column '{col}': {non_numeric} non-numeric values coerced to NaN"
                    )

    # Report missing data
    total_missing = df.isna().sum().sum()
    if total_missing > 0:
        warnings.append(f"Total missing values: {total_missing}")
        # Report by column
        for col in df.columns:
            col_missing = df[col].isna().sum()
            if col_missing > 0:
                pct = col_missing / len(df) * 100
                warnings.append(f"  '{col}': {col_missing} missing ({pct:.1f}%)")

    # Drop rows with missing data in key columns
    if numeric_columns:
        available_cols = [c for c in numeric_columns if c in df.columns]
        if available_cols:
            before = len(df)
            df = df.dropna(subset=available_cols)
            dropped = before - len(df)
            if dropped > 0:
                warnings.append(f"Dropped {dropped} rows with missing numeric values")

    # Check minimum rows
    if len(df) < min_rows:
        raise ValueError(
            f"Insufficient data: {len(df)} rows remaining (minimum {min_rows} required)"
        )

    return df, warnings


def generate_sample_regression_data() -> pd.DataFrame:
    """
    Generate a realistic sample dataset for the regression module.

    Creates 30 years of synthetic electricity demand data with
    GDP, population, electricity price, and temperature drivers.

    Returns:
        DataFrame with Year index and 5 columns.
    """
    np.random.seed(42)
    years = list(range(1993, 2023))
    n = len(years)

    # Base values
    gdp_base = 50.0  # billion USD
    pop_base = 20.0  # million
    price_base = 0.08  # USD/kWh
    temp_base = 25.0  # °C

    # Growth trends with noise
    gdp = gdp_base * np.cumprod(1 + np.random.normal(0.04, 0.02, n))
    population = pop_base * np.cumprod(1 + np.random.normal(0.02, 0.005, n))
    elec_price = price_base * np.cumprod(1 + np.random.normal(0.01, 0.015, n))
    temperature = temp_base + np.random.normal(0, 1.5, n)

    # Demand model: log(D) = a + b1*log(GDP) + b2*log(Pop) + b3*log(Price) + noise
    log_demand = (
        2.0 +
        0.65 * np.log(gdp) +
        0.40 * np.log(population) -
        0.25 * np.log(elec_price) +
        0.02 * temperature +
        np.random.normal(0, 0.03, n)
    )
    electricity_demand = np.exp(log_demand)  # GWh

    df = pd.DataFrame({
        "Year": years,
        "Electricity_Demand_GWh": np.round(electricity_demand, 1),
        "GDP_Billion_USD": np.round(gdp, 2),
        "Population_Million": np.round(population, 3),
        "Electricity_Price_USD_kWh": np.round(elec_price, 4),
        "Avg_Temperature_C": np.round(temperature, 1)
    })

    return df


def generate_sample_energy_balance() -> Dict[str, Any]:
    """
    Generate a sample energy balance dataset for the LEAP scenario module.

    Returns:
        Dictionary with base year data, sector parameters, and scenario assumptions.
    """
    return {
        "base_year": 2022,
        "projection_horizon": 30,
        "units": {
            "energy": "PJ",
            "emissions": "Mt CO2",
            "population": "million"
        },
        "sectors": {
            "Residential": {
                "activity_level": 8.5,
                "activity_unit": "million households",
                "energy_intensity": 25.0,
                "intensity_unit": "GJ/household",
                "fuel_shares": {
                    "Electricity": 0.45,
                    "Natural Gas": 0.35,
                    "Oil Products": 0.15,
                    "Renewables": 0.05
                }
            },
            "Commercial": {
                "activity_level": 120.0,
                "activity_unit": "million m² floor area",
                "energy_intensity": 0.8,
                "intensity_unit": "GJ/m²",
                "fuel_shares": {
                    "Electricity": 0.60,
                    "Natural Gas": 0.30,
                    "Oil Products": 0.10
                }
            },
            "Industrial": {
                "activity_level": 45.0,
                "activity_unit": "billion USD value added",
                "energy_intensity": 8.0,
                "intensity_unit": "PJ/billion USD",
                "fuel_shares": {
                    "Electricity": 0.30,
                    "Natural Gas": 0.25,
                    "Oil Products": 0.20,
                    "Coal": 0.20,
                    "Renewables": 0.05
                }
            },
            "Agriculture": {
                "activity_level": 15.0,
                "activity_unit": "billion USD value added",
                "energy_intensity": 2.5,
                "intensity_unit": "PJ/billion USD",
                "fuel_shares": {
                    "Electricity": 0.25,
                    "Oil Products": 0.60,
                    "Natural Gas": 0.15
                }
            },
            "Transport": {
                "activity_level": 250.0,
                "activity_unit": "billion passenger-km",
                "energy_intensity": 1.8,
                "intensity_unit": "MJ/passenger-km",
                "fuel_shares": {
                    "Oil Products": 0.85,
                    "Electricity": 0.05,
                    "Natural Gas": 0.10
                }
            }
        },
        "scenarios": {
            "BAU": {
                "description": "Business as Usual — continuation of current trends",
                "activity_growth": {
                    "Residential": 0.025,
                    "Commercial": 0.035,
                    "Industrial": 0.040,
                    "Agriculture": 0.020,
                    "Transport": 0.030
                },
                "intensity_change": {
                    "Residential": -0.005,
                    "Commercial": -0.008,
                    "Industrial": -0.010,
                    "Agriculture": -0.005,
                    "Transport": -0.005
                },
                "fuel_switching": {}
            },
            "Low Carbon": {
                "description": "Aggressive decarbonization with efficiency and renewables",
                "activity_growth": {
                    "Residential": 0.020,
                    "Commercial": 0.030,
                    "Industrial": 0.030,
                    "Agriculture": 0.015,
                    "Transport": 0.020
                },
                "intensity_change": {
                    "Residential": -0.020,
                    "Commercial": -0.025,
                    "Industrial": -0.030,
                    "Agriculture": -0.015,
                    "Transport": -0.025
                },
                "fuel_switching": {
                    "Residential": {"target_fuel": "Renewables", "shift_per_year": 0.01},
                    "Commercial": {"target_fuel": "Electricity", "shift_per_year": 0.008},
                    "Industrial": {"target_fuel": "Renewables", "shift_per_year": 0.012},
                    "Transport": {"target_fuel": "Electricity", "shift_per_year": 0.015}
                }
            },
            "High Growth": {
                "description": "Rapid economic expansion with moderate efficiency gains",
                "activity_growth": {
                    "Residential": 0.030,
                    "Commercial": 0.050,
                    "Industrial": 0.060,
                    "Agriculture": 0.035,
                    "Transport": 0.045
                },
                "intensity_change": {
                    "Residential": -0.008,
                    "Commercial": -0.010,
                    "Industrial": -0.012,
                    "Agriculture": -0.008,
                    "Transport": -0.008
                },
                "fuel_switching": {}
            }
        },
        "supply": {
            "generation_mix_base_year": {
                "Coal": 0.35,
                "Natural Gas": 0.30,
                "Oil Products": 0.05,
                "Hydro": 0.15,
                "Solar": 0.08,
                "Wind": 0.05,
                "Nuclear": 0.02
            },
            "transformation_efficiency": 0.35,
            "transmission_losses": 0.08
        },
        "emission_factors_kg_CO2_per_GJ": {
            "Natural Gas": 56.1,
            "Oil Products": 73.3,
            "Coal": 94.6,
            "Electricity": 0.0,
            "Renewables": 0.0
        }
    }


def generate_sample_financial_data() -> Dict[str, Any]:
    """
    Generate a sample financial dataset for the RETScreen module.

    Models a 50 MW solar PV project.

    Returns:
        Dictionary with project parameters.
    """
    return {
        "project_name": "Solar PV Plant — 50 MW",
        "technology": "Solar PV (Utility-Scale)",
        "capacity_mw": 50.0,
        "capacity_factor": 0.22,
        "annual_generation_mwh": 50.0 * 0.22 * 8760,

        "capex_total_usd": 45_000_000,
        "capex_breakdown": {
            "Modules & Inverters": 25_000_000,
            "Balance of System": 10_000_000,
            "Engineering & Development": 5_000_000,
            "Contingency": 5_000_000
        },

        "annual_opex_usd": 650_000,
        "opex_breakdown": {
            "O&M Labor": 250_000,
            "Insurance": 150_000,
            "Land Lease": 100_000,
            "Spare Parts & Repairs": 100_000,
            "Administration": 50_000
        },

        "project_life_years": 25,
        "discount_rate": 0.08,
        "inflation_rate": 0.02,
        "degradation_rate": 0.005,

        "electricity_price_usd_mwh": 65.0,
        "price_escalation_rate": 0.015,

        "debt_fraction": 0.70,
        "debt_interest_rate": 0.06,
        "debt_term_years": 15,
        "tax_rate": 0.20,
        "depreciation_years": 20,

        "sensitivity_parameters": {
            "capex_range": [-0.20, -0.10, 0.0, 0.10, 0.20],
            "discount_rate_range": [0.05, 0.06, 0.08, 0.10, 0.12],
            "electricity_price_range": [45, 55, 65, 75, 85],
            "capacity_factor_range": [0.18, 0.20, 0.22, 0.24, 0.26]
        }
    }
