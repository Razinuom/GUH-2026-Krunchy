"""Heirloom backend. Run from the repo root:  uvicorn backend.main:app --reload

Every endpoint reads the same six personas and transaction feed (backend.heirloom), so the
forecast, hardship early warning, Time Machine, voice coach and frontend all agree.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.hardship.api import router as hardship_router
from backend.heirloom import claimcheck as claim_checker  # not `claimcheck`: that's the route function below
from backend.heirloom import guidance, service, synth
from backend.heirloom import timemachine as tm
from backend.heirloom.personas import personas
from backend.heirloom.schemas import (FamilyInfo, ForecastRequest, ForecastResponse, MemberSummary,
                                      TimeMachineRequest, TimeMachineResponse)
from backend.voice import router as voice
from backend.voice.router import router as voice_router


@asynccontextmanager
async def lifespan(_app):
    service.tx_for(synth.default_as_of())  # generate / load the transaction feed once at startup
    yield


app = FastAPI(title="Heirloom API", version="0.3.0", lifespan=lifespan,
              description="Guidance, not regulated financial advice.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(hardship_router)
app.include_router(voice_router)


@lru_cache(maxsize=128)
def _timemachine_cached(as_of: date, family_id: str, gift: float, timing: str, monthly_saving: float,
                        region: str | None, deposit_pct: int | None, lisa: bool) -> dict:
    return tm.simulate(family_id, gift, timing, monthly_saving, region=region, deposit_pct=deposit_pct, lisa=lisa)


@app.get("/health")
def health() -> dict:
    as_of = synth.default_as_of()
    return {"status": "ok", "as_of": as_of.isoformat(), "data_through": (as_of - timedelta(days=1)).isoformat()}


@app.get("/members", response_model=list[MemberSummary])
def members() -> list[dict]:
    return [{"id": p.id, "name": p.name, "family": p.family, "age": p.age, "role": p.role}
            for p in personas().values()]


@app.get("/families", response_model=list[FamilyInfo])
def families() -> list[dict]:
    """Everything the frontend needs to draw the family switcher, member cards and Time Machine setup."""
    ps = personas()
    year = synth.default_as_of().year
    out = []
    for fid, cfg in tm.FAMILIES.items():
        mem = sorted((p for p in ps.values() if p.family == fid), key=lambda p: p.generation)
        gp = ps[cfg["grandparent"]]
        out.append({
            "id": fid, "name": cfg["name"],
            "members": [{"id": p.id, "name": p.name, "first_name": p.first_name, "family": p.family, "age": p.age,
                         "role": p.role, "generation": p.generation, "languages": list(p.languages)} for p in mem],
            "time_machine": {"grandparent": cfg["grandparent"], "young_adult": cfg["young_adult"],
                             "region": cfg["region"].removesuffix(" Region"), "deposit_pct": cfg["deposit_pct"],
                             "target_year": year + cfg["target_years"],
                             "inheritance_expected_years": round(tm.life_expectancy(gp.age)),
                             "controls": cfg["controls"]},
        })
    return out


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
    return _timemachine_cached(synth.default_as_of(), family_id, req.gift, req.timing, req.monthly_saving,
                               req.region, req.deposit_pct, req.lisa)


# ------------------------------------------------------------------ guidance: Claim Check, /ask, handoff
class ClaimRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    lang: str = "en"


class EscalateRequest(BaseModel):
    member_id: str
    reason: Literal["debt", "scam", "advice", "distress", "other"] = "other"
    summary: str = ""


@app.post("/claimcheck")
def claimcheck(req: ClaimRequest) -> dict:
    return claim_checker.check_claim(req.claim)


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    return guidance.ask(req.question, req.lang)


@app.post("/escalate")
def escalate(req: EscalateRequest) -> dict:
    """'Talk to a person' from the website: log the handoff and return free, confidential help lines."""
    p = personas().get(req.member_id.strip().lower())
    if not p:
        raise HTTPException(404, f"Unknown member_id '{req.member_id}'")
    contacts = [voice.HELP[k] for k in voice.HELP_BY_REASON[req.reason]]
    record = {"ts": datetime.now(timezone.utc).isoformat(), "member_id": p.id, "family_id": p.family,
              "reason": req.reason, "summary": req.summary, "language": "en", "channel": "web"}
    voice._log("escalations.jsonl", record)
    voice.bus.publish("escalation", p.family, {**record, "member_name": p.name, "contacts": contacts})
    return {"handoff_logged": True, "reason": req.reason, "contacts": contacts}
