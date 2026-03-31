import os

from fastapi import APIRouter, File, HTTPException, UploadFile

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
from services.rag_service import ingest_document_text, retrieve_chunks

router = APIRouter(prefix="/api")
init_interview_tables()


@router.get("/health")
def health():
    # 健康检查，同时返回是否已配置 DeepSeek key，方便排查环境问题
    return {"ok": True, "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY"))}


@router.post("/resume-diagnosis", response_model=ResumeDiagnosisResponse)
def resume_diagnosis(payload: ResumeDiagnosisRequest):
    # 文本输入版本的简历诊断
    return resume_suggestions_from_text(payload.experience)


@router.post("/resume-diagnosis/upload", response_model=ResumeDiagnosisResponse)
async def resume_diagnosis_upload(file: UploadFile = File(...)):
    # 文件上传版本：读取文件 -> 提取文本 -> 走同一诊断逻辑
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
    # 限制送入模型的长度，避免超长输入导致成本和延迟升高
    return resume_suggestions_from_text(text[:12000])


@router.post("/job-match", response_model=JobMatchResponse)
def job_match(payload: JobMatchRequest):
    return job_match_with_llm(payload)


@router.post("/interview/chat", response_model=InterviewChatResponse)
def interview_chat(payload: InterviewChatRequest):
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
    )
    return result


@router.get("/interview/history/{session_id}", response_model=InterviewHistoryResponse)
def interview_history(session_id: str):
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
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


@router.post("/rag/ingest-text", response_model=RagIngestResponse)
def rag_ingest_text(payload: RagIngestTextRequest):
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


@router.post("/rag/retrieve", response_model=RagRetrieveResponse)
def rag_retrieve(payload: RagRetrieveRequest):
    chunks = retrieve_chunks(query=payload.query, top_k=payload.top_k)
    return RagRetrieveResponse(
        query=payload.query,
        chunks=[RagChunk(**item) for item in chunks],
    )
