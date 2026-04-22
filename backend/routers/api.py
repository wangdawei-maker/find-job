"""
HTTP API 路由（前缀 ``/api``）。

聚合简历诊断、岗位匹配、模拟面试、RAG 导入/检索/管理等端点，
调用 ``services`` 层完成业务逻辑；面试与 RAG 数据落盘至 ``backend/data/app.db``。
RAG 上传的原始文件保存目录：``backend/data/rag_uploads``。
"""

import os
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas import (
    InterviewHistoryItem,
    InterviewHistoryResponse,
    InterviewSessionListResponse,
    InterviewSessionSummary,
    InterviewChatRequest,
    InterviewChatResponse,
    InterviewCompareItem,
    InterviewCompareRequest,
    InterviewCompareResponse,
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
    LlmProviderUpdateRequest,
    LlmProviderResponse,
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


def _bad_request(message: str, code: str = "bad_request", hint: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": code, "message": message, "hint": hint},
    )


def _ensure_ollama_ready() -> None:
    """
    切换 provider 前检查 Ollama 服务可用性与目标模型是否已安装。
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:7b").strip()
    timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))

    try:
        with httpx.Client(timeout=min(timeout_seconds, 5.0)) as client:
            tags_resp = client.get(f"{base_url}/api/tags")
            tags_resp.raise_for_status()
            models = tags_resp.json().get("models", [])
    except Exception as exc:
        raise _bad_request(
            "Ollama 服务不可用，无法切换到 ollama",
            code="ollama_unavailable",
            hint=f"请确认 {base_url} 可访问且已启动 Ollama（error: {exc}）",
        ) from exc

    names = {str(item.get("name", "")) for item in models}
    if model not in names:
        raise _bad_request(
            "Ollama 模型未安装，无法切换到 ollama",
            code="ollama_model_missing",
            hint=f"请先执行 `ollama pull {model}`，当前已安装：{', '.join(sorted(names)) or '无'}",
        )


@router.get("/health")
def health():
    """
    健康检查。

    Returns:
        ``{"ok": true, "deepseek_configured": bool}``，便于排查是否配置 API Key。
    """
    return {"ok": True, "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY"))}


@router.get("/healthz")
def healthz():
    """
    扩展健康检查（含版本与简单依赖状态）。

    Returns:
        ``{"ok": true, "status": "healthy", "version": "...", ...}``。
    """
    return {
        "ok": True,
        "status": "healthy",
        "version": "0.1.0",
        "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        "llm_provider": os.getenv("LLM_PROVIDER", "deepseek").strip().lower() or "deepseek",
    }


@router.get("/llm/provider", response_model=LlmProviderResponse)
def get_llm_provider():
    """
    获取当前 LLM 提供方（运行时）。
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower() or "deepseek"
    if provider not in {"deepseek", "ollama"}:
        provider = "deepseek"
    return LlmProviderResponse(provider=provider)


@router.post("/llm/provider", response_model=LlmProviderResponse)
def set_llm_provider(payload: LlmProviderUpdateRequest):
    """
    切换当前 LLM 提供方（运行时生效，重启后以 .env 为准）。
    """
    provider = payload.provider.strip().lower()
    if provider not in {"deepseek", "ollama"}:
        raise _bad_request("provider 仅支持 deepseek 或 ollama", code="llm_provider_invalid")
    if provider == "ollama":
        _ensure_ollama_ready()
    os.environ["LLM_PROVIDER"] = provider
    return LlmProviderResponse(provider=provider)


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
        raise _bad_request("文件名为空", code="upload_filename_missing", hint="请重新选择文件后上传")
    content = await file.read()
    if not content:
        raise _bad_request("上传文件为空", code="upload_empty_file", hint="请确认文件内容后重试")
    if len(content) > 8 * 1024 * 1024:
        raise _bad_request(
            "文件大小超过 8MB，请压缩后再上传",
            code="upload_file_too_large",
            hint="建议删减附件页或导出纯文本版 PDF/docx",
        )

    text = extract_resume_text(file.filename, content)
    if len(text.strip()) < 10:
        raise _bad_request(
            "提取到的文本过少：该文件可能是扫描图片版 PDF",
            code="upload_text_too_short",
            hint="建议导出可复制文本的 PDF 或 docx",
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
        rag_sources=result.rag_sources,
        reply_kind=result.turn_mode,
    )
    if not payload.debug:
        result.rag_sources = []
    return result


@router.post("/interview/chat-compare", response_model=InterviewCompareResponse)
def interview_chat_compare(payload: InterviewCompareRequest):
    """
    模拟面试 A/B 对比：同一输入分别调用不同 provider，不写入历史。
    """
    session_id = payload.session_id or f"ab_{uuid4().hex}"
    providers = payload.providers or ["deepseek", "ollama"]
    deduped = []
    for p in providers:
        if p not in deduped:
            deduped.append(p)

    base_request = InterviewChatRequest(
        job_title=payload.job_title,
        messages=payload.messages,
        session_id=payload.session_id,
        debug=payload.debug,
        force_ask_interviewer=payload.force_ask_interviewer,
    )
    results: list[InterviewCompareItem] = []
    for provider in deduped:
        try:
            item = interview_chat_with_llm(base_request, session_id=session_id, llm_provider=provider)
            if not payload.debug:
                item.rag_sources = []
            results.append(
                InterviewCompareItem(
                    provider=provider,
                    turn_mode=item.turn_mode,
                    reply=item.reply,
                    score=item.score,
                    strengths=item.strengths,
                    improvements=item.improvements,
                    rag_sources=item.rag_sources,
                )
            )
        except HTTPException as exc:
            results.append(
                InterviewCompareItem(
                    provider=provider,
                    error=str(exc.detail),
                )
            )

    return InterviewCompareResponse(session_id=session_id, results=results)


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
        raise _bad_request("文件名为空", code="upload_filename_missing", hint="请重新选择文件后上传")
    content = await file.read()
    if not content:
        raise _bad_request("上传文件为空", code="upload_empty_file", hint="请确认文件内容后重试")
    if len(content) > 10 * 1024 * 1024:
        raise _bad_request(
            "文件大小超过 10MB，请压缩后再上传",
            code="upload_file_too_large",
            hint="建议拆分文档后分批导入",
        )

    clean_source = (source or "upload").strip()
    clean_title = (title or "").strip() or Path(file.filename).stem
    text = extract_resume_text(file.filename, content)
    if len(text.strip()) < 20:
        raise _bad_request(
            "提取到的文本过少，暂不建议入库",
            code="upload_text_too_short",
            hint="请上传可复制文本的 PDF/docx/txt/md",
        )

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
    top_k = max(1, min(payload.top_k, 10))
    min_score = float(payload.min_score)
    chunks = retrieve_chunks(query=payload.query, top_k=top_k, min_score=min_score)
    return RagRetrieveResponse(
        query=payload.query,
        top_k=top_k,
        min_score=min_score,
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
