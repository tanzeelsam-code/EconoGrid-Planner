"""
Input Validation for EconoGrid Planner API endpoints.

Validates and sanitises request payloads for all three modules,
returning clean data + warnings or raising ValidationError.
"""
import re
from typing import Any, Dict, List, Optional, Tuple


class ValidationError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _range(val: float, lo: float, hi: float, name: str) -> Optional[str]:
    if not (lo <= val <= hi):
        return f"'{name}' must be between {lo} and {hi}, got {val}"
    return None


class FinancialInputValidator:
    REQUIRED = {
        "capex_total_usd":          (1_000, 1e11),
        "annual_opex_usd":          (0,     1e9),
        "electricity_price_usd_mwh":(0.1,   10_000),
        "capacity_factor":          (0.01,  0.99),
        "project_life_years":       (1,     50),
        "discount_rate":            (0.001, 0.50),
        "capacity_mw":              (0.001, 100_000),
    }
    OPTIONAL = {
        "inflation_rate":       (0.02, 0.0,  0.30),
        "degradation_rate":     (0.005,0.0,  0.10),
        "tax_rate":             (0.0,  0.0,  0.99),
        "debt_fraction":        (0.70, 0.0,  1.0),
        "debt_interest_rate":   (0.06, 0.001,0.50),
        "debt_term_years":      (15,   1,    50),
    }

    @classmethod
    def validate(cls, data: dict) -> Tuple[dict, List[str]]:
        errors, warnings, cleaned = [], [], {}
        for field, (lo, hi) in cls.REQUIRED.items():
            if field in data:
                try:
                    v = float(data[field])
                    err = _range(v, lo, hi, field)
                    if err:
                        errors.append(err)
                    else:
                        cleaned[field] = v
                except (TypeError, ValueError):
                    errors.append(f"'{field}' must be a number")
        for field, (default, lo, hi) in cls.OPTIONAL.items():
            if field in data:
                try:
                    v = float(data[field])
                    err = _range(v, lo, hi, field)
                    if err:
                        warnings.append(f"{err} — using default {default}")
                        cleaned[field] = default
                    else:
                        cleaned[field] = v
                except (TypeError, ValueError):
                    warnings.append(f"'{field}' invalid, using default {default}")
                    cleaned[field] = default
        if "debt_term_years" in cleaned and "project_life_years" in cleaned:
            if cleaned["debt_term_years"] > cleaned["project_life_years"]:
                errors.append("'debt_term_years' cannot exceed 'project_life_years'")
        if errors:
            raise ValidationError(errors)
        for k, v in data.items():
            cleaned.setdefault(k, v)
        return cleaned, warnings


class RegressionInputValidator:
    VALID_MODELS = {"linear", "log_log", "semi_log"}

    @classmethod
    def validate(cls, data: dict) -> Tuple[dict, List[str]]:
        errors, warnings, cleaned = [], [], dict(data)
        mt = data.get("model_type", "log_log")
        if mt not in cls.VALID_MODELS:
            errors.append(f"'model_type' must be one of {cls.VALID_MODELS}, got '{mt}'")
        else:
            cleaned["model_type"] = mt
        try:
            fy = int(data.get("forecast_years", 30))
            err = _range(fy, 1, 100, "forecast_years")
            if err:
                errors.append(err)
            else:
                cleaned["forecast_years"] = fy
        except (TypeError, ValueError):
            warnings.append("'forecast_years' invalid, using 30")
            cleaned["forecast_years"] = 30
        try:
            cl = float(data.get("confidence_level", 0.95))
            err = _range(cl, 0.50, 0.999, "confidence_level")
            if err:
                errors.append(err)
            else:
                cleaned["confidence_level"] = cl
        except (TypeError, ValueError):
            warnings.append("'confidence_level' invalid, using 0.95")
            cleaned["confidence_level"] = 0.95
        if errors:
            raise ValidationError(errors)
        return cleaned, warnings


class ScenarioInputValidator:
    @classmethod
    def validate(cls, data: dict) -> Tuple[dict, List[str]]:
        errors, warnings, cleaned = [], [], dict(data)
        try:
            by = int(data.get("base_year", 2022))
            err = _range(by, 1990, 2030, "base_year")
            warnings.append(err + " — using 2022") if err else cleaned.update({"base_year": by})
        except (TypeError, ValueError):
            warnings.append("'base_year' invalid, using 2022")
            cleaned["base_year"] = 2022
        try:
            ph = int(data.get("projection_horizon", 30))
            err = _range(ph, 5, 80, "projection_horizon")
            warnings.append(err + " — using 30") if err else cleaned.update({"projection_horizon": ph})
        except (TypeError, ValueError):
            warnings.append("'projection_horizon' invalid, using 30")
            cleaned["projection_horizon"] = 30
        uploaded = data.get("uploaded_data")
        if uploaded and isinstance(uploaded, list) and uploaded:
            required = {"Sector", "Fuel", "Base_Year_Demand_PJ", "Activity_Growth_Rate"}
            missing = required - set(uploaded[0].keys())
            if missing:
                errors.append(f"Uploaded data missing columns: {missing}")
        if errors:
            raise ValidationError(errors)
        return cleaned, warnings


class UploadValidator:
    ALLOWED = {".csv", ".xlsx", ".xls"}

    @classmethod
    def validate_filename(cls, filename: str) -> Tuple[bool, str]:
        if not filename:
            return False, "No filename"
        if not re.match(r"^[\w\-. ]+$", filename):
            return False, "Filename contains invalid characters"
        ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        if ext not in cls.ALLOWED:
            return False, f"File type '{ext}' not allowed. Use: {cls.ALLOWED}"
        return True, "OK"

    @classmethod
    def validate_regression_columns(cls, cols: List[str]) -> Tuple[bool, List[str]]:
        missing = {"Year", "Electricity_Demand_GWh", "GDP_Billion_USD"} - set(cols)
        return (not missing), ([f"Missing: {missing}"] if missing else [])

    @classmethod
    def validate_scenario_columns(cls, cols: List[str]) -> Tuple[bool, List[str]]:
        missing = {"Sector", "Fuel", "Base_Year_Demand_PJ"} - set(cols)
        return (not missing), ([f"Missing: {missing}"] if missing else [])

    @classmethod
    def validate_dataframe_size(cls, n_rows: int, n_cols: int) -> Tuple[bool, str]:
        if n_rows == 0:
            return False, "File is empty"
        if n_rows > 10_000:
            return False, f"Too many rows: {n_rows} (max 10,000)"
        if n_cols > 100:
            return False, f"Too many columns: {n_cols} (max 100)"
        return True, "OK"
