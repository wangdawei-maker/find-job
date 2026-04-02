"""
模拟面试会话与消息的 SQLite 持久化。

数据库文件：``backend/data/app.db``，表 ``interview_sessions``、``interview_messages``。
消息表含可选评分、亮点/改进 JSON，以及 ``reply_kind``（作答 / 追问面试官）。
"""

import json
import sqlite3
import uuid
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def _get_conn() -> sqlite3.Connection:
    """
    创建 SQLite 连接，行以 dict-like ``sqlite3.Row`` 访问。

    Returns:
        已设置 ``row_factory`` 的连接；调用方负责在上下文中关闭。
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_interview_tables() -> None:
    """
    创建面试相关表及索引；对旧库执行 ``reply_kind`` 列迁移。

    应在应用启动时调用一次（见 ``routers.api``）。
    """
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
        _ensure_interview_message_columns(conn)


def _ensure_interview_message_columns(conn: sqlite3.Connection) -> None:
    """
    若缺少 ``reply_kind`` 列则 ``ALTER TABLE`` 追加（兼容已有数据库）。

    Args:
        conn: 已打开的数据库连接。
    """
    rows = conn.execute("PRAGMA table_info(interview_messages)").fetchall()
    names = {row["name"] for row in rows}
    if "reply_kind" not in names:
        conn.execute("ALTER TABLE interview_messages ADD COLUMN reply_kind TEXT DEFAULT 'answer'")


def ensure_session(job_title: str, session_id: str | None = None) -> str:
    """
    确保会话存在：无则插入，有则更新岗位标题与 ``updated_at``。

    Args:
        job_title: 当前应聘岗位名称。
        session_id: 已有会话 ID；为 ``None`` 时生成新 UUID hex。

    Returns:
        最终使用的 ``session_id``。
    """
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
    reply_kind: str = "answer",
) -> None:
    """
    追加一条会话消息，并刷新会话 ``updated_at``。

    Args:
        session_id: 会话 ID。
        role: ``user`` 或 ``assistant``。
        content: 消息正文。
        score: 作答回合评分；用户消息或追问回合可为 ``None``。
        strengths: 亮点列表，存为 JSON。
        improvements: 改进建议列表，存为 JSON。
        reply_kind: ``answer``（默认）或 ``ask_interviewer``（追问答复）。
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO interview_messages(session_id, role, content, score, strengths_json, improvements_json, reply_kind)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                score,
                json.dumps(strengths or [], ensure_ascii=False),
                json.dumps(improvements or [], ensure_ascii=False),
                reply_kind,
            ),
        )
        conn.execute(
            "UPDATE interview_sessions SET updated_at = datetime('now') WHERE session_id = ?",
            (session_id,),
        )


def get_history(session_id: str) -> tuple[str | None, list[dict]]:
    """
    读取会话岗位名与全部消息（按时间顺序）。

    Args:
        session_id: 会话 ID。

    Returns:
        ``(job_title, messages)``。会话不存在时 ``job_title`` 为 ``None``，``messages`` 为空列表。
        每条 message 含 ``role``、``content``、``score``、``strengths``、``improvements``、
        ``created_at``、``reply_kind``。
    """
    with _get_conn() as conn:
        session_row = conn.execute(
            "SELECT job_title FROM interview_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT role, content, score, strengths_json, improvements_json, created_at, reply_kind
            FROM interview_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    history = []
    for row in rows:
        rk = row["reply_kind"] or "answer"
        history.append(
            {
                "role": row["role"],
                "content": row["content"],
                "score": row["score"],
                "strengths": json.loads(row["strengths_json"] or "[]"),
                "improvements": json.loads(row["improvements_json"] or "[]"),
                "created_at": row["created_at"],
                "reply_kind": rk or "answer",
            }
        )
    return (session_row["job_title"] if session_row else None, history)


def list_sessions(limit: int = 20, offset: int = 0) -> list[dict]:
    """
    分页列出会话摘要，按 ``updated_at`` 倒序。

    Args:
        limit: 每页条数，限制在 1～100。
        offset: 跳过条数，≥0。

    Returns:
        字典列表，每项含 ``session_id``、``job_title``、``created_at``、``updated_at``、``message_count``。
    """
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
    """
    删除会话及其所有消息。

    Args:
        session_id: 会话 ID。

    Returns:
        若会话存在并删除成功为 ``True``，否则 ``False``。
    """
    with _get_conn() as conn:
        conn.execute("DELETE FROM interview_messages WHERE session_id = ?", (session_id,))
        result = conn.execute("DELETE FROM interview_sessions WHERE session_id = ?", (session_id,))
    return result.rowcount > 0
