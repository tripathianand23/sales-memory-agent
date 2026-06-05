from __future__ import annotations

import os
from typing import Any

import requests


def _groq_model() -> str:
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _memory_context(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return "No previous memories were recalled."
    return "\n\n".join(f"- {memory.get('text', '')}" for memory in memories)


def _fallback_completion(kind: str, prospect: dict[str, Any], memories: list[dict[str, Any]]) -> str:
    context = _memory_context(memories)
    if kind == "email":
        return (
            f"Subject: Following up on next steps for {prospect['company']}\n\n"
            f"Hi {prospect['name']},\n\n"
            "Thanks again for the conversation. Based on our previous discussions, I understand "
            f"that the team is evaluating priorities around {prospect['company']} and wants a clear "
            "path that addresses the concerns we captured.\n\n"
            "The most relevant history I have is:\n"
            f"{context}\n\n"
            "Would it be useful to schedule the next conversation with the right stakeholders so we "
            "can map the rollout, confirm success criteria, and address the remaining risk directly?\n\n"
            "Best,\nSales Memory Agent"
        )
    return (
        f"Sales brief for {prospect['name']} at {prospect['company']}\n\n"
        f"Memory context:\n{context}\n\n"
        "Recommended strategy: acknowledge the latest objection, connect the product value to the "
        "business pain already discussed, bring in the named decision makers, and secure the next "
        "mutual commitment before the deal loses momentum."
    )


def groq_chat(system: str, user: str, fallback: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return fallback + "\n\n[Generated with deterministic local fallback because GROQ_API_KEY is missing.]"
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _groq_model(),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.4,
                "max_tokens": 1100,
            },
            timeout=35,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException as exc:
        return fallback + f"\n\n[Groq request failed; local fallback used. Error: {exc}]"


def generate_sales_brief(prospect: dict[str, Any], memories: list[dict[str, Any]]) -> str:
    fallback = _fallback_completion("brief", prospect, memories)
    return groq_chat(
        "You are a senior sales intelligence analyst. Produce concise, deal-aware sales briefs.",
        f"""
Prospect:
{prospect}

Recalled Hindsight memories:
{_memory_context(memories)}

Write a concise sales brief with these sections:
Who they are, what they care about, previous objections, competitors mentioned,
best follow-up strategy, deal risks, and recommended next action.
""",
        fallback,
    )


def generate_followup_email(prospect: dict[str, Any], memories: list[dict[str, Any]]) -> str:
    fallback = _fallback_completion("email", prospect, memories)
    return groq_chat(
        "You write crisp, professional B2B sales follow-up emails using only the supplied memory.",
        f"""
Prospect:
{prospect}

Recalled Hindsight memories:
{_memory_context(memories)}

Generate a personalized follow-up email. Reference the previous conversation, one specific
objection, business pain, and next step. Keep the tone consultative and professional.
""",
        fallback,
    )


def generate_generic_followup(company: str) -> str:
    return (
        f"Subject: Following up on our conversation\n\n"
        "Hi there,\n\n"
        f"Thanks for taking the time to speak with us about {company}. I wanted to follow up and "
        "see whether you had any questions about our solution. We would be happy to schedule a "
        "demo and discuss next steps whenever convenient.\n\n"
        "Best,\nSales Team"
    )
