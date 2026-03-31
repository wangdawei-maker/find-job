from typing import List, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AI Job Copilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResumeDiagnosisRequest(BaseModel):
    experience: str


class ResumeDiagnosisResponse(BaseModel):
    suggestions: List[str]


class JobMatchRequest(BaseModel):
    experience: str
    target_job: str
    jd: str


class JobMatchResponse(BaseModel):
    score: int
    advantages: List[str]
    gaps: List[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class InterviewChatRequest(BaseModel):
    job_title: str
    messages: List[ChatMessage]


class InterviewChatResponse(BaseModel):
    reply: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/resume-diagnosis", response_model=ResumeDiagnosisResponse)
def resume_diagnosis(payload: ResumeDiagnosisRequest):
    text = payload.experience.strip()
    length_tip = "补充可量化成果（如提升 xx%、节省 xx 小时）"
    if len(text) > 120:
        length_tip = "内容较完整，下一步可按 STAR 结构重写每段经历"
    return ResumeDiagnosisResponse(
        suggestions=[
            "开头增加一句职业定位，明确你要应聘的方向",
            length_tip,
            "为每段经历补充技术栈关键词，方便 ATS 检索",
        ]
    )


@app.post("/api/job-match", response_model=JobMatchResponse)
def job_match(payload: JobMatchRequest):
    exp = payload.experience.lower()
    jd = payload.jd.lower()
    common_keywords = ["python", "react", "llm", "fastapi", "sql", "docker"]

    hit = [kw for kw in common_keywords if kw in exp and kw in jd]
    miss = [kw for kw in common_keywords if kw in jd and kw not in exp]
    score = min(95, 45 + len(hit) * 10 - len(miss) * 3)
    score = max(20, score)

    advantages = [f"已具备 {kw} 相关经历" for kw in hit] or ["工程经验描述较完整"]
    gaps = [f"建议补充 {kw} 的项目实践" for kw in miss] or ["可补充更具体的业务成果指标"]

    return JobMatchResponse(score=score, advantages=advantages, gaps=gaps)


@app.post("/api/interview/chat", response_model=InterviewChatResponse)
def interview_chat(payload: InterviewChatRequest):
    user_messages = [m.content for m in payload.messages if m.role == "user"]
    latest = user_messages[-1] if user_messages else ""
    prompt = (
        f"你刚提到：{latest[:80]}。"
        f"下一题（岗位：{payload.job_title}）：请讲一个你主导解决复杂问题的案例，"
        "重点说明背景、行动、结果。"
    )
    return InterviewChatResponse(reply=prompt)
