"""
Monte Carlo Simulation for Financial Risk Analysis.

Runs N simulations varying key parameters stochastically to produce
probability distributions for NPV, IRR, and LCOE.
"""
import numpy as np
import numpy_financial as npf
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class MonteCarloResult:
    n_simulations: int
    npv_distribution: np.ndarray
    irr_distribution: np.ndarray
    lcoe_distribution: np.ndarray
    npv_p10: float
    npv_p50: float
    npv_p90: float
    irr_p10: float
    irr_p50: float
    irr_p90: float
    lcoe_p10: float
    lcoe_p50: float
    lcoe_p90: float
    prob_positive_npv: float
    param_correlations: Dict[str, float]
    histogram_data: Dict


class MonteCarloSimulator:
    """
    Monte Carlo simulator for energy project financial analysis.
    Varies CAPEX, OPEX, capacity factor, electricity price, and discount rate
    using triangular or normal distributions.
    """

    DEFAULT_UNCERTAINTIES = {
        "capex":              {"dist": "triangular", "low": -0.20, "mode": 0.0, "high": 0.30},
        "opex":               {"dist": "triangular", "low": -0.10, "mode": 0.0, "high": 0.20},
        "capacity_factor":    {"dist": "normal",     "std": 0.05},
        "electricity_price":  {"dist": "triangular", "low": -0.15, "mode": 0.0, "high": 0.25},
        "discount_rate":      {"dist": "normal",     "std": 0.01},
    }

    def __init__(self, base_params: dict, uncertainties: Optional[dict] = None,
                 n_simulations: int = 5000, seed: int = 42):
        self.base = base_params
        self.uncertainties = uncertainties or self.DEFAULT_UNCERTAINTIES
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(seed)

    def _sample(self, base: float, spec: dict) -> np.ndarray:
        n = self.n_simulations
        if spec["dist"] == "triangular":
            return self.rng.triangular(
                base * (1 + spec["low"]),
                base * (1 + spec["mode"]),
                base * (1 + spec["high"]),
                n,
            )
        return self.rng.normal(base, base * spec["std"], n)

    def _npv_single(self, capex, opex, cf, price, dr, life, degradation,
                    debt_fraction, debt_rate, debt_term):
        cashflows = [-capex]
        for yr in range(1, int(life) + 1):
            gen = cf * 8760 * (1 - degradation) ** yr
            rev = gen * price
            if yr <= int(debt_term):
                denom = (1 + debt_rate) ** debt_term - 1
                annuity = (capex * debt_fraction * debt_rate * (1 + debt_rate) ** debt_term / denom
                           if denom > 0 else 0)
            else:
                annuity = 0
            cashflows.append(rev - opex - annuity)
        try:
            return float(npf.npv(dr, cashflows))
        except Exception:
            return np.nan

    def _lcoe_single(self, capex, opex, cf, dr, life, degradation):
        total_cost = capex
        total_gen = 0.0
        for yr in range(1, int(life) + 1):
            gen = cf * 8760 * (1 - degradation) ** yr
            disc = (1 + dr) ** yr
            total_cost += opex / disc
            total_gen += gen / disc
        return total_cost / total_gen * 1000 if total_gen > 0 else np.nan

    def run(self) -> MonteCarloResult:
        b = self.base
        base_cf     = b.get("capacity_factor", 0.22)
        base_capex  = b.get("capex_total_usd", 45_000_000)
        base_opex   = b.get("annual_opex_usd", 650_000)
        base_price  = b.get("electricity_price_usd_mwh", 80.0)
        base_dr     = b.get("discount_rate", 0.08)
        life        = b.get("project_life_years", 25)
        degradation = b.get("degradation_rate", 0.005)
        debt_frac   = b.get("debt_fraction", 0.70)
        debt_rate   = b.get("debt_interest_rate", 0.06)
        debt_term   = b.get("debt_term_years", 15)

        capex_arr = self._sample(base_capex, self.uncertainties["capex"])
        opex_arr  = self._sample(base_opex,  self.uncertainties["opex"])
        cf_arr    = np.clip(self._sample(base_cf,    self.uncertainties["capacity_factor"]), 0.05, 0.95)
        price_arr = self._sample(base_price, self.uncertainties["electricity_price"])
        dr_arr    = np.clip(self._sample(base_dr,    self.uncertainties["discount_rate"]), 0.01, 0.30)

        npv_arr = np.array([
            self._npv_single(capex_arr[i], opex_arr[i], cf_arr[i], price_arr[i],
                             dr_arr[i], life, degradation, debt_frac, debt_rate, debt_term)
            for i in range(self.n_simulations)
        ])
        lcoe_arr = np.array([
            self._lcoe_single(capex_arr[i], opex_arr[i], cf_arr[i], dr_arr[i], life, degradation)
            for i in range(self.n_simulations)
        ])
        # Rough IRR proxy: avg annual net / capex
        irr_arr = (cf_arr * 8760 * price_arr - opex_arr) / capex_arr

        valid = np.isfinite(npv_arr) & np.isfinite(lcoe_arr)
        npv_arr  = npv_arr[valid]
        lcoe_arr = lcoe_arr[valid]
        irr_arr  = irr_arr[valid]

        def pct(a, p): return float(np.percentile(a, p))

        def hist(a, bins=40):
            counts, edges = np.histogram(a, bins=bins)
            return {"counts": counts.tolist(), "edges": edges.tolist(),
                    "mean": float(np.mean(a)), "std": float(np.std(a))}

        corr = {}
        for name, arr in [("capex", capex_arr[valid]), ("opex", opex_arr[valid]),
                           ("capacity_factor", cf_arr[valid]), ("price", price_arr[valid]),
                           ("discount_rate", dr_arr[valid])]:
            try:
                corr[name] = round(float(np.corrcoef(arr, npv_arr)[0, 1]), 4)
            except Exception:
                corr[name] = 0.0

        return MonteCarloResult(
            n_simulations=int(np.sum(valid)),
            npv_distribution=npv_arr,
            irr_distribution=irr_arr,
            lcoe_distribution=lcoe_arr,
            npv_p10=pct(npv_arr, 10), npv_p50=pct(npv_arr, 50), npv_p90=pct(npv_arr, 90),
            irr_p10=pct(irr_arr, 10), irr_p50=pct(irr_arr, 50), irr_p90=pct(irr_arr, 90),
            lcoe_p10=pct(lcoe_arr, 10), lcoe_p50=pct(lcoe_arr, 50), lcoe_p90=pct(lcoe_arr, 90),
            prob_positive_npv=float(np.mean(npv_arr > 0)),
            param_correlations=corr,
            histogram_data={
                "npv":  hist(npv_arr),
                "irr":  hist(irr_arr),
                "lcoe": hist(lcoe_arr),
            },
        )
