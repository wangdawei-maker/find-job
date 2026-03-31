import json
import os
import re

import httpx
from fastapi import HTTPException


def extract_json_obj(text: str) -> dict:
    # DeepSeek 有时会返回 ```json ... ``` 包裹的内容，先尝试提取 fenced JSON
    fence_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    # 否则尝试在整段文本里抓第一个 JSON 对象
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        return json.loads(obj_match.group(0))

    # 最后兜底：假设整个字符串就是 JSON
    return json.loads(text)


def call_deepseek(messages: list[dict], temperature: float = 0.3, timeout_seconds: float | None = None) -> str:
    # 从 .env 读取 DeepSeek 配置
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="DEEPSEEK_API_KEY is missing. Please set it in backend/.env",
        )

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    request_timeout = timeout_seconds
    if request_timeout is None:
        request_timeout = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "40"))

    try:
        # 这里使用兼容 OpenAI Chat Completions 的请求格式
        with httpx.Client(timeout=request_timeout) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"DeepSeek request failed: {exc}") from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="DeepSeek response format invalid") from exc
