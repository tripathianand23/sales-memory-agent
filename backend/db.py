from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from models import InteractionCreate

DB_PATH = Path(__file__).resolve().parent / "sales_memory_agent.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT NOT NULL,
                role_title TEXT NOT NULL,
                deal_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                prospect_name TEXT NOT NULL,
                company TEXT NOT NULL,
                role_title TEXT NOT NULL,
                interaction_type TEXT DEFAULT 'Sales interaction',
                meeting_notes TEXT NOT NULL,
                objections TEXT,
                competitor_mentioned TEXT,
                budget TEXT,
                timeline TEXT,
                decision_makers TEXT,
                next_steps TEXT,
                deal_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (prospect_id) REFERENCES prospects(id)
            );

            CREATE TABLE IF NOT EXISTS memory_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                prospect_name TEXT NOT NULL,
                company TEXT NOT NULL,
                deal_id TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                content TEXT NOT NULL,
                result TEXT NOT NULL,
                provider TEXT NOT NULL,
                fallback_mode INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS local_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_name TEXT NOT NULL,
                company TEXT NOT NULL,
                deal_id TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(conn, "interactions", "interaction_type", "TEXT DEFAULT 'Sales interaction'")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def deal_id_for(company: str, prospect_name: str) -> str:
    base = f"{company}-{prospect_name}".lower()
    return "deal-" + "".join(ch if ch.isalnum() else "-" for ch in base).strip("-")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    if "tags_json" in data:
        data["tags"] = json.loads(data.pop("tags_json"))
    if "fallback_mode" in data:
        data["fallback_mode"] = bool(data["fallback_mode"])
    return data


def upsert_prospect(payload: InteractionCreate) -> dict[str, Any]:
    now = utc_now()
    deal_id = payload.deal_id or deal_id_for(payload.company, payload.prospect_name)
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM prospects WHERE deal_id = ?", (deal_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE prospects
                SET name = ?, company = ?, role_title = ?, updated_at = ?
                WHERE deal_id = ?
                """,
                (payload.prospect_name, payload.company, payload.role_title, now, deal_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO prospects (name, company, role_title, deal_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (payload.prospect_name, payload.company, payload.role_title, deal_id, now, now),
            )
        prospect = conn.execute("SELECT * FROM prospects WHERE deal_id = ?", (deal_id,)).fetchone()
        return row_to_dict(prospect)


def create_interaction(payload: InteractionCreate, prospect_id: int, deal_id: str) -> dict[str, Any]:
    now = utc_now()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO interactions (
                prospect_id, prospect_name, company, role_title, interaction_type,
                meeting_notes, objections, competitor_mentioned, budget, timeline,
                decision_makers, next_steps, deal_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prospect_id,
                payload.prospect_name,
                payload.company,
                payload.role_title,
                payload.interaction_type,
                payload.meeting_notes,
                payload.objections,
                payload.competitor_mentioned,
                payload.budget,
                payload.timeline,
                payload.decision_makers,
                payload.next_steps,
                deal_id,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return row_to_dict(row)


def interaction_exists(deal_id: str, meeting_notes: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM interactions WHERE deal_id = ? AND meeting_notes = ? LIMIT 1",
            (deal_id, meeting_notes),
        ).fetchone()
        return row is not None


def list_prospects() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM prospects ORDER BY updated_at DESC").fetchall()
        return [row_to_dict(row) for row in rows]


def get_prospect(prospect_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        return row_to_dict(row) if row else None


def list_interactions_for_deal(deal_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM interactions WHERE deal_id = ? ORDER BY created_at DESC",
            (deal_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def log_memory_activity(
    operation: str,
    prospect_name: str,
    company: str,
    deal_id: str,
    tags: list[str],
    content: str,
    result: str,
    provider: str,
    fallback_mode: bool,
) -> dict[str, Any]:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memory_activity (
                operation, prospect_name, company, deal_id, tags_json, content,
                result, provider, fallback_mode, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operation,
                prospect_name,
                company,
                deal_id,
                json.dumps(tags),
                content,
                result,
                provider,
                int(fallback_mode),
                utc_now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM memory_activity WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return row_to_dict(row)


def add_local_memory(
    prospect_name: str, company: str, deal_id: str, tags: list[str], content: str
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO local_memories (prospect_name, company, deal_id, tags_json, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (prospect_name, company, deal_id, json.dumps(tags), content, utc_now()),
        )


def search_local_memories(
    prospect_name: str, company: str, deal_id: str, query: str | None = None
) -> list[dict[str, Any]]:
    terms = {prospect_name.lower(), company.lower(), deal_id.lower()}
    if query:
        terms.update(word.lower().strip(".,:;") for word in query.split() if len(word) > 3)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM local_memories ORDER BY created_at DESC"
        ).fetchall()
    scoped: list[sqlite3.Row] = [
        row
        for row in rows
        if row["deal_id"] == deal_id
        or (
            row["prospect_name"].lower() == prospect_name.lower()
            and row["company"].lower() == company.lower()
        )
    ]
    fallback_rows = scoped or rows
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in fallback_rows:
        item = row_to_dict(row)
        haystack = " ".join(
            [item["prospect_name"], item["company"], item["deal_id"], " ".join(item["tags"]), item["content"]]
        ).lower()
        score = sum(1 for term in terms if term and term in haystack)
        if item["deal_id"] == deal_id:
            score += 5
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (pair[0], pair[1]["created_at"]), reverse=True)
    return [item for _, item in scored[:10]]


def list_memory_activity(deal_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if deal_id:
            rows = conn.execute(
                "SELECT * FROM memory_activity WHERE deal_id = ? ORDER BY created_at DESC LIMIT ?",
                (deal_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_activity ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [row_to_dict(row) for row in rows]


def dashboard_stats(fallback_mode: bool, memory_health: dict[str, Any] | None = None) -> dict[str, Any]:
    with get_conn() as conn:
        prospect_count = conn.execute("SELECT COUNT(*) AS c FROM prospects").fetchone()["c"]
        interaction_count = conn.execute("SELECT COUNT(*) AS c FROM interactions").fetchone()["c"]
        retained_count = conn.execute(
            "SELECT COUNT(*) AS c FROM memory_activity WHERE operation = 'retain'"
        ).fetchone()["c"]
        objection_rows = conn.execute(
            """
            SELECT objections
            FROM interactions
            WHERE TRIM(COALESCE(objections, '')) != ''
            """
        ).fetchall()
    counts: dict[str, int] = {}
    for row in objection_rows:
        for objection in row["objections"].replace(";", ",").split(","):
            key = objection.strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    top_objections = [
        {"objection": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:6]
    ]
    return {
        "prospects": prospect_count,
        "interactions": interaction_count,
        "retained_memories": retained_count,
        "top_objections": top_objections,
        "recent_activity": list_memory_activity(limit=8),
        "fallback_mode": fallback_mode,
        "memory_health": memory_health or {},
    }
