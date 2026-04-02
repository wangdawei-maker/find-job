"""
RAG 知识库的 SQLite 仓储层。

表：``rag_documents``（文档元数据）、``rag_chunks``（文本块 + embedding JSON）。
与 ``rag_service`` 配合完成入库与全量扫描检索（MVP 实现）。
"""

import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def _get_conn() -> sqlite3.Connection:
    """
    创建指向 ``app.db`` 的 SQLite 连接。

    Returns:
        ``row_factory`` 为 ``sqlite3.Row`` 的连接。
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_rag_tables() -> None:
    """
    创建 RAG 表与索引；为旧库追加 ``file_*`` 等列（上传文件元数据）。
    """
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
        _ensure_rag_document_columns(conn)


def _ensure_rag_document_columns(conn: sqlite3.Connection) -> None:
    """
    迁移：为 ``rag_documents`` 增加文件相关列（若不存在）。

    Args:
        conn: 数据库连接。
    """
    rows = conn.execute("PRAGMA table_info(rag_documents)").fetchall()
    existing = {row["name"] for row in rows}
    needed = {
        "file_name": "TEXT",
        "file_path": "TEXT",
        "mime_type": "TEXT",
        "file_size": "INTEGER",
    }
    for col, col_type in needed.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE rag_documents ADD COLUMN {col} {col_type}")


def create_document(
    source: str,
    title: str,
    file_name: str | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
) -> int:
    """
    插入一条文档记录。

    Args:
        source: 来源标识（如文件名、``manual``、``upload``）。
        title: 展示标题。
        file_name: 原始上传文件名（可选）。
        file_path: 磁盘保存路径（可选）。
        mime_type: MIME 类型（可选）。
        file_size: 字节大小（可选）。

    Returns:
        新文档的自增 ``id``。
    """
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO rag_documents(source, title, file_name, file_path, mime_type, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, title, file_name, file_path, mime_type, file_size),
        )
    return int(cur.lastrowid)


def insert_chunk(document_id: int, chunk_index: int, chunk_text: str, embedding: list[float]) -> None:
    """
    插入一个文本块及其向量（JSON 序列化存储）。

    Args:
        document_id: 所属文档 ID。
        chunk_index: 块在文档内的顺序（从 0 起）。
        chunk_text: 块正文。
        embedding: 浮点向量列表。
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO rag_chunks(document_id, chunk_index, chunk_text, embedding_json)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, chunk_index, chunk_text, json.dumps(embedding)),
        )


def fetch_all_chunks() -> list[dict]:
    """
    读取所有 chunk 及关联文档的 ``source``、``title``。

    Returns:
        字典列表，含 ``id``、``chunk_text``、``embedding_json``、``source``、``title``。
    """
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


def list_documents(limit: int = 50, offset: int = 0) -> list[dict]:
    """
    分页列出文档及每个文档下的 chunk 数量。

    Args:
        limit: 每页条数，最大 200。
        offset: 跳过条数。

    Returns:
        字典列表，含 ``id``、``source``、``title``、``created_at``、文件元数据、``chunk_count``。
    """
    page_limit = max(1, min(limit, 200))
    page_offset = max(0, offset)
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.source,
                d.title,
                d.created_at,
                d.file_name,
                d.file_path,
                d.mime_type,
                d.file_size,
                COUNT(c.id) AS chunk_count
            FROM rag_documents d
            LEFT JOIN rag_chunks c ON c.document_id = d.id
            GROUP BY d.id
            ORDER BY d.id DESC
            LIMIT ? OFFSET ?
            """,
            (page_limit, page_offset),
        ).fetchall()
    return [dict(row) for row in rows]


def get_document(document_id: int) -> dict | None:
    """
    按 ID 查询单条文档元数据。

    Args:
        document_id: 文档主键。

    Returns:
        文档字段字典；不存在则 ``None``。
    """
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                id, source, title, created_at, file_name, file_path, mime_type, file_size
            FROM rag_documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_document(document_id: int) -> bool:
    """
    删除文档及其全部 chunk。

    Args:
        document_id: 文档主键。

    Returns:
        若删除到至少一行文档为 ``True``。
    """
    with _get_conn() as conn:
        conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
        cur = conn.execute("DELETE FROM rag_documents WHERE id = ?", (document_id,))
    return int(cur.rowcount) > 0


def clear_rag_data() -> dict:
    """
    清空 RAG 两张表（危险操作，供管理端使用）。

    Returns:
        ``{"documents_deleted": n, "chunks_deleted": m}`` 删除前统计数量。
    """
    with _get_conn() as conn:
        chunks_deleted = conn.execute("SELECT COUNT(1) FROM rag_chunks").fetchone()[0]
        docs_deleted = conn.execute("SELECT COUNT(1) FROM rag_documents").fetchone()[0]
        conn.execute("DELETE FROM rag_chunks")
        conn.execute("DELETE FROM rag_documents")
    return {
        "documents_deleted": int(docs_deleted),
        "chunks_deleted": int(chunks_deleted),
    }
