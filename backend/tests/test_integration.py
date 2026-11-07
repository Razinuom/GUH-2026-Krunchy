"""One family, one dataset: every endpoint must describe the same people with the same numbers."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.hardship import service as hardship
from backend.heirloom import service, synth
from backend.heirloom import timemachine as tm
from backend.heirloom.personas import personas

AS_OF = date(2026, 11, 7)
MEMBERS = list(personas())
DEMO_BANDS = {"halina": "low", "tomasz": "watch", "zofia": "low", "grace": "low", "daniel": "high", "ada": "low"}


@pytest.fixture(scope="module")
def client():
    service.clear_caches()
    hardship._data_for.cache_clear()
    main._timemachine_cached.cache_clear()
    with TestClient(main.app) as c:
        yield c


# ---------------------------------------------------------------- one dataset
def test_default_as_of_is_pinned_for_tests():
    assert synth.default_as_of() == AS_OF


@pytest.mark.parametrize("member", MEMBERS)
def test_forecast_and_hardship_use_the_same_balance(client, member):
    f = client.post("/forecast", json={"member_id": member}).json()
    h = client.post("/hardship", json={"member_id": member}).json()
    assert h["balance"] == pytest.approx(f["start_balance"], abs=0.01)
    assert h["as_of"] == "2026-11-06"


@pytest.mark.parametrize("member,expected", DEMO_BANDS.items())
def test_forecast_and_hardship_agree_on_the_risk_band(client, member, expected):
    f = client.post("/forecast", json={"member_id": member}).json()
    h = client.post("/hardship", json={"member_id": member}).json()
    assert f["risk_band"] == h["band"] == expected


def test_demo_script_numbers(client):
    tomasz = client.post("/forecast", json={"member_id": "tomasz"}).json()
    assert 0.10 <= tomasz["overdraft_probability"] <= 0.18  # "about 14%, Watch"
    daniel = client.post("/hardship", json={"member_id": "daniel"}).json()
    assert daniel["guardian"]["escalate"]


def test_hardship_sees_mapped_categories():
    tx, _ = hardship._data()
    cats = set(tx.category)
    assert {"bnpl", "communication", "council_tax", "savings_transfer"} <= cats
    assert "phone" not in cats and "savings" not in cats


def test_shared_csv_is_not_overwritten_by_hardship_personas():
    from backend.hardship import personas as hp
    assert hp.OUT_DIR.name == "hardship_personas"


# ---------------------------------------------------------------- /families
def test_families_lists_both_families_in_generation_order(client):
    fams = {f["id"]: f for f in client.get("/families").json()}
    assert set(fams) == {"nowak", "okafor"}
    assert [m["id"] for m in fams["nowak"]["members"]] == ["halina", "tomasz", "zofia"]
    assert [m["generation"] for m in fams["okafor"]["members"]] == [1, 2, 3]
    assert "pl" in fams["nowak"]["members"][0]["languages"]
    assert fams["nowak"]["time_machine"]["region"] == "West Midlands"
    assert fams["nowak"]["time_machine"]["target_year"] == 2032


# ---------------------------------------------------------------- Time Machine
def test_timemachine_gift_now_raises_deposit_chance_and_floor_holds(client):
    r = client.post("/timemachine", json={"family_id": "nowak", "gift": 8000, "timing": "now",
                                          "monthly_saving": 200, "lisa": False}).json()
    assert r["p_deposit_by_target"] > r["baseline"]["p_deposit_by_target"] + 0.2
    assert r["p_parent_floor_safe"] >= 0.9
    assert len(r["giver_band"]) == len(r["genz_band"]) == len(r["deposit_goal"]) == len(r["years"])
    assert r["deposit_goal"][0] == r["deposit_target"]["amount"]
    assert r["target_year"] == 2032 and r["deposit_target"]["region"] == "West Midlands Region"
    assert r["starting_savings"]["grandparent"] > 60000


def test_timemachine_lisa_bonus_helps():
    with_lisa = tm.simulate("okafor", 0, "now", 60, n=2000, seed=4, lisa=True)
    without = tm.simulate("okafor", 0, "now", 60, n=2000, seed=4, lisa=False)
    assert with_lisa["genz_band"][-1]["p50"] > without["genz_band"][-1]["p50"]


# ---------------------------------------------------------------- Claim Check, /ask, /escalate
def test_claimcheck_red_amber_green(client):
    red = client.post("/claimcheck", json={"claim": "This coin is guaranteed to 10x, act now"}).json()
    assert red["rating"] == "red" and red["label"] == "Likely Scam" and len(red["signals"]) >= 2
    assert any("fca.org.uk" in s["url"] for s in red["sources"])
    green = client.post("/claimcheck", json={"claim": "The Lifetime ISA adds a 25% bonus"}).json()
    assert green["rating"] == "green"
    accurate = client.post("/claimcheck", json={"claim": "You can gift £3,000 a year free of inheritance tax"}).json()
    assert accurate["rating"] == "green"  # the annual exemption really is £3,000
    overstated = client.post("/claimcheck", json={"claim": "You can give away £3,000 a year with no inheritance tax, "
                                                            "and anything else is tax-free after 7 years."}).json()
    assert overstated["rating"] == "amber" and overstated["label"] == "Partly Supported"
    assert overstated["researcher"] == "saved"  # tests never call Firecrawl (see conftest.py)


def test_ask_cites_sources_and_refuses_stock_picks(client):
    a = client.post("/ask", json={"question": "How much is the Lifetime ISA bonus?", "lang": "en"}).json()
    assert a["sources"] and any("lifetime-isa" in s["url"] for s in a["sources"])
    refused = client.post("/ask", json={"question": "Which stock should I buy?"}).json()
    assert refused["refused"] is True


def test_escalate_logs_and_returns_help(client, monkeypatch, tmp_path):
    monkeypatch.setattr("backend.voice.router.LOG_DIR", tmp_path)
    r = client.post("/escalate", json={"member_id": "daniel", "reason": "debt"})
    assert r.status_code == 200 and r.json()["contacts"][0]["name"].startswith("StepChange")
    assert "daniel" in (tmp_path / "escalations.jsonl").read_text()
    assert client.post("/escalate", json={"member_id": "nobody"}).status_code == 404


# ---------------------------------------------------------------- offline snapshot must match the live API
def test_frontend_snapshot_is_up_to_date(client):
    """If this fails, run: python scripts/export_frontend_snapshot.py"""
    import json
    from pathlib import Path

    snap = json.loads((Path(__file__).resolve().parents[2] / "frontend/src/data/snapshot.json").read_text())
    assert snap["as_of"] == AS_OF.isoformat()
    assert snap["families"] == client.get("/families").json()
    for m in MEMBERS:
        live_f = client.post("/forecast", json={"member_id": m}).json()
        live_h = client.post("/hardship", json={"member_id": m}).json()
        assert snap["forecasts"][m]["overdraft_probability"] == live_f["overdraft_probability"], m
        assert snap["forecasts"][m]["days"] == live_f["days"], m
        assert snap["hardship"][m]["risk_score"] == live_h["risk_score"], m
