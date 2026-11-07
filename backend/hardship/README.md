# Hardship early warning

Risk score that a member's current account goes below £0 in the next 30/60/90 days, the reasons behind it (SHAP), and a Guardian escalation to free help when risk is high.

## Run

```bash
pip install -r requirements.txt
python -m backend.hardship.train      # ~70s; already trained, models are in model/
uvicorn backend.main:app --reload
pytest tests/test_hardship.py
```

## Data: the shared Heirloom personas

`/hardship` scores the same six personas and transaction feed as `/forecast`, `/timemachine` and the voice coach
(`backend/heirloom`), via `adapter.py`, which maps our categories to this model's (e.g. Klarna/Clearpay -> `bnpl`,
phone -> `communication`, savings -> `savings_transfer`, council tax -> `council_tax`). Balances come from the same feed,
so every page shows one consistent family. Set `HEIRLOOM_TX_PATH` and `HEIRLOOM_MEMBERS_PATH` to score a different
feed instead. `python -m backend.hardship.personas` still builds the model's original standalone households, now into
`data/synthetic/hardship_personas/` (reference only, never served).

## API

`POST /hardship` `{"member_id": "tomasz"}` or `{"family_id": "okafor"}`

```jsonc
{
  "member_id": "tomasz", "name": "Tomasz Nowak", "balance": 2461.98, "as_of": "2026-11-06",
  "risk_score": 15,                        // 0-100 = P(overdrawn within 90 days) x 100
  "band": "watch",                         // low <10 | watch 10-30 | high >=30 (same cut-offs as /forecast)
  "overdraft_probability": 0.152,          // drop-in for /forecast's overdraft_probability
  "overdraft_probability_by_horizon": {"30d": 0.02, "60d": 0.069, "90d": 0.152},
  "baseline_probability": 0.178,           // average household; reason impacts add up to the gap
  "reasons": [                             // drop-in for /forecast's reasons (feature + impact)
    {"feature": "Rent or mortgage increase", "key": "housing_increase", "impact": 0.06,
     "direction": "raises risk", "detail": "Rent or mortgage is up £210 a month", "value": 210.0,
     "tip": "...", "source": "https://www.gov.uk/universal-credit"}
  ],
  "guardian": {"escalate": false, "signals": [], "message": "...",
               "resources": [{"id": "moneyhelper", "name": "...", "phone": "0800 138 7777", "url": "..."}]},
  "features": {...}, "model": {...}, "disclaimer": "Guidance, not regulated financial advice..."
}
```

`impact` is in probability points (0.06 = +6 points). Sort/filter on `direction` to split drivers from protective factors.

`POST /hardship/score` `{"balance": 812.5, "transactions": [{"date": "2026-10-01", "amount": -42.1, "category": "groceries"}, ...]}` scores any raw feed (NatWest Bank of APIs adapter: map their transactions to our categories).

`GET /hardship/model` model card: AUC, Brier score, fairness by income band and income type.

From Python (e.g. inside `/forecast`): `from backend.hardship.service import assess_member`.

## Demo personas (shared with the forecast, demo date 2026-11-07)

The forecast and this model agree on every band (enforced by `backend/tests/test_integration.py`).

| Member | Score | Band | 90-day forecast | Story |
|---|---|---|---|---|
| halina | 0 | low | 0% low | Homeowner, two pensions, £62k savings |
| tomasz | 13 | watch | 14% watch | Rent up £230 in September, car repair in October, car insurance due in December |
| zofia | 8 | low | 8% low | Graduate in a flatshare, Klarna, high eating-out spend |
| grace | 6 | low | 0% low | State Pension + Pension Credit, social housing |
| daniel | 34 | high | 88% high | Courier with variable income, van finance and a January tax bill: Guardian escalates |
| ada | 2 | low | 0% low | Apprentice at home, saving monthly |

## How it works

- `simulate.py` simulates daily transactions for a household (salary / gig / pension / benefits income, housing, bills, LCF-calibrated day-to-day spending, BNPL, payday loans, gambling, shocks, overdraft limits, people cutting back when money is tight).
- `train.py` simulates 3,000 random households, takes 9,000 snapshots, labels whether the balance actually went below £0 in the next 30/60/90 days, and trains one LightGBM classifier per horizon. Hold-out is by household.
- Monotone constraints: more balance or savings can never raise risk, and more debt or overdrawn days can never lower it, so explanations always point the sensible way.
- `features.py` has 16 plain-English features; it is used for both training and serving. No age, sex, ethnicity or region.
- Explanations use LightGBM's exact TreeSHAP (`pred_contrib`), converted from log-odds to probability points.

Held-out 90-day metrics: AUC 0.97 overall. AUC 0.90 for people **not overdrawn at all in the last 90 days** (the real early-warning case, 7% base rate). Calibration by income band is within about 4 points (see `model/report.json`).

**Caveat for Q&A:** trained on synthetic data, so the metrics show the pipeline works, not real-world accuracy. The same code retrains on real Open Banking data.
