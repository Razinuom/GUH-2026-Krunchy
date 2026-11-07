"""Feed the hardship model from the shared Heirloom transaction feed (backend.heirloom).

The forecaster, Time Machine, voice coach and this model all read the same personas and
transactions, so every page shows one consistent family. This module only translates our
transaction categories into the hardship model's taxonomy (see features.py).
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

BNPL_MERCHANTS = {"KLARNA", "CLEARPAY"}
GAMBLING_MERCHANTS = {"BET365"}
CATEGORY_MAP = {
    "phone": "communication",       # features.ESSENTIAL uses "communication"
    "savings": "savings_transfer",  # features.NOT_SPEND / savings_rate use "savings_transfer"
    "family": "housing",            # e.g. board paid to a parent
}


def to_hardship_categories(tx: pd.DataFrame) -> pd.DataFrame:
    out = tx.copy()
    cat = out["category"].replace(CATEGORY_MAP)
    merchant = out["merchant"].fillna("").str.upper()
    cat = cat.mask(merchant.isin(BNPL_MERCHANTS), "bnpl")
    cat = cat.mask(merchant.isin(GAMBLING_MERCHANTS), "gambling")
    cat = cat.mask(merchant.str.contains("COUNCIL TAX"), "council_tax")  # keep it out of "housing"
    out["category"] = cat
    return out


def load(as_of: date | None = None) -> tuple[pd.DataFrame, dict]:
    """(transactions in hardship categories, members) for all personas, from the shared feed."""
    from backend.heirloom import service, synth
    from backend.heirloom.personas import personas

    as_of = as_of or synth.default_as_of()
    tx = service.tx_for(as_of)
    data_through = (as_of - timedelta(days=1)).isoformat()
    members = {}
    for p in personas().values():
        mine = tx[tx.member_id == p.id]
        members[p.id] = {
            "member_id": p.id, "name": p.name, "age": p.age, "family_id": p.family,
            "role": {1: "grandparent", 2: "parent", 3: "young adult"}[p.generation],
            "balance": round(float(mine.balance.iloc[-1]), 2) if len(mine) else float(p.current_balance),
            "overdraft_limit": 0, "as_of": data_through,
        }
    return to_hardship_categories(tx[["date", "member_id", "amount", "category", "merchant"]]), members
