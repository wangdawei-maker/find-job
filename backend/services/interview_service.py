"""
模拟面试对话业务。

支持两种回合类型：
- **作答**：对用户回答评分、给改进点，并生成下一题（JSON）。
- **追问面试官**：用户向面试官提问，不评分，仅回复并拉回面试节奏。

分支策略：请求体 ``force_ask_interviewer``（显式）+ ``detect_ask_interviewer_intent``（启发式）。
RAG 片段注入两种分支的 prompt，便于结合 JD/知识库回答。
"""

import logging
import os
import re

from schemas import InterviewChatRequest, InterviewChatResponse
from services.deepseek import call_deepseek, extract_json_obj
from services.rag_service import retrieve_chunks

logger = logging.getLogger(__name__)
PROMPT_DEBUG_ENABLED = os.getenv("INTERVIEW_PROMPT_DEBUG", "false").lower() == "true"


def _last_assistant_before_user(messages: list) -> str:
    """
    取「当前最后一条用户消息」之前、最近一条助手消息的摘要。

    用于追问分支中回顾上一轮面试问题。

    Args:
        messages: 对话列表，元素需含 ``role``、``content``（一般为 ``ChatMessage``）。

    Returns:
        助手消息正文前 800 字符；若无则空字符串。
    """
    seen_user = False
    for msg in reversed(messages):
        if msg.role == "user":
            seen_user = True
            continue
        if seen_user and msg.role == "assistant":
            return (msg.content or "").strip()[:800]
    return ""


def detect_ask_interviewer_intent(latest_user_text: str, force: bool) -> bool:
    """
    判断本轮是否应按「向面试官追问」处理（策略 A：启发式）。

    长文本（>320 字）默认视为作答，减少误判。``force=True`` 时恒为追问。

    Args:
        latest_user_text: 用户本轮输入全文。
        force: 是否由前端显式指定为追问回合。

    Returns:
        ``True`` 走追问分支，``False`` 走作答评分分支。
    """
    if force:
        return True
    text = (latest_user_text or "").strip()
    if not text:
        return False
    if len(text) > 320:
        return False

    if re.match(r"^(请问|想问|想了解一下|能否|是否可以|麻烦问下|咨询一下)", text):
        return True
    if re.match(r"^(你们|咱们|贵司|贵公司|这个岗位|该岗位|团队|部门)", text):
        return True

    has_qmark = text.endswith("？") or text.endswith("?") or "？" in text
    particles = (
        "吗",
        "么",
        "呢",
        "什么",
        "怎么",
        "如何",
        "为啥",
        "为什么",
        "多少",
        "有没有",
        "是否",
        "技术栈",
        "加班",
        "薪资",
        "流程",
    )
    if has_qmark and any(p in text for p in particles):
        return True
    if has_qmark and len(text) <= 72:
        return True
    return False


def _build_rag_block(query: str) -> tuple[str, list[str]]:
    """
    按查询文本做向量检索，拼出注入 prompt 的上下文与来源列表。

    Args:
        query: 检索查询串（通常含岗位名 + 用户输入 ± 上轮问题摘要）。

    Returns:
        ``(rag_context, rag_sources)``：前者为多段文本块拼接，后者为 ``source (score=...)`` 字符串列表。
    """
    rag_chunks = retrieve_chunks(query=query, top_k=3) if query.strip() else []
    rag_context = "\n\n".join(
        [
            f"[{idx + 1}] {c['title']} ({c['source']})\n{c['text']}"
            for idx, c in enumerate(rag_chunks)
        ]
    )
    rag_sources = [f"{c['source']} (score={c['score']})" for c in rag_chunks]
    return rag_context, rag_sources


