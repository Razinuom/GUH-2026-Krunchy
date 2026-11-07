# Heirloom — Hackathon Build Brief

**Track:** NatWest — AI for financial fairness and social mobility
**Time box:** 6 hours · **Team:** 3 people + 3 Claude agents
**One-liner:** An AI money coach that forecasts a family's finances across three generations and explains them by voice, in the languages the family actually speaks.

---

## 1. The problem

Wealthy families get a financial adviser, a plan and regular money conversations. Most families get none of these. Knowledge about pensions, gifting, ISAs and scams rarely gets passed between generations, so younger people learn from social media and older people are targeted by scams. That gap holds social mobility back.

## 2. What we're building

A web app with one family dashboard and three generations (grandparent, parent, young adult). Five features:

| # | Feature | What the judge sees | Brief criterion |
|---|---|---|---|
| 1 | **90-day cash-flow forecast** | Balance forecast with uncertainty band, the lowest point, and the probability of going overdrawn | Predictive insights, "financial time travel" |
| 2 | **Hardship early warning** | Risk score plus the reasons behind it (SHAP) | Anticipate hardship, transparency |
| 3 | **Family Time Machine** | 25-year Monte Carlo fan chart. "Gift now vs in 10 years vs as inheritance": chance the young adult reaches a deposit, and chance the grandparent's savings stay above a safety floor | Personalised planning, long-term resilience |
| 4 | **Voice coach** (ElevenLabs) | Grandparent asks a question in Polish; the agent calls our forecast API and answers in Polish while the dashboard updates in English | Accessibility, inclusion, trusted coach |
| 5 | **Claim Check** (Firecrawl) | Paste a social-media money claim; it gets a rating with sources from gov.uk, MoneyHelper and the FCA register | Ethical, transparent, protects vulnerable users |

**Guardrails across the app:** guidance, not regulated advice · every figure has a source or a visible assumption · a "Talk to a person" handoff (MoneyHelper, StepChange) · voice features are opt-in.

**Social-mobility proof:** demo persona #2 (the Okafor family) has nothing to inherit. The app still helps them: small regular saving, Lifetime ISA bonus, avoiding debt traps.

---

## 3. Data

| Dataset | Use | Notes |
|---|---|---|
| NatWest Bank of APIs sandbox (Account & Transaction API) | Transaction feed | Register at bankofapis.com in hour 1. Fallback: synthetic data |
| Synthetic family transactions | Model training + demo | Agent A generates them, calibrated to ONS Living Costs and Food Survey |
| ONS Wealth and Assets Survey | Wealth-by-age benchmark, problem slide | Lost official accreditation in 2025, so present it as indicative |
| ONS ASHE (earnings by age) | Income growth assumptions | |
| ONS National Life Tables | Planning horizon for retirement | |
| HM Land Registry UK HPI | Regional deposit targets | |
| ONS CPI + Bank of England Bank Rate | Inflation / rate scenarios | |
| yfinance (FTSE All-Share / global index) | Historical returns for block bootstrap | Cache to CSV at start |
| FCA Financial Services Register API | Scam checks (is this firm authorised?) | Free, needs a key: register in hour 1 |
| gov.uk + MoneyHelper pages via Firecrawl | Rules knowledge base for RAG | Snapshot to disk in case of rate limits |

---

## 4. Architecture

```
 React/Next or Streamlit UI  ──►  FastAPI backend
        │                           ├── /forecast         (cash-flow model + risk)
        │                           ├── /timemachine      (Monte Carlo + gifting scenarios)
        │                           ├── /claimcheck       (Firecrawl + FCA + LLM rater)
        │                           ├── /ask              (RAG over scraped rules, cites sources)
        │                           └── /escalate         (logs handoff, returns help resources)
        │
 ElevenLabs Agent (voice) ── webhook tools ──► /timemachine, /forecast, /ask
        └── built-in language detection · guardrails · human transfer
```

**Agent roles in the backend (for the "advanced" story):**
- **Researcher:** Firecrawl + RAG, always returns sources
- **Forecaster:** runs the models
- **Guardian:** compliance filter (no stock tips), scam signals, distress detection → escalation
- **Coach:** the ElevenLabs voice layer

---

## 5. API contracts (agree these in the first 30 minutes so everyone can build in parallel)

```jsonc
// POST /forecast
{ "member_id": "halina" }
→ { "days": [ {"d":0,"p10":1200,"p50":1450,"p90":1700}, ... ],
    "overdraft_probability": 0.18,
    "lowest_point": {"day": 27, "p50": 140},
    "reasons": [ {"feature":"Rent increase","impact":0.07}, ... ] }

// POST /timemachine
{ "family_id":"nowak", "gift": 8000, "timing": "now|10y|inheritance", "monthly_saving": 250 }
→ { "years":[2026,...], "genz_band":[{"p10":..,"p50":..,"p90":..}],
    "p_deposit_by_target": 0.71, "p_parent_floor_safe": 0.93, "assumptions": {...} }

// POST /claimcheck
{ "claim": "This stock is guaranteed to 10x" }
→ { "rating": "red|amber|green", "summary": "...", "signals": ["guaranteed returns"],
    "sources": [ {"title":"...","url":"..."} ] }

// POST /ask
{ "question": "...", "lang": "pl" } → { "answer": "...", "sources": [...] }
```

