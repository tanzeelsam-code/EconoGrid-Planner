# EconoGrid Planner — User Manual

**Version 1.0 | Econometric & Energy Planning Suite**

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dashboard Overview](#2-dashboard-overview)
3. [Module 1: Regression Engine (EViews-Equivalent)](#3-module-1-regression-engine)
4. [Module 2: Scenario Model (LEAP-Equivalent)](#4-module-2-scenario-model)
5. [Module 3: Financial Screening (RETScreen-Equivalent)](#5-module-3-financial-screening)
6. [Uploading Your Own Data](#6-uploading-your-own-data)
7. [Excel Export](#7-excel-export)
8. [Formulas & Methodology](#8-formulas--methodology)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Getting Started

### Prerequisites

- Python 3.8+
- Internet connection (first time only, for installing dependencies)

### Installation

```bash
cd "Energy calculations"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application

```bash
source venv/bin/activate
python run.py
```

Open your browser to **http://localhost:5001**

> **Note:** Port 5001 is used instead of 5000 to avoid conflict with macOS AirPlay Receiver.

---

## 2. Dashboard Overview

The home page shows three module cards:

| Module | Icon | Equivalent To | Purpose |
|--------|------|---------------|---------|
| **Regression Engine** | 📊 | EViews | Econometric demand modeling & forecasting |
| **Scenario Model** | 🔋 | LEAP | Energy system planning & emissions |
| **Financial Screening** | 💰 | RETScreen | Techno-economic assessment |

The navigation bar at the top provides quick access to all modules.

---

## 3. Module 1: Regression Engine

**Path:** `/regression`

### What It Does

Runs Ordinary Least Squares (OLS) regression to model electricity demand as a function of economic variables, then forecasts demand 30 years forward.

### Input Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Model Specification** | Log-Log (elasticity), Linear, or Semi-Log | Log-Log |
| **Dependent Variable** | The variable to predict | Electricity Demand (GWh) |
| **GDP Growth Rate (%)** | Annual GDP growth for forecasting | 4.0% |
| **Population Growth (%)** | Annual population growth | 2.0% |
| **Price Growth (%)** | Annual electricity price growth | 1.0% |

### How to Use

1. Select your **model type** (Log-Log recommended for elasticity analysis)
2. Adjust **growth rate assumptions** for the forecast
3. Click **▶ Run Regression**
4. Review the results:
   - **R², Adj. R², F-statistic, Durbin-Watson** — model fit metrics
   - **Coefficient Table** — variable elasticities and significance
   - **Diagnostic Tests** — Jarque-Bera, Breusch-Pagan, Breusch-Godfrey
   - **Forecast Chart** — 30-year demand projection
   - **Residuals Chart** — model fit quality
   - **EViews-Style Summary** — text output matching EViews format

### Uploading Custom Data

Click **"Upload CSV / Excel"** to use your own data. Required columns:
- `Year` (numeric)
- A dependent variable column (e.g., `Electricity_Demand_GWh`)
- Independent variable columns (e.g., `GDP_Billion_USD`, `Population_Million`)

After upload, select which column is the dependent variable and check/uncheck independent variables.

---

## 4. Module 2: Scenario Model

**Path:** `/scenario`

### What It Does

Bottom-up energy demand projections under 3 scenarios (BAU, Low Carbon, High Growth), with peak demand (MW) calculation and emissions accounting.

### Input Parameters

#### Planning Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Base Year** | Starting year for projections | 2022 |
| **Projection Horizon** | Number of years to project | 30 |
| **Population (million)** | Optional — enables per-capita kWh metric | — |
| **Population Growth (%)** | Annual population growth rate | 2.0% |
| **Summer Load Factor** | Avg demand / Peak demand in summer | 0.60 |
| **Winter Load Factor** | Avg demand / Peak demand in winter (lower = higher peaks) | 0.45 |
| **Reserve Margin (%)** | Extra capacity above system peak | 15% |

#### Sector Base Demand Table

An editable table where you directly enter demand per sector:

| Column | Description |
|--------|-------------|
| **Sector** | Name (editable — add your own) |
| **Base Demand (GWh)** | Starting year electricity demand |
| **BAU Growth (%/yr)** | Growth rate for Business As Usual |
| **Low Carbon Growth (%/yr)** | Growth rate for efficiency scenario |
| **High Growth (%/yr)** | Growth rate for accelerated development |

Default sectors: Residential (12,500), Commercial (8,200), Industrial (25,000), Agriculture (3,500), Transport (5,800) = **55,000 GWh total**.

Use **"+ Add Sector"** to add additional sectors. Click **✕** to remove a sector.

### How to Use

1. Set your **base year** and **projection horizon**
2. Enter **population** if you want per-capita metrics
3. Set **summer/winter load factors** for MW peak demand calculation
4. Edit the **sector demand table** with your actual GWh values and growth rates
5. Click **▶ Run All Scenarios**

### Output Metrics

| Metric | Description |
|--------|-------------|
| **Total Demand (GWh)** | Base year total electricity demand |
| **Summer Peak (MW)** | Peak demand using summer load factor |
| **Winter Peak (MW)** | Peak demand using winter load factor (typically higher) |
| **Required Capacity (MW)** | Winter peak + reserve margin — tells you how much installed capacity you need |
| **Per Capita (kWh)** | Demand per person per year (if population entered) |

### Understanding Load Factors

- **Load Factor** = Average Demand ÷ Peak Demand
- A **lower** load factor means **higher** peak relative to average (more "peaky" demand)
- **Winter** typically has lower load factor due to heating spikes
- **Summer** may have lower load factor in hot climates due to air conditioning

The formula: **Peak MW = GWh × 1000 ÷ (8760 × Load Factor)**

### Charts Produced

1. **Total Energy Demand by Scenario** — 3-line comparison (GWh over time)
2. **CO₂ Emissions by Scenario** — emissions trajectory comparison
3. **Demand by Sector** — stacked area chart showing sector contributions

---

## 5. Module 3: Financial Screening

**Path:** `/financial`

### What It Does

Techno-economic assessment of energy projects: calculates LCOE, NPV, IRR, payback period, benefit-cost ratio, and runs sensitivity analysis.

### Input Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **CAPEX (USD)** | Total capital expenditure | $45,000,000 |
| **Annual OPEX (USD)** | Annual operating costs | $650,000 |
| **Capacity (MW)** | Plant capacity | 50 MW |
| **Capacity Factor** | Annual energy output / Maximum output | 0.22 |
| **Discount Rate (%)** | Used for NPV and LCOE discounting | 8% |
| **Electricity Price (USD/MWh)** | Revenue per MWh sold | $65 |
| **Project Life (years)** | Operational lifetime | 25 years |
| **Debt Fraction (%)** | Percentage of financing via debt | 70% |

### How to Use

1. Enter your **project parameters** in the form
2. Click **▶ Run Analysis**
3. Review the key metrics:

| Metric | What It Means |
|--------|---------------|
| **LCOE (USD/MWh)** | Levelized Cost of Energy — your cost per MWh |
| **NPV (USD)** | Net Present Value — total project value in today's dollars |
| **IRR (%)** | Internal Rate of Return — annualized return rate |
| **Payback (years)** | When cumulative cash flow turns positive |
| **B/C Ratio** | Benefit-Cost Ratio — must be >1.0 to be viable |

### Charts Produced

1. **Cumulative Cash Flow** — shows payback year visually
2. **Annual Net Cash Flow** — yearly profitability
3. **Revenue vs. Total Costs** — revenue-cost crossover
4. **NPV Sensitivity (Tornado)** — which parameters impact NPV most

### Sensitivity Analysis

The tornado chart shows how ±20% changes in each parameter affect NPV:
- **Green bars** = upside (favorable change)
- **Red bars** = downside (unfavorable change)
- **Longest bar** = most sensitive parameter

---

## 6. Uploading Your Own Data

All three modules support **CSV and Excel** file upload.

### How to Upload

1. Click **"Upload CSV / Excel"** toggle button
2. Either **drag & drop** your file or click **browse**
3. Review the data preview
4. Click **Run** — the model uses your uploaded data

### Download Templates

Click **"📄 Download Template"** on any module to get a sample CSV with the correct column names.

### Supported Formats

| Format | Extension |
|--------|-----------|
| CSV | `.csv` |
| Excel | `.xlsx`, `.xls` |

### Tips

- For **Regression**: include a `Year` column and numeric columns for your variables
- For **Scenario**: include `Sector`, `Fuel`, `Base_Year_Demand_PJ`, `Activity_Growth_Rate`, `Intensity_Change_Rate`
- For **Financial**: single row with project parameters as column headers (use the template as reference)
- The financial module **auto-fills** the form when you upload a matching CSV

---

## 7. Excel Export

Every module produces a **professional Excel workbook** with:

- Formatted tables with headers, borders, and number formatting
- Summary sheets with key metrics
- Detailed data sheets
- Chart-ready data layouts

Click **"📥 Download Excel"** after running an analysis (button becomes active after results are shown).

Files are saved to the `output/` directory with timestamps.

---

## 8. Formulas & Methodology

### Regression Module

| Model | Equation |
|-------|----------|
| **Log-Log** | ln(Y) = β₀ + β₁·ln(X₁) + β₂·ln(X₂) + ... |
| **Linear** | Y = β₀ + β₁·X₁ + β₂·X₂ + ... |
| **Semi-Log** | ln(Y) = β₀ + β₁·X₁ + β₂·X₂ + ... |

In Log-Log, coefficients are **elasticities** (e.g., β₁ = 0.8 means 1% GDP increase → 0.8% demand increase).

**Diagnostic Tests:**
- Jarque-Bera: normality of residuals
- Breusch-Pagan: heteroscedasticity
- Breusch-Godfrey: serial correlation

### Scenario Module

**Energy Demand:**
```
Demand(t) = Base Demand × (1 + Growth Rate)^t × (1 + Intensity Change)^t
```

**Peak Demand Conversion:**
```
Peak MW = Energy (GWh) × 1000 / (8760 × Load Factor)
Required Capacity = System Peak × (1 + Reserve Margin)
```

**Per-Capita:**
```
Per Capita (kWh) = Total GWh × 1,000,000 / Population (million)
```

### Financial Module

**LCOE:**
```
LCOE = Σ(Costs_t / (1+r)^t) / Σ(Generation_t / (1+r)^t)
```

**NPV:**
```
NPV = -CAPEX + Σ(Net Cash Flow_t / (1+r)^t)
```

**IRR:**
The discount rate that makes NPV = 0.

---

## 9. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Port 5000 in use** | Already handled — app uses port 5001 |
| **"NaN" error in Financial** | Fixed — NaN values converted to null for JSON |
| **Module not loading** | Run `pip install -r requirements.txt` to ensure all dependencies |
| **Charts not showing** | Ensure browser allows JavaScript; try refreshing the page |
| **Excel download fails** | Ensure `output/` directory exists (created automatically) |

### Checking Health

Visit **http://localhost:5001/health** — should return `{"status": "healthy"}`.

### Running Tests

```bash
source venv/bin/activate
python -m pytest tests/test_all.py -v
```

Expected: **25 passed**.

### Project Structure

```
Energy calculations/
├── run.py                  # Entry point
├── config.py               # Configuration
├── requirements.txt        # Dependencies
├── modules/
│   ├── regression/         # OLS, diagnostics, forecasting, export
│   ├── scenario/           # LEAP model, scenarios, emissions, supply
│   └── financial/          # LCOE, NPV/IRR, cash flow, sensitivity
├── dashboard/
│   ├── app.py              # Flask app factory
│   ├── routes/             # API endpoints per module + upload
│   ├── templates/          # HTML pages
│   └── static/             # CSS, JS
├── utils/                  # Shared data & Excel utilities
├── tests/                  # Test suite (25 tests)
└── output/                 # Generated Excel files
```

---

*EconoGrid Planner — Built with Python, Flask, Plotly, statsmodels, numpy-financial*
