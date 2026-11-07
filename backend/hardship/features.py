"""Explainable features computed from a transaction history.

The same function is used for training (simulated households) and serving
(demo personas or a NatWest Bank of APIs transaction feed), so there is no
train/serve skew. Every feature has a plain-English label for SHAP reasons.
No protected characteristics (age, sex, ethnicity, region) are used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ESSENTIAL = {"housing", "utilities", "council_tax", "insurance", "communication", "groceries"}
NOT_SPEND = {"income", "payday_loan", "savings_transfer"}

# name -> (label, monotone direction for risk: +1 more = riskier, -1 more = safer, 0 free)
FEATURES: dict[str, tuple[str, int]] = {
    "balance_now": ("Current balance", -1),
    "buffer_days": ("Days of spending the balance covers", -1),
    "min_balance_90d": ("Lowest balance in the last 3 months", -1),
    "days_overdrawn_90d": ("Days overdrawn in the last 3 months", +1),
    "spend_to_income_90d": ("Spending compared with income", +1),
    "essentials_share": ("Share of income going on essentials", +1),
    "income_volatility": ("How much income varies month to month", +1),
    "income_change_30d": ("Change in income this month", -1),
    "spending_trend_30d": ("Change in spending this month", +1),
    "housing_increase": ("Rent or mortgage increase", +1),
    "bnpl_share": ("Buy now, pay later repayments", +1),
    "payday_loans_90d": ("Payday loans taken", +1),
    "gambling_share": ("Gambling spend", +1),
    "unexpected_bills_share": ("Unexpected one-off bills", 0),
    "savings_rate": ("Regular saving", -1),
    "days_to_next_income": ("Days until next income", +1),
}
FEATURE_NAMES = list(FEATURES)
MONOTONE = [FEATURES[f][1] for f in FEATURE_NAMES]


def _daily_balances(tx: pd.DataFrame, balance_now: float, as_of: pd.Timestamp, days: int) -> np.ndarray:
    """End-of-day balance for the last `days` days, reconstructed backwards from today's balance."""
    idx = pd.date_range(as_of - pd.Timedelta(days=days - 1), as_of, freq="D")
    net = tx.groupby("date")["amount"].sum().reindex(idx, fill_value=0.0).to_numpy()
    after = np.concatenate([np.cumsum(net[::-1])[::-1][1:], [0.0]])  # flows after each day
    return balance_now - after


def compute_features(tx: pd.DataFrame, balance_now: float, as_of=None) -> dict[str, float]:
    tx = tx.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.normalize()
    as_of = pd.Timestamp(as_of).normalize() if as_of is not None else tx["date"].max()
    tx = tx[(tx["date"] <= as_of) & (tx["date"] > as_of - pd.Timedelta(days=180))]

    def window(days, end_offset=0):
        hi = as_of - pd.Timedelta(days=end_offset)
        return tx[(tx["date"] > hi - pd.Timedelta(days=days)) & (tx["date"] <= hi)]

    w90, w30 = window(90), window(30)
    inc = lambda w: w.loc[w["category"] == "income", "amount"].sum()
    spend = lambda w: -w.loc[(w["amount"] < 0) & ~w["category"].isin(NOT_SPEND), "amount"].sum()
    cat = lambda w, c: -w.loc[w["category"] == c, "amount"].sum() + 0.0

    income_90 = max(inc(w90), 1.0)
    spend_90 = spend(w90)
    bal = _daily_balances(tx, balance_now, as_of, 90)

    # income per 30-day block over the last 180 days
    blocks = [inc(window(30, 30 * k)) for k in range(6)]
    blocks_arr = np.array(blocks)
    vol = float(blocks_arr.std() / blocks_arr.mean()) if blocks_arr.mean() > 0 else 1.0
    prior_inc = np.mean(blocks[1:3]) if np.mean(blocks[1:3]) > 0 else 1.0
    prior_spend = (spend(window(60, 30)) / 2) or 1.0

    housing = tx[tx["category"] == "housing"].sort_values("date")
    if len(housing) >= 2:
        latest = -housing["amount"].iloc[-1]
        older = housing[housing["date"] <= as_of - pd.Timedelta(days=75)]
        base = -older["amount"].median() if len(older) else -housing["amount"].iloc[0]
        housing_increase = max(latest - base, 0.0)
    else:
        housing_increase = 0.0

    inc_dates = tx.loc[(tx["category"] == "income") & (tx["amount"] > 0), "date"].drop_duplicates().sort_values()
    if len(inc_dates) >= 2:
        gap = float(np.median(np.diff(inc_dates.to_numpy()).astype("timedelta64[D]").astype(float)))
        since = float((as_of - inc_dates.iloc[-1]).days)
        to_next = max(gap - since, 0.0)
    else:
        to_next = 30.0

    daily_out = max(spend_90 / 90, 1.0)
    return {
        "balance_now": float(balance_now),
        "buffer_days": float(np.clip(balance_now / daily_out, -60, 365)),
        "min_balance_90d": float(bal.min()),
        "days_overdrawn_90d": float((bal < 0).sum()),
        "spend_to_income_90d": float(min(spend_90 / income_90, 5.0)),
        "essentials_share": float(min(-w90.loc[w90["category"].isin(ESSENTIAL), "amount"].sum() / income_90, 5.0)),
        "income_volatility": min(vol, 3.0),
        "income_change_30d": float(min(blocks[0] / prior_inc, 3.0)),
        "spending_trend_30d": float(min(spend(w30) / prior_spend, 5.0)),
        "housing_increase": float(housing_increase),
        "bnpl_share": float(cat(w90, "bnpl") / income_90),
        "payday_loans_90d": float((w90["category"] == "payday_loan").sum()),
        "gambling_share": float(cat(w90, "gambling") / income_90),
        "unexpected_bills_share": float(cat(w90, "one_off") / income_90),
        "savings_rate": float(cat(w90, "savings_transfer") / income_90),
        "days_to_next_income": to_next,
    }


def explain_value(name: str, f: dict[str, float]) -> str:
    """A short human sentence describing the feature value."""
    v = f[name]
    gbp = lambda x: f"£{x:,.0f}" if x >= 0 else f"-£{-x:,.0f}"
    pct = lambda x: f"{x * 100:.0f}%"
    return {
        "balance_now": f"Balance today is {gbp(v)}",
        "buffer_days": f"Balance covers about {max(v, 0):.0f} days of usual spending",
        "min_balance_90d": f"Lowest point in the last 3 months was {gbp(v)}",
        "days_overdrawn_90d": f"Overdrawn on {v:.0f} of the last 90 days",
        "spend_to_income_90d": f"Spent {pct(v)} of income over the last 3 months",
        "essentials_share": f"Essentials (housing, bills, food) take {pct(v)} of income",
        "income_volatility": f"Monthly income varies by about {pct(v)}",
        "income_change_30d": f"Income this month is {pct(v)} of the usual level",
        "spending_trend_30d": f"Spending this month is {pct(v)} of the usual level",
        "housing_increase": f"Rent or mortgage is up {gbp(v)} a month" if v > 0 else "No rent or mortgage increase",
        "bnpl_share": f"Buy now, pay later repayments take {pct(v)} of income",
        "payday_loans_90d": f"{v:.0f} payday loan(s) in the last 3 months",
        "gambling_share": f"Gambling takes {pct(v)} of income",
        "unexpected_bills_share": f"One-off bills took {pct(v)} of income in the last 3 months",
        "savings_rate": f"Saving {pct(v)} of income each month" if v > 0 else "No regular saving",
        "days_to_next_income": f"Next income expected in about {v:.0f} days",
    }[name]
