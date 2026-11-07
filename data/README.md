# Heirloom open data

Everything here is free and needs no API key or sign-up. Regenerate with:

    pip install requests pandas openpyxl beautifulsoup4 yfinance
    python scripts/fetch_open_data.py            # or: ons boe hpi markets kb

`MANIFEST.json` records every file's source URL and fetch time (use it for the "every figure has a source" guardrail).

| Path | Source | Brief use |
|---|---|---|
| `raw/ons/lcf_wb1..wb4_*.xlsx` | ONS Family Spending (Living Costs and Food Survey) FYE 2025 | Calibrate synthetic transactions (by category, income decile, region, household type) |
| `raw/ons/was_*.xlsx` | ONS Wealth and Assets Survey (total, financial, property, pension, debt, individual) | Wealth-by-age problem slide. **Indicative only**: lost accredited status in 2025 |
| `raw/ons/ashe_table6_age__*.zip`, `ashe_table3_*` | ONS ASHE 2026 provisional | Earnings by age / region x occupation, income growth |
| `raw/ons/national_life_tables_uk__current.xlsx` | ONS National Life Tables | Retirement planning horizon |
| `clean/cpi_*.csv`, `clean/cpih_annual_rate.csv` | ONS CPI/CPIH | Inflation scenarios |
| `clean/awe_total_pay_growth.csv`, `clean/household_saving_ratio.csv` | ONS AWE, saving ratio | Wage growth, savings benchmark |
| `clean/boe_bank_rate_changes.csv` | Bank of England Bank Rate history (1975 on) | Rate scenarios |
| `clean/hpi_regions_monthly.csv`, `clean/hpi_latest_deposit_targets.csv` | HM Land Registry UK HPI (full file in `raw/hpi/`, ~35MB) | Regional first-time-buyer prices, 5%/10% deposit targets |
| `clean/markets/*_1d.csv`, `*_1mo.csv` | Yahoo Finance via yfinance: FTSE All-Share, FTSE 100, VWRL.L, MSCI World (URTH), GBP/USD | Block bootstrap returns |
| `clean/markets/jst_uk_annual_returns.csv` | Jorda-Schularick-Taylor Macrohistory R6 (CC BY-NC-SA) | UK equity, bond, housing, bill returns 1870-2020 for long-horizon Monte Carlo |
| `kb/govuk/*.md` | gov.uk Content API | RAG: ISAs, LISA, JISA, IHT and gifts, pensions, benefits, debt |
| `kb/fca/*.md`, `kb/citizensadvice/*.md` | FCA ScamSmart and consumer pages, Citizens Advice | Claim Check signals and sources |

Not included (need a key, sign-up, or block scripts): NatWest Bank of APIs sandbox, FCA Register API, Firecrawl, MoneyHelper, StepChange, Action Fraud.
