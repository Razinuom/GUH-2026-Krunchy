"""Claim Check (brief feature 5): rate a social-media money claim red / amber / green, with sources.

The Researcher agent, in three steps:
  1. Warning signs: the FCA ScamSmart red flags (rules in guidance.RED_FLAGS).
  2. Firm check: firm names in the claim are searched against the FCA's published warnings
     (fca.org.uk/news/warnings). Only an exact name match counts, never a similar-sounding firm.
  3. Evidence: Firecrawl searches GOV.UK, MoneyHelper and the FCA live; every figure in the claim
     (£ amounts, percentages, years, "10x") is checked against those official pages, and the
     matching sentence is quoted.

Firecrawl results are cached on disk (data/kb/firecrawl/), as the brief asks, so repeat checks are
instant and the demo survives rate limits. Without a key, or if Firecrawl fails, the saved
GOV.UK / FCA / Citizens Advice pages in data/kb are used instead. Guidance, not advice.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import httpx

from backend.voice import config as _config  # loads .env
from backend.voice import kb_search

from .guidance import DISCLAIMER, RED_FLAGS, SRC

FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
OFFICIAL_DOMAINS = ["gov.uk", "moneyhelper.org.uk", "fca.org.uk"]
# "gov.uk" in a search also matches every council and agency subdomain, so evidence is kept to these hosts
OFFICIAL_HOSTS = {"www.gov.uk", "www.moneyhelper.org.uk", "www.fca.org.uk"}
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "kb" / "firecrawl"
CACHE_TTL_SECS = 7 * 24 * 3600
TIMEOUT_SECS = 20

# words that make a claim sound absolute even when its figures are right
ABSOLUTES = r"\b(anything|everything|always|never|all|any|no one|nobody|guaranteed?|definitely|100%)\b"
FIRM_SUFFIX = (r"Ltd|Limited|LLP|PLC|Plc|Capital|Markets|Investments?|Invest|Trading|Traders|FX|Forex|"
               r"Wealth|Finance|Financial|Group|Partners|Asset Management|Crypto|Coin|Exchange|Bank")
FIRM_RE = re.compile(rf"\b((?:[A-Z][\w&'.-]*\s+){{0,3}}(?:{FIRM_SUFFIX}))\b")
STOP_FIRM_WORDS = {"the", "a", "an", "this", "my", "our", "your", "uk", "and", "of"}


# ------------------------------------------------------------------ Firecrawl (cached)
def _api_key() -> str:
    return _config._get("FIRECRAWL_API_KEY")


def firecrawl_search(query: str, domains: list[str], limit: int = 3, scrape: bool = True) -> list[dict] | None:
    """Firecrawl /v2/search restricted to `domains`. Returns [{url,title,description,markdown}] or None on failure."""
    key = _api_key()
    if not key:
        return None
    body = {"query": query[:480], "limit": limit, "includeDomains": domains, "country": "GB", "timeout": TIMEOUT_SECS * 1000}
    if scrape:
        body["scrapeOptions"] = {"formats": [{"type": "markdown"}], "onlyMainContent": True}
    cache = CACHE_DIR / (hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest() + ".json")
    try:
        if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_SECS:
            return json.loads(cache.read_text())["results"]
    except (OSError, ValueError):
        pass
    try:
        r = httpx.post(FIRECRAWL_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_SECS + 5)
        r.raise_for_status()
        web = (r.json().get("data") or {}).get("web") or []
    except (httpx.HTTPError, ValueError):
        try:  # no network / rate-limited: an older saved result is better than nothing
            return json.loads(cache.read_text())["results"] if cache.exists() else None
        except (OSError, ValueError):
            return None
    results = [{"url": w.get("url", ""), "title": (w.get("title") or "").strip(), "description": w.get("description") or "",
                "markdown": w.get("markdown") or ""} for w in web if w.get("url")]
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"query": query, "fetched": time.time(), "results": results}))
    except OSError:
        pass
    return results


# ------------------------------------------------------------------ figures in a claim
def _num(s: str) -> float:
    s = s.replace(",", "").lower().strip()
    mult = 1000 if s.endswith("k") else 1_000_000 if s.endswith("m") else 1
    return float(s.rstrip("km")) * mult


def extract_figures(text: str) -> list[dict]:
    """£ amounts, percentages, years and multiples, normalised so '£4k' matches '£4,000'."""
    figs = []
    for m in re.finditer(r"£\s?(\d[\d,]*(?:\.\d+)?\s?[km]?)\b", text, re.I):
        figs.append({"text": m.group(0).replace(" ", ""), "kind": "gbp", "value": _num(m.group(1))})
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s?%", text):
        figs.append({"text": m.group(0).replace(" ", ""), "kind": "pct", "value": float(m.group(1))})
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10}
    for m in re.finditer(r"\b(\d+|one|two|three|four|five|six|seven|ten)\s+years?\b", text, re.I):
        v = m.group(1).lower()
        figs.append({"text": m.group(0), "kind": "years", "value": float(words.get(v, v))})
    seen, out = set(), []
    for f in figs:
        k = (f["kind"], f["value"])
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def _figure_patterns(f: dict) -> list[str]:
    v = f["value"]
    iv = int(v) if v == int(v) else v
    if f["kind"] == "gbp":
        forms = {f"£{iv:,}", f"£{iv}"} if isinstance(iv, int) else {f"£{v:,.2f}", f"£{v}"}
        if isinstance(iv, int) and iv >= 1000 and iv % 1000 == 0:
            forms.add(f"£{iv // 1000}k")
        return [re.escape(x) + r"(?![\d,])" for x in forms]
    if f["kind"] == "pct":
        return [rf"(?<![\d.]){re.escape(str(iv))}\s?(%|per ?cent)"]
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 10: "ten"}
    alts = [str(iv)] + ([words[iv]] if iv in words else [])
    return [rf"\b({'|'.join(alts)})\s+(full\s+)?years?\b"]


def _sentences(md: str) -> list[str]:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)", r"\1", md)  # drop images, keep link text
    text = re.sub(r"[#>*_`|]+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if 30 <= len(s.strip()) <= 400]


def find_evidence(figures: list[dict], claim: str, pages: list[dict]) -> tuple[list[dict], set[str]]:
    """For each official page, the sentence that best supports the claim, and which figures it contains."""
    claim_words = {w for w in re.findall(r"[a-z]{4,}", claim.lower())}
    evidence, found = [], set()
    for p in pages:
        md = p.get("markdown") or p.get("text") or ""
        if not md:
            continue
        best, best_score, best_figs = None, 0.0, set()
        for s in _sentences(md):
            figs_here = {f["text"] for f in figures if any(re.search(pt, s, re.I) for pt in _figure_patterns(f))}
            overlap = len(claim_words & set(re.findall(r"[a-z]{4,}", s.lower())))
            score = 3 * len(figs_here) + overlap
            if score > best_score:
                best, best_score, best_figs = s, score, figs_here
        page_figs = {f["text"] for f in figures if any(re.search(pt, md, re.I) for pt in _figure_patterns(f))}
        found |= page_figs
        # a quote must contain a figure from the claim, or share at least 3 words with it
        if best and (best_figs or best_score >= 3):
            evidence.append({"title": p["title"], "url": p["url"], "quote": best, "figures": sorted(page_figs | best_figs)})
    return evidence, found


# ------------------------------------------------------------------ firm check
def extract_firms(text: str) -> list[str]:
    names = []
    for m in FIRM_RE.finditer(text):
        name = m.group(1).strip(" .,'")
        words = [w for w in re.findall(r"[A-Za-z0-9&]+", name) if w.lower() not in STOP_FIRM_WORDS]
        if len(words) >= 2 and name not in names:  # "Capital" alone is not a firm name
            names.append(name)
    return names[:2]


def _slug_tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP_FIRM_WORDS and w not in {"ltd", "limited", "clone"}}


def check_firm(name: str) -> dict:
    """Exact-name match against FCA published warnings (and the FCA Register). Never matches a merely similar
    firm: the warning page's address must name exactly this firm, e.g. /news/warnings/quantum-partners-ltd-clone."""
    wanted = _slug_tokens(name)
    results = firecrawl_search(f"{name} FCA warning", ["fca.org.uk"], limit=5, scrape=False)
    if results is None:
        return {"name": name, "checked": False, "warning": False, "registered": False, "url": SRC["register"]["url"]}
    for r in results:
        if "/news/warnings/" not in r["url"]:
            continue
        slug_tokens = _slug_tokens(r["url"].rstrip("/").rsplit("/", 1)[-1].replace("-", " "))
        if wanted and slug_tokens == wanted:
            title = re.sub(r"\s*[-|]\s*FCA\s*$", "", r["title"]).strip() or name
            return {"name": name, "checked": True, "warning": True, "registered": False, "url": r["url"], "title": title}
    for r in results:  # an exact entry on the FCA Register (it could still be a clone, so this is only a note)
        if r["url"].startswith("https://register.fca.org.uk/") and " - FCA Register" in r["title"]:
            if wanted and _slug_tokens(r["title"].split(" - FCA Register")[0]) == wanted:
                return {"name": name, "checked": True, "warning": False, "registered": True, "url": r["url"]}
    return {"name": name, "checked": True, "warning": False, "registered": False, "url": SRC["register"]["url"]}


