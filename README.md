# Econometric & Energy Modeling Toolkit (EEMT)

An integrated production-ready software platform combining:

1. **EViews-Equivalent Regression Engine** — Econometric demand modeling with OLS, diagnostics, and 30-year forecasting
2. **LEAP-Equivalent Scenario Model** — Bottom-up energy planning with multi-sector demand/supply/emissions projections
3. **RETScreen-Equivalent Financial Screening** — LCOE, NPV, IRR, cash flow analysis, and sensitivity

All modules produce **professionally formatted Excel workbooks** and are accessible via a **dark-themed Flask web dashboard** with interactive Plotly charts.

---

## Quick Start

```bash
# 1. Install dependencies
cd "Energy calculations"
pip install -r requirements.txt

# 2. Run the dashboard
python run.py

# 3. Open in browser
# http://localhost:5000
```

## Run Tests

```bash
python -m pytest tests/ -v
```

---

## Project Structure

```
Energy calculations/
├── run.py                    # Entry point — starts Flask server
├── config.py                 # Global configuration & defaults
├── requirements.txt          # Python dependencies
│
├── modules/
│   ├── regression/           # Module 1: EViews-equivalent
│   │   ├── regression_engine.py    # OLS (linear/log-log/semi-log)
│   │   ├── diagnostics.py         # JB, BP, BG, VIF, DW tests
│   │   ├── forecast_engine.py     # 30-year demand forecasting
│   │   └── excel_export.py        # EViews-style workbook
│   │
│   ├── scenario/             # Module 2: LEAP-equivalent
│   │   ├── leap_model.py          # Activity × Intensity framework
│   │   ├── scenario_engine.py     # BAU/Low Carbon/High Growth
│   │   ├── emissions_engine.py    # CO₂ accounting
│   │   ├── supply_transformation.py  # Generation mix
│   │   └── excel_export.py        # LEAP-style workbook
│   │
│   └── financial/            # Module 3: RETScreen-equivalent
│       ├── finance_engine.py      # NPV/IRR/payback/BCR
│       ├── lcoe.py                # LCOE calculation
│       ├── cashflow.py            # Annual cash flow analysis
│       ├── sensitivity.py         # OAT sensitivity analysis
│       └── excel_export.py        # RETScreen-style workbook
│
├── dashboard/                # Flask web application
│   ├── app.py                # App factory
│   ├── routes/               # API endpoints per module
│   ├── templates/            # HTML (dark theme)
│   └── static/               # CSS + JS
│
├── utils/                    # Shared utilities
│   ├── excel_utils.py        # Professional Excel formatter
│   └── data_utils.py         # Data loading + sample generators
│
├── outputs/                  # Generated Excel workbooks
└── tests/                    # pytest test suite
```

---

## Module 1 — Regression Engine

**Model Types:** Linear, Log-Log (elasticity), Semi-Log

**Outputs:**
- EViews-style coefficient table (Variable / Coefficient / Std.Error / t-Stat / Prob.)
- R², Adjusted R², F-statistic, Durbin-Watson, AIC, BIC
- Jarque-Bera normality, Breusch-Pagan, Breusch-Godfrey, VIF
- 30-year demand forecast with confidence intervals
- Multi-scenario comparison

## Module 2 — Scenario Model

**Sectors:** Residential, Commercial, Industrial, Agriculture, Transport

**Scenarios:** BAU, Low Carbon, High Growth (user-configurable)

**Outputs:**
- Base year energy balance (sector × fuel matrix)
- Demand projections by sector and fuel
- CO₂ emissions (demand-side + supply-side)
- Scenario comparison tables and charts
- Generation mix evolution

## Module 3 — Financial Screening

**Metrics:** LCOE, NPV, IRR, Simple/Discounted Payback, Benefit-Cost Ratio, Equity IRR

**Features:**
- Annual cash flow analysis (25-year)
- Debt/equity structure with annuity payments
- Depreciation and tax
- OPEX inflation and generation degradation
- Sensitivity analysis on 5 parameters (CAPEX, discount rate, price, capacity factor, OPEX)
- Tornado chart data

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Econometrics | statsmodels |
| Data | pandas, numpy |
| Financial Math | numpy-financial |
| Excel Export | openpyxl |
| Visualization | Plotly |
| Web Framework | Flask |
| Testing | pytest |

---

## Dashboard

Dark-themed, professional UI with:
- **Tab-based navigation** — Home / EViews / LEAP / RETScreen
- **Parameter input forms** for each module
- **Interactive Plotly charts** (forecast, scenarios, cash flow, tornado)
- **Results cards** with key metrics
- **Excel download buttons** for each module

---

## License

Open source — for planning, analysis, and educational purposes.
