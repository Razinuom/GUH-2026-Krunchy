"""Daily current-account simulator for UK households.

Produces transactions in the shared contract format
(date, member_id, amount, category, merchant), negative amount = money out,
plus the daily end-of-day balance. Used for both the demo personas and the
thousands of random households the hardship model is trained on.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .calibration import discretionary_shares

MERCHANTS = {
    "groceries": ["Tesco", "Lidl", "Aldi", "Sainsbury's", "Asda", "Co-op"],
    "transport": ["Shell", "BP", "TfL", "National Rail", "Stagecoach", "Esso"],
    "eating_out": ["Greggs", "Costa", "Nando's", "Deliveroo", "Just Eat", "Wetherspoons"],
    "shopping": ["Amazon", "Primark", "Argos", "Boots", "B&M", "Next"],
    "recreation": ["Netflix", "Spotify", "Vue Cinema", "PureGym", "Steam", "Odeon"],
    "personal": ["Superdrug", "Barber", "Post Office", "Pets at Home"],
    "one_off": ["Kwik Fit", "Boiler repair", "Vets4Pets", "Dentist", "Currys", "Funeral costs"],
}
INCOME_MERCHANT = {
    "salary": "Employer payroll",
    "apprentice": "Employer payroll (apprentice)",
    "gig": "Courier platform payout",
    "pension": "DWP State Pension",
    "benefits": "DWP Universal Credit",
}
DECLINABLE = {"groceries", "transport", "eating_out", "shopping", "recreation", "personal",
              "cash_withdrawal", "gambling"}
BILLS = [  # (category, merchant, day of month, share of bills budget)
    ("council_tax", "Council Tax", 1, 0.30),
    ("insurance", "Aviva", 5, 0.12),
    ("utilities", "Octopus Energy", 14, 0.33),
    ("utilities", "Thames Water", 18, 0.10),
    ("communication", "BT Broadband & Mobile", 22, 0.15),
]


@dataclass
class Profile:
    member_id: str
    income_kind: str = "salary"          # salary | apprentice | gig | pension | benefits
    monthly_income: float = 2200.0       # net, GBP
    income_cv: float = 0.03              # payment-to-payment noise
    quiet_month_prob: float = 0.0        # gig: chance a month has much less work
    pay_day: int = 28
    private_pension: float = 0.0         # pension: extra monthly private pension
    housing_cost: float = 800.0
    housing_day: int = 1
    housing_label: str = "Rent"
    housing_increase: float = 0.0        # GBP/month added from housing_increase_day
    housing_increase_day: int | None = None
    bills: float = 250.0
    spend_ratio: float = 0.9             # target total outgoings / income
    savings_monthly: float = 0.0
    opening_balance: float = 500.0
    overdraft_limit: float = 500.0
    bnpl_per_month: float = 0.0          # expected BNPL purchases per month
    bnpl_size: float = 120.0
    payday_loan_prob: float = 0.0        # chance of taking one when overdrawn
    gambling_weekly: float = 0.0
    shock_rate: float = 2.0              # unexpected bills per year
    shock_mean: float = 300.0
    income_cut_day: int | None = None    # permanent income change (job loss, fewer hours)
    income_cut_factor: float = 1.0
    meta: dict = field(default_factory=dict)


def _wd(d: date) -> date:
    """Move weekend payments to the previous Friday, as UK payroll does."""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def simulate(p: Profile, start: date, n_days: int, seed: int = 0):
    """Returns (transactions DataFrame, daily balance Series indexed by date)."""
    rng = np.random.default_rng(seed)
    shares = discretionary_shares()
    cats = list(shares)
    probs = np.array([shares[c] for c in cats])

    rows: list[tuple] = []
    bal = p.opening_balance
    balances = np.empty(n_days)
    pending: dict[int, list[tuple]] = {}  # day index -> scheduled debits (cat, merchant, amount)

    weekly_income = p.monthly_income * 12 / 52
    month_mult = 1.0
    current_month = None

    for i in range(n_days):
        d = start + timedelta(days=i)
        cut = p.income_cut_factor if p.income_cut_day is not None and i >= p.income_cut_day else 1.0
        today: list[tuple] = []

        if (d.year, d.month) != current_month:
            current_month = (d.year, d.month)
            month_mult = 1.0
            if p.quiet_month_prob and rng.random() < p.quiet_month_prob:
                month_mult = rng.uniform(0.45, 0.8)

        # ---- income ----
        if p.income_kind in ("salary", "apprentice", "benefits"):
            payday = _wd(date(d.year, d.month, min(p.pay_day, 28)))
            if d == payday:
                amt = p.monthly_income * cut * (1 + rng.normal(0, p.income_cv))
                today.append(("income", INCOME_MERCHANT[p.income_kind], max(amt, 0)))
        elif p.income_kind == "gig":
            if d.weekday() == 4:
                amt = weekly_income * cut * month_mult * rng.lognormal(0, p.income_cv) / np.exp(p.income_cv**2 / 2)
                today.append(("income", INCOME_MERCHANT["gig"], max(amt, 0)))
        elif p.income_kind == "pension":
            state = p.monthly_income - p.private_pension
            if i % 28 == 7:
                today.append(("income", INCOME_MERCHANT["pension"], state * 12 / 13 * cut))
            if d.day == 1 and p.private_pension:
                today.append(("income", "Workplace pension", p.private_pension))

        # ---- fixed outgoings ----
        if d.day == p.housing_day:
            h = p.housing_cost
            if p.housing_increase_day is not None and i >= p.housing_increase_day:
                h += p.housing_increase
            if h > 0:
                today.append(("housing", p.housing_label, -h))
        for cat, merch, day, share in BILLS:
            if d.day == day and p.bills > 0:
                today.append((cat, merch, -p.bills * share * rng.uniform(0.95, 1.08)))
        if p.savings_monthly and d.day == min(p.pay_day + 1, 28) and bal > p.savings_monthly + 200:
            today.append(("savings_transfer", "Transfer to savings", -p.savings_monthly))

        # ---- discretionary day-to-day spend ----
        # people adapt spending to a lower income about a month after it changes
        adj = p.income_cut_factor if p.income_cut_day is not None and i >= p.income_cut_day + 30 else 1.0
        inc_eff = p.monthly_income * adj
        fixed = p.housing_cost + p.bills + p.savings_monthly
        extras = (p.shock_rate * p.shock_mean / 12 + p.gambling_weekly * 52 / 12
                  + p.bnpl_per_month * p.bnpl_size + 50)
        disc_month = max(inc_eff * p.spend_ratio - fixed - extras, 0.12 * inc_eff)
        disc_day = disc_month * 12 / 365
        # people cut back when money is tight
        squeeze = 0.6 if bal < 0 else 0.85 if bal < 0.15 * inc_eff else 1.0
        n_tx = rng.poisson(1.6)
        if n_tx:
            amts = rng.gamma(2.0, disc_day * squeeze / (2.0 * 1.6), size=n_tx)
            for a, c in zip(amts, rng.choice(cats, size=n_tx, p=probs)):
                today.append((c, rng.choice(MERCHANTS[c]), -round(float(a), 2)))
        if rng.random() < 0.04:
            today.append(("cash_withdrawal", "ATM", -float(rng.choice([20, 40, 50, 100]))))

        # ---- risk behaviours ----
        if p.gambling_weekly and rng.random() < 3 / 7:
            today.append(("gambling", rng.choice(["Bet365", "Sky Bet", "Paddy Power"]),
                          -round(rng.gamma(2, p.gambling_weekly / 6), 2)))
        if p.bnpl_per_month and rng.random() < p.bnpl_per_month / 30:
            size = rng.gamma(2, p.bnpl_size / 2)
            for k in (0, 30, 60):  # pay in 3
                pending.setdefault(i + k, []).append(("bnpl", "Klarna", -round(size / 3, 2)))
        if rng.random() < p.shock_rate / 365:
            today.append(("one_off", rng.choice(MERCHANTS["one_off"]),
                          -round(rng.lognormal(np.log(p.shock_mean), 0.6), 2)))

        today.extend(pending.pop(i, []))

        net = sum(a for _, _, a in today)
        # card payments are declined past the overdraft limit (direct debits still go through)
        if bal + net < -p.overdraft_limit:
            kept = []
            for t in sorted(today, key=lambda t: t[0] in DECLINABLE):
                if t[0] in DECLINABLE and bal + sum(a for _, _, a in kept) + t[2] < -p.overdraft_limit:
                    continue
                kept.append(t)
            today = kept
            net = sum(a for _, _, a in today)
        # payday loan when the account would go deep into the red
        if p.payday_loan_prob and bal + net < -0.6 * p.overdraft_limit and rng.random() < p.payday_loan_prob:
            loan = float(rng.choice([200, 300, 400]))
            today.append(("payday_loan", "QuickCash Loans", loan))
            pending.setdefault(i + 30, []).append(("payday_loan_repayment", "QuickCash Loans", -loan * 1.3))
            net += loan
        # overdraft interest, charged monthly on the 1st (approx 35% EAR)
        if d.day == 1 and i > 0:
            od_days = balances[max(0, i - 30):i]
            interest = -float(np.clip(od_days, None, 0).sum()) * 0.35 / 365
            if interest > 0.5:
                today.append(("bank_fee", "Arranged overdraft interest", -round(interest, 2)))
                net -= interest

        bal += net
        balances[i] = bal
        for cat, merch, amt in today:
            rows.append((d, p.member_id, round(float(amt), 2), cat, merch))

    tx = pd.DataFrame(rows, columns=["date", "member_id", "amount", "category", "merchant"])
    tx["date"] = pd.to_datetime(tx["date"])
    bal_s = pd.Series(balances, index=pd.date_range(start, periods=n_days, freq="D"), name="balance")
    return tx, bal_s


def random_profile(rng: np.random.Generator, idx: int) -> Profile:
    """A random UK household for training. Broad on purpose: the model should see
    comfortable savers, people living in their overdraft and everything between."""
    kind = rng.choice(["salary", "apprentice", "gig", "pension", "benefits"], p=[0.45, 0.08, 0.17, 0.18, 0.12])
    base = {
        "salary": rng.lognormal(np.log(2300), 0.4),
        "apprentice": rng.uniform(900, 1500),
        "gig": rng.lognormal(np.log(1900), 0.35),
        "pension": rng.lognormal(np.log(1250), 0.35),
        "benefits": rng.uniform(700, 1500),
    }[kind]
    income = float(np.clip(base, 600, 9000))
    housing_share = float(np.clip(rng.normal(0.32, 0.1), 0.0, 0.6))
    if kind == "pension" and rng.random() < 0.6:
        housing_share = rng.uniform(0, 0.08)  # owns outright
    if kind == "apprentice" and rng.random() < 0.6:
        housing_share = rng.uniform(0.05, 0.2)  # living with family, board
    housing = income * housing_share
    bills = float(np.clip(rng.normal(0.13, 0.04), 0.05, 0.3) * income)
    spend_ratio = float(np.clip(rng.normal(0.93, 0.07), 0.75, 1.15))
    saver = rng.random() < 0.35 and spend_ratio < 0.95
    od = float(rng.choice([0, 250, 500, 1000, 1500], p=[0.15, 0.2, 0.3, 0.25, 0.1]))
    increase_day = int(rng.integers(60, 420)) if rng.random() < 0.3 else None
    cut_day = int(rng.integers(90, 450)) if rng.random() < 0.12 else None
    return Profile(
        member_id=f"sim{idx:05d}",
        income_kind=str(kind),
        monthly_income=income,
        income_cv={"gig": rng.uniform(0.15, 0.5)}.get(kind, rng.uniform(0.0, 0.06)),
        quiet_month_prob=rng.uniform(0.05, 0.35) if kind == "gig" else 0.0,
        pay_day=int(rng.integers(1, 29)),
        private_pension=income * rng.uniform(0, 0.5) if kind == "pension" else 0.0,
        housing_cost=housing,
        housing_day=int(rng.integers(1, 29)),
        housing_increase=float(housing * rng.uniform(0.05, 0.35)) if increase_day else 0.0,
        housing_increase_day=increase_day,
        bills=bills,
        spend_ratio=spend_ratio,
        savings_monthly=float(income * rng.uniform(0.03, 0.15)) if saver else 0.0,
        opening_balance=float(income * rng.lognormal(np.log(0.6), 1.0) - rng.uniform(0, od)),
        overdraft_limit=od,
        bnpl_per_month=float(rng.exponential(0.6)) if rng.random() < 0.35 else 0.0,
        bnpl_size=float(rng.uniform(60, 300)),
        payday_loan_prob=float(rng.uniform(0.05, 0.4)) if rng.random() < 0.15 else 0.0,
        gambling_weekly=float(rng.exponential(25)) if rng.random() < 0.15 else 0.0,
        shock_rate=float(rng.uniform(0.5, 5)),
        shock_mean=float(rng.uniform(100, 700)),
        income_cut_day=cut_day,
        income_cut_factor=float(rng.uniform(0.4, 0.85)) if cut_day else 1.0,
    )


def profile_dict(p: Profile) -> dict:
    return asdict(p)
