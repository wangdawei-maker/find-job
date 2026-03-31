from schemas import InterviewChatRequest, InterviewChatResponse
from services.deepseek import call_deepseek, extract_json_obj
from services.rag_service import retrieve_chunks


def interview_chat_with_llm(payload: InterviewChatRequest, session_id: str) -> InterviewChatResponse:
    # 模拟面试：对用户本轮回答评分并给改进建议，再继续下一问
    system_prompt = (
        "你是一位中文技术面试官，只能根据对话历史做评估。"
        "禁止编造候选人未提及的项目、指标、公司经历。"
        "若信息不足，请在 improvements 中明确写“信息不足，建议补充xxx”。"
        "你不能输出任何 JSON 以外的内容。"
        "输出字段固定为：reply, score, strengths, improvements。"
        "约束：score=0-100整数；strengths/improvements各1-3条；每条不超过40字。"
    )
    latest_user_text = ""
    for msg in reversed(payload.messages):
        if msg.role == "user":
            latest_user_text = msg.content
            break
    query = f"{payload.job_title}\n{latest_user_text}".strip()
    rag_chunks = retrieve_chunks(query=query, top_k=3) if query else []
    rag_context = "\n\n".join(
        [
            f"[{idx + 1}] {c['title']} ({c['source']})\n{c['text']}"
            for idx, c in enumerate(rag_chunks)
        ]
    )
    rag_sources = [f"{c['source']} (score={c['score']})" for c in rag_chunks]

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
    content = call_deepseek(chat_messages, temperature=0.6)
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
            reply=reply,
            score=score,
            strengths=strengths,
            improvements=improvements,
            rag_sources=rag_sources if payload.debug else [],
        )
    except Exception:
        # 兜底：模型输出不符合 JSON 时仍返回可用结果
        return InterviewChatResponse(
            session_id=session_id,
            reply=content.strip() or "请继续介绍一个你最有代表性的项目经历。",
            score=70,
            strengths=["回答有一定条理。"],
            improvements=["建议使用 STAR 结构并加入量化结果。"],
            rag_sources=rag_sources if payload.debug else [],
        )
