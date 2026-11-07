"""90-day cash-flow forecast: profile extraction -> Monte Carlo -> scenario attribution.

The profile is learned from the transaction feed alone (recurring payments, irregular income,
everyday spending), so the same code works on an Open Banking feed. The only non-transaction
inputs are known future events (`scheduled_changes`) and the ONS LCF spending benchmark.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import calibration
from .personas import personas, scheduled_changes

N_PATHS = 2000
BLOCK = 7                 # block bootstrap length (days) - keeps the weekly rhythm
VARIABLE_WINDOW = 180     # days of everyday spending to resample from
RISK_BANDS = ((0.10, "ok"), (0.30, "watch"), (1.01, "high"))
SPEND_CATEGORIES = {"groceries", "eating_out", "transport", "shopping", "leisure", "health", "misc", "fuel"}
CATEGORY_LABEL = {"groceries": "Groceries", "eating_out": "Eating out & takeaways", "transport": "Travel",
                  "shopping": "Shopping", "leisure": "Leisure & entertainment", "health": "Health",
                  "misc": "Other spending", "fuel": "Fuel"}
DISCLAIMER = ("Guidance, not regulated financial advice. Figures are simulations based on past transactions "
              "and stated assumptions. For help with money worries, contact MoneyHelper (0800 138 7777) "
              "or StepChange (0800 138 1111).")


# ------------------------------------------------------------------ profile extraction
@dataclass
class Flow:
    merchant: str
    category: str
    sign: int
    cadence: str              # weekly | fortnightly | four_weekly | monthly
    amount: float             # signed, typical (median of last 3)
    cv: float                 # amount coefficient of variation
    last_date: date
    day_of_month: int | None = None
    observed: list[float] = field(default_factory=list)  # signed amounts, newest last
    miss_prob: float = 0.0
    irregular: bool = False   # income whose amount varies a lot (gig work)
    by_month: dict[int, float] = field(default_factory=dict)  # seasonal bills: amount seen in that month last year

    def amount_on(self, d: date) -> float:
        return self.by_month.get(d.month, self.amount) if self.cv > 0.15 else self.amount

    def next_dates(self, start: date, end: date) -> list[date]:
        out: list[date] = []
        if self.cadence == "monthly":
            y, m = start.year, start.month
            while True:
                d = date(y, m, min(self.day_of_month, calendar.monthrange(y, m)[1]))
                if d > end:
                    break
                if d >= start:
                    out.append(d)
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            return out
        step = {"weekly": 7, "fortnightly": 14, "four_weekly": 28}[self.cadence]
        d = self.last_date + timedelta(days=step)
        while d < start:
            d += timedelta(days=step)
        while d <= end:
            out.append(d)
            d += timedelta(days=step)
        return out

    @property
    def monthly_equivalent(self) -> float:
        per_month = {"weekly": 52 / 12, "fortnightly": 26 / 12, "four_weekly": 13 / 12, "monthly": 1}[self.cadence]
        return abs(self.amount) * per_month * (1 - self.miss_prob)


def _cadence(gaps: np.ndarray, doms: np.ndarray) -> tuple[str | None, float]:
    med = float(np.median(gaps))
    if 6 <= med <= 8:
        return "weekly", float(np.mean((gaps >= 6) & (gaps <= 8) | (gaps % 7 == 0)))
    if 13 <= med <= 15:
        return "fortnightly", float(np.mean((gaps >= 13) & (gaps <= 15)))
    if 26 <= med <= 33:
        if np.all((gaps >= 27) & (gaps <= 29)) and gaps.std() < 0.6:
            return "four_weekly", 1.0
        return "monthly", float(np.mean((gaps >= 26) & (gaps <= 33)))
    return None, 0.0


def detect_recurring(tx: pd.DataFrame, as_of: date) -> list[Flow]:
    flows: list[Flow] = []
    tx = tx.assign(sign=np.sign(tx.amount).astype(int))
    for (merchant, sign), g in tx.groupby(["merchant", "sign"]):
        daily = g.groupby(g.date.dt.date).agg(amount=("amount", "sum"), category=("category", "first"))
        if len(daily) < 3:
            continue
        dates = np.array(daily.index, dtype="datetime64[D]")
        gaps = np.diff(dates).astype(int)
        doms = np.array([d.day for d in daily.index])
        cadence, regularity = _cadence(gaps, doms)
        if cadence is None or regularity < 0.75:
            continue
        period = {"weekly": 7, "fortnightly": 14, "four_weekly": 28, "monthly": 31}[cadence]
        last = daily.index[-1]
        if (as_of - last).days > period * 1.6 + 3:  # stopped
            continue
        amounts = daily.amount.to_numpy()
        cv = float(np.std(amounts) / max(abs(np.mean(amounts)), 1e-9))
        irregular = sign > 0 and cv > 0.25
        if sign < 0 and (cv > 0.6 or (cv > 0.35 and regularity < 0.9)):  # not a fixed bill
            continue
        miss = 0.0
        if irregular:
            span = (last - daily.index[0]).days
            expected = span / period + 1
            miss = float(np.clip(1 - len(daily) / expected, 0, 0.5))
        flows.append(Flow(
            merchant=merchant, category=daily.category.iloc[-1], sign=sign, cadence=cadence,
            amount=float(np.median(amounts[-3:])) if not irregular else float(np.mean(amounts[-26:])),
            cv=min(cv, 0.3), last_date=last,
            day_of_month=int(np.median(doms[-6:])) if cadence == "monthly" else None,
            observed=list(amounts[-26:]), miss_prob=miss, irregular=irregular,
            by_month={d.month: float(a) for d, a in zip(daily.index, amounts) if (as_of - d).days > 31}))
    return flows


@dataclass
class Profile:
    member_id: str
    as_of: date                 # first forecast day
    start_balance: float
    flows: list[Flow]
    var_dates: list[date]       # the resampling window
    var_matrix: np.ndarray      # (categories, days) signed daily totals
    var_categories: list[str]
    seasonal: dict[str, float]  # category -> multiplier for the forecast window
    observed_weekly: dict[str, float]
    history_days: int


def build_profile(member_id: str, tx: pd.DataFrame, as_of: date, horizon: int) -> Profile:
    tx = tx.sort_values("date", kind="stable")
    start_balance = float(tx.balance.iloc[-1])
    flows = detect_recurring(tx, as_of)
    recurring_keys = {(f.merchant, f.sign) for f in flows}
    is_rec = [(m, int(np.sign(a))) in recurring_keys for m, a in zip(tx.merchant, tx.amount)]
    var = tx[~np.array(is_rec)]

    end = as_of - timedelta(days=1)
    win_start = end - timedelta(days=VARIABLE_WINDOW - 1)
    days = pd.date_range(win_start, end, freq="D")
    var_win = var[var.date >= pd.Timestamp(win_start)]
    pivot = (var_win.pivot_table(index="category", columns="date", values="amount", aggfunc="sum", fill_value=0.0)
             .reindex(columns=days, fill_value=0.0))
    cats = list(pivot.index)

    # seasonality: same window last year vs the yearly average, per spending category
    hist_start = tx.date.min().date()
    history_days = (end - hist_start).days + 1
    seasonal = {}
    if history_days >= 330:
        ly_start, ly_end = as_of - timedelta(days=365), as_of - timedelta(days=365 - horizon)
        for c in cats:
            if c not in SPEND_CATEGORIES:
                continue
            s = var[var.category == c]
            annual = -s.amount.sum() / history_days
            ly = -s[(s.date >= pd.Timestamp(ly_start)) & (s.date < pd.Timestamp(ly_end))].amount.sum() / horizon
            if annual > 0:
                seasonal[c] = float(np.clip(ly / annual, 0.75, 1.5))
    observed_weekly = {c: float(-pivot.loc[c].sum() / VARIABLE_WINDOW * 7) for c in cats if c in SPEND_CATEGORIES}
    return Profile(member_id, as_of, start_balance, flows, [d.date() for d in days], pivot.to_numpy(float), cats,
                   seasonal, observed_weekly, history_days)


# ------------------------------------------------------------------ simulation
def _occurrence_index(dates: list[date], as_of: date, horizon: int) -> np.ndarray:
    return np.array([(d - as_of).days for d in dates if 0 <= (d - as_of).days < horizon], dtype=int)


def simulate(profile: Profile, horizon: int, n: int, seed: int, changes: list[dict]):
    """Returns (start_balance, components). Each component is an (n, horizon) array of daily cash flow,
    with an optional neutral counterpart used for attribution."""
    rng = np.random.default_rng(seed)
    as_of, end = profile.as_of, profile.as_of + timedelta(days=horizon - 1)
    comps: dict[str, dict] = {}

    def place(idx: np.ndarray, amounts: np.ndarray, slip: np.ndarray | None = None) -> np.ndarray:
        arr = np.zeros((n, horizon))
        if len(idx) == 0:
            return arr
        cols = np.broadcast_to(idx, (n, len(idx)))
        if slip is not None:
            cols = np.clip(cols + slip, 0, horizon - 1)
        rows = np.broadcast_to(np.arange(n)[:, None], cols.shape)
        np.add.at(arr, (rows, cols), amounts)
        return arr

    amount_changes = {c["merchant"]: c for c in changes if c["kind"] == "amount_change"}
    for f in profile.flows:
        dates = f.next_dates(as_of, end)
        idx = _occurrence_index(dates, as_of, horizon)
        k = len(idx)
        slip = rng.choice([-1, 0, 0, 0, 1], size=(n, k)) if f.sign > 0 else None
        if f.irregular:
            obs = np.array(f.observed)
            draws = rng.choice(obs, size=(n, k)) * (rng.random((n, k)) >= f.miss_prob)
            neutral = place(idx, np.full((n, k), obs.mean() * (1 - f.miss_prob)), slip)
            comps[f"flow:{f.merchant}"] = {"flow": f, "arr": place(idx, draws, slip), "neutral": neutral}
            continue
        base = np.array([f.amount_on(d) for d in dates if 0 <= (d - as_of).days < horizon])
        amounts = base * (1 + min(f.cv, 0.1) * rng.standard_normal((n, k)))
        comps[f"flow:{f.merchant}"] = {"flow": f, "arr": place(idx, amounts, slip)}
        ch = amount_changes.get(f.merchant)
        if ch:
            later = np.array([d >= ch["from_date"] for d in dates if 0 <= (d - as_of).days < horizon])
            delta = np.where(later, ch["new_amount"] - base, 0.0)
            comps[f"change:{ch['feature']}"] = {"change": ch, "arr": place(idx, np.broadcast_to(delta, (n, k)), slip)}
    for ch in changes:
        if ch["kind"] == "one_off":
            idx = _occurrence_index([ch["date"]], as_of, horizon)
            comps[f"change:{ch['feature']}"] = {"change": ch, "arr": place(idx, np.full((n, len(idx)), ch["amount"]))}

    # everyday spending: 7-day block bootstrap aligned on weekday, shared across categories
    V = profile.var_matrix
    D = V.shape[1]
    starts = [s for s in range(D - BLOCK + 1) if profile.var_dates[s].weekday() == as_of.weekday()]
    n_blocks = -(-horizon // BLOCK)
    picks = rng.choice(starts, size=(n, n_blocks))
    idx = (picks[:, :, None] + np.arange(BLOCK)).reshape(n, -1)[:, :horizon]
    weekday_of = np.array([d.weekday() for d in profile.var_dates])
    fc_weekday = np.array([(as_of + timedelta(days=i)).weekday() for i in range(horizon)])
    for ci, c in enumerate(profile.var_categories):
        s = profile.seasonal.get(c, 1.0)
        arr = V[ci][idx] * s
        wd_mean = np.array([V[ci][weekday_of == w].mean() for w in range(7)])
        comps[f"var:{c}"] = {"category": c, "seasonal": s, "arr": arr,
                             "mean": np.broadcast_to(wd_mean[fc_weekday] * s, (n, horizon)),
                             "unseasonal": arr / s if s else arr}
    return comps


def _summarise(start: float, total: np.ndarray) -> dict:
    bal = start + np.cumsum(total, axis=1)
    running_min = np.minimum.accumulate(bal, axis=1)
    return {"bal": bal, "p_by_day": (running_min < 0).mean(axis=0)}


def _p_overdraft(start: float, total: np.ndarray) -> float:
    return float(((start + np.cumsum(total, axis=1)).min(axis=1) < 0).mean())


# ------------------------------------------------------------------ attribution
MAX_SHAPLEY_DRIVERS = 9


def _drivers(profile: Profile, comps: dict, total: np.ndarray, benchmark: dict[str, float]) -> list[dict]:
    """Each driver = a label + `delta`, the change in daily cash flow if that driver were switched off."""
    out = []

    def add(feature, detail, delta, kind):
        out.append({"feature": feature, "detail": detail, "kind": kind, "delta": delta})

    spend_arr = np.zeros_like(total)
    spend_mean = np.zeros_like(total)
    seasonal_delta = np.zeros_like(total)
    for key, c in comps.items():
        if key.startswith("change:"):
            ch = c["change"]
            add(ch["feature"], ch.get("detail", ""), -c["arr"], "scheduled")
        elif key.startswith("flow:"):
            f: Flow = c["flow"]
            if f.irregular:
                add("Irregular income", f"{f.merchant.title()} payouts vary week to week "
                    f"(typical £{abs(f.amount):,.0f}, no payout in {f.miss_prob:.0%} of weeks)",
                    c["neutral"] - c["arr"], "volatility")
            elif f.sign < 0 and f.category == "debt":
                add(f"{f.merchant.title()} repayments", f"£{f.monthly_equivalent:,.0f} a month", -c["arr"], "debt")
        elif key.startswith("var:") and c["category"] in SPEND_CATEGORIES:
            spend_arr += c["arr"]
            spend_mean += c["mean"]
            seasonal_delta += c["arr"] - c["unseasonal"]
            cat = c["category"]
            obs, bench = profile.observed_weekly.get(cat, 0.0), benchmark.get(cat)
            if bench and obs > 1.25 * bench:
                add(f"{CATEGORY_LABEL[cat]} above typical", f"£{obs:,.0f}/week vs £{bench:,.0f} typical "
                    f"for similar households (ONS)", -c["arr"] * (1 - bench / obs), "spending")
    if spend_arr.any():
        add("Day-to-day spending swings", "Everyday spending varies a lot from week to week",
            spend_mean - spend_arr, "volatility")
    if seasonal_delta.sum() < 0:
        add("Seasonal spending", "Spending in this period last year was higher than usual (e.g. Christmas)",
            -seasonal_delta, "seasonal")
    return out


def attribute(profile: Profile, comps: dict, total: np.ndarray, base_p: float, benchmark: dict[str, float]) -> list[dict]:
    """Exact Shapley attribution of P(overdraft) over the drivers (SHAP-style, but on the simulator).

    v(S) = P(overdraft) with the drivers in S switched off, scored on the same simulated paths.
    Each driver's impact is its average marginal reduction in risk; impacts sum to
    base P - P(all drivers off), so they never all claim the same risk.
    """
    from math import factorial

    drivers = _drivers(profile, comps, total, benchmark)
    if base_p == 0 or not drivers:
        return []
    start = profile.start_balance
    if len(drivers) > MAX_SHAPLEY_DRIVERS:  # keep the strongest by one-at-a-time effect
        solo = [base_p - _p_overdraft(start, total + d["delta"]) for d in drivers]
        drivers = [d for _, d in sorted(zip(solo, drivers), key=lambda t: -t[0])][:MAX_SHAPLEY_DRIVERS]
    k = len(drivers)
    deltas = np.stack([d["delta"] for d in drivers]).astype(np.float32)
    base = total.astype(np.float32)
    # A 0/1 overdraft count can't tell a £50 driver from a £700 one when any one alone tips the balance,
    # so the game is scored with a smoothed probability (sigmoid of each path's low point, width tau)
    # and the Shapley values are then rescaled to the real probability drop.
    driver_size = np.abs(deltas.sum(axis=2)).mean(axis=1)  # mean cash each driver moves over the horizon
    tau = float(max(100.0, 0.5 * np.median(driver_size)))

    def soft_p(flows):
        m = start + np.cumsum(flows, axis=1).min(axis=1)
        return float(np.mean(1 / (1 + np.exp(np.clip(m / tau, -50, 50)))))

    v = np.empty(1 << k)
    for mask in range(1 << k):
        sel = [i for i in range(k) if mask >> i & 1]
        v[mask] = soft_p(base + deltas[sel].sum(axis=0)) if sel else soft_p(base)
    weights = [factorial(s) * factorial(k - s - 1) / factorial(k) for s in range(k)]
    phi = np.zeros(k)
    for mask in range(1 << k):
        size = bin(mask).count("1")
        for i in range(k):
            if not mask >> i & 1:
                phi[i] += weights[size] * (v[mask] - v[mask | 1 << i])
    explained = base_p - _p_overdraft(start, base + deltas.sum(axis=0))
    if phi.sum() > 0:
        phi = phi * explained / phi.sum()
    out = [{"feature": d["feature"], "impact": round(float(p), 3), "detail": d["detail"], "kind": d["kind"]}
           for d, p in zip(drivers, phi)]
    return sorted([o for o in out if o["impact"] > 0.005], key=lambda o: -o["impact"])[:4]


# ------------------------------------------------------------------ public entry point
def benchmark_for(member_id: str) -> dict[str, float]:
    p = personas().get(member_id)
    lcf = calibration.load()["lcf"]
    status, hh = (p.status, p.household_size) if p else ("all", 1.0)
    return {c: v * hh for c, v in lcf[status]["weekly_per_person"].items()}


def forecast(member_id: str, tx: pd.DataFrame, as_of: date, horizon: int = 90, n: int = N_PATHS, seed: int = 7) -> dict:
    tx = tx[tx.member_id == member_id]
    if tx.empty:
        raise KeyError(member_id)
    profile = build_profile(member_id, tx, as_of, horizon)
    changes = scheduled_changes(member_id, as_of)
    comps = simulate(profile, horizon, n, seed, changes)
    total = sum(c["arr"] for c in comps.values())
    s = _summarise(profile.start_balance, total)
    bal = s["bal"]
    q = np.percentile(bal, [10, 50, 90], axis=0)
    start = round(profile.start_balance)
    days = [{"d": 0, "date": (as_of - timedelta(days=1)).isoformat(), "p10": start, "p50": start, "p90": start}]
    days += [{"d": i + 1, "date": (as_of + timedelta(days=i)).isoformat(),
              "p10": int(round(q[0, i])), "p50": int(round(q[1, i])), "p90": int(round(q[2, i]))}
             for i in range(horizon)]
    low = int(np.argmin(q[1]))
    p90d = float(s["p_by_day"][-1])
    by_h = {str(h): round(float(s["p_by_day"][min(h, horizon) - 1]), 3) for h in (30, 60, 90) if h <= horizon}
    band = next(name for thr, name in RISK_BANDS if p90d < thr)
    reasons = attribute(profile, comps, total, p90d, benchmark_for(member_id))

    p = personas().get(member_id)
    cal = calibration.load()
    return {
        "member_id": member_id,
        "member": {"name": p.name, "family": p.family, "age": p.age, "role": p.role} if p else None,
        "start_date": as_of.isoformat(),
        "start_balance": round(profile.start_balance, 2),
        "days": days,
        "overdraft_probability": round(p90d, 3),
        "overdraft_probability_by_horizon": by_h,
        "risk_band": band,
        "lowest_point": {"day": low + 1, "date": (as_of + timedelta(days=low)).isoformat(),
                         "p10": int(round(q[0, low])), "p50": int(round(q[1, low])), "p90": int(round(q[2, low]))},
        "reasons": reasons,
        "upcoming": [{"date": d.isoformat(), "merchant": f.merchant, "amount": round(f.amount_on(d), 2),
                      "category": f.category}
                     for f in profile.flows for d in f.next_dates(as_of, as_of + timedelta(days=13))
                     if not f.irregular] + [
                     {"date": c["date"].isoformat(), "merchant": c["feature"], "amount": c["amount"], "category": "scheduled"}
                     for c in changes if c["kind"] == "one_off" and (c["date"] - as_of).days < 14],
        "assumptions": {
            "method": f"Monte Carlo, {n} simulated paths; recurring payments projected from history, "
                      f"everyday spending resampled in {BLOCK}-day blocks from the last {VARIABLE_WINDOW} days",
            "overdraft_definition": "Balance below £0 on any day in the horizon (arranged overdraft not counted)",
            "reasons_method": "Shapley attribution over the simulator: drivers are switched off in every "
                              "combination and the chance of going overdrawn is re-measured on the same "
                              "simulated paths. Impact = each driver's average share of the risk.",
            "recurring_detected": [{"merchant": f.merchant, "cadence": f.cadence, "amount": round(f.amount, 2),
                                    "irregular": f.irregular} for f in profile.flows],
            "scheduled_changes": [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in c.items()}
                                  for c in changes],
            "seasonal_adjustment": {k: round(v, 2) for k, v in profile.seasonal.items()},
            "history_days": profile.history_days,
            "seed": seed,
            "disclaimer": DISCLAIMER,
        },
        "sources": [
            {"title": "Synthetic transactions calibrated to ONS data (NatWest sandbox-ready)",
             "url": "data/synthetic/transactions.csv"},
            {"title": cal["lcf_source"],
             "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/personalandhouseholdfinances/expenditure/"
                    "datasets/familyspendingworkbook4expenditurebyhouseholdcharacteristic"},
            {"title": "ONS ASHE 2026 provisional, Table 6.7a (earnings by age)",
             "url": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/"
                    "datasets/agegroupashetable6"},
            {"title": "gov.uk: The new State Pension", "url": cal["state_pension"]["source"]},
        ],
    }
