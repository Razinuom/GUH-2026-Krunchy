"""Generate 12 months of daily transactions for the six personas.

Deterministic for a given (as_of, seed). The current balance on `as_of - 1` equals each persona's
`current_balance`; the opening balance is back-solved from it.
"""
from __future__ import annotations

import calendar
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import calibration
from .personas import Persona, monthly_net_salary, personas, state_pension_4weekly

OUT = calibration.DATA / "synthetic/transactions.csv"
HISTORY_DAYS = 365

# category -> (P(transaction) on a weekday, on a weekend day, lognormal sigma, merchants)
PATTERNS = {
    "groceries":  (0.40, 0.60, 0.55, ["TESCO", "ALDI", "LIDL", "SAINSBURYS", "CO-OP"]),
    "eating_out": (0.20, 0.45, 0.60, ["GREGGS", "NANDOS", "PRET", "JUST EAT", "DELIVEROO", "LOCAL PUB"]),
    "transport":  (0.30, 0.20, 0.50, ["SHELL", "BP", "TFL", "NORTHERN RAIL", "UBER", "FIRST BUS"]),
    "shopping":   (0.12, 0.25, 0.80, ["AMAZON", "PRIMARK", "ARGOS", "B&M", "BOOTS", "VINTED"]),
    "leisure":    (0.12, 0.30, 0.70, ["CINEWORLD", "STEAM", "WATERSTONES", "BET365", "GARDEN CENTRE"]),
    "health":     (0.04, 0.04, 0.50, ["BOOTS PHARMACY", "SUPERDRUG", "DENTAL CARE"]),
    "misc":       (0.10, 0.10, 0.80, ["POST OFFICE", "TIMPSON", "CHARITY SHOP", "PAYPAL"]),
    "fuel":       (0.30, 0.10, 0.25, ["SHELL", "BP", "ESSO", "TEXACO"]),
}
VARIABLE_FROM_LCF = ["groceries", "eating_out", "transport", "shopping", "leisure", "health", "misc"]
# month -> category multipliers (Black Friday, Christmas, January squeeze, summer)
SEASONAL = {
    11: {"shopping": 1.25},
    12: {"shopping": 1.7, "leisure": 1.35, "eating_out": 1.3, "groceries": 1.15},
    1: {"shopping": 0.75, "leisure": 0.8, "eating_out": 0.8},
    7: {"leisure": 1.15, "eating_out": 1.1},
    8: {"leisure": 1.15, "eating_out": 1.1},
}
ENERGY_SEASON = {11: 1.35, 12: 1.6, 1: 1.7, 2: 1.5, 3: 1.25, 4: 1.0, 5: 0.75, 6: 0.6, 7: 0.55, 8: 0.55, 9: 0.7, 10: 1.0}


def default_as_of() -> date:
    env = os.environ.get("HEIRLOOM_AS_OF")
    return date.fromisoformat(env) if env else date.today()


def _payday(y: int, m: int, day: int) -> date:
    d = date(y, m, min(day, calendar.monthrange(y, m)[1]))
    while d.weekday() >= 5:  # weekend -> previous Friday
        d -= timedelta(days=1)
    return d


