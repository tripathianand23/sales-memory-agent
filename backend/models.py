from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InteractionCreate(BaseModel):
    prospect_name: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    role_title: str = Field(..., min_length=1)
    interaction_type: str = "Sales interaction"
    meeting_notes: str = Field(..., min_length=1)
    objections: str = ""
    competitor_mentioned: str = ""
    budget: str = ""
    timeline: str = ""
    decision_makers: str = ""
    next_steps: str = ""
    deal_id: str | None = None


class Interaction(InteractionCreate):
    id: int
    prospect_id: int
    created_at: datetime


class Prospect(BaseModel):
    id: int
    name: str
    company: str
    role_title: str
    deal_id: str
    created_at: datetime
    updated_at: datetime


class MemoryActivity(BaseModel):
    id: int
    operation: str
    prospect_name: str
    company: str
    deal_id: str
    tags: list[str]
    content: str
    result: str
    provider: str
    fallback_mode: bool
    created_at: datetime


class GeneratedResponse(BaseModel):
    prospect: Prospect
    memory_mode: str
    memory_source: str
    memory_warning: str | None = None
    recalled_memories: list[dict[str, Any]]
    content: str


class DashboardStats(BaseModel):
    prospects: int
    interactions: int
    retained_memories: int
    top_objections: list[dict[str, Any]]
    recent_activity: list[MemoryActivity]
    fallback_mode: bool
    memory_health: dict[str, Any]


class Health(BaseModel):
    status: str
    memory_mode: str


class MemoryHealth(BaseModel):
    hindsight_enabled: bool
    configured: bool
    reachable: bool
    bank_id: str | None = None
    fallback_enabled: bool
    last_error: str | None = None
    memory_mode: str
