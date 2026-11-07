"""Spending calibration from ONS Living Costs and Food Survey (FYE 2025, Table A1).

Average weekly household expenditure (GBP, all UK households). We read it from
the workbook in data/raw/ons when available and fall back to the values below
(copied from the same table) so the module works without openpyxl.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LCF_PATH = REPO / "data" / "raw" / "ons" / "lcf_wb1_detailed_expenditure__fye2025.xlsx"
SOURCE = "ONS Family Spending FYE 2025, Living Costs and Food Survey, Table A1"

# COICOP division -> average weekly spend (GBP), FYE 2025.
LCF_WEEKLY_FALLBACK = {
    1: 73.70,   # Food & non-alcoholic drinks
    2: 11.30,   # Alcoholic drink, tobacco & narcotics
    3: 18.00,   # Clothing & footwear
    4: 118.40,  # Housing (net), fuel & power  -> modelled separately as housing + utilities
    5: 40.60,   # Household goods & services
    6: 11.90,   # Health
    7: 96.40,   # Transport
    8: 22.40,   # Communication
    9: 82.10,   # Recreation & culture
    11: 49.20,  # Restaurants & hotels
    12: 49.80,  # Miscellaneous goods and services
}

# Our transaction categories -> (COICOP divisions, share of that division that shows
# up as day-to-day card spend rather than big one-off purchases like cars).
CATEGORY_MAP = {
    "groceries": ([1, 2], 1.0),
    "transport": ([7], 0.55),
    "eating_out": ([11], 1.0),
    "shopping": ([3, 5, 6], 0.8),
    "recreation": ([9], 0.6),
    "personal": ([12], 0.6),
}


@lru_cache(maxsize=1)
def lcf_weekly() -> dict[int, float]:
    try:
        import pandas as pd

        df = pd.read_excel(LCF_PATH, sheet_name="A1", header=None)
        top = df[df[0].astype(str).str.fullmatch(r"\d{1,2}")]
        out = {}
        for _, row in top.iterrows():
            val = row[6]
            if isinstance(val, (int, float)) and val == val:
                out[int(row[0])] = float(val)
        if len(out) >= 10:
            return out
    except Exception:
        pass
    return dict(LCF_WEEKLY_FALLBACK)


@lru_cache(maxsize=1)
def discretionary_shares() -> dict[str, float]:
    """Share of day-to-day discretionary spend going to each category."""
    weekly = lcf_weekly()
    raw = {
        cat: sum(weekly.get(d, 0.0) for d in divs) * frac
        for cat, (divs, frac) in CATEGORY_MAP.items()
    }
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def average_weekly_discretionary() -> float:
    weekly = lcf_weekly()
    return sum(
        sum(weekly.get(d, 0.0) for d in divs) * frac for divs, frac in CATEGORY_MAP.values()
    )
