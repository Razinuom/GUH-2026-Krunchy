"""Heirloom backend. Run from the repo root:  uvicorn backend.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.hardship.api import router as hardship_router
from backend.heirloom import service, synth
from backend.heirloom import timemachine as tm
from backend.heirloom.personas import personas
from backend.heirloom.schemas import (ForecastRequest, ForecastResponse, MemberSummary,
                                      TimeMachineRequest, TimeMachineResponse)
from backend.voice.router import router as voice_router

@asynccontextmanager
async def lifespan(_app):
    service.tx_for(synth.default_as_of())  # generate / load the transaction feed once at startup
    yield


app = FastAPI(title="Heirloom API", version="0.2.0", lifespan=lifespan,
              description="Guidance, not regulated financial advice.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(hardship_router)
app.include_router(voice_router)


@lru_cache(maxsize=64)
def _timemachine_cached(family_id: str, gift: float, timing: str, monthly_saving: float,
                         region: str, deposit_pct: int) -> dict:
    return tm.simulate(family_id, gift, timing, monthly_saving, region=region, deposit_pct=deposit_pct)


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
    return service.forecast_now(member_id, req.horizon_days, req.seed)


@app.post("/timemachine", response_model=TimeMachineResponse)
def timemachine(req: TimeMachineRequest) -> dict:
    family_id = req.family_id.strip().lower()
    if family_id not in tm.FAMILIES:
        raise HTTPException(404, f"Unknown family_id '{req.family_id}'. Try 'nowak' or 'okafor'.")
    return _timemachine_cached(family_id, req.gift, req.timing, req.monthly_saving, req.region, req.deposit_pct)
