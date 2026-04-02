"""
HTTP API 路由（前缀 ``/api``）。

聚合简历诊断、岗位匹配、模拟面试、RAG 导入/检索/管理等端点，
调用 ``services`` 层完成业务逻辑；面试与 RAG 数据落盘至 ``backend/data/app.db``。
RAG 上传的原始文件保存目录：``backend/data/rag_uploads``。
"""

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas import (
    InterviewHistoryItem,
    InterviewHistoryResponse,
    InterviewSessionListResponse,
    InterviewSessionSummary,
    InterviewChatRequest,
    InterviewChatResponse,
    JobMatchRequest,
    JobMatchResponse,
    ResumeDiagnosisRequest,
    ResumeDiagnosisResponse,
    RagChunk,
    RagIngestResponse,
    RagIngestTextRequest,
    RagRetrieveRequest,
    RagRetrieveResponse,
    RagDocumentItem,
    RagDocumentListResponse,
    RagDeleteResponse,
    RagClearResponse,
)
from services.interview_repo import (
    delete_session,
    ensure_session,
    get_history,
    init_interview_tables,
    list_sessions,
    save_message,
)
from services.interview_service import interview_chat_with_llm
from services.job_match_service import job_match_with_llm
from services.resume_parser import extract_resume_text
from services.resume_service import resume_suggestions_from_text
from services.rag_service import (
    clear_rag_knowledge,
    delete_rag_document,
    ingest_document_text,
    list_rag_documents,
    retrieve_chunks,
)

router = APIRouter(prefix="/api")
init_interview_tables()
RAG_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "rag_uploads"


@router.get("/health")
def health():
    """
    健康检查。

    Returns:
        ``{"ok": true, "deepseek_configured": bool}``，便于排查是否配置 API Key。
    """
    return {"ok": True, "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY"))}


@router.post("/resume-diagnosis", response_model=ResumeDiagnosisResponse)
def resume_diagnosis(payload: ResumeDiagnosisRequest):
    """
    简历诊断（纯文本）。

    Args:
        payload: ``experience`` 为简历/经历正文。

    Returns:
        ``ResumeDiagnosisResponse``：优化建议列表。
    """
    return resume_suggestions_from_text(payload.experience)


