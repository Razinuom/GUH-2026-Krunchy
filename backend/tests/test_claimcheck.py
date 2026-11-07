"""Claim Check: rules, firm checks and figure evidence. Firecrawl is faked here (no network, no credits)."""
import pytest

from backend.heirloom import claimcheck as cc

GOVUK_LISA = {"url": "https://www.gov.uk/lifetime-isa", "title": "Lifetime ISA: Overview - GOV.UK", "description": "",
              "markdown": "You can put in up to £4,000 each year, until you're 50.\n"
                          "The government will add a 25% bonus to your savings, up to a maximum of £1,000 per year."}
COUNCIL_PDF = {"url": "https://democracy.example-council.gov.uk/pack.pdf", "title": "Planning pack", "description": "",
               "markdown": "The government will add a 25% bonus to your savings of £4,000 in this planning pack."}


@pytest.fixture()
def fake_firecrawl(monkeypatch):
    calls = []

    def fake(query, domains, limit=3, scrape=True):
        calls.append((query, tuple(domains), scrape))
        if domains == ["fca.org.uk"]:  # firm warning search
            return [
                {"url": "https://www.fca.org.uk/news/warnings/quantum-partners-ltd-clone",
                 "title": "Quantum Partners Ltd (clone of FCA authorised firm) - FCA", "description": "", "markdown": ""},
                {"url": "https://www.fca.org.uk/news/warnings/quantum-ai", "title": "Quantum AI - FCA",
                 "description": "", "markdown": ""},
                {"url": "https://register.fca.org.uk/s/firm?id=1", "title": "Northgate Wealth Ltd - FCA Register",
                 "description": "", "markdown": ""},
            ]
        return [COUNCIL_PDF, GOVUK_LISA]

    monkeypatch.setattr(cc, "firecrawl_search", fake)
    return calls


# ---------------------------------------------------------------- figures
def test_extract_figures_normalises_amounts():
    figs = {(f["kind"], f["value"]) for f in cc.extract_figures("A 25% bonus on £4k, or £4,000, after seven years")}
    assert figs == {("pct", 25.0), ("gbp", 4000.0), ("years", 7.0)}


def test_figure_patterns_match_official_wording():
    f4000 = cc.extract_figures("£4k")[0]
    assert any(__import__("re").search(p, "up to £4,000 each year") for p in cc._figure_patterns(f4000))
    seven = cc.extract_figures("7 years")[0]
    assert any(__import__("re").search(p, "within seven years of the gift") for p in cc._figure_patterns(seven))


# ---------------------------------------------------------------- firms
def test_extract_firms():
    assert cc.extract_firms("Quantum Partners Ltd says I can double my pension") == ["Quantum Partners Ltd"]
    assert cc.extract_firms("This Crypto coin is great") == []  # one word plus a suffix is not a firm name


def test_firm_warning_needs_an_exact_name_match(fake_firecrawl):
    assert cc.check_firm("Quantum Partners Ltd")["warning"] is True
    # "Quantum Capital Markets" must NOT be matched to Quantum Partners Ltd or Quantum AI
    other = cc.check_firm("Quantum Capital Markets")
    assert other["warning"] is False and other["checked"] is True


def test_firm_on_register_is_noted_not_trusted(fake_firecrawl):
    r = cc.check_firm("Northgate Wealth Ltd")
    assert r["registered"] is True and r["warning"] is False


# ---------------------------------------------------------------- ratings
def test_scam_claim_is_red_without_an_evidence_search(fake_firecrawl):
    r = cc.check_claim("This stock is guaranteed to 10x. DM me before it's too late!")
    assert r["rating"] == "red" and r["label"] == "Likely Scam"
    assert all(domains == ("fca.org.uk",) for _, domains, _ in fake_firecrawl)  # no official-guidance search


def test_fca_warning_makes_a_claim_red(fake_firecrawl):
    r = cc.check_claim("Quantum Partners Ltd can grow your pension")
    assert r["rating"] == "red"
    assert any("quantum-partners-ltd-clone" in s["url"] for s in r["sources"])


def test_matching_figures_are_green_and_quoted_from_official_hosts_only(fake_firecrawl):
    r = cc.check_claim("The Lifetime ISA adds a 25% bonus on up to £4,000 a year.")
    assert r["rating"] == "green" and r["researcher"] == "firecrawl"
    assert [e["url"] for e in r["evidence"]] == ["https://www.gov.uk/lifetime-isa"]  # council PDF filtered out
    assert all("example-council" not in s["url"] for s in r["sources"])


def test_absolute_wording_downgrades_to_amber(fake_firecrawl):
    r = cc.check_claim("Everyone always gets a 25% bonus on £4,000")
    assert r["rating"] == "amber" and r["label"] == "Partly Supported"


def test_wrong_figure_is_flagged(fake_firecrawl):
    r = cc.check_claim("The Lifetime ISA adds a 50% bonus on £4,000")
    assert r["rating"] == "amber" and "50%" in r["figures"]["missing"]


def test_falls_back_to_saved_pages_without_firecrawl(monkeypatch):
    monkeypatch.setattr(cc, "firecrawl_search", lambda *a, **k: None)
    r = cc.check_claim("The Lifetime ISA adds a 25% bonus on up to £4,000 a year.")
    assert r["researcher"] == "saved" and r["rating"] == "green"
    assert any("gov.uk/lifetime-isa" in e["url"] for e in r["evidence"])
