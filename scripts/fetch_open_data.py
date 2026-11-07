"""Download every open dataset from HEIRLOOM_BRIEF.md that needs no API key or sign-up.

Usage:  python scripts/fetch_open_data.py            # everything
        python scripts/fetch_open_data.py ons kb     # only some groups

Groups: ons, boe, hpi, markets, kb
Output: data/raw/... (source files), data/clean/... (tidy CSVs), data/kb/... (rules knowledge base),
        data/MANIFEST.json (what was fetched, from where, when).

Needs: requests, pandas, openpyxl, beautifulsoup4, yfinance (markets only).
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent / "data"
RAW, CLEAN, KB = ROOT / "raw", ROOT / "clean", ROOT / "kb"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36 heirloom-hackathon-data-fetch")
S = requests.Session()
S.headers["User-Agent"] = UA
ONS = "https://www.ons.gov.uk"
MANIFEST: list[dict] = []


def log(name, url, path, note=""):
    MANIFEST.append({"name": name, "url": url, "path": str(Path(path).relative_to(ROOT)),
                     "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "note": note})
    print(f"  ok  {name} -> {Path(path).relative_to(ROOT)}")


def get(url, **kw):
    if "ons.gov.uk" in url:
        time.sleep(2.5)  # ONS rate-limits hard (HTTP 429); stay polite
    for attempt in range(5):
        try:
            r = S.get(url, timeout=120, **kw)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 0) or 0) or 30 * (attempt + 1)
                print(f"  429 from {url.split('/')[2]}, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.HTTPError:
            raise  # 4xx/5xx other than 429: don't hammer
        except requests.RequestException as e:
            if attempt == 4:
                raise
            print(f"  retry {url}: {e}")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"gave up after repeated 429s: {url}")


def save(url, path: Path, name, note=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(get(url).content)
    log(name, url, path, note)
    return path


# ---------------------------------------------------------------- ONS
ONS_DATASETS = {
    # name: (landing page uri, note)
    "ashe_table6_age": ("/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/agegroupashetable6",
                        "ASHE earnings by age group -> income growth assumptions"),
    "ashe_table3_region_occupation": ("/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/regionbyoccupation2digitsocashetable3",
                                      "ASHE earnings by region x occupation (courier/apprentice personas)"),
    "national_life_tables_uk": ("/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/nationallifetablesunitedkingdomreferencetables",
                                "Life expectancy by age/sex -> retirement planning horizon"),
    "was_total_wealth": ("/peoplepopulationandcommunity/personalandhouseholdfinances/incomeandwealth/datasets/totalwealthwealthingreatbritain",
                         "Wealth and Assets Survey; lost accredited status in 2025, present as indicative"),
    "was_financial_wealth": ("/peoplepopulationandcommunity/personalandhouseholdfinances/incomeandwealth/datasets/financialwealthwealthingreatbritain", "WAS indicative"),
    "was_property_wealth": ("/peoplepopulationandcommunity/personalandhouseholdfinances/incomeandwealth/datasets/propertywealthwealthingreatbritain", "WAS indicative"),
    "was_pension_wealth": ("/peoplepopulationandcommunity/personalandhouseholdfinances/incomeandwealth/datasets/pensionwealthwealthingreatbritain", "WAS indicative"),
    "was_household_debt": ("/peoplepopulationandcommunity/personalandhouseholdfinances/incomeandwealth/datasets/householddebtwealthingreatbritain", "WAS indicative; arrears / problem debt"),
    "was_individual_wealth": ("/peoplepopulationandcommunity/personalandhouseholdfinances/incomeandwealth/datasets/individualwealthwealthingreatbritain", "WAS indicative; wealth by age of individual"),
    "lcf_wb1_detailed_expenditure": ("/peoplepopulationandcommunity/personalandhouseholdfinances/expenditure/datasets/familyspendingworkbook1detailedexpenditureandtrends",
                                     "Living Costs and Food Survey -> calibrate synthetic transactions"),
    "lcf_wb2_by_income": ("/peoplepopulationandcommunity/personalandhouseholdfinances/expenditure/datasets/familyspendingworkbook2expenditurebyincome", "LCF by income decile"),
    "lcf_wb3_by_region": ("/peoplepopulationandcommunity/personalandhouseholdfinances/expenditure/datasets/familyspendingworkbook3expenditurebyregion", "LCF by region"),
    "lcf_wb4_by_household": ("/peoplepopulationandcommunity/personalandhouseholdfinances/expenditure/datasets/familyspendingworkbook4expenditurebyhouseholdcharacteristic",
                             "LCF by household type / age of reference person"),
}

_PRICES = "/economy/inflationandpriceindices/timeseries"
ONS_SERIES = {
    # name: (timeseries uri, note)
    "cpi_annual_rate": (f"{_PRICES}/d7g7/mm23", "CPI 12-month rate, %"),
    "cpi_index": (f"{_PRICES}/d7bt/mm23", "CPI index 2015=100"),
    "cpih_annual_rate": (f"{_PRICES}/l55o/mm23", "CPIH 12-month rate, %"),
    "awe_total_pay_growth": ("/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms",
                             "Average weekly earnings, total pay, 3m avg y/y %"),
    "household_saving_ratio": ("/economy/grossdomesticproductgdp/timeseries/nrjs/ukea", "Households' saving ratio, %"),
}


def ons_latest_file(landing_uri):
    land = get(f"{ONS}{landing_uri}/data").json()
    editions = land.get("datasets") or []
    for ed in editions:  # newest first
        d = get(f"{ONS}{ed['uri']}/data").json()
        files = [f["file"] for f in d.get("downloads", []) if f.get("file")]
        if files:
            # prefer xlsx over xls/zip if several
            files.sort(key=lambda f: (not f.endswith(".xlsx"), not f.endswith(".zip")))
            return f"{ONS}/file?uri={ed['uri']}/{files[0]}", ed["uri"].rsplit("/", 1)[-1], files[0]
    raise RuntimeError(f"no downloads for {landing_uri}")


def fetch_ons():
    print("ONS datasets")
    for name, (uri, note) in ONS_DATASETS.items():
        try:
            url, edition, fname = ons_latest_file(uri)
            ext = Path(fname).suffix or ".xlsx"
            save(url, RAW / "ons" / f"{name}__{edition}{ext}", name, f"{note}; edition {edition}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
    print("ONS time series")
    for name, (uri, note) in ONS_SERIES.items():
        url = f"{ONS}/generator?format=csv&uri={uri}"
        cdid = uri.split("/")[-2]
        try:
            text = get(url).text
            p = RAW / "ons" / f"{name}_{cdid}.csv"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            log(name, url, p, note)
            # tidy: keep monthly rows ("2024 JAN") or quarterly/annual if no monthly
            rows = [l.split(",", 1) for l in text.splitlines()]
            rows = [(a.strip('"'), b.strip('"')) for a, b in (r for r in rows if len(r) == 2)
                    if re.fullmatch(r"\d{4}( [A-Z]{3}| Q[1-4])?", a.strip('"'))]
            df = pd.DataFrame(rows, columns=["period", "value"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            monthly = df[df.period.str.contains(r" [A-Z]{3}$")]
            quarterly = df[df.period.str.contains(r" Q\d$")]
            out = monthly if len(monthly) else quarterly if len(quarterly) else df
            if out is monthly and len(out):
                out = out.assign(date=pd.to_datetime(out.period, format="%Y %b")).loc[:, ["date", "value"]]
            out.to_csv(CLEAN / f"{name}.csv", index=False)
        except Exception as e:
            print(f"  FAIL {name}: {e}")


# ---------------------------------------------------------------- Bank of England
def fetch_boe():
    print("Bank of England Bank Rate")
    url = "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp"
    html = get(url).text
    p = RAW / "boe" / "bank_rate_history.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html)
    cells = re.findall(r'<td[^>]*>\s*([^<]*?)\s*</td>', html)
    pairs = [(cells[i], cells[i + 1]) for i in range(0, len(cells) - 1)
             if re.fullmatch(r"\d{2} [A-Z][a-z]{2} \d{2}", cells[i]) and re.fullmatch(r"-?\d+(\.\d+)?", cells[i + 1])]
    df = pd.DataFrame(pairs, columns=["date", "bank_rate"])
    df["date"] = pd.to_datetime(df.date, format="%d %b %y")
    df.loc[df.date.dt.year > datetime.now().year, "date"] -= pd.DateOffset(years=100)
    df["bank_rate"] = df.bank_rate.astype(float)
    df = df.sort_values("date").drop_duplicates()
    df.to_csv(CLEAN / "boe_bank_rate_changes.csv", index=False)
    log("boe_bank_rate", url, CLEAN / "boe_bank_rate_changes.csv", f"{len(df)} rate changes since {df.date.min().date()}")


# ---------------------------------------------------------------- HM Land Registry UK HPI
HPI_REGIONS = ["United Kingdom", "England", "Wales", "Scotland", "Northern Ireland", "London", "South East",
               "South West", "East of England", "East Midlands", "West Midlands Region", "Yorkshire and The Humber",
               "North West", "North East", "Inner London", "Outer London"]


def fetch_hpi():
    print("HM Land Registry UK HPI")
    now = datetime.now()
    for back in range(0, 8):
        y, m = now.year, now.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        url = f"https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-{y}-{m:02d}.csv"
        if S.head(url, timeout=30).status_code == 200:
            break
    else:
        print("  FAIL no HPI file found")
        return
    p = save(url, RAW / "hpi" / Path(url).name, "uk_hpi_full", "OGL; ~35MB, all local authorities")
    df = pd.read_csv(p, low_memory=False)
    keep = [c for c in ["Date", "RegionName", "AreaCode", "AveragePrice", "Index", "1m%Change", "12m%Change",
                        "FTBPrice", "FTBIndex", "FOOPrice", "DetachedPrice", "SemiDetachedPrice",
                        "TerracedPrice", "FlatPrice", "SalesVolume"] if c in df.columns]
    reg = df[df.RegionName.isin(HPI_REGIONS)][keep].copy()
    reg["Date"] = pd.to_datetime(reg.Date, dayfirst=True)
    reg.sort_values(["RegionName", "Date"]).to_csv(CLEAN / "hpi_regions_monthly.csv", index=False)
    latest = reg[reg.Date == reg.Date.max()].copy()
    latest["deposit_10pct_ftb"] = (latest.get("FTBPrice", latest.AveragePrice) * 0.10).round(-2)
    latest["deposit_5pct_ftb"] = (latest.get("FTBPrice", latest.AveragePrice) * 0.05).round(-2)
    latest.to_csv(CLEAN / "hpi_latest_deposit_targets.csv", index=False)
    log("hpi_regions", url, CLEAN / "hpi_regions_monthly.csv", f"regional subset; latest {reg.Date.max().date()}")


# ---------------------------------------------------------------- markets
TICKERS = {"^FTAS": "FTSE All-Share", "^FTSE": "FTSE 100", "VWRL.L": "Vanguard FTSE All-World (GBP)",
           "URTH": "iShares MSCI World (USD)", "GBPUSD=X": "GBP/USD"}


def fetch_markets():
    print("Market returns (yfinance, no key) + JST Macrohistory (UK 1870+)")
    try:
        import yfinance as yf
        for t, desc in TICKERS.items():
            for interval in ("1d", "1mo"):
                d = yf.download(t, period="max", interval=interval, progress=False, auto_adjust=False)
                if d.empty:
                    print(f"  FAIL {t} {interval}: empty")
                    continue
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                p = CLEAN / "markets" / f"{t.replace('^', '').replace('=', '')}_{interval}.csv"
                p.parent.mkdir(parents=True, exist_ok=True)
                d.to_csv(p)
                log(f"yf_{t}_{interval}", f"yfinance:{t}", p, f"{desc}; {d.index.min().date()}..{d.index.max().date()}")
    except ImportError:
        print("  SKIP yfinance not installed (pip install yfinance)")
    url = "https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.xlsx"  # actually serves Stata .dta
    try:
        p = save(url, RAW / "markets" / "JSTdatasetR6.dta", "jst_macrohistory",
                 "Jorda-Schularick-Taylor; CC BY-NC-SA; long-run equity/bond/housing returns, 18 countries")
        jst = pd.read_stata(p)
        cols = [c for c in ["year", "country", "iso", "eq_tr", "bond_tr", "bill_rate", "housing_tr", "cpi",
                            "eq_capgain", "eq_dp", "hpnom", "ltrate", "stir"] if c in jst.columns]
        jst[jst.iso == "GBR"][cols].to_csv(CLEAN / "markets" / "jst_uk_annual_returns.csv", index=False)
    except Exception as e:
        print(f"  FAIL jst: {e}")


# ---------------------------------------------------------------- knowledge base (replaces Firecrawl)
GOVUK_PAGES = [
    "lifetime-isa", "junior-individual-savings-accounts", "individual-savings-accounts",
    "inheritance-tax", "inheritance-tax/gifts", "inheritance-tax/passing-on-home", "inheritance-tax/rates",
    "inheritance-tax/thresholds", "child-trust-funds", "apply-for-tax-free-childcare",
    "get-help-savings-low-income", "apply-tax-free-interest-on-savings",
    "new-state-pension", "pension-credit", "plan-retirement-income", "workplace-pensions",
    "tax-on-your-private-pension", "budgeting-help-benefits",
    "universal-credit", "report-suspicious-emails-websites-phishing", "options-for-paying-off-your-debts",
    "power-of-attorney", "find-pension-contact-details", "check-state-pension",
    "first-homes-scheme", "affordable-home-ownership-schemes", "income-tax-rates",
]
FCA_PAGES = [
    "https://www.fca.org.uk/scamsmart",
    "https://www.fca.org.uk/scamsmart/how-avoid-investment-scams",
    "https://www.fca.org.uk/consumers/protect-yourself-scams",
    "https://www.fca.org.uk/consumers/avoid-scams-unauthorised-firms",
    "https://www.fca.org.uk/consumers/pension-scams",
    "https://www.fca.org.uk/consumers/cryptoassets",
    "https://www.fca.org.uk/consumers/loan-fee-fraud",
    "https://www.fca.org.uk/consumers/recovery-room-scams",
    "https://www.fca.org.uk/firms/financial-services-register",
]
EXTRA_PAGES = [  # charities / free guidance; some block bots, failures are expected and logged
    "https://www.moneyhelper.org.uk/en/money-troubles/scams/how-to-spot-a-scam",
    "https://www.moneyhelper.org.uk/en/savings/types-of-savings/lifetime-isas",
    "https://www.moneyhelper.org.uk/en/pensions-and-retirement/pension-wise",
    "https://www.stepchange.org/debt-info/debt-advice.aspx",
    "https://www.actionfraud.police.uk/a-z-of-fraud/investment-fraud",
    "https://www.citizensadvice.org.uk/consumer/scams/check-if-something-might-be-a-scam/",
]


def html_to_text(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "noscript", "svg", "form"]):
        t.decompose()
    main = soup.find("main") or soup.body or soup
    lines = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        if el.name != "li" and el.find_parent("li"):
            continue  # gov.uk wraps <p> inside <li>; the <li> already carries the text
        txt = " ".join(el.get_text(" ", strip=True).split())
        if not txt:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            lines.append("\n" + "#" * int(el.name[1]) + " " + txt)
        elif el.name == "li":
            lines.append("- " + txt)
        else:
            lines.append(txt)
    out, seen = [], set()
    for l in lines:  # drop exact dupes (nested li/p)
        if l not in seen:
            out.append(l)
            seen.add(l)
    return "\n".join(out).strip()


def write_kb(slug, title, url, body, publisher):
    p = KB / publisher / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = {"title": title, "url": url, "publisher": publisher,
          "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p.write_text("---\n" + "\n".join(f"{k}: {json.dumps(v)}" for k, v in fm.items()) + "\n---\n\n" + body + "\n")
    log(f"kb_{publisher}_{slug}", url, p)


def fetch_kb():
    print("Knowledge base: gov.uk Content API (no key)")
    for path in GOVUK_PAGES:
        api = f"https://www.gov.uk/api/content/{path}"
        try:
            d = get(api).json()
            det = d.get("details", {})
            parts = []
            if det.get("body"):
                parts.append(html_to_text(det["body"]) if isinstance(det["body"], str) else "")
            for part in det.get("parts", []):
                parts.append(f"\n## {part.get('title', '')}\n" + html_to_text(part.get("body", "")))
            if not parts and det.get("introductory_paragraph"):
                parts.append(html_to_text(det["introductory_paragraph"]))
            body = "\n".join(p for p in parts if p).strip()
            if not body:  # some formats (e.g. transactions) only have intro/more_information
                body = "\n".join(html_to_text(v) for k, v in det.items() if isinstance(v, str) and "<" in v)
            write_kb(path.replace("/", "__"), d.get("title", path), f"https://www.gov.uk/{path}", body, "govuk")
        except Exception as e:
            print(f"  FAIL govuk {path}: {e}")
        time.sleep(0.3)
    print("Knowledge base: FCA + charity pages (plain HTTP)")
    for url in FCA_PAGES + EXTRA_PAGES:
        publisher = re.sub(r"^www\.|\..*$", "", url.split("/")[2])
        slug = re.sub(r"[^a-z0-9]+", "-", url.split("/", 3)[-1].lower()).strip("-")[:80] or "index"
        try:
            r = S.get(url, timeout=60, headers={"Accept": "text/html", "Accept-Language": "en-GB"})
            if r.status_code != 200:
                print(f"  FAIL {url}: HTTP {r.status_code} (bot-blocked; open in a browser and save if needed)")
                continue
            title = re.search(r"<title>(.*?)</title>", r.text, re.S)
            body = html_to_text(r.text)
            if len(body) < 200:
                print(f"  FAIL {url}: page rendered by JS, too little text")
                continue
            write_kb(slug, " ".join(title.group(1).split()) if title else slug, url, body, publisher)
        except Exception as e:
            print(f"  FAIL {url}: {e}")
        time.sleep(0.5)


GROUPS = {"ons": fetch_ons, "boe": fetch_boe, "hpi": fetch_hpi, "markets": fetch_markets, "kb": fetch_kb}

if __name__ == "__main__":
    want = sys.argv[1:] or list(GROUPS)
    for d in (RAW, CLEAN, KB):
        d.mkdir(parents=True, exist_ok=True)
    for g in want:
        GROUPS[g]()
    mf = ROOT / "MANIFEST.json"
    old = json.loads(mf.read_text()) if mf.exists() else []
    names = {m["name"] for m in MANIFEST}
    mf.write_text(json.dumps([m for m in old if m["name"] not in names] + MANIFEST, indent=2))
    print(f"\n{len(MANIFEST)} items fetched; manifest at {mf}")