def _run_answer_turn(
    payload: InterviewChatRequest,
    session_id: str,
    rag_context: str,
    rag_sources: list[str],
) -> list[dict]:
    """
    组装「作答回合」发给模型的 messages（含 system、历史、最后 user 指令）。

    Args:
        payload: 面试请求（含 ``job_title``、``messages``）。
        session_id: 当前会话 ID（本函数未直接使用，保留签名便于扩展日志）。
        rag_context: RAG 拼接正文。
        rag_sources: 来源列表（本函数未直接使用，保留签名与调用方一致）。

    Returns:
        OpenAI 格式的 ``messages`` 列表。
    """
    _ = session_id, rag_sources
    system_prompt = (
        "你是一位中文技术面试官，只能根据对话历史做评估。"
        "禁止编造候选人未提及的项目、指标、公司经历。"
        "若信息不足，请在 improvements 中明确写“信息不足，建议补充xxx”。"
        "你不能输出任何 JSON 以外的内容。"
        "输出字段固定为：reply, score, strengths, improvements。"
        "约束：score=0-100整数；strengths/improvements各1-3条；每条不超过40字。"
    )
    chat_messages = [{"role": "system", "content": system_prompt}]
    chat_messages.extend([{"role": m.role, "content": m.content} for m in payload.messages])
    chat_messages.append(
        {
            "role": "user",
            "content": (
                f"当前应聘岗位：{payload.job_title}。"
                f"\n可参考知识片段（若为空则忽略）：\n{rag_context or '无'}\n"
                "请只针对我「最近一次」用户回答做评估，并给出下一题。"
                "评分 score 必须按以下维度综合打分（0-100 整数；不要固定给 80、85、90 这类常见分数）："
                "相关性（是否答到点）、完整性（结构/要点）、证据性（是否有具体项目/数据/结果）、"
                "表达清晰度。回答越空泛、越短、越缺证据则分数越低。"
                "输出严格 JSON，且仅含这些键："
                '{"reply":"<下一题问题>","score":<整数>,"strengths":"<数组>","improvements":"<数组>"}。'
                "strengths/improvements 各 1-3 条。"
            ),
        }
    )
    return chat_messages


def _run_ask_interviewer_turn(
    payload: InterviewChatRequest,
    session_id: str,
    rag_context: str,
    rag_sources: list[str],
    latest_user_text: str,
) -> list[dict]:
    """
    组装「追问面试官」回合的 messages。

    Args:
        payload: 面试请求。
        session_id: 会话 ID（占位，便于扩展）。
        rag_context: RAG 拼接正文。
        rag_sources: 来源列表（占位）。
        latest_user_text: 用户本轮追问内容。

    Returns:
        OpenAI 格式的 ``messages`` 列表；模型应只输出 ``{"reply":"..."}``。
    """
    _ = session_id, rag_sources
    last_q = _last_assistant_before_user(payload.messages)
    system_prompt = (
        "你是中文技术面试官，正在面试候选人。"
        "候选人本轮是在向你提问（岗位、团队、流程、技术栈、工作方式等），不是在回答面试题。"
        "要求：\n"
        "1) 仅结合对话历史与参考知识作答；参考知识为空或不足时，明确说明公开信息未提及，建议其向 HR 或现场面试官确认。\n"
        "2) 禁止编造内部制度、具体薪资数字、未公开的团队规模等。\n"
        "3) 回答简洁专业，优先 200 字以内。\n"
        "4) 结尾用一句话把对话拉回面试，例如邀请其继续回答你上一轮提出的面试问题（可简要复述该问题）。\n"
        "你不能输出任何 JSON 以外的内容。"
        '输出严格 JSON，且仅含键：{"reply":"<你的答复>"}。'
    )
    chat_messages = [{"role": "system", "content": system_prompt}]
    chat_messages.extend([{"role": m.role, "content": m.content} for m in payload.messages])
    hint = f"我上一轮面试问题摘要（若有）：{last_q or '（无，可请候选人说明指哪一题）'}"
    chat_messages.append(
        {
            "role": "user",
            "content": (
                f"当前应聘岗位：{payload.job_title}。\n{hint}\n"
                f"候选人追问：{latest_user_text}\n"
                f"可参考知识片段（若为空则忽略）：\n{rag_context or '无'}\n"
                "请作为面试官直接回复候选人。"
            ),
        }
    )
    return chat_messages


