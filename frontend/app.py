from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Sales Memory Agent", page_icon="SMA", layout="wide")


def api_get(path: str) -> Any:
    response = requests.get(f"{API_URL}{path}", timeout=45)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    response = requests.post(f"{API_URL}{path}", json=payload or {}, timeout=60)
    response.raise_for_status()
    return response.json()


def memory_badge(mode: str | None = None, fallback: bool | None = None) -> None:
    if fallback is True or (mode and "fallback" in mode.lower()):
        st.warning(
            "Memory mode: Local fallback. Add HINDSIGHT_API_KEY, HINDSIGHT_BASE_URL, "
            "and HINDSIGHT_BANK_ID to use Hindsight Cloud."
        )
    else:
        st.success(f"Memory mode: {mode or 'Hindsight Cloud'}")


def source_badge(source: str | None, warning: str | None = None) -> None:
    if source == "hindsight":
        st.success("Memory source: Hindsight Cloud")
    elif source == "fallback":
        st.warning("Memory source: local fallback")
    else:
        st.info(f"Memory source: {source or 'unknown'}")
    if warning:
        st.warning(warning)


def load_prospects() -> list[dict[str, Any]]:
    try:
        return api_get("/prospects")
    except requests.RequestException:
        return []


def prospect_picker(label: str = "Choose prospect") -> dict[str, Any] | None:
    prospects = load_prospects()
    if not prospects:
        st.info("No prospects yet. Seed demo data or log an interaction first.")
        return None
    labels = [f"{p['company']} - {p['name']} ({p['role_title']})" for p in prospects]
    selected = st.selectbox(label, range(len(prospects)), format_func=lambda idx: labels[idx])
    return prospects[selected]


def show_memory_items(memories: list[dict[str, Any]]) -> None:
    if not memories:
        st.info("No recalled memories returned yet.")
        return
    for idx, item in enumerate(memories, start=1):
        with st.expander(f"Recalled memory {idx}: {item.get('type', 'memory')}"):
            st.write(item.get("text", item))
            if item.get("tags"):
                st.caption("Tags: " + ", ".join(item["tags"]))
            if item.get("metadata"):
                st.json(item["metadata"])
            if item.get("created_at"):
                st.caption(f"Timestamp: {item['created_at']}")
            if item.get("score") is not None:
                st.caption(f"Score: {item['score']}")


