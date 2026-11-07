import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.heirloom import timemachine as tm

FAMILIES = list(tm.FAMILIES)


# ---------------------------------------------------------------- building blocks
def test_returns_are_real_and_span_the_dataset():
    rets = tm._returns()
    assert rets.year.min() < 1900 and rets.year.max() >= 2019
    assert {"eq", "bond", "cash", "house"} <= set(rets.columns)
    assert rets[["eq", "bond", "cash", "house"]].isna().sum().sum() == 0


def test_deposit_target_falls_back_for_regions_without_a_figure():
    assert tm.deposit_target("England")["amount"] > 0
    ni = tm.deposit_target("Northern Ireland")  # no FTB deposit column in the source data
    assert ni["region"] == "England"


def test_survival_curve_is_decreasing_and_bounded():
    s = tm.survival_curve(71, 25)
    assert (np.diff(s) <= 0).all()
    assert 0 <= s[-1] <= s[0] <= 1


def test_annual_outgoings_positive_for_both_grandparents():
    from backend.heirloom.personas import personas
    ps = personas()
    assert tm.annual_outgoings(ps["halina"]) > 0
    assert tm.annual_outgoings(ps["grace"]) > 0


# ---------------------------------------------------------------- simulate()
@pytest.mark.parametrize("family_id", FAMILIES)
@pytest.mark.parametrize("timing", ["now", "10y", "inheritance"])
def test_band_is_ordered_and_sized(family_id, timing):
    r = tm.simulate(family_id, gift=8000, timing=timing, monthly_saving=250, n=500, seed=1)
    assert len(r["years"]) == len(r["genz_band"]) == tm.HORIZON_YEARS + 1
    for band in r["genz_band"]:
        assert band["p10"] <= band["p50"] <= band["p90"]
    assert 0 <= r["p_deposit_by_target"] <= 1
    assert 0 <= r["p_parent_floor_safe"] <= 1
    assert r["genz_band"][0] == {"p10": 0.0, "p50": 0.0, "p90": 0.0}  # nothing received before year 0


def test_same_seed_same_answer():
    a = tm.simulate("nowak", 8000, "now", 250, n=500, seed=3)
    b = tm.simulate("nowak", 8000, "now", 250, n=500, seed=3)
    assert a == b


def test_gifting_now_beats_inheritance_for_the_young_adult():
    """More compounding runway (and no chance the gift misses the 25-year window) should raise the
    young adult's deposit chance, matching the demo script's "gift now vs as inheritance" story."""
    now = tm.simulate("nowak", 8000, "now", 250, n=4000, seed=5)
    inheritance = tm.simulate("nowak", 8000, "inheritance", 250, n=4000, seed=5)
    assert now["genz_band"][-1]["p50"] > inheritance["genz_band"][-1]["p50"]
    assert now["p_deposit_by_target"] >= inheritance["p_deposit_by_target"]


def test_inheritance_keeps_the_grandparents_own_safety_net_intact():
    """Keeping the gift until death (vs. handing it over now) should never leave the grandparent
    worse off on their own safety floor, since they're never out the cash while alive."""
    now = tm.simulate("nowak", 8000, "now", 250, n=4000, seed=5)
    inheritance = tm.simulate("nowak", 8000, "inheritance", 250, n=4000, seed=5)
    assert inheritance["p_parent_floor_safe"] >= now["p_parent_floor_safe"]


def test_okafor_grandmother_has_no_estate_to_speak_of():
    """Grace (social housing, no savings to speak of) is the social-mobility proof persona: the
    inheritance-tax machinery should report nothing is due regardless."""
    r = tm.simulate("okafor", 2000, "inheritance", 100, n=500, seed=2)
    assert r["assumptions"]["inheritance_tax"]["exceeds_nil_rate_band"] is False
    assert r["assumptions"]["inheritance_tax"]["likely_tax_due"] == 0.0


def test_unknown_family_raises():
    with pytest.raises(KeyError):
        tm.simulate("smith", 1000, "now", 100)


# ---------------------------------------------------------------- API
@pytest.fixture()
def client():
    main._timemachine_cached.cache_clear()
    with TestClient(main.app) as c:
        yield c
    main._timemachine_cached.cache_clear()


def test_api_contract(client):
    r = client.post("/timemachine", json={"family_id": "nowak", "gift": 8000, "timing": "now", "monthly_saving": 250})
    assert r.status_code == 200
    body = r.json()
    assert {"years", "genz_band", "p_deposit_by_target", "p_parent_floor_safe"} <= set(body)
    assert len(body["years"]) == len(body["genz_band"])
    assert "not regulated" in body["assumptions"]["disclaimer"]


def test_api_unknown_family_404(client):
    r = client.post("/timemachine", json={"family_id": "smith", "gift": 1000, "timing": "now", "monthly_saving": 0})
    assert r.status_code == 404
