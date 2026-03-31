import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_rag_tables() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(document_id) REFERENCES rag_documents(id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_chunks_document
            ON rag_chunks(document_id, chunk_index)
            """
        )


def create_document(source: str, title: str) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO rag_documents(source, title) VALUES (?, ?)",
            (source, title),
        )
    return int(cur.lastrowid)


def insert_chunk(document_id: int, chunk_index: int, chunk_text: str, embedding: list[float]) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO rag_chunks(document_id, chunk_index, chunk_text, embedding_json)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, chunk_index, chunk_text, json.dumps(embedding)),
        )


def fetch_all_chunks() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.chunk_text,
                c.embedding_json,
                d.source,
                d.title
            FROM rag_chunks c
            JOIN rag_documents d ON c.document_id = d.id
            """
        ).fetchall()
    return [dict(row) for row in rows]
