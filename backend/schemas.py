"""
Pydantic 请求/响应模型。

与 FastAPI 路由配合做校验与 OpenAPI 文档生成；字段含义与前后端契约保持一致。
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ResumeDiagnosisRequest(BaseModel):
    """简历诊断请求（文本）。"""

    experience: str
    """候选人经历或简历正文。"""


class ResumeDiagnosisResponse(BaseModel):
    """简历诊断响应。"""

    suggestions: List[str]
    """3～6 条可执行的优化建议。"""


class JobMatchRequest(BaseModel):
    """岗位匹配请求。"""

    experience: str
    """候选人经历摘要。"""
    target_job: str
    """目标岗位名称或方向。"""
    jd: str
    """岗位 JD 全文。"""


class JobMatchResponse(BaseModel):
    """岗位匹配响应。"""

    score: int
    """匹配度 0～100。"""
    advantages: List[str]
    """相对 JD 的优势点。"""
    gaps: List[str]
    """待补足或弱项。"""


class ChatMessage(BaseModel):
    """单条对话消息。"""

    role: Literal["user", "assistant"]
    """发言角色。"""
    content: str
    """消息正文。"""


class InterviewChatRequest(BaseModel):
    """模拟面试单轮请求。"""

    job_title: str
    """应聘岗位名称。"""
    messages: List[ChatMessage]
    """完整对话历史（含本轮用户消息）。"""
    session_id: Optional[str] = None
    """已有会话 ID；空则服务端新建。"""
    debug: bool = False
    """为 True 时在响应中返回 RAG 命中来源摘要。"""
    force_ask_interviewer: bool = False
    """为 True 时本回合强制按「向面试官追问」处理，不参与作答评分。"""


class InterviewChatResponse(BaseModel):
    """模拟面试单轮响应。"""

    session_id: str
    """当前会话 ID。"""
    turn_mode: Literal["answer", "ask_interviewer"] = "answer"
    """answer：作答评估；ask_interviewer：追问面试官答复。"""
    reply: str
    """助手回复正文（下一题或追问答复）。"""
    score: Optional[int] = None
    """作答得分 0～100；追问模式下为 None。"""
    strengths: List[str] = Field(default_factory=list)
    """亮点；追问模式通常为空。"""
    improvements: List[str] = Field(default_factory=list)
    """改进建议；追问模式通常为空。"""
    rag_sources: List[str] = Field(default_factory=list)
    """debug 为 True 时的 RAG 来源列表。"""


class InterviewHistoryItem(BaseModel):
    """历史中的一条消息。"""

    role: Literal["user", "assistant"]
    content: str
    score: Optional[int] = None
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    created_at: str
    reply_kind: Literal["answer", "ask_interviewer"] = "answer"
    """与 ``turn_mode`` 对应，用于前端区分是否展示评分区。"""


class InterviewHistoryResponse(BaseModel):
    """某会话完整历史。"""

    session_id: str
    job_title: str
    messages: List[InterviewHistoryItem]


class InterviewSessionSummary(BaseModel):
    """会话列表中单条摘要。"""

    session_id: str
    job_title: str
    created_at: str
    updated_at: str
    message_count: int


class InterviewSessionListResponse(BaseModel):
    """会话分页列表。"""

    sessions: List[InterviewSessionSummary]
    total: int
    offset: int
    limit: int
    has_more: bool


class RagIngestTextRequest(BaseModel):
    """RAG 文本导入请求。"""

    source: str
    """来源标识（如文件名、业务标签）。"""
    title: str
    """文档标题。"""
    text: str
    """待切块入库的全文。"""


class RagIngestResponse(BaseModel):
    """RAG 导入结果。"""

    source: str
    title: str
    chunks_count: int
    """写入的 chunk 条数。"""


class RagRetrieveRequest(BaseModel):
    """RAG 检索请求。"""

    query: str
    top_k: int = 3
    """返回前 K 条，服务端还会做上下限裁剪。"""


class RagChunk(BaseModel):
    """检索到的一条知识块。"""

    chunk_id: int
    source: str
    title: str
    text: str
    score: float
    """检索相似度分值。"""


class RagRetrieveResponse(BaseModel):
    """RAG 检索响应。"""

    query: str
    chunks: List[RagChunk]


class RagDocumentItem(BaseModel):
    """RAG 文档列表中单条记录。"""

    id: int
    source: str
    title: str
    created_at: str
    chunk_count: int
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class RagDocumentListResponse(BaseModel):
    """RAG 文档分页列表。"""

    documents: List[RagDocumentItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class RagDeleteResponse(BaseModel):
    """删除文档结果。"""

    ok: bool


class RagClearResponse(BaseModel):
    """清空 RAG 库结果。"""

    ok: bool
    documents_deleted: int
    chunks_deleted: int
