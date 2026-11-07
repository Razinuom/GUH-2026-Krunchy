"""Heirloom backend. Run from the repo root:  uvicorn backend.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.heirloom import service, synth
from backend.heirloom.personas import personas
from backend.heirloom.schemas import ForecastRequest, ForecastResponse, MemberSummary
from backend.voice.router import router as voice_router


@asynccontextmanager
async def lifespan(_app):
    service.tx_for(synth.default_as_of())  # generate / load the transaction feed once at startup
    yield


app = FastAPI(title="Heirloom API", version="0.2.0", lifespan=lifespan,
              description="Guidance, not regulated financial advice.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(voice_router)


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
