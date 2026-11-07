"""Family Time Machine: 25-year Monte Carlo fan chart for a gifted deposit vs. a grandparent's
safety floor, under three gift-timing choices (now / in 10 years / as an inheritance).

Real (CPI-deflated) UK equity, bond and house-price returns are block-bootstrapped from the
Jorda-Schularick-Taylor Macrohistory dataset (1870-2020), so multi-year cycles (a crash followed
by a recovery) stay intact. Figures are in today's money throughout. The grandparent's own cash
flow is derived from the same persona definitions used by the 90-day forecaster, so it is
calibrated to the same ONS data rather than a separate guess. Mortality for the "inheritance"
scenario comes from the ONS National Life Tables (period expectation of life, females, as both
demo grandparents are women).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import calibration
from .personas import Persona, personas
from .synth import default_as_of

DATA = calibration.DATA
RETURNS_CSV = DATA / "clean/markets/jst_uk_annual_returns.csv"
DEPOSIT_CSV = DATA / "clean/hpi_latest_deposit_targets.csv"

HORIZON_YEARS = 25
N_PATHS = 5000
BLOCK = 5  # years per bootstrap block, so a historical boom/bust stays together

FAMILIES = {
    # region / deposit_pct: the young adult's default house-deposit goal (HM Land Registry UK HPI region)
    # target_years: the deposit question is "by which year?" (Zofia at 28, Ada at 29)
    # controls: the website's starting scenario and slider ranges (gift capped well inside the grandparent's savings)
    "nowak": {"name": "Nowak Family", "grandparent": "halina", "young_adult": "zofia",
              "region": "West Midlands Region", "deposit_pct": 10, "target_years": 6,
              "controls": {"gift": 8000, "timing": "now", "monthly_saving": 200, "lisa": False,
                           "gift_max": 20000, "monthly_max": 800}},
    "okafor": {"name": "Okafor Family", "grandparent": "grace", "young_adult": "ada",
               "region": "North West", "deposit_pct": 5, "target_years": 10,
               "controls": {"gift": 0, "timing": "now", "monthly_saving": 60, "lisa": True,
                            "gift_max": 2000, "monthly_max": 400}},
}

# Asset mix: young adult's Lifetime ISA (growth-focused) vs. the grandparent's own, capital-preserving savings.
YOUNG_MIX = {"eq": 0.80, "bond": 0.20}
GRANDPARENT_MIX = {"eq": 0.25, "bond": 0.75}

LISA_ANNUAL_CAP = 4000.0   # gov.uk/lifetime-isa: contributions above this earn no bonus
LISA_BONUS_RATE = 0.25
LISA_MAX_AGE = 50          # no further bonus once you turn 50

SAFETY_FLOOR_MONTHS = 3.0  # assumption: keep at least 3 months of essential outgoings in reserve

IHT_NIL_RATE_BAND = 325_000.0
IHT_RATE = 0.40
# years-before-death -> rate on the slice of a gift above the nil-rate band (gov.uk/inheritance-tax/gifts)
IHT_TAPER = [(3, 0.40), (4, 0.32), (5, 0.24), (6, 0.16), (7, 0.08)]

VARIABLE_FROM_LCF = ["groceries", "eating_out", "transport", "shopping", "leisure", "health", "misc"]

DISCLAIMER = ("Guidance, not regulated financial advice. Figures are simulations based on historical "
              "UK asset returns and are not a promise of future performance or house prices. For help, "
              "contact MoneyHelper (0800 138 7777) or StepChange (0800 138 1111).")

# ONS National Life Tables, United Kingdom, 2022-2024, Females: survivors out of 100,000 born, by age (lx).
# https://www.ons.gov.uk/.../nationallifetablesunitedkingdomreferencetables/current/nltuk198020223.xlsx
FEMALE_LX = {
    60: 93959.8, 61: 93488.2, 62: 92980.3, 63: 92415.9, 64: 91796.0, 65: 91123.8, 66: 90400.0,
    67: 89590.7, 68: 88706.4, 69: 87750.4, 70: 86727.3, 71: 85624.6, 72: 84440.1, 73: 83130.9,
    74: 81714.0, 75: 80179.8, 76: 78493.4, 77: 76670.4, 78: 74664.6, 79: 72433.3, 80: 70005.6,
    81: 67349.7, 82: 64416.0, 83: 61232.2, 84: 57803.1, 85: 54160.9, 86: 50330.8, 87: 46272.1,
    88: 42062.0, 89: 37715.7, 90: 33308.2, 91: 28834.8, 92: 24448.4, 93: 20291.4, 94: 16463.4,
    95: 13049.4, 96: 10082.4, 97: 7565.9, 98: 5505.6, 99: 3864.4, 100: 2638.6,
}


@lru_cache(maxsize=1)
def _returns() -> pd.DataFrame:
    """Real (CPI-deflated) annual UK returns, 1897-2020 (every column of the raw series present)."""
    raw = pd.read_csv(RETURNS_CSV)
    inflation = raw.cpi.pct_change()

    def real(nominal: pd.Series) -> pd.Series:
        return (1 + nominal) / (1 + inflation) - 1

    out = pd.DataFrame({"year": raw.year, "eq": real(raw.eq_tr), "bond": real(raw.bond_tr),
                        "cash": real(raw.bill_rate), "house": real(raw.housing_tr)})
    return out.dropna().reset_index(drop=True)


@lru_cache(maxsize=1)
def _deposit_targets() -> pd.DataFrame:
    df = pd.read_csv(DEPOSIT_CSV)
    return df[df.Date == df.Date.max()].set_index("RegionName")


def deposit_target(region: str, pct: int = 10) -> dict:
    df = _deposit_targets()
    col = "deposit_10pct_ftb" if pct == 10 else "deposit_5pct_ftb"
    row = df.loc[region] if region in df.index else None
    if row is None or pd.isna(row[col]):  # e.g. Northern Ireland / UK rows don't carry a FTB deposit figure
        region = "England"
        row = df.loc[region]
    return {"region": region, "pct": pct, "amount": float(row[col]),
            "ftb_price": float(row.FTBPrice), "as_of": row.Date}


def life_expectancy(age: int) -> float:
    """Remaining years of life (curtate + 0.5) from the ONS period life table above."""
    lx0 = FEMALE_LX[age]
    return 0.5 + sum(FEMALE_LX[a] / lx0 for a in FEMALE_LX if a > age)


def survival_curve(age: int, years: int) -> np.ndarray:
    """P(still alive) at the end of each of the next `years` years, from the ONS period life table."""
    lx0 = FEMALE_LX[age]
    return np.array([FEMALE_LX.get(age + t, 0.0) / lx0 for t in range(1, years + 1)])


# ------------------------------------------------------------------ grandparent cash flow (from the persona)
def annual_net_cashflow(p: Persona) -> float:
    """Guaranteed income minus bills minus everyday spending, in today's money -- the same figures
    the synthetic transaction generator draws on, so the Time Machine stays consistent with the
    90-day forecast for the same person."""
    income = 0.0
    for inc in p.incomes:
        if inc.kind == "state_pension":
            income += calibration.load()["state_pension"]["weekly"] * inc.state_pension_share * 52
        elif inc.kind == "monthly":
            income += inc.amount * 12
        elif inc.kind == "salary":
            band = calibration.age_band(p.age)
            gross = calibration.load()["ashe"]["bands"][band][inc.ashe_percentile]
            income += calibration.net_annual_pay(gross)
        elif inc.kind == "gig_weekly":
            income += inc.amount * (1 - inc.miss_prob) * 52

    bills = 0.0
    for b in p.bills:
        amount = b.changed[1] if b.changed else b.amount  # today's amount if the bill changed in the past
        if b.months is not None:
            bills += amount * len(b.months)
        elif b.every_days is not None:
            bills += amount * 365 / b.every_days
        else:
            bills += amount * 12

    lcf = calibration.load()["lcf"][p.status]["weekly_per_person"]
    spend = sum(lcf[c] * p.category_scale.get(c, 1.0) for c in VARIABLE_FROM_LCF if c in lcf)
    spend = spend * p.household_size * p.spend_scale * 52
    spend += sum(p.extra_weekly.values()) * 52

    return income - bills - spend


def annual_outgoings(p: Persona) -> float:
    """Bills plus everyday spending only (no income) -- the base for the safety-floor assumption."""
    bills = 0.0
    for b in p.bills:
        amount = b.changed[1] if b.changed else b.amount  # today's amount if the bill changed in the past
        if b.months is not None:
            bills += amount * len(b.months)
        elif b.every_days is not None:
            bills += amount * 365 / b.every_days
        else:
            bills += amount * 12
    lcf = calibration.load()["lcf"][p.status]["weekly_per_person"]
    spend = sum(lcf[c] * p.category_scale.get(c, 1.0) for c in VARIABLE_FROM_LCF if c in lcf)
    spend = spend * p.household_size * p.spend_scale * 52
    spend += sum(p.extra_weekly.values()) * 52
    return bills + spend


# ------------------------------------------------------------------ Monte Carlo
def _bootstrap_year_idx(n_hist: int, horizon: int, n: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = -(-horizon // BLOCK)
    starts = rng.integers(0, n_hist - BLOCK + 1, size=(n, n_blocks))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(n, -1)[:, :horizon]
    return idx


def simulate(family_id: str, gift: float, timing: str, monthly_saving: float, region: str | None = None,
             deposit_pct: int | None = None, horizon: int = HORIZON_YEARS, n: int = N_PATHS, seed: int = 11,
             lisa: bool = True, _with_baseline: bool = True) -> dict:
    if family_id not in FAMILIES:
        raise KeyError(family_id)
    fam = FAMILIES[family_id]
    region = region or fam["region"]
    deposit_pct = deposit_pct or fam["deposit_pct"]
    target_years = fam["target_years"]
    ps = personas()
    gp = ps[fam["grandparent"]]
    ya = ps[fam["young_adult"]]
    as_of = default_as_of()

    rng = np.random.default_rng(seed)
    rets = _returns()
    idx = _bootstrap_year_idx(len(rets), horizon, n, rng)
    eq, bond, house = (rets[c].to_numpy()[idx] for c in ("eq", "bond", "house"))
    young_r = YOUNG_MIX["eq"] * eq + YOUNG_MIX["bond"] * bond
    gp_r = GRANDPARENT_MIX["eq"] * eq + GRANDPARENT_MIX["bond"] * bond

    # -------- grandparent's own balance: the gift leaves it immediately ("now"/"10y") or never ("inheritance")
    gp_net = annual_net_cashflow(gp)
    gp_bal = np.empty((n, horizon + 1))
    gp_bal[:, 0] = gp.current_balance + gp.savings_balance  # current account + savings pot
    for t in range(1, horizon + 1):
        outflow = gift if (timing == "now" and t == 1) or (timing == "10y" and t == 10) else 0.0
        gp_bal[:, t] = (gp_bal[:, t - 1] + gp_net - outflow) * (1 + gp_r[:, t - 1])
    floor = SAFETY_FLOOR_MONTHS / 12 * annual_outgoings(gp)
    p_floor_safe = float(np.mean(gp_bal[:, 1:].min(axis=1) >= floor))

    # -------- young adult's deposit pot
    annual_contrib = monthly_saving * 12
    pot = np.zeros((n, horizon + 1))
    pot[:, 0] = ya.savings_balance  # what the young adult has already saved
    death_idx = None
    bequest_value = None
    if timing == "inheritance":
        surv = survival_curve(gp.age, horizon)
        p_alive_prev = np.concatenate([[1.0], surv[:-1]])
        p_die_this_year = np.clip(p_alive_prev - surv, 0, None)
        probs = np.append(p_die_this_year, surv[-1])
        probs = probs / probs.sum()
        death_idx = rng.choice(horizon + 1, size=n, p=probs)  # value == horizon -> still alive at the end
        cum_gp_growth = np.cumprod(1 + gp_r, axis=1)
        gross_bequest = gift * np.take_along_axis(cum_gp_growth, np.clip(death_idx, 0, horizon - 1)[:, None], 1)[:, 0]
        # inherited (not lifetime-gifted), so taper relief doesn't apply -- it's a flat estate-tax test instead
        estate_at_death = gp_bal[np.arange(n), np.clip(death_idx + 1, 0, horizon)] + gross_bequest
        taxable = np.clip(estate_at_death - IHT_NIL_RATE_BAND, 0, None)
        tax_share = np.where(estate_at_death > 0, gross_bequest / estate_at_death, 0.0)  # tax apportioned pro-rata
        bequest_value = np.where(death_idx < horizon, gross_bequest - taxable * IHT_RATE * tax_share, 0.0)

    for t in range(1, horizon + 1):
        age_t = ya.age + t - 1
        bonus = min(annual_contrib, LISA_ANNUAL_CAP) * LISA_BONUS_RATE if lisa and age_t < LISA_MAX_AGE else 0.0
        inflow = np.full(n, annual_contrib + bonus)
        if timing == "now" and t == 1:
            inflow = inflow + gift
        elif timing == "10y" and t == 10:
            inflow = inflow + gift
        elif timing == "inheritance":
            inflow = inflow + np.where(death_idx == t - 1, bequest_value, 0.0)
        pot[:, t] = (pot[:, t - 1] + inflow) * (1 + young_r[:, t - 1])

    target0 = deposit_target(region, deposit_pct)
    target_path = target0["amount"] * np.cumprod(1 + house, axis=1)  # the target itself moves with real house prices
    hit = pot[:, 1:] >= target_path
    p_deposit = float(np.mean(hit[:, :target_years].any(axis=1)))   # by the target year
    p_deposit_horizon = float(np.mean(hit.any(axis=1)))             # at any point in the horizon

    def band(arr: np.ndarray) -> list[dict]:
        q = np.percentile(arr, [10, 25, 50, 75, 90], axis=0)
        return [{"p10": round(float(q[0, t]), 2), "p25": round(float(q[1, t]), 2), "p50": round(float(q[2, t]), 2),
                 "p75": round(float(q[3, t]), 2), "p90": round(float(q[4, t]), 2)} for t in range(arr.shape[1])]

    years = [as_of.year + t for t in range(horizon + 1)]
    genz_band = band(pot)
    giver_band = band(gp_bal)
    deposit_goal = [round(target0["amount"], 2)] + [round(float(v), 2) for v in np.median(target_path, axis=0)]
    baseline = None
    if _with_baseline:
        base = simulate(family_id, 0.0, timing, monthly_saving, region, deposit_pct, horizon, n, seed, lisa,
                        _with_baseline=False)
        baseline = {"p_deposit_by_target": base["p_deposit_by_target"],
                    "p_parent_floor_safe": base["p_parent_floor_safe"]}

    estate_now = gp.current_balance + gp.savings_balance  # the gift comes out of this, so it's already included
    iht = {
        "nil_rate_band": IHT_NIL_RATE_BAND,
        "rate": IHT_RATE,
        "taper_relief": [{"years_before_death": y, "rate": r} for y, r in IHT_TAPER],
        "seven_year_rule": "No Inheritance Tax on a lifetime gift if the giver lives 7+ years after giving it, "
                            "unless it's part of a trust.",
        "estate_now": round(estate_now, 2),
        "exceeds_nil_rate_band": estate_now > IHT_NIL_RATE_BAND,
        "likely_tax_due": round(max(0.0, estate_now - IHT_NIL_RATE_BAND) * IHT_RATE, 2),
    }

    return {
        "family_id": family_id,
        "grandparent": {"id": gp.id, "name": gp.name, "first_name": gp.first_name, "age": gp.age},
        "young_adult": {"id": ya.id, "name": ya.name, "first_name": ya.first_name, "age": ya.age},
        "gift": gift,
        "timing": timing,
        "monthly_saving": monthly_saving,
        "lisa": lisa,
        "years": years,
        "genz_band": genz_band,
        "giver_band": giver_band,
        "deposit_goal": deposit_goal,
        "target_year": as_of.year + target_years,
        "p_deposit_by_target": round(p_deposit, 3),
        "p_deposit_within_horizon": round(p_deposit_horizon, 3),
        "p_parent_floor_safe": round(p_floor_safe, 3),
        "baseline": baseline,
        "deposit_target": target0,
        "safety_floor": round(floor, 2),
        "inheritance_expected_years": round(life_expectancy(gp.age)),
        "starting_savings": {"grandparent": round(gp.current_balance + gp.savings_balance, 2),
                             "young_adult": round(ya.savings_balance, 2)},
        "assumptions": {
            "method": f"Monte Carlo, {n} paths over {horizon} years, block-bootstrapped in {BLOCK}-year blocks "
                      f"from real (CPI-deflated) UK returns, {int(rets.year.min())}-{int(rets.year.max())} "
                      "(Jorda-Schularick-Taylor Macrohistory dataset). All figures are in today's money.",
            "young_adult_asset_mix": YOUNG_MIX,
            "grandparent_asset_mix": GRANDPARENT_MIX,
            "lifetime_isa_bonus": (f"25% government bonus on contributions up to £{LISA_ANNUAL_CAP:,.0f}/year, "
                                   f"until age {LISA_MAX_AGE} (gov.uk/lifetime-isa)") if lisa
                                  else "Not used: savings go into an ordinary savings account (no bonus)",
            "starting_savings": f"{gp.first_name} starts with £{gp.current_balance + gp.savings_balance:,.0f} "
                                f"(current account and savings); {ya.first_name} starts with "
                                f"£{ya.savings_balance:,.0f} already saved",
            "deposit_goal": f"{deposit_pct}% of the average first-time-buyer price in {target0['region'].removesuffix(' Region')} "
                            f"(HM Land Registry UK HPI, {target0['as_of']}), moving with real UK house prices; "
                            f"target year {as_of.year + target_years}",
            "grandparent_annual_net_cashflow": round(gp_net, 2),
            "safety_floor_method": f"{SAFETY_FLOOR_MONTHS:.0f} months of the grandparent's bills and everyday "
                                   "spending (assumption, not a cited guideline)",
            "inheritance_mortality": (
                "Years-of-death are sampled from the ONS National Life Tables 2022-2024 "
                f"period life expectancy for a {gp.age}-year-old woman "
                f"(about {FEMALE_LX.get(gp.age + horizon, 0) / FEMALE_LX[gp.age]:.0%} chance "
                f"of living beyond {horizon} more years); a gift via inheritance that falls "
                "outside this window is not received in the simulation."
            ) if timing == "inheritance" else "Not used for this timing choice.",
            "inheritance_tax": iht,
            "deposit_target_region": region,
            "disclaimer": DISCLAIMER,
        },
        "sources": [
            {"title": "Jorda-Schularick-Taylor Macrohistory Database R6 (UK equity, bond, bill and housing "
                      "total returns, 1870-2020)", "url": "https://www.macrohistory.net/database/"},
            {"title": "HM Land Registry UK House Price Index -- regional deposit targets",
             "url": "https://www.gov.uk/government/collections/uk-house-price-index-reports"},
            {"title": "gov.uk: Lifetime ISA", "url": "https://www.gov.uk/lifetime-isa"},
            {"title": "gov.uk: How Inheritance Tax works -- gifts",
             "url": "https://www.gov.uk/inheritance-tax/gifts"},
            {"title": "ONS National Life Tables, United Kingdom, 2022-2024",
             "url": "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/"
                    "lifeexpectancies/datasets/nationallifetablesunitedkingdomreferencetables/current/"
                    "nltuk198020223.xlsx"},
        ],
    }
