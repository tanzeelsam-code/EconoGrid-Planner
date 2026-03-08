"""
Online data connectors for Pakistan-focused helper workflows.
"""

import json
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen


class PakistanDataConnector:
    """Fetch Pakistan macro and solar data from official/public APIs."""

    WORLD_BANK_BASE = "https://api.worldbank.org/v2/country/PAK/indicator/{indicator}"
    NASA_POWER_BASE = "https://power.larc.nasa.gov/api/temporal/climatology/point"

    WORLD_BANK_INDICATORS = {
        "gdp_usd": "NY.GDP.MKTP.CD",
        "population_total": "SP.POP.TOTL",
        "electricity_use_kwh_pc": "EG.USE.ELEC.KH.PC",
        "electricity_access_pct": "EG.ELC.ACCS.ZS",
    }

    PAKISTAN_LOCATIONS = {
        "Islamabad": {"lat": 33.6844, "lon": 73.0479},
        "Lahore": {"lat": 31.5204, "lon": 74.3587},
        "Karachi": {"lat": 24.8607, "lon": 67.0011},
        "Peshawar": {"lat": 34.0151, "lon": 71.5249},
        "Quetta": {"lat": 30.1798, "lon": 66.9750},
    }

    def fetch_regression_seed(self, start_year: int = 2000, end_year: int = 2024) -> Dict[str, Any]:
        """Build a regression-friendly annual dataset from World Bank indicators."""
        gdp = self.fetch_world_bank_indicator("gdp_usd", start_year, end_year)
        population = self.fetch_world_bank_indicator("population_total", start_year, end_year)
        elec_use = self.fetch_world_bank_indicator("electricity_use_kwh_pc", start_year, end_year)
        elec_access = self.fetch_world_bank_indicator("electricity_access_pct", start_year, end_year)

        years = sorted(set(gdp) & set(population) & set(elec_use))
        records: List[Dict[str, Any]] = []
        for year in years:
            total_demand_gwh = (population[year] * elec_use[year]) / 1_000_000
            records.append({
                "Year": year,
                "Electricity_Demand_GWh": round(total_demand_gwh, 2),
                "GDP_Billion_USD": round(gdp[year] / 1_000_000_000, 2),
                "Population_Million": round(population[year] / 1_000_000, 3),
                "Electricity_Use_kWh_per_Capita": round(elec_use[year], 2),
                "Electricity_Access_pct": round(elec_access.get(year), 2) if elec_access.get(year) is not None else None,
            })

        return {
            "status": "success",
            "country": "Pakistan",
            "source": "World Bank Open Data API",
            "indicators": self.WORLD_BANK_INDICATORS,
            "rows": len(records),
            "data": records,
        }

    def fetch_world_bank_indicator(self, indicator_key: str, start_year: int, end_year: int) -> Dict[int, float]:
        """Fetch a single World Bank indicator series for Pakistan."""
        indicator = self.WORLD_BANK_INDICATORS[indicator_key]
        query = urlencode({
            "format": "json",
            "per_page": 200,
            "mrv": max(end_year - start_year + 5, 30),
        })
        url = f"{self.WORLD_BANK_BASE.format(indicator=indicator)}?{query}"
        payload = self._fetch_json(url)
        if not isinstance(payload, list) or len(payload) < 2:
            raise ValueError(f"Unexpected World Bank response for {indicator_key}.")

        series: Dict[int, float] = {}
        for row in payload[1]:
            if row.get("value") is None:
                continue
            year = int(row["date"])
            if start_year <= year <= end_year:
                series[year] = float(row["value"])
        if not series:
            raise ValueError(f"No World Bank data returned for {indicator_key}.")
        return series

    def fetch_solar_resource(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Fetch monthly solar climatology for a Pakistan location from NASA POWER."""
        query = urlencode({
            "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M",
            "community": "RE",
            "longitude": longitude,
            "latitude": latitude,
            "format": "JSON",
        })
        payload = self._fetch_json(f"{self.NASA_POWER_BASE}?{query}")
        params = payload.get("properties", {}).get("parameter", {})
        if not params:
            raise ValueError("Unexpected NASA POWER response.")

        months = [
            "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
            "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
        ]
        records = []
        irradiance_values = []
        for month in months:
            ghi = float(params.get("ALLSKY_SFC_SW_DWN", {}).get(month, 0.0))
            temp = float(params.get("T2M", {}).get(month, 0.0))
            wind = float(params.get("WS10M", {}).get(month, 0.0))
            irradiance_values.append(ghi)
            records.append({
                "Month": month,
                "Solar_Irradiance_kWh_m2_day": round(ghi, 3),
                "Temperature_C": round(temp, 2),
                "Wind_Speed_m_s": round(wind, 2),
            })

        return {
            "status": "success",
            "country": "Pakistan",
            "source": "NASA POWER",
            "latitude": latitude,
            "longitude": longitude,
            "annual_average_irradiance": round(sum(irradiance_values) / len(irradiance_values), 3),
            "data": records,
        }

    def source_catalog(self) -> Dict[str, Any]:
        """Describe the supported online sources."""
        return {
            "country": "Pakistan",
            "sources": [
                {
                    "name": "World Bank Open Data API",
                    "module_fit": ["regression", "scenario"],
                    "description": "GDP, population, electricity use, and access indicators.",
                    "official_url": "https://api.worldbank.org/",
                },
                {
                    "name": "NASA POWER",
                    "module_fit": ["financial"],
                    "description": "Solar irradiance, temperature, and wind climatology.",
                    "official_url": "https://power.larc.nasa.gov/",
                },
            ],
        }

    def _fetch_json(self, url: str) -> Any:
        with urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
