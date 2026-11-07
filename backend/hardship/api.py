"""FastAPI router for hardship early warning. Mount with `app.include_router(router)`."""
from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import service

router = APIRouter(tags=["hardship"])


class HardshipRequest(BaseModel):
    member_id: Optional[str] = Field(None, examples=["tomasz"])
    family_id: Optional[str] = Field(None, examples=["okafor"])
    top_k: int = Field(5, ge=1, le=16)


class Transaction(BaseModel):
    date: str
    amount: float
    category: str
    merchant: Optional[str] = None


class ScoreRequest(BaseModel):
    """Score a raw transaction feed (e.g. NatWest Bank of APIs, mapped to our categories)."""
    transactions: list[Transaction]
    balance: float
    as_of: Optional[str] = None
    top_k: int = Field(5, ge=1, le=16)


@router.post("/hardship")
def hardship(req: HardshipRequest):
    if req.member_id:
        try:
            return service.assess_member(req.member_id, req.top_k)
        except KeyError:
            raise HTTPException(404, f"unknown member_id {req.member_id!r}")
    if req.family_id:
        out = service.assess_family(req.family_id)
        if not out:
            raise HTTPException(404, f"unknown family_id {req.family_id!r}")
        return {"family_id": req.family_id, "members": out}
    raise HTTPException(422, "send member_id or family_id")


@router.post("/hardship/score")
def hardship_score(req: ScoreRequest):
    if not req.transactions:
        raise HTTPException(422, "transactions is empty")
    tx = pd.DataFrame([t.model_dump() for t in req.transactions])
    return service.assess(tx, req.balance, req.as_of, req.top_k)


@router.get("/hardship/model")
def hardship_model():
    """Model card: metrics and fairness checks by income band / income type."""
    return service.model_report()
