import json
import sqlite3
import uuid
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_interview_tables() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                session_id TEXT PRIMARY KEY,
                job_title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                score INTEGER,
                strengths_json TEXT,
                improvements_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(session_id) REFERENCES interview_sessions(session_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_interview_messages_session
            ON interview_messages(session_id, id)
            """
        )


def ensure_session(job_title: str, session_id: str | None = None) -> str:
    sid = session_id or uuid.uuid4().hex
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT session_id FROM interview_sessions WHERE session_id = ?",
            (sid,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO interview_sessions(session_id, job_title) VALUES (?, ?)",
                (sid, job_title),
            )
        else:
            conn.execute(
                "UPDATE interview_sessions SET job_title = ?, updated_at = datetime('now') WHERE session_id = ?",
                (job_title, sid),
            )
    return sid


def save_message(
    session_id: str,
    role: str,
    content: str,
    score: int | None = None,
    strengths: list[str] | None = None,
    improvements: list[str] | None = None,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO interview_messages(session_id, role, content, score, strengths_json, improvements_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                score,
                json.dumps(strengths or [], ensure_ascii=False),
                json.dumps(improvements or [], ensure_ascii=False),
            ),
        )
        conn.execute(
            "UPDATE interview_sessions SET updated_at = datetime('now') WHERE session_id = ?",
            (session_id,),
        )


def get_history(session_id: str) -> tuple[str | None, list[dict]]:
    with _get_conn() as conn:
        session_row = conn.execute(
            "SELECT job_title FROM interview_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT role, content, score, strengths_json, improvements_json, created_at
            FROM interview_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    history = []
    for row in rows:
        history.append(
            {
                "role": row["role"],
                "content": row["content"],
                "score": row["score"],
                "strengths": json.loads(row["strengths_json"] or "[]"),
                "improvements": json.loads(row["improvements_json"] or "[]"),
                "created_at": row["created_at"],
            }
        )
    return (session_row["job_title"] if session_row else None, history)


def list_sessions(limit: int = 20, offset: int = 0) -> list[dict]:
    size = max(1, min(limit, 100))
    start = max(0, offset)
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                s.session_id,
                s.job_title,
                s.created_at,
                s.updated_at,
                (
                    SELECT COUNT(1)
                    FROM interview_messages m
                    WHERE m.session_id = s.session_id
                ) AS message_count
            FROM interview_sessions s
            ORDER BY s.updated_at DESC
            LIMIT ?
            OFFSET ?
            """,
            (size, start),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_session(session_id: str) -> bool:
    with _get_conn() as conn:
        conn.execute("DELETE FROM interview_messages WHERE session_id = ?", (session_id,))
        result = conn.execute("DELETE FROM interview_sessions WHERE session_id = ?", (session_id,))
    return result.rowcount > 0
