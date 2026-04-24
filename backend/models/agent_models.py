"""Pydantic models for the scheme action-planning agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EligibilityVerdict = Literal["eligible", "likely_eligible", "likely_ineligible", "unknown"]
PlanStatus = Literal["plan_ready", "need_more_info", "insufficient_data"]


class UserProfile(BaseModel):
    age: int | None = None
    gender: str | None = None
    state: str | None = None
    occupation: str | None = None
    annual_income: int | None = None
    category: str | None = None
    has_land: bool | None = None
    bpl: bool | None = None


class EligibilityCheck(BaseModel):
    scheme: str
    source_id: str
    verdict: EligibilityVerdict
    matched_criteria: list[str] = Field(default_factory=list)
    missing_criteria: list[str] = Field(default_factory=list)
    unknown_criteria: list[str] = Field(default_factory=list)


class ActionStep(BaseModel):
    order: int
    action: str
    where: str | None = None
    estimated_time: str | None = None


class AgentPlan(BaseModel):
    status: PlanStatus
    eligibility: list[EligibilityCheck] = Field(default_factory=list)
    documents_needed: list[str] = Field(default_factory=list)
    steps: list[ActionStep] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    disclaimer: str
