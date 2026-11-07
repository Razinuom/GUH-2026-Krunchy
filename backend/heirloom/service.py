"""Shared, cached access to the transaction feed and forecasts (used by /forecast and the voice tools)."""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd

from . import forecast as fc
from . import synth


def load_transactions(as_of: date) -> pd.DataFrame:
    """Transaction feed. Today: synthetic CSV. Swap in a NatWest Bank of APIs adapter here
    (same columns: date, member_id, amount, category, merchant, balance)."""
    return synth.ensure(as_of)


@lru_cache(maxsize=1)
def tx_for(as_of: date) -> pd.DataFrame:
    return load_transactions(as_of)


@lru_cache(maxsize=64)
def forecast_cached(member_id: str, as_of: date, horizon: int = 90, seed: int = 7) -> dict:
    return fc.forecast(member_id, tx_for(as_of), as_of, horizon=horizon, seed=seed)


def forecast_now(member_id: str, horizon: int = 90, seed: int = 7) -> dict:
    return forecast_cached(member_id, synth.default_as_of(), horizon, seed)


def forecast_what_if(member_id: str, extra_changes: list[dict], horizon: int = 90, seed: int = 7) -> dict:
    as_of = synth.default_as_of()
    return fc.forecast(member_id, tx_for(as_of), as_of, horizon=horizon, seed=seed, extra_changes=extra_changes)


def clear_caches() -> None:
    tx_for.cache_clear()
    forecast_cached.cache_clear()