def _months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _persona_rows(p: Persona, start: date, end: date, rng: np.random.Generator) -> list[dict]:
    cal = calibration.load()
    rows: list[dict] = []

    def add(d: date, amount: float, category: str, merchant: str):
        if start <= d <= end:
            rows.append({"date": d, "member_id": p.id, "amount": round(amount, 2), "category": category, "merchant": merchant})

    # ---- income
    for inc in p.incomes:
        if inc.kind == "salary":
            net = monthly_net_salary(p, inc)
            for y, m in _months(start, end):
                add(_payday(y, m, inc.day), net, "income", inc.merchant)
        elif inc.kind == "monthly":
            for y, m in _months(start, end):
                add(_payday(y, m, inc.day), inc.amount, "income", inc.merchant)
        elif inc.kind == "state_pension":
            amt = state_pension_4weekly(inc)
            d = end - timedelta(days=int(rng.integers(3, 25)))  # anchor inside the last 4 weeks
            while d >= start:
                add(d, amt, "income", inc.merchant)
                d -= timedelta(days=28)
        elif inc.kind == "gig_weekly":
            d = start + timedelta(days=(4 - start.weekday()) % 7)  # Fridays
            mu = np.log(inc.amount) - inc.sigma ** 2 / 2
            while d <= end:
                if rng.random() >= inc.miss_prob:
                    seasonal = 1.15 if d.month == 12 else (0.85 if d.month in (1, 2) else 1.0)  # peak season
                    add(d, float(rng.lognormal(mu, inc.sigma)) * seasonal, "income", inc.merchant)
                d += timedelta(days=7)

    # ---- bills
    as_of = end + timedelta(days=1)
    for b in p.bills:
        if b.every_days:
            d = start + timedelta(days=int(rng.integers(0, b.every_days)))
            while d <= end:
                add(d, -b.amount_on(d, as_of), b.category, b.merchant)
                d += timedelta(days=b.every_days)
            continue
        for y, m in _months(start, end):
            if b.months and m not in b.months:
                continue
            d = date(y, m, min(b.day, calendar.monthrange(y, m)[1]))
            amt = b.amount_on(d, as_of) * (ENERGY_SEASON[m] if b.seasonal_energy else 1.0)
            add(d, -amt, b.category, b.merchant)

    # ---- unexpected one-off costs in the history (category "one_off")
    for days_before, amount, merchant in p.past_one_offs:
        add(as_of - timedelta(days=days_before), -amount, "one_off", merchant)

    # ---- everyday spending, calibrated to LCF per-person weekly means
    lcf = cal["lcf"][p.status]["weekly_per_person"]
    weekly = {c: lcf[c] * p.household_size * p.spend_scale * p.category_scale.get(c, 1.0) for c in VARIABLE_FROM_LCF}
    weekly.update(p.extra_weekly)
    d = start
    while d <= end:
        weekend = d.weekday() >= 5
        for cat, target in weekly.items():
            p_wd, p_we, sigma, merchants = PATTERNS[cat]
            n_per_week = 5 * p_wd + 2 * p_we
            mean_amt = target / n_per_week * SEASONAL.get(d.month, {}).get(cat, 1.0)
            if rng.random() < (p_we if weekend else p_wd):
                amt = float(rng.lognormal(np.log(mean_amt) - sigma ** 2 / 2, sigma))
                add(d, -amt, cat, merchants[int(rng.integers(len(merchants)))])
        if rng.random() < 0.015:  # occasional refund
            add(d, float(rng.uniform(8, 60)), "refund", "AMAZON REFUND")
        d += timedelta(days=1)
    return rows


def generate(as_of: date | None = None, seed: int = 42) -> pd.DataFrame:
    as_of = as_of or default_as_of()
    end = as_of - timedelta(days=1)
    start = as_of - timedelta(days=HISTORY_DAYS)
    frames = []
    for i, p in enumerate(personas().values()):
        rng = np.random.default_rng(seed * 1000 + i)
        rows = _persona_rows(p, start, end, rng)
        surplus = sum(r["amount"] for r in rows)
        if surplus > 300:  # savers sweep most of the surplus to a savings pot each month
            sweep = round(0.85 * surplus / 12, -1)
            for y, m in _months(start, end):
                d = date(y, m, 3)
                if start <= d <= end:
                    rows.append({"date": d, "member_id": p.id, "amount": -sweep, "category": "savings",
                                 "merchant": "TRANSFER TO SAVINGS"})
        df = pd.DataFrame(rows)
        df = df.sort_values(["date", "amount"], ascending=[True, False], kind="stable").reset_index(drop=True)
        opening = p.current_balance - df.amount.sum()
        df["balance"] = (opening + df.amount.cumsum()).round(2)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out


def write(as_of: date | None = None, seed: int = 42, path: Path = OUT) -> pd.DataFrame:
    df = generate(as_of, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, date_format="%Y-%m-%d")
    return df


def ensure(as_of: date | None = None, path: Path = OUT) -> pd.DataFrame:
    """The shared transaction feed for `as_of`, always generated from the current personas (deterministic,
    ~20 ms), so editing a persona can never leave a stale CSV behind. The CSV on disk is a copy for
    inspection and is only rewritten when its contents change."""
    as_of = as_of or default_as_of()
    df = generate(as_of)
    text = df.to_csv(index=False, date_format="%Y-%m-%d")
    try:
        current = path.read_text() if path.exists() else None
    except OSError:
        current = None
    if current != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return df


if __name__ == "__main__":
    df = write()
    print(df.groupby("member_id").agg(n=("amount", "size"), net=("amount", "sum"), last_balance=("balance", "last"),
                                      min_balance=("balance", "min")))
