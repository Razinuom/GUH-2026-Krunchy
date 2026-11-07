from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.hardship.features import FEATURE_NAMES, compute_features
from backend.hardship.service import assess, assess_member, band
from backend.hardship.simulate import Profile, simulate
from backend.main import app

client = TestClient(app)


def test_daily_balance_reconstruction_matches_simulator():
    p = Profile("t", opening_balance=300, overdraft_limit=500)
    tx, bal = simulate(p, date(2025, 1, 1), 200, seed=3)
    f = compute_features(tx, float(bal.iloc[-1]), bal.index[-1])
    assert f["min_balance_90d"] == pytest.approx(bal.iloc[-90:].min(), abs=0.05)
    assert f["days_overdrawn_90d"] == (bal.iloc[-90:] < 0).sum()


def test_overdraft_limit_declines_card_spend():
    p = Profile("t", monthly_income=1000, housing_cost=0, bills=0, spend_ratio=1.6,
                opening_balance=0, overdraft_limit=200, shock_rate=0)
    _, bal = simulate(p, date(2025, 1, 1), 200, seed=1)
    assert bal.min() >= -200 - 1


def test_features_complete_and_finite():
    tx, bal = simulate(Profile("t"), date(2025, 1, 1), 200, seed=0)
    f = compute_features(tx, float(bal.iloc[-1]))
    assert list(f) == FEATURE_NAMES
    assert all(np.isfinite(v) for v in f.values())


def test_probabilities_monotone_in_horizon_and_bounded():
    for mid in ["halina", "tomasz", "zofia", "grace", "daniel", "ada"]:
        r = assess_member(mid)
        ps = list(r["overdraft_probability_by_horizon"].values())
        assert ps == sorted(ps) and all(0 <= x <= 1 for x in ps)
        assert r["risk_score"] == round(r["overdraft_probability"] * 100)


def test_demo_story():
    assert assess_member("tomasz")["band"] == "watch"
    d = assess_member("daniel")
    assert d["band"] == "high" and d["guardian"]["escalate"]
    assert any(x["id"] == "stepchange" for x in d["guardian"]["resources"])
    assert assess_member("halina")["band"] == "low"
    assert any(r["key"] == "housing_increase" for r in assess_member("tomasz")["reasons"])


def test_reason_impacts_sum_to_shift_from_baseline():
    r = assess_member("daniel", top_k=16)
    total = sum(x["impact"] for x in r["reasons"])
    # small reasons (<0.5pp) are dropped, so allow slack
    assert total == pytest.approx(r["overdraft_probability"] - r["baseline_probability"], abs=0.06)


def test_more_money_never_raises_risk():
    tx, bal = simulate(Profile("t", opening_balance=200), date(2025, 1, 1), 200, seed=5)
    lo = assess(tx, float(bal.iloc[-1]))["overdraft_probability"]
    tx2 = pd.concat([tx, pd.DataFrame([{"date": tx["date"].max(), "member_id": "t", "amount": 2000.0,
                                        "category": "gift", "merchant": "Gran"}])])
    hi = assess(tx2, float(bal.iloc[-1]) + 2000)["overdraft_probability"]
    assert hi <= lo + 1e-9


def test_bands():
    assert band(0.05) == "low" and band(0.14) == "watch" and band(0.5) == "high"


def test_api_member_family_and_errors():
    r = client.post("/hardship", json={"member_id": "tomasz"})
    assert r.status_code == 200 and {"risk_score", "reasons", "guardian"} <= r.json().keys()
    fam = client.post("/hardship", json={"family_id": "okafor"}).json()
    assert {m["member_id"] for m in fam["members"]} == {"grace", "daniel", "ada"}
    assert client.post("/hardship", json={"member_id": "nobody"}).status_code == 404
    assert client.post("/hardship", json={}).status_code == 422


def test_api_score_raw_feed():
    tx, bal = simulate(Profile("x"), date(2025, 1, 1), 120, seed=2)
    body = {"balance": float(bal.iloc[-1]),
            "transactions": [{"date": d.strftime("%Y-%m-%d"), "amount": a, "category": c, "merchant": m}
                             for d, a, c, m in tx[["date", "amount", "category", "merchant"]].itertuples(index=False)]}
    r = client.post("/hardship/score", json=body)
    assert r.status_code == 200 and 0 <= r.json()["risk_score"] <= 100


def test_api_model_card():
    rep = client.get("/hardship/model").json()
    assert rep["horizons"]["90d"]["test_auc_not_recently_overdrawn"] > 0.8