def interview_chat_with_llm(payload: InterviewChatRequest, session_id: str) -> InterviewChatResponse:
    """
    模拟面试核心：根据回合类型调用 DeepSeek，返回结构化响应。

    Args:
        payload: 含 ``job_title``、``messages``、``debug``、``force_ask_interviewer``。
        session_id: 当前会话 ID（写入响应供前端持久化）。

    Returns:
        ``InterviewChatResponse``：``turn_mode`` 为 ``answer`` 或 ``ask_interviewer``；
        追问时 ``score`` 为 ``None``，``strengths``/``improvements`` 为空列表。
    """
    latest_user_text = ""
    for msg in reversed(payload.messages):
        if msg.role == "user":
            latest_user_text = msg.content
            break

    is_ask = detect_ask_interviewer_intent(latest_user_text, payload.force_ask_interviewer)
    last_snip = _last_assistant_before_user(payload.messages)
    if is_ask:
        query = f"{payload.job_title}\n{latest_user_text}\n{last_snip}".strip()
    else:
        query = f"{payload.job_title}\n{latest_user_text}".strip()

    rag_context, rag_sources = _build_rag_block(query)

    if is_ask:
        chat_messages = _run_ask_interviewer_turn(
            payload, session_id, rag_context, rag_sources, latest_user_text
        )
    else:
        chat_messages = _run_answer_turn(payload, session_id, rag_context, rag_sources)

    if PROMPT_DEBUG_ENABLED:
        prompt_tail = chat_messages[-1]["content"][:1200]
        logger.warning(
            "Interview prompt debug | turn=%s | force_ask=%s | query=%s | rag_sources=%s",
            "ask_interviewer" if is_ask else "answer",
            payload.force_ask_interviewer,
            query[:200],
            rag_sources,
        )
        logger.warning("Interview prompt tail:\n%s", prompt_tail)

    content = call_deepseek(chat_messages, temperature=0.55 if is_ask else 0.6)

    if is_ask:
        try:
            parsed = extract_json_obj(content)
            reply = str(parsed.get("reply", "")).strip() or "这个问题我这边没有更细的公开信息，建议你向 HR 确认。我们先回到面试，请你继续说说上一题的思路。"
        except Exception:
            reply = content.strip() or "我们先回到面试，请你继续完成上一题的回答。"
        return InterviewChatResponse(
            session_id=session_id,
            turn_mode="ask_interviewer",
            reply=reply,
            score=None,
            strengths=[],
            improvements=[],
            rag_sources=rag_sources if payload.debug else [],
        )

    try:
        parsed = extract_json_obj(content)
        reply = str(parsed.get("reply", "")).strip() or "请继续介绍一个你最有代表性的项目经历。"
        score = int(parsed.get("score", 70))
        score = max(0, min(100, score))
        strengths = [str(x).strip() for x in parsed.get("strengths", []) if str(x).strip()][:3]
        improvements = [str(x).strip() for x in parsed.get("improvements", []) if str(x).strip()][:3]
        if not strengths:
            strengths = ["表达比较完整，基本覆盖了问题核心。"]
        if not improvements:
            improvements = ["可以补充更具体的数据指标和结果。"]
        return InterviewChatResponse(
            session_id=session_id,
            turn_mode="answer",
            reply=reply,
            score=score,
            strengths=strengths,
            improvements=improvements,
            rag_sources=rag_sources if payload.debug else [],
        )
    except Exception:
        return InterviewChatResponse(
            session_id=session_id,
            turn_mode="answer",
            reply=content.strip() or "请继续介绍一个你最有代表性的项目经历。",
            score=70,
            strengths=["回答有一定条理。"],
            improvements=["建议使用 STAR 结构并加入量化结果。"],
            rag_sources=rag_sources if payload.debug else [],
        )
