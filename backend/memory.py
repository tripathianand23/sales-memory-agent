from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import find_dotenv, load_dotenv

import db

load_dotenv(find_dotenv())


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _truncate(value: Any, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:limit]


class HindsightMemoryClient:
    """Thin Hindsight adapter with an explicit local fallback path.

    The HTTP paths follow the Hindsight Cloud API docs:
    POST /v1/default/banks/{bank_id}/memories
    POST /v1/default/banks/{bank_id}/memories/recall
    POST /v1/default/banks/{bank_id}/reflect
    GET  /v1/default/banks/{bank_id}/tags
    """

    def __init__(self) -> None:
        load_dotenv(find_dotenv())
        self.enabled = _truthy(os.getenv("HINDSIGHT_ENABLED"), default=True)
        self.fallback_enabled = _truthy(os.getenv("HINDSIGHT_FALLBACK_ENABLED"), default=True)
        self.api_key = os.getenv("HINDSIGHT_API_KEY", "").strip()
        self.base_url = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io").strip().rstrip("/")
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "").strip()
        self.api_prefix = os.getenv("HINDSIGHT_API_PREFIX", "/v1/default/banks").strip().strip("/")
        self.last_error: str | None = None

    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key and self.base_url and self.bank_id)

    def fallback_mode(self) -> bool:
        return not self.is_configured()

    def memory_mode_label(self) -> str:
        if self.is_configured():
            return "Hindsight Cloud"
        if not self.enabled:
            return "Local fallback memory (Hindsight disabled)"
        return "Local fallback memory (Hindsight not configured)"

    def health(self, check_reachable: bool = True) -> dict[str, Any]:
        reachable = False
        configured = self.is_configured()
        last_error = self.last_error
        if not self.enabled:
            last_error = "HINDSIGHT_ENABLED=false"
        elif not configured:
            last_error = "Missing HINDSIGHT_API_KEY, HINDSIGHT_BASE_URL, or HINDSIGHT_BANK_ID."
        elif check_reachable:
            try:
                self._request("GET", "/tags", params={"limit": 1, "source": "memories"}, timeout=8)
                reachable = True
                last_error = None
            except requests.RequestException as exc:
                last_error = self._safe_error(exc)
                self.last_error = last_error
        return {
            "hindsight_enabled": self.enabled,
            "configured": configured,
            "reachable": reachable,
            "bank_id": self.bank_id if self.bank_id else None,
            "fallback_enabled": self.fallback_enabled or not self.enabled,
            "last_error": last_error,
            "memory_mode": self.memory_mode_label(),
        }

    def retain_sales_memory(self, interaction: dict[str, Any]) -> dict[str, Any]:
        payload = self._retention_payload(interaction)
        tags = payload["metadata"]["tags"]
        if not self.is_configured():
            reason = "Hindsight disabled or not configured."
            return self._fallback_retain(interaction, payload, reason)

        try:
            response = self._request(
                "POST",
                "/memories",
                json={
                    "items": [
                        {
                            "content": payload["content"],
                            "context": payload["context"],
                            "timestamp": payload["metadata"]["timestamp"],
                            "tags": tags,
                            "metadata": payload["metadata"],
                        }
                    ],
                    "async": False,
                },
                timeout=30,
            )
            result = response.json() if response.content else {}
            self.last_error = None
            memory_id = (
                result.get("memory_id")
                or result.get("id")
                or result.get("operation_id")
                or (result.get("operation_ids") or [None])[0]
            )
            activity = db.log_memory_activity(
                "retain",
                interaction["prospect_name"],
                interaction["company"],
                interaction["deal_id"],
                tags,
                payload["content"],
                _truncate(result),
                "hindsight",
                False,
            )
            return {
                "operation": "retain",
                "status": "retained",
                "memory_source": "hindsight",
                "provider": "hindsight",
                "fallback_mode": False,
                "memory_id": memory_id,
                "retained_payload": payload,
                "activity": activity,
                "warning": None,
                "error": None,
            }
        except requests.RequestException as exc:
            error = self._safe_error(exc)
            self.last_error = error
            if self.fallback_enabled:
                return self._fallback_retain(interaction, payload, error)
            return self._failed_operation("retain", interaction, tags, payload["content"], error)

    def recall_sales_memory(
        self, prospect_name: str, company_name: str, deal_id: str | None = None, query: str | None = None
    ) -> dict[str, Any]:
        tags = tags_for(prospect_name, company_name, deal_id)
        recall_query = query or (
            f"Recall sales interactions, objections, competitors, budget, decision makers, "
            f"and next steps for {prospect_name} at {company_name}."
        )
        if deal_id:
            recall_query += f" Deal ID: {deal_id}."

        if not self.is_configured():
            return self._fallback_recall(prospect_name, company_name, deal_id or "", tags, recall_query, None)

        try:
            response = self._request(
                "POST",
                "/memories/recall",
                json={
                    "query": recall_query,
                    "types": ["experience", "world", "observation"],
                    "budget": "mid",
                    "max_tokens": 2500,
                    "tags": tags,
                    "tags_match": "any_strict",
                },
                timeout=35,
            )
            payload = response.json() if response.content else {}
            memories = self._normalize_results(payload)
            self.last_error = None
            db.log_memory_activity(
                "recall",
                prospect_name,
                company_name,
                deal_id or "",
                tags,
                recall_query,
                _truncate(payload),
                "hindsight",
                False,
            )
            return {
                "operation": "recall",
                "status": "recalled",
                "memory_source": "hindsight",
                "provider": "hindsight",
                "fallback_mode": False,
                "recalled_memories": memories,
                "raw_response": payload,
                "warning": None,
                "error": None,
            }
        except requests.RequestException as exc:
            error = self._safe_error(exc)
            self.last_error = error
            if self.fallback_enabled:
                return self._fallback_recall(prospect_name, company_name, deal_id or "", tags, recall_query, error)
            db.log_memory_activity(
                "recall", prospect_name, company_name, deal_id or "", tags, recall_query, error, "hindsight", False
            )
            return {
                "operation": "recall",
                "status": "failed",
                "memory_source": "hindsight",
                "provider": "hindsight",
                "fallback_mode": False,
                "recalled_memories": [],
                "raw_response": None,
                "warning": None,
                "error": error,
            }

    def reflect_sales_strategy(self, prospect_name: str, company_name: str, query: str) -> dict[str, Any]:
        recall_result = self.recall_sales_memory(prospect_name, company_name, None, query)
        recalled = recall_result.get("recalled_memories", [])
        if not self.is_configured():
            text = self._fallback_reflection_text(recalled)
            return {
                "operation": "reflect",
                "status": "fallback",
                "memory_source": "fallback",
                "provider": "local-fallback",
                "fallback_mode": True,
                "text": text,
                "based_on": recalled,
                "warning": "Hindsight disabled or not configured; reflected over local fallback memories.",
                "error": None,
            }

        try:
            response = self._request(
                "POST",
                "/reflect",
                json={"query": query, "budget": "mid", "max_tokens": 1800},
                timeout=45,
            )
            payload = response.json() if response.content else {}
            text = payload.get("text") or _truncate(payload)
            db.log_memory_activity(
                "reflect",
                prospect_name,
                company_name,
                "",
                tags_for(prospect_name, company_name, None),
                query,
                _truncate(payload),
                "hindsight",
                False,
            )
            return {
                "operation": "reflect",
                "status": "reflected",
                "memory_source": "hindsight",
                "provider": "hindsight",
                "fallback_mode": False,
                "text": text,
                "based_on": payload.get("based_on") or recalled,
                "raw_response": payload,
                "warning": None,
                "error": None,
            }
        except requests.RequestException as exc:
            error = self._safe_error(exc)
            self.last_error = error
            if self.fallback_enabled:
                text = self._fallback_reflection_text(recalled)
                return {
                    "operation": "reflect",
                    "status": "fallback",
                    "memory_source": "fallback",
                    "provider": "local-fallback",
                    "fallback_mode": True,
                    "text": text,
                    "based_on": recalled,
                    "warning": f"Hindsight reflect failed; fallback used. {error}",
                    "error": error,
                }
            return {
                "operation": "reflect",
                "status": "failed",
                "memory_source": "hindsight",
                "provider": "hindsight",
                "fallback_mode": False,
                "text": "",
                "based_on": recalled,
                "warning": None,
                "error": error,
            }

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}/{self.api_prefix}/{self.bank_id}{path}"
        headers = kwargs.pop("headers", {})
        response = requests.request(
            method,
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                **headers,
            },
            **kwargs,
        )
        response.raise_for_status()
        return response

    def _retention_payload(self, interaction: dict[str, Any]) -> dict[str, Any]:
        timestamp = interaction.get("created_at") or datetime.now(timezone.utc).isoformat()
        sales_insight = self._sales_insight(interaction)
        content = "\n".join(
            [
                f"Prospect: {interaction['prospect_name']}",
                f"Company: {interaction['company']}",
                f"Role: {interaction.get('role_title') or 'Unknown'}",
                f"Deal ID: {interaction.get('deal_id') or 'Unknown'}",
                f"Interaction Type: {interaction.get('interaction_type') or 'Sales interaction'}",
                f"Meeting Notes: {interaction.get('meeting_notes') or 'None'}",
                f"Objections: {interaction.get('objections') or 'None captured'}",
                f"Competitors Mentioned: {interaction.get('competitor_mentioned') or 'None'}",
                f"Budget: {interaction.get('budget') or 'Unknown'}",
                f"Timeline: {interaction.get('timeline') or 'Unknown'}",
                f"Decision Makers: {interaction.get('decision_makers') or 'Unknown'}",
                f"Next Steps: {interaction.get('next_steps') or 'None'}",
                f"Sales Insight: {sales_insight}",
            ]
        )
        metadata = {
            "prospect_name": interaction["prospect_name"],
            "company_name": interaction["company"],
            "deal_id": interaction.get("deal_id"),
            "memory_type": "sales_interaction",
            "objection_type": interaction.get("objections") or None,
            "competitor": interaction.get("competitor_mentioned") or None,
            "timestamp": timestamp,
            "tags": tags_for(interaction["prospect_name"], interaction["company"], interaction.get("deal_id")),
        }
        return {
            "content": content,
            "context": "Sales Memory Agent prospect interaction",
            "metadata": metadata,
            "preview": content[:900],
        }

    def _sales_insight(self, interaction: dict[str, Any]) -> str:
        parts = []
        if interaction.get("objections"):
            parts.append(f"Address {interaction['objections']} directly.")
        if interaction.get("competitor_mentioned"):
            parts.append(f"Differentiate against {interaction['competitor_mentioned']}.")
        if interaction.get("decision_makers"):
            parts.append(f"Include {interaction['decision_makers']} in next steps.")
        if interaction.get("next_steps"):
            parts.append(f"Commitment: {interaction['next_steps']}.")
        return " ".join(parts) or "Continue discovery and capture a concrete next commitment."

    def _fallback_retain(self, interaction: dict[str, Any], payload: dict[str, Any], reason: str) -> dict[str, Any]:
        if not (self.fallback_enabled or not self.enabled):
            return self._failed_operation(
                "retain", interaction, payload["metadata"]["tags"], payload["content"], reason
            )
        db.add_local_memory(
            interaction["prospect_name"],
            interaction["company"],
            interaction["deal_id"],
            payload["metadata"]["tags"],
            payload["content"],
        )
        activity = db.log_memory_activity(
            "retain",
            interaction["prospect_name"],
            interaction["company"],
            interaction["deal_id"],
            payload["metadata"]["tags"],
            payload["content"],
            f"Stored in local fallback memory. Reason: {reason}",
            "local-fallback",
            True,
        )
        return {
            "operation": "retain",
            "status": "fallback",
            "memory_source": "fallback",
            "provider": "local-fallback",
            "fallback_mode": True,
            "memory_id": None,
            "retained_payload": payload,
            "activity": activity,
            "warning": f"Stored in local fallback memory. Reason: {reason}",
            "error": None,
        }

    def _fallback_recall(
        self,
        prospect_name: str,
        company_name: str,
        deal_id: str,
        tags: list[str],
        recall_query: str,
        reason: str | None,
    ) -> dict[str, Any]:
        local = db.search_local_memories(prospect_name, company_name, deal_id, recall_query)
        memories = [
            {
                "id": item["id"],
                "text": item["content"],
                "type": "experience",
                "score": None,
                "tags": item["tags"],
                "metadata": {
                    "prospect_name": item["prospect_name"],
                    "company_name": item["company"],
                    "deal_id": item["deal_id"],
                    "memory_type": "sales_interaction",
                },
                "created_at": item["created_at"],
            }
            for item in local
        ]
        warning = "Hindsight disabled or not configured; recalled local fallback memories."
        if reason:
            warning = f"Hindsight recall failed; recalled local fallback memories. {reason}"
        db.log_memory_activity(
            "recall",
            prospect_name,
            company_name,
            deal_id,
            tags,
            recall_query,
            f"Recalled {len(memories)} local fallback memories. {reason or ''}".strip(),
            "local-fallback",
            True,
        )
        return {
            "operation": "recall",
            "status": "fallback",
            "memory_source": "fallback",
            "provider": "local-fallback",
            "fallback_mode": True,
            "recalled_memories": memories,
            "raw_response": None,
            "warning": warning,
            "error": None,
        }

    def _failed_operation(
        self, operation: str, interaction: dict[str, Any], tags: list[str], content: str, error: str
    ) -> dict[str, Any]:
        db.log_memory_activity(
            operation,
            interaction["prospect_name"],
            interaction["company"],
            interaction.get("deal_id") or "",
            tags,
            content,
            error,
            "hindsight",
            False,
        )
        return {
            "operation": operation,
            "status": "failed",
            "memory_source": "hindsight",
            "provider": "hindsight",
            "fallback_mode": False,
            "memory_id": None,
            "retained_payload": {"content": content, "metadata": {"tags": tags}},
            "warning": None,
            "error": error,
        }

    def _normalize_results(self, payload: Any) -> list[dict[str, Any]]:
        raw_results = []
        if isinstance(payload, dict):
            raw_results = payload.get("results") or payload.get("memories") or payload.get("items") or []
        elif isinstance(payload, list):
            raw_results = payload
        normalized = []
        for item in raw_results:
            if isinstance(item, str):
                normalized.append({"text": item, "type": "memory", "score": None, "tags": [], "metadata": {}})
                continue
            if isinstance(item, dict):
                normalized.append(
                    {
                        "id": item.get("id"),
                        "text": item.get("text") or item.get("content") or item.get("memory") or _truncate(item),
                        "type": item.get("type", "memory"),
                        "score": item.get("score"),
                        "tags": item.get("tags") or item.get("metadata", {}).get("tags") or [],
                        "metadata": item.get("metadata") or {},
                        "created_at": item.get("created_at") or item.get("mentioned_at") or item.get("timestamp"),
                        "raw": item,
                    }
                )
        return normalized

    def _fallback_reflection_text(self, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return "No relevant memories are available yet. Continue discovery and capture next commitments."
        return (
            "Fallback reflection based on recalled sales memories: acknowledge the latest objection, "
            "tie value to the business pain already discussed, include the named decision makers, "
            "and secure the next mutual commitment."
        )

    def _safe_error(self, exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is not None:
            return f"Hindsight API error {response.status_code}: {response.text[:500]}"
        return f"Hindsight API error: {exc}"


def client() -> HindsightMemoryClient:
    return HindsightMemoryClient()


def fallback_mode() -> bool:
    return client().fallback_mode()


def memory_mode_label() -> str:
    return client().memory_mode_label()


def memory_health(check_reachable: bool = True) -> dict[str, Any]:
    return client().health(check_reachable=check_reachable)


def tags_for(prospect_name: str, company: str, deal_id: str | None = None) -> list[str]:
    tags = [
        f"prospect_name:{prospect_name}",
        f"company_name:{company}",
        "memory_type:sales_interaction",
    ]
    if deal_id:
        tags.append(f"deal_id:{deal_id}")
    return tags


def retain_sales_memory(interaction: dict[str, Any]) -> dict[str, Any]:
    return client().retain_sales_memory(interaction)


def recall_sales_memory(
    prospect_name: str, company_name: str, deal_id: str | None = None, query: str | None = None
) -> dict[str, Any]:
    return client().recall_sales_memory(prospect_name, company_name, deal_id, query)


def reflect_sales_strategy(prospect_name: str, company_name: str, query: str) -> dict[str, Any]:
    return client().reflect_sales_strategy(prospect_name, company_name, query)
