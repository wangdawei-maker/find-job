from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ResumeDiagnosisRequest(BaseModel):
    # 前端“文本输入诊断”时传入的简历文本
    experience: str


class ResumeDiagnosisResponse(BaseModel):
    # 返回给前端的建议列表
    suggestions: List[str]


class JobMatchRequest(BaseModel):
    # 候选人经历 + 目标岗位 + JD
    experience: str
    target_job: str
    jd: str


class JobMatchResponse(BaseModel):
    # 匹配结果：分数 + 优势 + 差距
    score: int
    advantages: List[str]
    gaps: List[str]


class ChatMessage(BaseModel):
    # 模拟面试消息，角色必须是 user / assistant
    role: Literal["user", "assistant"]
    content: str


class InterviewChatRequest(BaseModel):
    # 模拟面试请求：岗位名称 + 历史消息
    job_title: str
    messages: List[ChatMessage]
    # 会话ID（用于持久化同一场面试）
    session_id: Optional[str] = None
    # 调试开关：开启后返回命中的 RAG 来源
    debug: bool = False


class InterviewChatResponse(BaseModel):
    # 会话ID
    session_id: str
    # 面试官下一轮问题
    reply: str
    # 本轮回答评分（0-100）
    score: int
    # 候选人回答亮点
    strengths: List[str]
    # 候选人回答可改进点
    improvements: List[str]
    # 调试信息（仅 debug=true 时返回）
    rag_sources: List[str] = Field(default_factory=list)


class InterviewHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    score: Optional[int] = None
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    created_at: str


class InterviewHistoryResponse(BaseModel):
    session_id: str
    job_title: str
    messages: List[InterviewHistoryItem]


class InterviewSessionSummary(BaseModel):
    session_id: str
    job_title: str
    created_at: str
    updated_at: str
    message_count: int


class InterviewSessionListResponse(BaseModel):
    sessions: List[InterviewSessionSummary]
    total: int
    offset: int
    limit: int
    has_more: bool


class RagIngestTextRequest(BaseModel):
    source: str
    title: str
    text: str


class RagIngestResponse(BaseModel):
    source: str
    title: str
    chunks_count: int


class RagRetrieveRequest(BaseModel):
    query: str
    top_k: int = 3


class RagChunk(BaseModel):
    chunk_id: int
    source: str
    title: str
    text: str
    score: float


class RagRetrieveResponse(BaseModel):
    query: str
    chunks: List[RagChunk]