---

## 6. Team and agent split

| Owner | Area | Their Claude agent |
|---|---|---|
| **Person 1 (ML lead)** | Cash-flow forecaster, hardship model + SHAP, Monte Carlo + gifting optimiser | **Agent A:** generate synthetic personas and transactions, scaffold models, write unit tests for the maths |
| **Person 2 (Backend)** | FastAPI, Firecrawl ingestion, RAG, FCA API, NatWest sandbox, escalation | **Agent B:** Firecrawl scrapers + chunking + vector store, `/claimcheck` and `/ask` endpoints |
| **Person 3 (Frontend + voice + pitch)** | UI, ElevenLabs agent config + webhook tools, demo script, slides | **Agent C:** build UI components against the mocked API contracts; adapt the prototype page |

### Starter prompts for the agents

**Agent A**
> Generate synthetic 12-month daily transactions for 6 people in 2 UK families (Nowak: Halina 71 retired, Tomasz 46, Zofia 22; Okafor: Grace 68, Daniel 44 courier with variable income, Ada 19 apprentice). Calibrate spending to ONS LCF categories. Output CSV with date, member_id, amount, category, merchant. Then build a LightGBM 90-day balance forecaster with quantile outputs (p10/p50/p90) and a classifier for P(overdraft in 30/60/90 days) with SHAP values. Write pytest tests.

**Agent B**
> Build a FastAPI service. Use Firecrawl to scrape and snapshot these pages to /data/kb: gov.uk Lifetime ISA, Junior ISA, Individual Savings Accounts, Inheritance Tax, gifts and inheritance tax; MoneyHelper pages on pensions, gifting and scams; the FCA ScamSmart page. Chunk, embed, and store in a local vector store. Implement /ask (RAG, must return sources, refuse personalised investment recommendations) and /claimcheck (rate a claim red/amber/green with signals and sources; query the FCA Register API for any firm named). Match the JSON contracts in the brief.

**Agent C**
> Build the front end from the Heirloom prototype: family switcher, member cards, forecast chart with bands, Time Machine controls and fan chart, voice coach panel, Claim Check. Call the API contracts in the brief; use mock JSON until the backend is live. Accessible: keyboard navigation, large text toggle, high contrast.

---

## 7. Timeline (6 hours)

| Time | Everyone | Checkpoint |
|---|---|---|
| **0:00–0:30** | Repo, keys (NatWest sandbox, FCA, ElevenLabs, Firecrawl, LLM), agree API contracts, kick off all 3 agents | Mock JSON for every endpoint committed |
| **0:30–2:30** | Core build: models (P1), scrapers + RAG (P2), UI on mocks (P3) | **2:30 integration:** UI hits real `/forecast` and `/timemachine` |
| **2:30–4:00** | ElevenLabs agent + webhook tools (P3), `/claimcheck` + FCA (P2), SHAP + optimiser (P1) | **4:00:** voice question answered end-to-end |
| **4:00–4:30** | Fix the demo path only | **4:30 FEATURE FREEZE** |
| **4:30–5:15** | Polish, record a backup demo video, slides (problem, demo, guardrails, data, impact) | Backup video saved |
| **5:15–6:00** | Rehearse the 3-minute pitch twice, submit | Submitted with 15 min spare |

**Rule:** if something isn't working by its checkpoint, switch to its fallback (section 8) and move on.

---

## 8. Risks and fallbacks

| Risk | Fallback |
|---|---|
| NatWest sandbox access is slow | Synthetic data, with "sandbox-ready" adapter shown on a slide |
| ElevenLabs latency on stage | Pre-generate the key voice answers; play them if live fails |
| Firecrawl rate limits | Use the snapshot in /data/kb |
| Models underfit | Use the simulation-based forecast (as in the prototype) |
| Wi-Fi dies | Backup demo video, local LLM optional |

---

## 9. Demo script (3 minutes)

1. **Problem (20s):** wealth by age chart; most families never talk about money.
2. **Dashboard (40s):** Nowak family. Tomasz's 90-day forecast shows about a 14% chance of going below £0 ("Watch"), with the top reasons. Then click Daniel (Okafor family) to show a high-risk case and the Guardian handoff.
3. **Time Machine (40s):** gift £8,000 now vs as inheritance: Zofia's deposit chance jumps, Halina's safety floor holds.
4. **Voice (40s):** Halina asks in Polish; the agent answers in Polish and the dashboard updates.
5. **Claim Check (20s):** "guaranteed to 10x" → red, with sources.
6. **Close (20s):** switch to the Okafor family (nothing to inherit) to show it still helps; guardrails slide; "Every family deserves a financial plan at the kitchen table."

## 10. Judging Q&A prep

- **"Is this financial advice?"** No. It gives guidance and scenarios. Personalised recommendations go to a regulated human.
- **"Isn't this for rich families?"** Show the Okafor family.
- **"How do you know the model is fair?"** Fairness checks across income bands and regions (fairlearn), plus SHAP explanations for every warning.
- **"What about data privacy?"** Consent per family member, data minimisation, Open Banking consent flow.
- **"What would NatWest do with it?"** It plugs into the Bank of APIs and gives customers a proactive coach, plus early-warning signals for support teams.
