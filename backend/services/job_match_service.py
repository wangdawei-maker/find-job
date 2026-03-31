from fastapi import HTTPException

from schemas import JobMatchRequest, JobMatchResponse
from services.deepseek import call_deepseek, extract_json_obj


def job_match_with_llm(payload: JobMatchRequest) -> JobMatchResponse:
    # 让模型直接输出结构化 JSON，前端可以直接渲染
    prompt = f"""
你是招聘顾问，请根据候选人经历和岗位 JD 做匹配分析。
必须只输出 JSON 对象，格式如下：
{{
  "score": 78,
  "advantages": ["优势1", "优势2"],
  "gaps": ["差距1", "差距2"]
}}
要求：
1) score 为 0-100 的整数；
2) advantages 和 gaps 各返回 2-5 条中文要点；
3) 不要输出任何 JSON 以外的内容。

目标岗位：
{payload.target_job}

候选人经历：
{payload.experience}

岗位 JD：
{payload.jd}
""".strip()
    content = call_deepseek(
        [
            {"role": "system", "content": "你是严谨的 JSON 生成助手。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    try:
        parsed = extract_json_obj(content)
        score = int(parsed.get("score", 0))
        score = max(0, min(100, score))
        advantages = [str(x).strip() for x in parsed.get("advantages", []) if str(x).strip()]
        gaps = [str(x).strip() for x in parsed.get("gaps", []) if str(x).strip()]
        if not advantages:
            advantages = ["经历与岗位存在一定契合点，建议继续补充量化成果"]
        if not gaps:
            gaps = ["建议补充与 JD 强相关的项目案例"]
        return JobMatchResponse(score=score, advantages=advantages[:5], gaps=gaps[:5])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Job match JSON parse failed: {exc}") from exc
