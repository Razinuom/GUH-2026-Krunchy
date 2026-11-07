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
    risk_band: Literal["low", "watch", "high"]
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


class TimeMachineRequest(BaseModel):
    family_id: str = Field(..., examples=["nowak"])
    gift: float = Field(..., ge=0, examples=[8000])
    timing: Literal["now", "10y", "inheritance"] = "now"
    monthly_saving: float = Field(0, ge=0, examples=[250])
    region: str | None = Field(None, description="HM Land Registry UK HPI region; defaults to the family's")
    deposit_pct: Literal[5, 10] | None = None
    lisa: bool = Field(True, description="Save into a Lifetime ISA (25% government bonus)")


class FamilyMember(BaseModel):
    id: str
    name: str
    first_name: str
    age: int


class YearBand(BaseModel):
    p10: float
    p25: float | None = None
    p50: float
    p75: float | None = None
    p90: float


class DepositTarget(BaseModel):
    region: str
    pct: int
    amount: float
    ftb_price: float
    as_of: str


class Probabilities(BaseModel):
    p_deposit_by_target: float
    p_parent_floor_safe: float


class TimeMachineResponse(BaseModel):
    family_id: str
    grandparent: FamilyMember
    young_adult: FamilyMember
    gift: float
    timing: Literal["now", "10y", "inheritance"]
    monthly_saving: float
    lisa: bool
    years: list[int]
    genz_band: list[YearBand]
    giver_band: list[YearBand]
    deposit_goal: list[float]
    target_year: int
    p_deposit_by_target: float
    p_deposit_within_horizon: float
    p_parent_floor_safe: float
    baseline: Probabilities | None
    deposit_target: DepositTarget
    safety_floor: float
    inheritance_expected_years: int
    starting_savings: dict[str, float]
    assumptions: dict[str, Any]
    sources: list[Source]


class FamilyMemberInfo(BaseModel):
    id: str
    name: str
    first_name: str
    family: str
    age: int
    role: str
    generation: Literal[1, 2, 3]
    languages: list[str]


class TimeMachineControls(BaseModel):
    gift: float
    timing: Literal["now", "10y", "inheritance"]
    monthly_saving: float
    lisa: bool
    gift_max: float
    monthly_max: float


class FamilyTimeMachine(BaseModel):
    grandparent: str
    young_adult: str
    region: str
    deposit_pct: int
    target_year: int
    inheritance_expected_years: int
    controls: TimeMachineControls


class FamilyInfo(BaseModel):
    id: str
    name: str
    members: list[FamilyMemberInfo]
    time_machine: FamilyTimeMachine
