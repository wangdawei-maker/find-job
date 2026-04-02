"""
简历诊断业务逻辑。

将候选人经历文本交给 DeepSeek，解析为结构化建议列表。
"""

from fastapi import HTTPException

from schemas import ResumeDiagnosisResponse
from services.deepseek import call_deepseek, extract_json_obj


def build_resume_prompt(experience: str) -> str:
    """
    构造简历诊断的用户提示词。

    Args:
        experience: 候选人经历正文。

    Returns:
        发给模型的完整 prompt 字符串。
    """
    return f"""
你是资深求职顾问。请基于候选人经历给出简历优化建议。
必须只输出 JSON 对象，格式如下：
{{
  "suggestions": ["建议1", "建议2", "建议3"]
}}
要求：
1) suggestions 返回 3-6 条中文建议；
2) 建议要具体、可执行；
3) 不要输出任何 JSON 以外的内容。

候选人经历：
{experience}
""".strip()


def resume_suggestions_from_text(experience: str) -> ResumeDiagnosisResponse:
    """
    根据经历文本生成简历优化建议。

    Args:
        experience: 简历或经历描述（已由上游限制长度时可切片）。

    Returns:
        ``ResumeDiagnosisResponse``，含 ``suggestions`` 列表（最多 6 条）。

    Raises:
        HTTPException: 模型返回无法解析或 ``suggestions`` 无效时，502。
    """
    prompt = build_resume_prompt(experience)
    content = call_deepseek(
        [
            {"role": "system", "content": "你是严谨的 JSON 生成助手。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    try:
        parsed = extract_json_obj(content)
        suggestions = parsed.get("suggestions", [])
        if not isinstance(suggestions, list) or not suggestions:
            raise ValueError("suggestions invalid")
        suggestions = [str(x).strip() for x in suggestions if str(x).strip()]
        return ResumeDiagnosisResponse(suggestions=suggestions[:6])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Resume JSON parse failed: {exc}") from exc