def dashboard_page() -> None:
    st.title("Sales Memory Agent")
    st.caption("A deal-aware sales intelligence agent powered by Hindsight retain, recall, and reflect.")
    try:
        stats = api_get("/dashboard")
    except requests.RequestException as exc:
        st.error(f"Backend is not reachable at {API_URL}. Start FastAPI first. {exc}")
        return
    memory_badge(fallback=stats["fallback_mode"])
    health = stats.get("memory_health", {})
    st.subheader("Hindsight memory health")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Enabled", "Yes" if health.get("hindsight_enabled") else "No")
    h2.metric("Configured", "Yes" if health.get("configured") else "No")
    h3.metric("Reachable", "Yes" if health.get("reachable") else "Not checked")
    h4.metric("Fallback", "On" if health.get("fallback_enabled") else "Off")
    if health.get("bank_id"):
        st.caption(f"Bank ID: {health['bank_id']}")
    if health.get("last_error"):
        st.warning(health["last_error"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Prospects", stats["prospects"])
    c2.metric("Interactions", stats["interactions"])
    c3.metric("Retained memories", stats["retained_memories"])

    left, right = st.columns([1, 2])
    with left:
        st.subheader("Top objections")
        if stats["top_objections"]:
            st.dataframe(pd.DataFrame(stats["top_objections"]), hide_index=True, width="stretch")
        else:
            st.info("No objections captured yet.")
    with right:
        st.subheader("Recent memory activity")
        for item in stats["recent_activity"]:
            st.markdown(f"**{item['operation'].upper()}** - {item['company']} / {item['prospect_name']}")
            st.caption(f"{item['created_at']} | {', '.join(item['tags'])}")


def log_interaction_page() -> None:
    st.title("Log Interaction")
    st.caption("Submitting an interaction saves it to SQLite and calls retain_sales_memory().")
    with st.form("interaction_form"):
        c1, c2, c3 = st.columns(3)
        prospect_name = c1.text_input("Prospect name")
        company = c2.text_input("Company")
        role_title = c3.text_input("Role/title")
        interaction_type = st.selectbox(
            "Interaction type",
            ["Discovery call", "Demo", "Security review", "Pricing call", "Procurement update", "Sales interaction"],
        )
        meeting_notes = st.text_area("Meeting notes", height=130)
        c4, c5 = st.columns(2)
        objections = c4.text_input("Objections raised")
        competitor_mentioned = c5.text_input("Competitor mentioned")
        c6, c7 = st.columns(2)
        budget = c6.text_input("Budget")
        timeline = c7.text_input("Timeline")
        decision_makers = st.text_input("Decision makers")
        next_steps = st.text_input("Next steps")
        deal_id = st.text_input("Deal ID (optional)")
        submitted = st.form_submit_button("Save and retain memory", type="primary")
    if submitted:
        payload = {
            "prospect_name": prospect_name,
            "company": company,
            "role_title": role_title,
            "interaction_type": interaction_type,
            "meeting_notes": meeting_notes,
            "objections": objections,
            "competitor_mentioned": competitor_mentioned,
            "budget": budget,
            "timeline": timeline,
            "decision_makers": decision_makers,
            "next_steps": next_steps,
            "deal_id": deal_id or None,
        }
        try:
            result = api_post("/interactions", payload)
            if result["memory_status"] == "retained":
                st.success("Interaction saved. Memory retained in Hindsight.")
            elif result["memory_status"] == "fallback":
                st.warning("Interaction saved. Memory retained in local fallback.")
            else:
                st.error("Interaction saved, but memory retain failed.")
            if result.get("memory_warning"):
                st.warning(result["memory_warning"])
            if result.get("memory_error"):
                st.error(result["memory_error"])
            st.write("**Retained payload preview**")
            st.code(result.get("retained_payload", {}).get("preview", ""), language="text")
            st.json(result)
        except requests.RequestException as exc:
            st.error(f"Could not save interaction: {exc}")


def sales_brief_page() -> None:
    st.title("Generate Sales Brief")
    prospect = prospect_picker()
    if prospect and st.button("Recall memory and generate brief", type="primary"):
        with st.spinner("Calling recall(), reflect(), and Groq..."):
            result = api_get(f"/prospects/{prospect['id']}/brief")
        memory_badge(result["memory_mode"])
        source_badge(result.get("memory_source"), result.get("memory_warning"))
        st.subheader("Raw recalled memories")
        show_memory_items(result["recalled_memories"])
        st.subheader("Generated brief")
        st.markdown(result["content"])


def followup_page() -> None:
    st.title("Generate Follow-up Email")
    prospect = prospect_picker()
    if prospect and st.button("Recall memory and write email", type="primary"):
        with st.spinner("Personalizing from recalled history..."):
            result = api_get(f"/prospects/{prospect['id']}/followup")
        memory_badge(result["memory_mode"])
        source_badge(result.get("memory_source"), result.get("memory_warning"))
        generic = llm_generic_preview(result["prospect"]["company"])
        left, right = st.columns(2)
        with left:
            st.subheader("Without Memory")
            st.code(generic, language="markdown")
        with right:
            st.subheader("With Hindsight Memory")
            st.code(result["content"], language="markdown")
        st.subheader("Memory used")
        show_memory_items(result["recalled_memories"])


def before_after_page() -> None:
    st.title("Before vs After Memory Demo")
    st.caption("This is the judge-facing contrast: generic assistant vs deal-aware memory agent.")
    prospect = prospect_picker()
    if prospect and st.button("Run comparison", type="primary"):
        result = api_get(f"/demo/before-after/{prospect['id']}")
        memory_badge(result["memory_mode"])
        source_badge(result.get("memory_source"), result.get("memory_warning"))
        left, right = st.columns(2)
        with left:
            st.subheader("Without Memory")
            st.code(result["without_memory"], language="markdown")
        with right:
            st.subheader("With Hindsight Memory")
            st.code(result["with_hindsight_memory"], language="markdown")
        st.subheader("Recall activity behind the improved answer")
        show_memory_items(result["recalled_memories"])


def inspector_page() -> None:
    st.title("Memory Inspector")
    prospect = prospect_picker("Filter by prospect")
    if prospect:
        result = api_get(f"/prospects/{prospect['id']}/memory")
        source_badge(result.get("memory_source"), result.get("memory_warning"))
        st.subheader("Raw recalled memories")
        show_memory_items(result.get("recalled_memories", []))
        activities = result.get("activity", [])
    else:
        activities = api_get("/memory")
    if not activities:
        st.info("No memory activity yet.")
        return
    for item in activities:
        with st.expander(f"{item['operation'].upper()} | {item['company']} | {item['created_at']}"):
            c1, c2 = st.columns(2)
            c1.write(f"**Prospect:** {item['prospect_name']}")
            c1.write(f"**Company:** {item['company']}")
            c1.write(f"**Deal ID:** {item['deal_id']}")
            c2.write(f"**Provider:** {item['provider']}")
            c2.write(f"**Fallback mode:** {item['fallback_mode']}")
            st.write("**Tags used**")
            st.code(", ".join(item["tags"]))
            st.write("**Content sent/query**")
            st.text(item["content"])
            st.write("**Provider result**")
            st.text(item["result"])


def llm_generic_preview(company: str) -> str:
    return (
        "Subject: Following up on our conversation\n\n"
        "Hi there,\n\n"
        f"Thanks for taking the time to speak with us about {company}. I wanted to follow up and "
        "see whether you had any questions about our solution. We would be happy to schedule a "
        "demo and discuss next steps whenever convenient.\n\n"
        "Best,\nSales Team"
    )


def seed_button() -> None:
    if st.sidebar.button("Seed demo data"):
        try:
            result = api_post("/seed")
            st.sidebar.success(f"Seeded {result['created_interactions']} interactions.")
        except requests.RequestException as exc:
            st.sidebar.error(f"Seed failed: {exc}")


PAGES = {
    "Dashboard": dashboard_page,
    "Log Interaction": log_interaction_page,
    "Generate Sales Brief": sales_brief_page,
    "Generate Follow-up Email": followup_page,
    "Before vs After Demo": before_after_page,
    "Memory Inspector": inspector_page,
}

st.sidebar.title("Sales Memory Agent")
page = st.sidebar.radio("Navigate", list(PAGES.keys()))
st.sidebar.caption(f"Backend: {API_URL}")
seed_button()
PAGES[page]()
