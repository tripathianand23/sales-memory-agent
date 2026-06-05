from __future__ import annotations

from datetime import datetime, timezone

from dotenv import find_dotenv, load_dotenv

import db
from memory import HindsightMemoryClient


def main() -> None:
    load_dotenv(find_dotenv())
    db.init_db()
    client = HindsightMemoryClient()
    health = client.health(check_reachable=True)
    print("Hindsight memory health")
    print(f"  enabled: {health['hindsight_enabled']}")
    print(f"  configured: {health['configured']}")
    print(f"  reachable: {health['reachable']}")
    print(f"  bank_id: {health['bank_id']}")
    print(f"  fallback_enabled: {health['fallback_enabled']}")
    if health["last_error"]:
        print(f"  last_error: {health['last_error']}")

    interaction = {
        "prospect_name": "Hindsight Test Prospect",
        "company": "CloudNova",
        "role_title": "VP Revenue Operations",
        "interaction_type": "Memory integration test",
        "meeting_notes": "Test retain from Sales Memory Agent. Prospect cares about remembering deal context.",
        "objections": "Security concerns",
        "competitor_mentioned": "Gong",
        "budget": "$100K test budget",
        "timeline": "This quarter",
        "decision_makers": "VP Revenue Operations and CISO",
        "next_steps": "Verify Hindsight recall returns this test memory",
        "deal_id": "deal-hindsight-test-cloudnova",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    print("\nRetaining test memory...")
    retain_result = client.retain_sales_memory(interaction)
    print(f"  status: {retain_result['status']}")
    print(f"  source: {retain_result['memory_source']}")
    print(f"  memory_id: {retain_result.get('memory_id')}")
    if retain_result.get("warning"):
        print(f"  warning: {retain_result['warning']}")
    if retain_result.get("error"):
        print(f"  error: {retain_result['error']}")
    print("  retained preview:")
    print(retain_result.get("retained_payload", {}).get("preview", ""))

    print("\nRecalling test memory...")
    recall_result = client.recall_sales_memory(
        "Hindsight Test Prospect",
        "CloudNova",
        "deal-hindsight-test-cloudnova",
        "Recall the CloudNova Hindsight memory integration test and its security concern.",
    )
    print(f"  status: {recall_result['status']}")
    print(f"  source: {recall_result['memory_source']}")
    if recall_result.get("warning"):
        print(f"  warning: {recall_result['warning']}")
    if recall_result.get("error"):
        print(f"  error: {recall_result['error']}")
    print(f"  memories: {len(recall_result['recalled_memories'])}")
    for idx, memory in enumerate(recall_result["recalled_memories"][:5], start=1):
        print(f"\n  Memory {idx}")
        print(f"  type: {memory.get('type')}")
        print(f"  tags: {memory.get('tags')}")
        print(f"  text: {memory.get('text')}")


if __name__ == "__main__":
    main()
