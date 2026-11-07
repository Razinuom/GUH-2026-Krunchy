"""Request/response models for /forecast. Field names follow the contract in HEIRLOOM_BRIEF.md section 5;
anything beyond the contract is additive so the frontend can ignore it."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    member_id: str = Field(..., examples=["tomasz"])
    horizon_days: int = Field(90, ge=7, le=180)
    seed: int = 7


class Day(BaseModel):
    d: int
    date: str
    p10: int
    p50: int
    p90: int


class LowestPoint(BaseModel):
    day: int
    date: str
    p10: int
    p50: int
    p90: int


class Reason(BaseModel):
    feature: str
    impact: float = Field(..., description="Share of the overdraft probability this driver accounts for")
    detail: str = ""
    kind: Literal["scheduled", "debt", "volatility", "spending", "seasonal"]


class Upcoming(BaseModel):
    date: str
    merchant: str
    amount: float
    category: str


class Member(BaseModel):
    name: str
    family: str
    age: int
    role: str


class Source(BaseModel):
    title: str
    url: str


class ForecastResponse(BaseModel):
    member_id: str
    member: Member | None
    start_date: str
    start_balance: float
    days: list[Day]
    overdraft_probability: float
    overdraft_probability_by_horizon: dict[str, float]
    risk_band: Literal["ok", "watch", "high"]
    lowest_point: LowestPoint
    reasons: list[Reason]
    upcoming: list[Upcoming]
    assumptions: dict[str, Any]
    sources: list[Source]


class MemberSummary(BaseModel):
    id: str
    name: str
    family: str
    age: int
    role: str