@router.post("/resume-diagnosis/upload", response_model=ResumeDiagnosisResponse)
async def resume_diagnosis_upload(file: UploadFile = File(...)):
    """
    简历诊断（文件上传）。

    Args:
        file: ``pdf`` / ``docx`` / ``txt`` / ``md``，最大 8MB。

    Returns:
        解析文本后走同一诊断逻辑。

    Raises:
        HTTPException: 文件名空、过大、解析失败或文本过短。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过 8MB，请压缩后再上传")

    text = extract_resume_text(file.filename, content)
    if len(text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="提取到的文本过少：该文件可能是扫描图片版 PDF，建议导出可复制文本的 PDF 或 docx",
        )
    return resume_suggestions_from_text(text[:12000])


@router.post("/job-match", response_model=JobMatchResponse)
def job_match(payload: JobMatchRequest):
    """
    岗位匹配分析。

    Args:
        payload: 经历、目标岗位、JD 全文。

    Returns:
        匹配分数与优劣势要点。
    """
    return job_match_with_llm(payload)


@router.post("/interview/chat", response_model=InterviewChatResponse)
def interview_chat(payload: InterviewChatRequest):
    """
    模拟面试单轮对话。

    根据 ``force_ask_interviewer`` 与启发式判断作答或追问分支；持久化用户与助手消息。

    Args:
        payload: 岗位、消息列表、可选 ``session_id``、``debug``、``force_ask_interviewer``。

    Returns:
        ``InterviewChatResponse``，含 ``turn_mode``、可选评分与 RAG 来源。
    """
    session_id = ensure_session(payload.job_title, payload.session_id)
    result = interview_chat_with_llm(payload, session_id=session_id)

    latest_user = ""
    for msg in reversed(payload.messages):
        if msg.role == "user":
            latest_user = msg.content.strip()
            break
    if latest_user:
        save_message(session_id, "user", latest_user)
    save_message(
        session_id,
        "assistant",
        result.reply,
        score=result.score,
        strengths=result.strengths,
        improvements=result.improvements,
        reply_kind=result.turn_mode,
    )
    return result


@router.get("/interview/history/{session_id}", response_model=InterviewHistoryResponse)
def interview_history(session_id: str):
    """
    拉取某会话完整消息历史。

    Args:
        session_id: 会话 ID。

    Returns:
        岗位名与消息列表（含 ``reply_kind``）。

    Raises:
        HTTPException: 404 会话不存在。
    """
    job_title, history = get_history(session_id)
    if job_title is None:
        raise HTTPException(status_code=404, detail="session not found")
    return InterviewHistoryResponse(
        session_id=session_id,
        job_title=job_title,
        messages=[InterviewHistoryItem(**item) for item in history],
    )


@router.get("/interview/sessions", response_model=InterviewSessionListResponse)
def interview_sessions(limit: int = 20, offset: int = 0):
    """
    分页列出面试会话摘要。

    Args:
        limit: 每页条数（上限 100）。
        offset: 偏移。

    Returns:
        会话列表及分页元数据。
    """
    sessions = list_sessions(limit=limit, offset=offset)
    page_limit = max(1, min(limit, 100))
    page_offset = max(0, offset)
    return InterviewSessionListResponse(
        sessions=[InterviewSessionSummary(**item) for item in sessions],
        total=len(sessions),
        offset=page_offset,
        limit=page_limit,
        has_more=len(sessions) == page_limit,
    )


@router.delete("/interview/sessions/{session_id}")
def interview_delete_session(session_id: str):
    """
    删除指定会话及下属消息。

    Args:
        session_id: 会话 ID。

    Returns:
        ``{"ok": true}``；不存在则 404。
    """
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


@router.post("/rag/ingest-text", response_model=RagIngestResponse)
def rag_ingest_text(payload: RagIngestTextRequest):
    """
    RAG：直接导入一段纯文本（切块 + embedding + 入库）。

    Args:
        payload: ``source``、``title``、``text``。

    Returns:
        导入结果及 chunk 数量。
    """
    chunks_count = ingest_document_text(
        source=payload.source.strip(),
        title=payload.title.strip(),
        text=payload.text,
    )
    return RagIngestResponse(
        source=payload.source.strip(),
        title=payload.title.strip(),
        chunks_count=chunks_count,
    )


@router.post("/rag/ingest-file", response_model=RagIngestResponse)
async def rag_ingest_file(
    file: UploadFile = File(...),
    source: str = Form("upload"),
    title: str = Form(""),
):
    """
    RAG：上传文件解析后入库，并将原始文件保存到 ``data/rag_uploads``。

    Args:
        file: ``pdf`` / ``docx`` / ``txt`` / ``md``，最大 10MB。
        source: 表单字段，文档来源标识，默认 ``upload``。
        title: 表单字段，展示标题；空则用文件名去后缀。

    Returns:
        导入结果及 chunk 数量。

    Raises:
        HTTPException: 校验或解析失败。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB，请压缩后再上传")

    clean_source = (source or "upload").strip()
    clean_title = (title or "").strip() or Path(file.filename).stem
    text = extract_resume_text(file.filename, content)
    if len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="提取到的文本过少，暂不建议入库")

    safe_name = Path(file.filename).name
    save_name = f"{uuid4().hex}_{safe_name}"
    RAG_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = RAG_UPLOAD_DIR / save_name
    saved_path.write_bytes(content)

    chunks_count = ingest_document_text(
        source=clean_source,
        title=clean_title,
        text=text[:50000],
        file_name=safe_name,
        file_path=str(saved_path),
        mime_type=file.content_type,
        file_size=len(content),
    )
    return RagIngestResponse(source=clean_source, title=clean_title, chunks_count=chunks_count)


@router.post("/rag/retrieve", response_model=RagRetrieveResponse)
def rag_retrieve(payload: RagRetrieveRequest):
    """
    RAG：调试/管理用向量检索。

    Args:
        payload: ``query``、``top_k``（可选）。

    Returns:
        Top-K chunk 及相似度分值。
    """
    chunks = retrieve_chunks(query=payload.query, top_k=payload.top_k)
    return RagRetrieveResponse(
        query=payload.query,
        chunks=[RagChunk(**item) for item in chunks],
    )


@router.get("/rag/documents", response_model=RagDocumentListResponse)
def rag_documents(limit: int = 50, offset: int = 0):
    """
    RAG：分页列出已入库文档。

    Args:
        limit: 每页条数（上限 200）。
        offset: 偏移。

    Returns:
        文档列表及分页信息。
    """
    docs = list_rag_documents(limit=limit, offset=offset)
    page_limit = max(1, min(limit, 200))
    page_offset = max(0, offset)
    return RagDocumentListResponse(
        documents=[RagDocumentItem(**item) for item in docs],
        total=len(docs),
        offset=page_offset,
        limit=page_limit,
        has_more=len(docs) == page_limit,
    )


@router.delete("/rag/documents/{document_id}", response_model=RagDeleteResponse)
def rag_delete_document(document_id: int):
    """
    RAG：按文档 ID 删除（含 chunk 及可选磁盘文件）。

    Args:
        document_id: ``rag_documents.id``。

    Returns:
        ``RagDeleteResponse``；不存在则 404。
    """
    deleted = delete_rag_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="document not found")
    return RagDeleteResponse(ok=True)


@router.post("/rag/clear", response_model=RagClearResponse)
def rag_clear():
    """
    RAG：清空全部文档与 chunk（不可恢复）。

    Returns:
        删除计数统计。
    """
    result = clear_rag_knowledge()
    return RagClearResponse(ok=True, **result)
