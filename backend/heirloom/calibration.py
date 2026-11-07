"""Turn the downloaded ONS files into the handful of numbers the synthetic data and forecaster need.

Every figure written to calibration.json carries the file it came from, so the API can cite it.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
LCF_WB4 = DATA / "raw/ons/lcf_wb4_by_household__fye2025.xlsx"
ASHE_ZIP = DATA / "raw/ons/ashe_table6_age__2026provisional.zip"
STATE_PENSION_MD = DATA / "kb/govuk/new-state-pension.md"
OUT = DATA / "clean/calibration.json"

# LCF A17 column header (rows 5-8, letters only, lower-cased) -> our status key
LCF_COLUMNS = {"fulltime": "employee_ft", "parttime": "employee_pt", "selfemployed": "self_employed",
               "retired": "retired", "allhouseholds": "all"}

# COICOP group -> transaction category used by the synthetic generator / benchmarks.
# Housing (4) and "other expenditure" (13) are modelled as explicit recurring bills instead.
COICOP_TO_CATEGORY = {
    1: "groceries", 2: "groceries", 3: "shopping", 5: "shopping", 6: "health", 7: "transport",
    8: "phone", 9: "leisure", 11: "eating_out", 12: "misc",
}
FALLBACK_STATE_PENSION_WEEKLY = 241.30  # gov.uk/new-state-pension, 2026/27

# 2026/27 UK (rUK) income tax and employee Class 1 NI. Thresholds are frozen to April 2028.
TAX = {"personal_allowance": 12570, "basic_limit": 50270, "basic_rate": 0.20, "higher_rate": 0.40,
       "ni_main": 0.08, "ni_upper": 0.02, "source": "https://www.gov.uk/income-tax-rates"}


def _letters(x) -> str:
    return re.sub(r"[^a-z]", "", str(x).lower()) if pd.notna(x) else ""


def parse_lcf_a17(path: Path = LCF_WB4) -> dict:
    """Average weekly spend per person (£) by category for each economic-activity status."""
    df = pd.read_excel(path, sheet_name="A17", header=None)
    header_rows = df.iloc[5:9]
    col_for = {}
    for c in df.columns:
        key = "".join(_letters(v) for v in header_rows[c])  # e.g. "economicallyinactiveretired"
        for suffix, status in LCF_COLUMNS.items():
            if key.endswith(suffix) and status not in col_for:
                col_for[status] = c
    missing = set(LCF_COLUMNS.values()) - set(col_for)
    if missing:
        raise ValueError(f"LCF A17 layout changed, missing columns {missing}")

    persons_row = df[df[0].astype(str).str.contains("persons per household", case=False, na=False)].iloc[0]
    out = {}
    for status, c in col_for.items():
        persons = float(persons_row[c])
        cats: dict[str, float] = {}
        for _, row in df.iterrows():
            code = str(row[0]).strip().removesuffix(".0")  # codes are stored as text ("1") or numbers
            if not code.isdigit() or int(code) not in COICOP_TO_CATEGORY:
                continue
            code = int(code)
            val = pd.to_numeric(str(row[c]).replace(",", ""), errors="coerce")  # cells are text
            if pd.isna(val):  # ".." = suppressed -> all households
                val = pd.to_numeric(str(row[col_for["all"]]).replace(",", ""), errors="coerce")
            cat = COICOP_TO_CATEGORY[int(code)]
            cats[cat] = round(cats.get(cat, 0.0) + float(val) / persons, 2)
        # Housing (net), fuel & power: we take a share as the energy bill (rent is set per persona)
        housing = df[df[0].astype(str).str.strip() == "4"]
        housing_val = float(housing.iloc[0][c]) if len(housing) else 0.0
        out[status] = {"weekly_per_person": cats, "persons_per_household": persons,
                       "housing_fuel_power_weekly_household": housing_val}
    return out


def parse_ashe_annual_gross(path: Path = ASHE_ZIP) -> dict:
    """Full-time gross annual pay percentiles by age band (ASHE Table 6.7a)."""
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if "6.7a" in n and "CV" not in n)
    df = pd.read_excel(io.BytesIO(z.read(name)), sheet_name="Full-Time", header=None)
    hdr_idx = df.index[df[0].astype(str).str.strip() == "Description"][0]
    hdr = df.loc[hdr_idx]
    cols = {}
    for c in df.columns:
        h = str(hdr[c]).strip()
        if h == "Median":
            cols["p50"] = c
        elif h.isdigit() and int(h) in (10, 20, 25, 30, 40, 60, 70, 75, 80, 90):
            cols[f"p{h}"] = c
    out = {}
    for _, row in df.loc[hdr_idx + 1:].iterrows():
        band = str(row[0]).strip()
        if not re.fullmatch(r"\d\d-\d\d|60\+", band):
            continue
        out[band] = {k: float(row[c]) for k, c in cols.items() if isinstance(row[c], (int, float))}
    return {"source": f"{path.name}::{name} (Full-Time)", "bands": out}


def parse_state_pension(path: Path = STATE_PENSION_MD) -> dict:
    try:
        m = re.search(r"full rate of new State Pension is £([\d.,]+) a week", path.read_text())
        if m:
            return {"weekly": float(m.group(1).replace(",", "")), "source": "https://www.gov.uk/new-state-pension"}
    except OSError:
        pass
    return {"weekly": FALLBACK_STATE_PENSION_WEEKLY, "source": "fallback constant (gov.uk 2026/27)"}


def net_annual_pay(gross: float) -> float:
    """Simple PAYE income tax + employee NI. No student loan / pension salary sacrifice."""
    pa, bl = TAX["personal_allowance"], TAX["basic_limit"]
    taxable_basic = max(0.0, min(gross, bl) - pa)
    taxable_higher = max(0.0, gross - bl)
    tax = taxable_basic * TAX["basic_rate"] + taxable_higher * TAX["higher_rate"]
    ni = max(0.0, min(gross, bl) - pa) * TAX["ni_main"] + max(0.0, gross - bl) * TAX["ni_upper"]
    return gross - tax - ni


def build(write: bool = True) -> dict:
    cal = {
        "lcf": parse_lcf_a17(),
        "lcf_source": f"ONS Family Spending FYE2025, Workbook 4 Table A17 ({LCF_WB4.name})",
        "ashe": parse_ashe_annual_gross(),
        "state_pension": parse_state_pension(),
        "tax": TAX,
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(cal, indent=2))
    return cal


@lru_cache(maxsize=1)
def load() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text())
    return build()


def age_band(age: int) -> str:
    for lo, hi in ((18, 21), (22, 29), (30, 39), (40, 49), (50, 59)):
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    return "60+"


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
