"""
RAG 业务层：切块、Embedding、入库与向量检索。

使用 LangChain ``OpenAIEmbeddings``（兼容 OpenAI 风格接口，如阿里云百炼）。
向量在库内截断/填充到 ``VECTOR_DIM`` 维；检索时对查询向量与各块向量做**点积**并排序（MVP，未做 L2 归一化）。
"""

import json
import os
from pathlib import Path

from langchain_openai import OpenAIEmbeddings
from services.rag_repo import (
    clear_rag_data,
    create_document,
    delete_document,
    fetch_all_chunks,
    get_document,
    init_rag_tables,
    insert_chunk,
    list_documents,
)

# 与入库时截断维度一致；检索侧向量需同维才能比对
VECTOR_DIM = 256
_embeddings_client: OpenAIEmbeddings | None = None


def _get_embeddings_client() -> OpenAIEmbeddings:
    """
    懒加载单例 Embedding 客户端。

    依赖环境变量：``EMBEDDING_API_KEY``、``EMBEDDING_BASE_URL``、``EMBEDDING_MODEL``。
    ``tiktoken_enabled=False`` 等配置用于兼容部分国产兼容接口。

    Returns:
        配置好的 ``OpenAIEmbeddings`` 实例。

    Raises:
        RuntimeError: 环境变量不完整时。
    """
    global _embeddings_client
    if _embeddings_client is not None:
        return _embeddings_client

    api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    base_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    if not (api_key and base_url and model):
        raise RuntimeError(
            "EMBEDDING_API_KEY / EMBEDDING_BASE_URL / EMBEDDING_MODEL 未配置，"
            "请在 backend/.env 中补充后再使用 RAG。"
        )

    _embeddings_client = OpenAIEmbeddings(
        model=model,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        tiktoken_enabled=False,
        check_embedding_ctx_length=False,
    )
    return _embeddings_client


def _normalize_dim(vec: list[float], dim: int = VECTOR_DIM) -> list[float]:
    """
    将向量截断或零填充到固定维度 ``dim``。

    Args:
        vec: 原始 embedding 列表。
        dim: 目标长度，默认 ``VECTOR_DIM``。

    Returns:
        长度为 ``dim`` 的浮点列表。
    """
    if len(vec) >= dim:
        return [float(x) for x in vec[:dim]]
    padded = [float(x) for x in vec]
    padded.extend([0.0] * (dim - len(padded)))
    return padded


def embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """
    对单段文本生成 embedding 并归一化到 ``dim`` 维。

    Args:
        text: 待编码文本；空串返回全零向量。
        dim: 目标维度。

    Returns:
        浮点向量。
    """
    if not (text or "").strip():
        return [0.0] * dim
    client = _get_embeddings_client()
    vec = client.embed_query(text)
    return _normalize_dim(vec, dim=dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    计算两向量点积，用于检索打分与排序。

    Args:
        a, b: 等长浮点列表。

    Returns:
        点积标量；长度不符或空向量为 ``0.0``。
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> list[str]:
    """
    按固定窗口与重叠长度切分纯文本。

    Args:
        text: 长文本。
        chunk_size: 每块最大字符数（近似）。
        overlap: 相邻块重叠字符数，避免句意被硬切断。

    Returns:
        非空子串列表。
    """
    content = (text or "").strip()
    if not content:
        return []

    chunks = []
    start = 0
    while start < len(content):
        end = min(len(content), start + chunk_size)
        piece = content[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(content):
            break
        start = max(0, end - overlap)
    return chunks


def ingest_document_text(
    source: str,
    title: str,
    text: str,
    file_name: str | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
) -> int:
    """
    将长文本切块、逐块 embedding 后写入数据库。

    Args:
        source: 文档来源标识。
        title: 标题。
        text: 全文。
        file_name, file_path, mime_type, file_size: 上传文件元数据（可选）。

    Returns:
        生成的 chunk 数量；无有效内容时为 ``0``。
    """
    init_rag_tables()
    chunks = chunk_text(text)
    if not chunks:
        return 0
    doc_id = create_document(
        source=source,
        title=title,
        file_name=file_name,
        file_path=file_path,
        mime_type=mime_type,
        file_size=file_size,
    )
    for idx, c in enumerate(chunks):
        insert_chunk(doc_id, idx, c, embed_text(c))
    return len(chunks)


def retrieve_chunks(query: str, top_k: int = 3) -> list[dict]:
    """
    用查询文本的向量与库中所有 chunk 做点积相似度，返回 Top-K。

    Args:
        query: 用户查询或拼接后的检索串。
        top_k: 返回条数，限制在 1～10。

    Returns:
        字典列表，含 ``chunk_id``、``source``、``title``、``text``、``score``（点积分值，越大越靠前）。
    """
    init_rag_tables()
    qv = embed_text(query)
    rows = fetch_all_chunks()
    scored = []
    for row in rows:
        emb = row.get("embedding_json", "[]")
        try:
            vec = json.loads(emb)
        except Exception:
            vec = []
        score = cosine_similarity(qv, vec)
        scored.append(
            {
                "chunk_id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "text": row["chunk_text"],
                "score": round(float(score), 4),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: max(1, min(top_k, 10))]


def list_rag_documents(limit: int = 50, offset: int = 0) -> list[dict]:
    """
    列出 RAG 文档（透传仓储层分页）。

    Args:
        limit: 每页条数。
        offset: 偏移。

    Returns:
        文档字典列表。
    """
    init_rag_tables()
    return list_documents(limit=limit, offset=offset)


def delete_rag_document(document_id: int) -> bool:
    """
    删除文档及 chunk；若记录过 ``file_path`` 则尝试删除磁盘文件。

    Args:
        document_id: 文档 ID。

    Returns:
        是否删除成功（文档存在）。
    """
    init_rag_tables()
    doc = get_document(document_id)
    deleted = delete_document(document_id)
    if deleted and doc and doc.get("file_path"):
        try:
            file_path = Path(str(doc["file_path"]))
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
    return deleted


def clear_rag_knowledge() -> dict:
    """
    清空全部 RAG 文档与 chunk。

    Returns:
        ``clear_rag_data`` 返回的删除计数。
    """
    init_rag_tables()
    return clear_rag_data()
