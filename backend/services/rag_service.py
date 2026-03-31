import json
import os

from langchain_openai import OpenAIEmbeddings
from services.rag_repo import create_document, fetch_all_chunks, init_rag_tables, insert_chunk


VECTOR_DIM = 256
_embeddings_client: OpenAIEmbeddings | None = None


def _get_embeddings_client() -> OpenAIEmbeddings:
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
    if len(vec) >= dim:
        return [float(x) for x in vec[:dim]]
    padded = [float(x) for x in vec]
    padded.extend([0.0] * (dim - len(padded)))
    return padded


def embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    if not (text or "").strip():
        return [0.0] * dim
    client = _get_embeddings_client()
    vec = client.embed_query(text)
    return _normalize_dim(vec, dim=dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list[str]:
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


def ingest_document_text(source: str, title: str, text: str) -> int:
    init_rag_tables()
    chunks = chunk_text(text)
    if not chunks:
        return 0
    doc_id = create_document(source=source, title=title)
    for idx, c in enumerate(chunks):
        insert_chunk(doc_id, idx, c, embed_text(c))
    return len(chunks)


def retrieve_chunks(query: str, top_k: int = 3) -> list[dict]:
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
