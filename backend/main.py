from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import db
import llm
import memory
from models import DashboardStats, GeneratedResponse, Health, InteractionCreate, MemoryActivity, MemoryHealth, Prospect
from seed import seed_payloads

app = FastAPI(title="Sales Memory Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()


def _create_interaction(payload: InteractionCreate) -> dict:
    prospect = db.upsert_prospect(payload)
    interaction = db.create_interaction(payload, prospect["id"], prospect["deal_id"])
    memory_result = memory.retain_sales_memory(interaction)
    return {
        "prospect": prospect,
        "interaction": interaction,
        "memory_status": memory_result["status"],
        "memory_source": memory_result["memory_source"],
        "memory_id": memory_result.get("memory_id"),
        "retained_payload": memory_result.get("retained_payload"),
        "memory_warning": memory_result.get("warning"),
        "memory_error": memory_result.get("error"),
    }


def _prospect_or_404(prospect_id: int) -> dict:
    prospect = db.get_prospect(prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", memory_mode=memory.memory_mode_label())


@app.get("/health/memory", response_model=MemoryHealth)
def health_memory() -> dict:
    return memory.memory_health()


@app.get("/dashboard", response_model=DashboardStats)
def dashboard() -> dict:
    health = memory.memory_health(check_reachable=False)
    return db.dashboard_stats(memory.fallback_mode(), health)


@app.post("/interactions")
def create_interaction(payload: InteractionCreate) -> dict:
    return _create_interaction(payload)


@app.get("/prospects", response_model=list[Prospect])
def prospects() -> list[dict]:
    return db.list_prospects()


@app.get("/prospects/{prospect_id}/brief", response_model=GeneratedResponse)
def sales_brief(prospect_id: int) -> dict:
    prospect = _prospect_or_404(prospect_id)
    recall_result = memory.recall_sales_memory(prospect["name"], prospect["company"], prospect["deal_id"])
    recalled = recall_result["recalled_memories"]
    reflection = memory.reflect_sales_strategy(
        prospect["name"],
        prospect["company"],
        f"What is the best sales strategy for {prospect['name']} at {prospect['company']}?",
    )
    if reflection.get("text"):
        recalled = recalled + [{"text": f"Hindsight reflect synthesis: {reflection['text']}", "type": "reflection"}]
    return {
        "prospect": prospect,
        "memory_mode": memory.memory_mode_label(),
        "memory_source": recall_result["memory_source"],
        "memory_warning": recall_result.get("warning") or reflection.get("warning"),
        "recalled_memories": recalled,
        "content": llm.generate_sales_brief(prospect, recalled),
    }


@app.get("/prospects/{prospect_id}/followup", response_model=GeneratedResponse)
def followup(prospect_id: int) -> dict:
    prospect = _prospect_or_404(prospect_id)
    recall_result = memory.recall_sales_memory(
        prospect["name"],
        prospect["company"],
        prospect["deal_id"],
        query=f"Recall prior objections, pains, business goals, and next commitments for {prospect['company']}.",
    )
    return {
        "prospect": prospect,
        "memory_mode": memory.memory_mode_label(),
        "memory_source": recall_result["memory_source"],
        "memory_warning": recall_result.get("warning"),
        "recalled_memories": recall_result["recalled_memories"],
        "content": llm.generate_followup_email(prospect, recall_result["recalled_memories"]),
    }


@app.get("/prospects/{prospect_id}/memory")
def prospect_memory(prospect_id: int) -> dict:
    prospect = _prospect_or_404(prospect_id)
    recall_result = memory.recall_sales_memory(
        prospect["name"],
        prospect["company"],
        prospect["deal_id"],
        query=f"Inspect raw Hindsight memories and tags for {prospect['name']} at {prospect['company']}.",
    )
    return {
        "prospect": prospect,
        "memory_source": recall_result["memory_source"],
        "memory_warning": recall_result.get("warning"),
        "recalled_memories": recall_result["recalled_memories"],
        "activity": db.list_memory_activity(prospect["deal_id"]),
    }


@app.get("/memory", response_model=list[MemoryActivity])
def all_memory() -> list[dict]:
    return db.list_memory_activity()


@app.get("/demo/before-after/{prospect_id}")
def before_after(prospect_id: int) -> dict:
    prospect = _prospect_or_404(prospect_id)
    recall_result = memory.recall_sales_memory(
        prospect["name"], prospect["company"], prospect["deal_id"], "Generate a follow-up email using deal history."
    )
    return {
        "prospect": prospect,
        "memory_mode": memory.memory_mode_label(),
        "memory_source": recall_result["memory_source"],
        "memory_warning": recall_result.get("warning"),
        "without_memory": llm.generate_generic_followup(prospect["company"]),
        "with_hindsight_memory": llm.generate_followup_email(prospect, recall_result["recalled_memories"]),
        "recalled_memories": recall_result["recalled_memories"],
    }


@app.post("/seed")
def seed() -> dict:
    created = 0
    for payload in seed_payloads():
        deal_id = payload.deal_id or db.deal_id_for(payload.company, payload.prospect_name)
        if db.interaction_exists(deal_id, payload.meeting_notes):
            continue
        _create_interaction(payload)
        created += 1
    return {"created_interactions": created, "memory_mode": memory.memory_mode_label()}
