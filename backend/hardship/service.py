"""Hardship early warning: risk score + SHAP reasons + Guardian escalation.

Usage from other backend code (e.g. to fill `overdraft_probability` and `reasons`
in the /forecast response):

    from backend.hardship.service import assess_member
    assess_member("tomasz")
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, FEATURES, compute_features, explain_value

MODEL_DIR = Path(__file__).resolve().parent / "model"
REPO = Path(__file__).resolve().parents[2]
# By default the model scores the shared Heirloom personas (backend.heirloom, via adapter.py), so
# /hardship, /forecast, /timemachine and the voice coach all describe the same family.
# Set both variables to score a different feed (e.g. an exported NatWest Bank of APIs history).
TX_PATH = os.environ.get("HEIRLOOM_TX_PATH")
MEMBERS_PATH = os.environ.get("HEIRLOOM_MEMBERS_PATH")
HORIZONS = (30, 60, 90)
BANDS = [(0.30, "high"), (0.10, "watch"), (0.0, "low")]  # same cut-offs as the 90-day forecast

DISCLAIMER = ("Guidance, not regulated financial advice. Scores come from a model trained on "
              "synthetic households calibrated to ONS spending data.")

RESOURCES = {
    "moneyhelper": {"name": "MoneyHelper (free, government-backed guidance)", "phone": "0800 138 7777",
                    "url": "https://www.moneyhelper.org.uk/en/money-troubles"},
    "stepchange": {"name": "StepChange Debt Charity (free debt advice)", "phone": "0800 138 1111",
                   "url": "https://www.stepchange.org"},
    "citizensadvice": {"name": "Citizens Advice", "url": "https://www.citizensadvice.org.uk/debt-and-money/"},
    "gamcare": {"name": "GamCare / National Gambling Helpline", "phone": "0808 8020 133",
                "url": "https://www.gamcare.org.uk"},
    "bank": {"name": "Talk to your bank's financial support team",
             "note": "Banks must treat customers in financial difficulty fairly (FCA Consumer Duty)."},
}

# What to suggest when a feature is pushing risk up. Sources are in data/kb.
TIPS = {
    "housing_increase": ("If your rent or mortgage has gone up, check whether you can get help with "
                         "housing costs through Universal Credit, or ask your lender about options.",
                         "https://www.gov.uk/universal-credit"),
    "income_change_30d": ("Income has dropped. A benefits check can show support you may be missing.",
                          "https://www.gov.uk/budgeting-help-benefits"),
    "income_volatility": ("With variable income, a buffer of one quiet month's costs helps smooth bills.",
                          "https://www.gov.uk/get-help-savings-low-income"),
    "payday_loans_90d": ("Payday loans are expensive. Free debt advice can help you find cheaper options.",
                         "https://www.gov.uk/options-for-paying-off-your-debts"),
    "bnpl_share": ("Buy now, pay later repayments are adding up. List them all before taking on more.",
                   "https://www.gov.uk/options-for-paying-off-your-debts"),
    "days_overdrawn_90d": ("You've been overdrawn often. Ask your bank about overdraft support.",
                           "https://www.gov.uk/options-for-paying-off-your-debts"),
    "spend_to_income_90d": ("Spending is close to or above income. A simple budget can show where to trim.",
                            "https://www.gov.uk/budgeting-help-benefits"),
    "essentials_share": ("Essentials take most of your income. Check for benefits, social tariffs and discounts.",
                         "https://www.gov.uk/budgeting-help-benefits"),
    "gambling_share": ("Gambling is a large share of spending. Free, confidential support is available.",
                       "https://www.gamcare.org.uk"),
    "savings_rate": ("Even a small regular saving builds a buffer; on a low income Help to Save adds a 50% bonus.",
                     "https://www.gov.uk/get-help-savings-low-income"),
}


@lru_cache(maxsize=1)
def models() -> dict[int, lgb.Booster]:
    missing = [h for h in HORIZONS if not (MODEL_DIR / f"hardship_{h}d.txt").exists()]
    if missing:
        raise FileNotFoundError(f"hardship models missing; run `python -m backend.hardship.train`")
    return {h: lgb.Booster(model_file=str(MODEL_DIR / f"hardship_{h}d.txt")) for h in HORIZONS}


@lru_cache(maxsize=1)
def model_report() -> dict:
    p = MODEL_DIR / "report.json"
    return json.loads(p.read_text()) if p.exists() else {}


@lru_cache(maxsize=4)
def _data_for(as_of):
    if TX_PATH and MEMBERS_PATH:
        tx = pd.read_csv(TX_PATH, parse_dates=["date"])
        members = json.loads(Path(MEMBERS_PATH).read_text())
        return tx, members
    from . import adapter
    return adapter.load(as_of)


def _data():
    from backend.heirloom.synth import default_as_of
    return _data_for(default_as_of())


def members() -> dict:
    return _data()[1]


def band(p: float) -> str:
    return next(name for cut, name in BANDS if p >= cut)


def score_features(feats: dict[str, float], top_k: int = 5) -> dict:
    X = pd.DataFrame([feats])[FEATURE_NAMES]
    ms = models()
    probs = {h: float(ms[h].predict(X)[0]) for h in HORIZONS}
    # risk can only accumulate with a longer horizon
    running = 0.0
    for h in HORIZONS:
        running = max(running, probs[h])
        probs[h] = running
    p90 = probs[90]

    # TreeSHAP (LightGBM native, exact) in log-odds; last column is the expected value.
    contrib = ms[90].predict(X, pred_contrib=True)[0]
    phi, base_logit = contrib[:-1], contrib[-1]
    p_base = 1 / (1 + np.exp(-base_logit))
    p_raw = 1 / (1 + np.exp(-(phi.sum() + base_logit)))
    total = phi.sum()
    # Share the probability change out in proportion to each feature's log-odds contribution,
    # so impacts add up to (risk - average risk) and read as percentage points.
    scale = (p_raw - p_base) / total if abs(total) > 1e-9 else 0.0
    impacts = phi * scale

    order = np.argsort(-np.abs(impacts))
    reasons = []
    for j in order[:top_k]:
        name = FEATURE_NAMES[j]
        if abs(impacts[j]) < 0.005:
            continue
        up = impacts[j] > 0
        r = {
            "feature": FEATURES[name][0],
            "key": name,
            "impact": round(float(impacts[j]), 3),
            "direction": "raises risk" if up else "lowers risk",
            "detail": explain_value(name, feats),
            "value": round(float(feats[name]), 3),
        }
        if up and name in TIPS:
            r["tip"], r["source"] = TIPS[name]
        reasons.append(r)

    return {
        "risk_score": int(round(round(p90, 3) * 100)),  # from the same rounded value as overdraft_probability
        "band": band(p90),
        "overdraft_probability": round(p90, 3),
        "overdraft_probability_by_horizon": {f"{h}d": round(probs[h], 3) for h in HORIZONS},
        "baseline_probability": round(float(p_base), 3),
        "reasons": reasons,
        "features": {k: round(float(v), 3) for k, v in feats.items()},
    }


def guardian(result: dict) -> dict:
    """Escalation layer: decides whether to offer a human handoff and which services."""
    keys = {r["key"] for r in result["reasons"] if r["impact"] > 0}
    f = result["features"]
    signals = []
    if result["band"] == "high":
        signals.append("high risk of going overdrawn")
    if f["payday_loans_90d"] > 0:
        signals.append("payday loan use")
    if f["gambling_share"] > 0.05:
        signals.append("gambling over 5% of income")
    if f["days_overdrawn_90d"] >= 30:
        signals.append("persistently overdrawn")
    if f["bnpl_share"] > 0.08:
        signals.append("heavy buy now, pay later use")

    res = []
    if signals or result["band"] == "high":
        res += ["stepchange", "moneyhelper", "bank"]
    elif result["band"] == "watch":
        res += ["moneyhelper"]
    if "gambling_share" in keys or f["gambling_share"] > 0.05:
        res.append("gamcare")
    escalate = result["band"] == "high" or len(signals) >= 2
    msg = {
        "high": "There's a real chance money gets very tight in the next few months. "
                "Talking to someone now, before it happens, gives you the most options.",
        "watch": "Things look manageable, but worth keeping an eye on. Small changes now can help.",
        "low": "You're in a steady position right now.",
    }[result["band"]]
    return {"escalate": escalate, "signals": signals, "message": msg,
            "resources": [{"id": k, **RESOURCES[k]} for k in dict.fromkeys(res)]}


def assess(tx: pd.DataFrame, balance: float, as_of=None, top_k: int = 5) -> dict:
    """Score any transaction history (e.g. a NatWest Bank of APIs feed)."""
    feats = compute_features(tx, balance, as_of)
    out = score_features(feats, top_k)
    out["guardian"] = guardian(out)
    rep = model_report().get("horizons", {}).get("90d", {})
    out["model"] = {"type": "LightGBM + TreeSHAP", "trained_at": model_report().get("trained_at"),
                    "test_auc_90d": rep.get("test_auc"),
                    "test_auc_90d_not_recently_overdrawn": rep.get("test_auc_not_recently_overdrawn")}
    out["disclaimer"] = DISCLAIMER
    return out


def assess_member(member_id: str, top_k: int = 5) -> dict:
    tx, mem = _data()
    if member_id not in mem:
        raise KeyError(member_id)
    m = mem[member_id]
    out = assess(tx[tx["member_id"] == member_id], m["balance"], m.get("as_of"), top_k)
    return {"member_id": member_id, "name": m.get("name"), "family_id": m.get("family_id"),
            "as_of": m.get("as_of"), "balance": m["balance"], **out}


def assess_family(family_id: str) -> list[dict]:
    return [assess_member(mid) for mid, m in members().items() if m.get("family_id") == family_id]
