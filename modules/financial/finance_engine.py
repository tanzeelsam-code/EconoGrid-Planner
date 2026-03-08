"""
Finance Engine — RETScreen-Equivalent Financial Analysis.

Central orchestrator for the financial screening module.
Coordinates LCOE, NPV, IRR, payback, cash flow, and sensitivity
calculations for clean energy project assessment.
"""

import numpy as np
import pandas as pd
import numpy_financial as npf
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class FinancialResult:
    """Container for all financial analysis outputs."""
    project_name: str
    technology: str

    # Key metrics
    lcoe: float                      # USD/MWh
    npv: float                       # USD
    firr: Optional[float]            # Financial IRR (with taxes/debt)
    eirr: Optional[float]            # Economic IRR (no taxes/debt)
    payback_period: Optional[float]  # Years or None
    discounted_payback: Optional[float]
    benefit_cost_ratio: float
    equity_irr: Optional[float]

    # Project parameters
    capex: float
    annual_opex: float
    annual_generation: float
    project_life: int
    discount_rate: float
    electricity_price: float

    # Annual tables
    cashflow_table: pd.DataFrame
    revenue_table: pd.DataFrame

    # Summary dict for easy export
    summary: Dict[str, Any]


class FinanceEngine:
    """
    RETScreen-equivalent financial analysis engine.

    Performs comprehensive techno-economic assessment:
    - LCOE (Levelized Cost of Electricity)
    - NPV (Net Present Value)
    - IRR (Internal Rate of Return)
    - Payback Period (simple and discounted)
    - Benefit-Cost Ratio
    - Annual cash flow analysis (20-30 years)
    - Debt/equity structure
    """

    def __init__(self, project_data: Dict[str, Any]):
        """
        Initialize with project parameters.

        Args:
            project_data: Dictionary from generate_sample_financial_data() or equivalent.
        """
        self.data = project_data
        self.project_name = project_data.get("project_name", "Unnamed Project")
        self.technology = project_data.get("technology", "")
        self.capacity_mw = project_data.get("capacity_mw", 0)
        self.capacity_factor = project_data.get("capacity_factor", 0.22)

        # Financial parameters
        self.capex = project_data.get("capex_total_usd", 0)
        self.annual_opex = project_data.get("annual_opex_usd", 0)
        self.annual_generation = project_data.get("annual_generation_mwh", 0)
        self.project_life = project_data.get("project_life_years", 25)
        self.discount_rate = project_data.get("discount_rate", 0.08)
        self.inflation_rate = project_data.get("inflation_rate", 0.02)
        self.degradation_rate = project_data.get("degradation_rate", 0.005)
        self.elec_price = project_data.get("electricity_price_usd_mwh", 65)
        self.price_escalation = project_data.get("price_escalation_rate", 0.015)

        # Debt/equity
        self.debt_fraction = project_data.get("debt_fraction", 0.70)
        self.debt_rate = project_data.get("debt_interest_rate", 0.06)
        self.debt_term = project_data.get("debt_term_years", 15)
        self.tax_rate = project_data.get("tax_rate", 0.0)
        self.depreciation_years = project_data.get("depreciation_years", 20)

        self._result: Optional[FinancialResult] = None

    @property
    def result(self) -> Optional[FinancialResult]:
        return self._result

    def run_analysis(self) -> FinancialResult:
        """
        Execute the full financial analysis.

        Returns:
            FinancialResult with all metrics and tables.
        """
        # ── Build annual cash flow table ───────────────────────────────────
        cashflow_df = self._build_cashflow_table()

        # ── LCOE ───────────────────────────────────────────────────────────
        lcoe = self._calculate_lcoe()

        # ── NPV ────────────────────────────────────────────────────────────
        project_cashflows = cashflow_df["Net Cash Flow"].values
        npv = float(npf.npv(self.discount_rate, project_cashflows))

        # ── FIRR (Financial IRR — includes taxes & debt service) ─────────
        try:
            firr = float(npf.irr(project_cashflows))
            if np.isnan(firr) or firr > 1.0 or firr < -1.0:
                firr = None
        except (ValueError, RuntimeError):
            firr = None

        # ── EIRR (Economic IRR — no taxes, no debt, pure economic flows) ──
        economic_cashflows = cashflow_df["Economic Cash Flow"].values
        try:
            eirr = float(npf.irr(economic_cashflows))
            if np.isnan(eirr) or eirr > 1.0 or eirr < -1.0:
                eirr = None
        except (ValueError, RuntimeError):
            eirr = None

        # ── Payback periods ────────────────────────────────────────────────
        payback = self._calculate_payback(cashflow_df["Net Cash Flow"].values)
        disc_payback = self._calculate_discounted_payback(
            cashflow_df["Net Cash Flow"].values
        )

        # ── Benefit-Cost Ratio ─────────────────────────────────────────────
        pv_benefits = sum(
            cashflow_df.loc[cashflow_df["Year"] > 0, "Revenue"].values /
            (1 + self.discount_rate) ** cashflow_df.loc[
                cashflow_df["Year"] > 0, "Year"
            ].values
        )
        pv_costs = self.capex + sum(
            cashflow_df.loc[cashflow_df["Year"] > 0, "Total Costs"].values /
            (1 + self.discount_rate) ** cashflow_df.loc[
                cashflow_df["Year"] > 0, "Year"
            ].values
        )
        bcr = pv_benefits / pv_costs if pv_costs > 0 else 0

        # ── Equity IRR ─────────────────────────────────────────────────────
        equity_flows = cashflow_df["Equity Cash Flow"].values
        try:
            equity_irr = float(npf.irr(equity_flows))
            if np.isnan(equity_irr) or equity_irr > 2.0 or equity_irr < -1.0:
                equity_irr = None
        except (ValueError, RuntimeError):
            equity_irr = None

        # ── Revenue table ──────────────────────────────────────────────────
        revenue_df = cashflow_df[
            ["Year", "Generation (MWh)", "Electricity Price", "Revenue"]
        ].copy()

        # ── Summary ────────────────────────────────────────────────────────
        summary = {
            "Project Name": self.project_name,
            "Technology": self.technology,
            "Capacity (MW)": self.capacity_mw,
            "Capacity Factor": f"{self.capacity_factor:.1%}",
            "CAPEX (USD)": f"${self.capex:,.0f}",
            "Annual OPEX (USD)": f"${self.annual_opex:,.0f}",
            "Project Life (years)": self.project_life,
            "Discount Rate": f"{self.discount_rate:.1%}",
            "LCOE (USD/MWh)": f"${lcoe:.2f}",
            "NPV (USD)": f"${npv:,.0f}",
            "FIRR (Financial)": f"{firr:.2%}" if firr is not None else "N/A",
            "EIRR (Economic)": f"{eirr:.2%}" if eirr is not None else "N/A",
            "Simple Payback (years)": f"{payback:.1f}" if payback else "N/A",
            "Discounted Payback (years)": f"{disc_payback:.1f}" if disc_payback else "N/A",
            "Benefit-Cost Ratio": f"{bcr:.3f}",
            "Equity IRR": f"{equity_irr:.2%}" if equity_irr is not None else "N/A",
        }

        self._result = FinancialResult(
            project_name=self.project_name,
            technology=self.technology,
            lcoe=round(lcoe, 2),
            npv=round(npv, 2),
            firr=round(firr, 4) if firr is not None else None,
            eirr=round(eirr, 4) if eirr is not None else None,
            payback_period=round(payback, 1) if payback else None,
            discounted_payback=round(disc_payback, 1) if disc_payback else None,
            benefit_cost_ratio=round(bcr, 3),
            equity_irr=round(equity_irr, 4) if equity_irr is not None else None,
            capex=self.capex,
            annual_opex=self.annual_opex,
            annual_generation=self.annual_generation,
            project_life=self.project_life,
            discount_rate=self.discount_rate,
            electricity_price=self.elec_price,
            cashflow_table=cashflow_df,
            revenue_table=revenue_df,
            summary=summary,
        )

        return self._result

    def _build_cashflow_table(self) -> pd.DataFrame:
        """Build the annual cash flow table (Year 0 to project_life)."""
        rows = []

        # Year 0: CAPEX
        equity = self.capex * (1 - self.debt_fraction)
        debt_amount = self.capex * self.debt_fraction
        annual_debt_payment = self._calculate_annual_debt_payment(debt_amount)

        rows.append({
            "Year": 0,
            "Generation (MWh)": 0,
            "Electricity Price": 0,
            "Revenue": 0,
            "OPEX": 0,
            "Total Costs": 0,
            "Debt Service": 0,
            "Depreciation": 0,
            "Tax": 0,
            "Net Cash Flow": -self.capex,
            "Economic Cash Flow": -self.capex,
            "Equity Cash Flow": -equity,
            "Cumulative Cash Flow": -self.capex,
            "Discounted CF": -self.capex,
            "Cumulative Discounted CF": -self.capex,
        })

        cumulative = -self.capex
        cumulative_disc = -self.capex

        for year in range(1, self.project_life + 1):
            # Generation with degradation
            gen = self.annual_generation * (1 - self.degradation_rate) ** (year - 1)

            # Revenue with price escalation
            price = self.elec_price * (1 + self.price_escalation) ** (year - 1)
            revenue = gen * price

            # OPEX with inflation
            opex = self.annual_opex * (1 + self.inflation_rate) ** (year - 1)

            # Debt service
            debt_service = annual_debt_payment if year <= self.debt_term else 0

            # Depreciation (straight-line)
            depreciation = self.capex / self.depreciation_years if year <= self.depreciation_years else 0

            # Tax
            taxable_income = revenue - opex - depreciation
            tax = max(0, taxable_income * self.tax_rate)

            # Net cash flow (financial: includes debt + tax)
            net_cf = revenue - opex - debt_service - tax

            # Economic cash flow (no taxes, no debt — pure project economics)
            economic_cf = revenue - opex

            # Equity cash flow
            equity_cf = net_cf  # Already accounts for debt service

            # Discounted
            disc_cf = net_cf / (1 + self.discount_rate) ** year

            cumulative += net_cf
            cumulative_disc += disc_cf

            rows.append({
                "Year": year,
                "Generation (MWh)": round(gen, 0),
                "Electricity Price": round(price, 2),
                "Revenue": round(revenue, 2),
                "OPEX": round(opex, 2),
                "Total Costs": round(opex + debt_service + tax, 2),
                "Debt Service": round(debt_service, 2),
                "Depreciation": round(depreciation, 2),
                "Tax": round(tax, 2),
                "Net Cash Flow": round(net_cf, 2),
                "Economic Cash Flow": round(economic_cf, 2),
                "Equity Cash Flow": round(equity_cf, 2),
                "Cumulative Cash Flow": round(cumulative, 2),
                "Discounted CF": round(disc_cf, 2),
                "Cumulative Discounted CF": round(cumulative_disc, 2),
            })

        return pd.DataFrame(rows)

    def _calculate_lcoe(self) -> float:
        """
        Calculate Levelized Cost of Electricity.

        LCOE = PV(Total Costs) / PV(Total Generation)
        """
        pv_costs = self.capex  # Year 0 cost
        pv_generation = 0

        for year in range(1, self.project_life + 1):
            gen = self.annual_generation * (1 - self.degradation_rate) ** (year - 1)
            opex = self.annual_opex * (1 + self.inflation_rate) ** (year - 1)

            pv_costs += opex / (1 + self.discount_rate) ** year
            pv_generation += gen / (1 + self.discount_rate) ** year

        return pv_costs / pv_generation if pv_generation > 0 else float('inf')

    def _calculate_payback(self, cashflows: np.ndarray) -> Optional[float]:
        """Calculate simple payback period."""
        cumulative = 0
        for i, cf in enumerate(cashflows):
            cumulative += cf
            if cumulative >= 0 and i > 0:
                # Interpolate
                prev_cum = cumulative - cf
                fraction = -prev_cum / cf if cf != 0 else 0
                return (i - 1) + fraction
        return None

    def _calculate_discounted_payback(self, cashflows: np.ndarray) -> Optional[float]:
        """Calculate discounted payback period."""
        cumulative = 0
        for i, cf in enumerate(cashflows):
            disc_cf = cf / (1 + self.discount_rate) ** i
            cumulative += disc_cf
            if cumulative >= 0 and i > 0:
                prev_cum = cumulative - disc_cf
                fraction = -prev_cum / disc_cf if disc_cf != 0 else 0
                return (i - 1) + fraction
        return None

    def _calculate_annual_debt_payment(self, principal: float) -> float:
        """Calculate equal annual debt repayment (annuity)."""
        if self.debt_fraction == 0 or principal == 0:
            return 0
        r = self.debt_rate
        n = self.debt_term
        if r == 0:
            return principal / n
        return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
