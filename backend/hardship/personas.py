"""Demo personas from the brief (Nowak and Okafor families).

    python -m backend.hardship.personas      # writes data/synthetic/transactions.csv + members.json

Transactions follow the shared contract: date, member_id, amount, category, merchant.
members.json carries each member's current balance and overdraft limit, which
the transaction feed alone doesn't give you.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .simulate import Profile, simulate

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "synthetic"
AS_OF = date(2026, 11, 6)
HISTORY_DAYS = 365
START = AS_OF - timedelta(days=HISTORY_DAYS - 1)

MEMBERS = {
    "halina": dict(name="Halina Nowak", age=71, family_id="nowak", role="grandparent"),
    "tomasz": dict(name="Tomasz Nowak", age=46, family_id="nowak", role="parent"),
    "zofia": dict(name="Zofia Nowak", age=22, family_id="nowak", role="young adult"),
    "grace": dict(name="Grace Okafor", age=68, family_id="okafor", role="grandparent"),
    "daniel": dict(name="Daniel Okafor", age=44, family_id="okafor", role="parent"),
    "ada": dict(name="Ada Okafor", age=19, family_id="okafor", role="young adult"),
}

# Seeds picked so the demo story lands (see brief section 9); profiles are fixed.
PROFILES: dict[str, tuple[Profile, int]] = {
    # Retired, owns her flat, state + small workplace pension, steady saver.
    "halina": (Profile("halina", income_kind="pension", monthly_income=1480, private_pension=520,
                       housing_cost=0, bills=270, spend_ratio=0.84, savings_monthly=100,
                       opening_balance=4200, overdraft_limit=0, shock_rate=2, shock_mean=250), 1),
    # Salaried; fixed-rate mortgage ended in summer, payment up £210/month; thin buffer.
    "tomasz": (Profile("tomasz", income_kind="salary", monthly_income=2950, pay_day=28,
                       housing_cost=1080, housing_label="Mortgage (Nationwide)", housing_day=2,
                       housing_increase=210, housing_increase_day=HISTORY_DAYS - 110,
                       bills=390, spend_ratio=0.93, opening_balance=2400, overdraft_limit=1000,
                       shock_rate=3, shock_mean=420, bnpl_per_month=0.3), 14),
    # Graduate first job, renting in a shared flat, leans on buy now pay later.
    "zofia": (Profile("zofia", income_kind="salary", monthly_income=1950, pay_day=25,
                      housing_cost=760, housing_label="Rent (Foxtons)", bills=160, spend_ratio=0.95,
                      opening_balance=700, overdraft_limit=500, bnpl_per_month=1.1, bnpl_size=140,
                      shock_rate=2, shock_mean=200), 10),
    # State pension + Pension Credit, housing association rent, careful budgeter.
    "grace": (Profile("grace", income_kind="pension", monthly_income=1160, private_pension=0,
                      housing_cost=430, housing_label="Rent (housing association)", bills=230,
                      spend_ratio=0.9, opening_balance=650, overdraft_limit=0,
                      shock_rate=1.5, shock_mean=200), 12),
    # Self-employed courier: weekly, volatile payouts, fewer shifts since late summer.
    "daniel": (Profile("daniel", income_kind="gig", monthly_income=2250, income_cv=0.4, quiet_month_prob=0.3,
                       housing_cost=950, housing_label="Rent (private landlord)", bills=330, spend_ratio=0.99,
                       opening_balance=300, overdraft_limit=750, payday_loan_prob=0.35,
                       bnpl_per_month=0.8, bnpl_size=150, shock_rate=4, shock_mean=380,
                       income_cut_day=HISTORY_DAYS - 80, income_cut_factor=0.72), 19),
    # Apprentice living at home, pays board, saving into a Lifetime ISA.
    "ada": (Profile("ada", income_kind="apprentice", monthly_income=1180, pay_day=20,
                    housing_cost=200, housing_label="Board to Mum", bills=45, spend_ratio=0.86,
                    savings_monthly=80, opening_balance=380, overdraft_limit=0,
                    shock_rate=1, shock_mean=150), 14),
}


def build(seeds: dict[str, int] | None = None):
    txs, members = [], {}
    for mid, (prof, seed) in PROFILES.items():
        seed = (seeds or {}).get(mid, seed)
        tx, bal = simulate(prof, START, HISTORY_DAYS, seed=seed)
        txs.append(tx)
        members[mid] = {**MEMBERS[mid], "member_id": mid, "balance": round(float(bal.iloc[-1]), 2),
                        "overdraft_limit": prof.overdraft_limit, "as_of": AS_OF.isoformat()}
    tx = pd.concat(txs, ignore_index=True).sort_values(["date", "member_id"]).reset_index(drop=True)
    return tx, members


def write(seeds: dict[str, int] | None = None, out_dir: Path = OUT_DIR):
    tx, members = build(seeds)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = tx.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(out_dir / "transactions.csv", index=False)
    (out_dir / "members.json").write_text(json.dumps(members, indent=2))
    return tx, members


if __name__ == "__main__":
    tx, members = write()
    print(f"wrote {len(tx)} transactions for {len(members)} members to {OUT_DIR}")