# ------------------------------------------------------------------ the rating
def _dedupe(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        if s.get("url") and s["url"] not in seen:
            seen.add(s["url"])
            out.append({"title": s.get("title") or s["url"], "url": s["url"]})
    return out


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/", 1)[0].lower()


def _saved_pages(claim: str) -> list[dict]:
    """Fallback evidence: the GOV.UK / FCA / Citizens Advice pages saved in data/kb."""
    return [{"title": h["title"], "url": h["url"], "text": h["text"]} for h in kb_search.search(claim, 4) if h["url"]]


def check_claim(claim: str) -> dict:
    text = claim.strip()
    flags = [(signal, src) for pattern, signal, src in RED_FLAGS if re.search(pattern, text, re.I)]
    signals = [s for s, _ in flags]
    sources = [SRC[src] for _, src in flags]

    firms = [check_firm(n) for n in extract_firms(text)]
    warned = [f for f in firms if f["warning"]]
    for f in warned:
        signals.append(f"The FCA has published a warning about {f['title']}")
        sources.append({"title": f"FCA warning: {f['title']}", "url": f["url"]})
    for f in firms:
        if f["warning"]:
            continue
        if f.get("registered"):
            signals.append(f"“{f['name']}” is listed on the FCA Register. Scammers copy real firms' names, so only "
                           "contact it using the details on the Register")
            sources.append({"title": f"FCA Register: {f['name']}", "url": f["url"]})
        else:
            signals.append(f"No FCA warning found for “{f['name']}”: check it is authorised on the FCA Register before paying")

    # Claims that already show scam warning signs skip the evidence search: the FCA pages above are the sources.
    pages = None if flags else firecrawl_search(text, OFFICIAL_DOMAINS, limit=3)
    pages = [p for p in (pages or []) if _host(p["url"]) in OFFICIAL_HOSTS and not p["url"].lower().split("?")[0].endswith(".pdf")]
    researcher = "firecrawl" if pages or any(f["checked"] for f in firms) else ("rules" if flags else "saved")
    if not pages and not flags:
        pages = _saved_pages(text)
    figures = extract_figures(text)
    evidence, found = find_evidence(figures, text, pages)
    missing = [f["text"] for f in figures if f["text"] not in found]
    absolute = re.search(ABSOLUTES, text, re.I) is not None

    if flags or warned:
        scam = len(flags) + 2 * len(warned) >= 2
        rating, label = "red", ("Likely Scam" if scam else "Warning Signs Found")
        summary = (("This claim has several signs the FCA links to investment scams. No genuine investment can promise "
                    "a fixed multiple of your money. Do not send money, and check any firm on the FCA Register first.")
                   if scam else
                   ("This claim has a warning sign the FCA links to scams. Treat it with care and check any firm named "
                    "on the FCA Register before you act."))
    elif figures and not missing and evidence:
        if absolute:
            rating, label = "amber", "Partly Supported"
            summary = (f"The figures ({', '.join(f['text'] for f in figures)}) match official guidance, but the claim is "
                       "worded as if there are no exceptions. Official guidance has conditions: read the source before acting.")
        else:
            rating, label = "green", "Matches Official Guidance"
            summary = (f"The figures in this claim ({', '.join(f['text'] for f in figures)}) match official guidance. "
                       "Read the source for the conditions that apply to you.")
    elif figures and found:
        rating, label = "amber", "Partly Supported"
        summary = (f"Some figures match official guidance ({', '.join(sorted(found))}), but "
                   f"{', '.join(missing)} {'does' if len(missing) == 1 else 'do'} not. Check the sources before acting.")
    elif figures:
        rating, label = "amber", "Not Found in Official Guidance"
        summary = (f"We could not find {', '.join(missing)} in official guidance on this topic. That does not make the "
                   "claim false, but ask where the figures come from before acting.")
    else:
        rating, label = "amber", "Needs Evidence"
        summary = ("This claim has no figures we can check. Read the official guidance below, and ask where the claim comes "
                   "from before acting.")

    if missing and rating != "red":
        signals.append(f"Not found in official guidance: {', '.join(missing)}")
    if found and rating != "red":
        signals.append(f"Found in official guidance: {', '.join(sorted(found))}")
    if absolute and rating == "amber" and figures and not missing:
        signals.append("Worded as if there are no exceptions")

    return {
        "rating": rating,
        "label": label,
        "summary": summary,
        "signals": signals,
        # official pages that were checked are listed even without a quote, so people can read the real figures
        "sources": _dedupe(sources + [{"title": e["title"], "url": e["url"]} for e in evidence]
                           + [{"title": p["title"], "url": p["url"]} for p in pages[:3]] + [SRC["register"]]),
        "evidence": evidence[:3],
        "figures": {"found": sorted(found), "missing": missing},
        "firms": firms,
        "researcher": researcher,
        "disclaimer": DISCLAIMER,
    }
