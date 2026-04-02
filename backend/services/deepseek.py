"""
DeepSeek 聊天补全封装。

从环境变量读取 ``DEEPSEEK_API_KEY``、``DEEPSEEK_BASE_URL``、``DEEPSEEK_MODEL``，
使用与 OpenAI Chat Completions 兼容的 HTTP 接口调用模型。
"""

import json
import os
import re

import httpx
from fastapi import HTTPException


def extract_json_obj(text: str) -> dict:
    """
    从模型返回的字符串中解析出第一个 JSON 对象。

    兼容：`` ```json ... ``` `` 代码块、正文中的 ``{...}``、或整段即为 JSON。

    Args:
        text: 模型原始输出文本。

    Returns:
        解析后的 ``dict``。

    Raises:
        json.JSONDecodeError: 无法解析为 JSON 时由 ``json.loads`` 抛出。
    """
    fence_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        return json.loads(obj_match.group(0))

    return json.loads(text)


def call_deepseek(
    messages: list[dict],
    temperature: float = 0.3,
    timeout_seconds: float | None = None,
) -> str:
    """
    调用 DeepSeek Chat Completions，返回助手消息正文。

    Args:
        messages: OpenAI 格式的消息列表，每项含 ``role``、``content``。
        temperature: 采样温度，越高越随机。
        timeout_seconds: 请求超时（秒）；为 ``None`` 时使用 ``DEEPSEEK_TIMEOUT_SECONDS`` 环境变量，默认 40。

    Returns:
        模型回复的纯文本内容。

    Raises:
        HTTPException: 未配置 API Key、HTTP 错误或响应结构异常时抛出。
    """
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
        with httpx.Client(timeout=request_timeout) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"DeepSeek request failed: {exc}") from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="DeepSeek response format invalid") from exc
