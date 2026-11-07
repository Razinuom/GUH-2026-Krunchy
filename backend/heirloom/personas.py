"""The six demo personas (two families) and the future events we know about for them.

Income comes from ASHE / gov.uk via calibration.py; everyday spending is scaled from ONS LCF.
Bills that LCF can't give us per person (rent, energy, finance) are explicit, plausible 2026 figures.
`current_balance` is the tuning knob: the generator back-solves the opening balance from it.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import calibration


@dataclass
class Bill:
    merchant: str
    category: str          # "housing", "utilities", "debt", "subscriptions", "transport", "phone", "insurance", "misc", "family"
    amount: float          # positive number, paid out
    day: int = 1           # day of month (monthly) or ignored for every_days
    every_days: int | None = None   # e.g. 14 for fortnightly BNPL
    months: tuple[int, ...] | None = None  # e.g. council tax Apr-Jan
    seasonal_energy: bool = False


@dataclass
class Income:
    kind: str              # "salary" | "state_pension" | "monthly" | "gig_weekly"
    merchant: str
    amount: float = 0.0    # monthly (monthly) / per payment (gig mean)
    ashe_percentile: str = "p50"
    state_pension_share: float = 1.0
    day: int = 28
    sigma: float = 0.0     # gig: lognormal sigma
    miss_prob: float = 0.0 # gig: chance of a week with no payout


@dataclass
class Persona:
    id: str
    name: str
    family: str
    age: int
    role: str
    status: str            # LCF A17 column: employee_ft, employee_pt, self_employed, retired
    household_size: float  # people this account's everyday spending covers
    spend_scale: float     # multiplier on LCF per-person benchmark
    current_balance: float
    incomes: list[Income]
    bills: list[Bill]
    category_scale: dict[str, float] = field(default_factory=dict)
    extra_weekly: dict[str, float] = field(default_factory=dict)  # e.g. courier fuel


def _phone(p_household: float, scale: float = 1.0) -> float:
    lcf = calibration.load()["lcf"]["employee_ft"]["weekly_per_person"]["phone"]
    return round(lcf * p_household * scale * 52 / 12, 2)


def personas() -> dict[str, Persona]:
    ct_months = (4, 5, 6, 7, 8, 9, 10, 11, 12, 1)  # council tax: 10 instalments Apr-Jan
    ps = [
        Persona("halina", "Halina Nowak", "nowak", 71, "Retired, widowed homeowner", "retired", 1.0, 0.55, 3150,
                incomes=[Income("state_pension", "DWP STATE PENSION"),
                         Income("monthly", "AVIVA ANNUITY", amount=420, day=1)],
                bills=[Bill("CITY COUNCIL TAX", "housing", 128, 1, months=ct_months),
                       Bill("OCTOPUS ENERGY", "utilities", 96, 15, seasonal_energy=True),
                       Bill("YORKSHIRE WATER", "utilities", 38, 5),
                       Bill("TV LICENSING", "subscriptions", 14.95, 1),
                       Bill("EE MOBILE", "phone", 18, 9)]),
        Persona("tomasz", "Tomasz Nowak", "nowak", 46, "Warehouse supervisor, renting", "employee_ft", 1.3, 0.65, 2450,
                incomes=[Income("salary", "NORTHGATE LOGISTICS SALARY", ashe_percentile="p40", day=28)],
                bills=[Bill("GREENWAY LETTINGS RENT", "housing", 1295, 1),
                       Bill("CITY COUNCIL TAX", "housing", 165, 1, months=ct_months),
                       Bill("OCTOPUS ENERGY", "utilities", 112, 15, seasonal_energy=True),
                       Bill("YORKSHIRE WATER", "utilities", 42, 5),
                       Bill("NORTHWAY CAR FINANCE", "debt", 245, 12),
                       Bill("VIRGIN MEDIA", "subscriptions", 32, 18),
                       Bill("NETFLIX", "subscriptions", 12.99, 22),
                       Bill("PUREGYM", "subscriptions", 29.99, 3),
                       Bill("VODAFONE", "phone", _phone(1.3), 9)]),
        Persona("zofia", "Zofia Nowak", "nowak", 22, "Junior marketing assistant, flatshare", "employee_ft", 1.0, 1.0, 1400,
                incomes=[Income("salary", "BRIGHTLANE MEDIA SALARY", ashe_percentile="p30", day=25)],
                bills=[Bill("S PATEL ROOM RENT", "housing", 895, 1),
                       Bill("CITY COUNCIL TAX", "housing", 58, 1, months=ct_months),
                       Bill("BULB SHARE ENERGY", "utilities", 45, 15, seasonal_energy=True),
                       Bill("GIFFGAFF", "phone", 15, 9),
                       Bill("SPOTIFY", "subscriptions", 11.99, 14),
                       Bill("KLARNA", "debt", 38, every_days=14)],
                category_scale={"eating_out": 1.8, "leisure": 1.15, "shopping": 1.0, "transport": 0.6}),
        Persona("grace", "Grace Okafor", "okafor", 68, "Retired care assistant, social housing", "retired", 1.0, 0.4, 810,
                incomes=[Income("state_pension", "DWP STATE PENSION", state_pension_share=0.82),
                         Income("monthly", "DWP PENSION CREDIT", amount=128, day=2)],
                bills=[Bill("HARBOUR HOUSING ASSOC", "housing", 420, 1),
                       Bill("CITY COUNCIL TAX", "housing", 45, 1, months=ct_months),
                       Bill("EDF ENERGY", "utilities", 85, 15, seasonal_energy=True),
                       Bill("SEVERN TRENT WATER", "utilities", 30, 5),
                       Bill("LEBARA MOBILE", "phone", 10, 9),
                       Bill("GOLDEN LEAVES FUNERAL PLAN", "insurance", 24, 20)]),
        Persona("daniel", "Daniel Okafor", "okafor", 44, "Self-employed courier, variable income", "self_employed", 1.5, 0.5, 1150,
                incomes=[Income("gig_weekly", "SWIFTDROP COURIER PAYOUT", amount=700, sigma=0.38, miss_prob=0.06),
                         Income("monthly", "A OKAFOR BOARD", amount=200, day=2)],
                bills=[Bill("PARKSIDE LETTINGS RENT", "housing", 950, 1),
                       Bill("CITY COUNCIL TAX", "housing", 150, 1, months=ct_months),
                       Bill("OCTOPUS ENERGY", "utilities", 120, 15, seasonal_energy=True),
                       Bill("SEVERN TRENT WATER", "utilities", 40, 5),
                       Bill("FLEETLINE VAN FINANCE", "debt", 385, 8),
                       Bill("LENDABLE LOAN", "debt", 118, 20),
                       Bill("COURIERCOVER VAN INSURANCE", "insurance", 96, 10),
                       Bill("THREE MOBILE", "phone", 30, 9)],
                category_scale={"transport": 0.2},
                extra_weekly={"fuel": 105}),
        Persona("ada", "Ada Okafor", "okafor", 19, "Electrical apprentice, lives with dad", "employee_ft", 1.0, 0.75, 570,
                incomes=[Income("salary", "SPARKWELL ELECTRICAL SALARY", ashe_percentile="p10", day=28)],
                bills=[Bill("D OKAFOR BOARD", "family", 200, 2),
                       Bill("METRO TRAVEL PASS", "transport", 89, 1),
                       Bill("SMARTY MOBILE", "phone", 12, 9),
                       Bill("CLEARPAY", "debt", 27, every_days=14)],
                category_scale={"transport": 0.25})]
    return {p.id: p for p in ps}


# ------------------------------------------------------------------ incomes from calibration
def gross_salary(p: Persona, inc: Income) -> float:
    band = calibration.age_band(p.age)
    return calibration.load()["ashe"]["bands"][band][inc.ashe_percentile]


def monthly_net_salary(p: Persona, inc: Income) -> float:
    return round(calibration.net_annual_pay(gross_salary(p, inc)) / 12, 2)


def state_pension_4weekly(inc: Income) -> float:
    return round(calibration.load()["state_pension"]["weekly"] * inc.state_pension_share * 4, 2)


# ------------------------------------------------------------------ known future events
def _next_month_day(as_of: date, day: int) -> date:
    y, m = (as_of.year + (as_of.month // 12), as_of.month % 12 + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def scheduled_changes(member_id: str, as_of: date) -> list[dict]:
    """Events the account holder has told us about / standing orders we can see coming.

    Stands in for what an Open Banking standing-order + direct-debit feed would provide.
    kind=amount_change: a recurring payment changes amount from `from_date`.
    kind=one_off: a single payment on `date`.
    """
    if member_id == "tomasz":
        return [
            {"kind": "amount_change", "merchant": "GREENWAY LETTINGS RENT", "new_amount": -1525.0,
             "from_date": _next_month_day(as_of, 1), "feature": "Rent increase",
             "detail": "Rent rises from £1,295 to £1,525 a month"},
            {"kind": "one_off", "date": as_of + timedelta(days=40), "amount": -742.0,
             "feature": "Car insurance renewal", "detail": "Annual car insurance due"},
        ]
    if member_id == "daniel":
        jan31 = date(as_of.year + (1 if as_of >= date(as_of.year, 1, 31) else 0), 1, 31)
        return [{"kind": "one_off", "date": jan31, "amount": -980.0, "feature": "Self Assessment tax bill",
                 "detail": "HMRC balancing payment due 31 January"}]
    if member_id == "zofia":
        return [{"kind": "one_off", "date": as_of + timedelta(days=21), "amount": -260.0,
                 "feature": "Festival ticket instalment", "detail": "Final payment on a pay-later festival ticket"}]
    return []
