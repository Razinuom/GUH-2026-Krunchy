from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.heirloom import calibration, forecast as fc, service, synth
from backend.heirloom.personas import personas

AS_OF = date(2026, 11, 7)
MEMBERS = list(personas())


@pytest.fixture(scope="module")
def tx():
    return synth.generate(AS_OF)


@pytest.fixture(scope="module")
def results(tx):
    return {m: fc.forecast(m, tx, AS_OF) for m in MEMBERS}


# ---------------------------------------------------------------- calibration
def test_calibration_reads_ons_tables():
    cal = calibration.build(write=False)
    ft = cal["lcf"]["employee_ft"]["weekly_per_person"]
    assert 20 < ft["groceries"] < 60 and set(ft) >= {"groceries", "transport", "eating_out"}
    assert cal["lcf"]["retired"]["weekly_per_person"] != ft  # status columns parsed separately
    assert 35_000 < cal["ashe"]["bands"]["40-49"]["p50"] < 60_000
    assert 200 < cal["state_pension"]["weekly"] < 300


def test_net_pay_is_below_gross_and_monotonic():
    assert calibration.net_annual_pay(12_000) == 12_000
    a, b = calibration.net_annual_pay(30_000), calibration.net_annual_pay(60_000)
    assert 0 < a < 30_000 and a < b < 60_000


# ---------------------------------------------------------------- synthetic data
def test_synthetic_balance_ends_at_persona_balance(tx):
    for p in personas().values():
        last = tx[tx.member_id == p.id].balance.iloc[-1]
        assert last == pytest.approx(p.current_balance, abs=0.05)
    assert tx.date.max().date() == date(2026, 11, 6)


def test_synthetic_is_deterministic():
    a, b = synth.generate(AS_OF), synth.generate(AS_OF)
    assert a.equals(b)


# ---------------------------------------------------------------- recurring detection
def test_detects_tomasz_salary_and_rent_from_transactions(tx):
    flows = {f.merchant: f for f in fc.detect_recurring(tx[tx.member_id == "tomasz"], AS_OF)}
    assert flows["NORTHGATE LOGISTICS SALARY"].cadence == "monthly"
    assert flows["NORTHGATE LOGISTICS SALARY"].amount > 2000
    assert flows["GREENWAY LETTINGS RENT"].amount == pytest.approx(-1525)  # after September's rent rise
    assert "TESCO" not in flows


def test_detects_four_weekly_pension_and_irregular_gig_income(tx):
    halina = {f.merchant: f for f in fc.detect_recurring(tx[tx.member_id == "halina"], AS_OF)}
    assert halina["DWP STATE PENSION"].cadence == "four_weekly"
    daniel = {f.merchant: f for f in fc.detect_recurring(tx[tx.member_id == "daniel"], AS_OF)}
    gig = daniel["SWIFTDROP COURIER PAYOUT"]
    assert gig.cadence == "weekly" and gig.irregular


# ---------------------------------------------------------------- forecast output
@pytest.mark.parametrize("member", MEMBERS)
def test_band_is_ordered_and_sized(results, member):
    r = results[member]
    assert len(r["days"]) == 91 and r["days"][0]["d"] == 0
    for d in r["days"]:
        assert d["p10"] <= d["p50"] <= d["p90"]
    assert 0 <= r["overdraft_probability"] <= 1
    hz = r["overdraft_probability_by_horizon"]
    assert hz["30"] <= hz["60"] <= hz["90"] == r["overdraft_probability"]
    low = r["lowest_point"]
    assert low["p50"] == min(d["p50"] for d in r["days"][1:])


def test_same_seed_same_answer(tx):
    assert fc.forecast("tomasz", tx, AS_OF, seed=3) == fc.forecast("tomasz", tx, AS_OF, seed=3)


def test_risk_ordering_matches_demo_script(results):
    p = {m: r["overdraft_probability"] for m, r in results.items()}
    assert p["daniel"] > p["tomasz"] > p["halina"]
    assert 0.05 <= p["tomasz"] <= 0.30 and results["tomasz"]["risk_band"] == "watch"
    assert results["daniel"]["risk_band"] == "high"
    assert results["halina"]["risk_band"] == "low"


def test_reasons_explain_tomasz(results):
    reasons = {r["feature"]: r for r in results["tomasz"]["reasons"]}
    assert "Car insurance renewal" in reasons and reasons["Car insurance renewal"]["impact"] > 0
    total = sum(r["impact"] for r in results["tomasz"]["reasons"])
    assert total <= results["tomasz"]["overdraft_probability"] + 1e-6


def test_removing_a_scheduled_bill_lowers_risk(tx, monkeypatch):
    base = fc.forecast("tomasz", tx, AS_OF)["overdraft_probability"]
    monkeypatch.setattr(fc, "scheduled_changes", lambda m, a: [])
    assert fc.forecast("tomasz", tx, AS_OF)["overdraft_probability"] < base


# ---------------------------------------------------------------- API
@pytest.fixture()
def client(tx, monkeypatch):
    monkeypatch.setenv("HEIRLOOM_AS_OF", AS_OF.isoformat())
    monkeypatch.setattr(service, "load_transactions", lambda as_of: tx)
    service.clear_caches()
    with TestClient(main.app) as c:
        yield c
    service.clear_caches()


def test_api_contract(client):
    r = client.post("/forecast", json={"member_id": "halina"})
    assert r.status_code == 200
    body = r.json()
    assert {"days", "overdraft_probability", "lowest_point", "reasons"} <= set(body)
    assert set(body["days"][1]) >= {"d", "p10", "p50", "p90"}
    assert set(body["lowest_point"]) >= {"day", "p50"}
    assert "not regulated" in body["assumptions"]["disclaimer"]


def test_api_unknown_member_404(client):
    assert client.post("/forecast", json={"member_id": "nobody"}).status_code == 404


def test_api_members(client):
    ids = [m["id"] for m in client.get("/members").json()]
    assert ids == MEMBERS
