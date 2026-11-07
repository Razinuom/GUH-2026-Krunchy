"""Heirloom backend. Run from the repo root:  uvicorn backend.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.hardship.api import router as hardship_router
from backend.heirloom import forecast as fc
from backend.heirloom import synth
from backend.heirloom.personas import personas
from backend.heirloom.schemas import ForecastRequest, ForecastResponse, MemberSummary

@asynccontextmanager
async def lifespan(_app):
    _tx_for(synth.default_as_of())  # generate / load the transaction feed once at startup
    yield


app = FastAPI(title="Heirloom API", version="0.1.0", lifespan=lifespan,
              description="Guidance, not regulated financial advice.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(hardship_router)


def load_transactions(as_of: date) -> pd.DataFrame:
    """Transaction feed. Today: synthetic CSV. Swap in a NatWest Bank of APIs adapter here
    (same columns: date, member_id, amount, category, merchant, balance)."""
    return synth.ensure(as_of)


@lru_cache(maxsize=1)
def _tx_for(as_of: date) -> pd.DataFrame:
    return load_transactions(as_of)


@lru_cache(maxsize=64)
def _forecast_cached(member_id: str, as_of: date, horizon: int, seed: int) -> dict:
    return fc.forecast(member_id, _tx_for(as_of), as_of, horizon=horizon, seed=seed)


@app.get("/health")
def health() -> dict:
    as_of = synth.default_as_of()
    return {"status": "ok", "as_of": as_of.isoformat(), "data_through": (as_of - timedelta(days=1)).isoformat()}


@app.get("/members", response_model=list[MemberSummary])
def members() -> list[dict]:
    return [{"id": p.id, "name": p.name, "family": p.family, "age": p.age, "role": p.role}
            for p in personas().values()]


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest) -> dict:
    member_id = req.member_id.strip().lower()
    if member_id not in personas():
        raise HTTPException(404, f"Unknown member_id '{req.member_id}'. Try GET /members.")
    return _forecast_cached(member_id, synth.default_as_of(), req.horizon_days, req.seed)
