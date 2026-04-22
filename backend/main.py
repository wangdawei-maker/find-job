"""
AI Job Copilot 后端入口。

负责创建 FastAPI 应用、加载环境变量、配置 CORS，并挂载 ``/api`` 路由。
运行方式：在 ``backend`` 目录执行 ``uvicorn main:app --reload``。
"""

import logging
import time
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers.api import router as api_router

load_dotenv()

app = FastAPI(title="AI Job Copilot API", version="0.1.0")
logger = logging.getLogger("app.http")

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


def _error_body(code: str, message: str, hint: str | None, request_id: str) -> dict:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "hint": hint,
            "request_id": request_id,
        },
    }


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "request_done request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = "请求失败"
    code = "bad_request" if exc.status_code < 500 else "server_error"
    hint = None
    if isinstance(detail, dict):
        message = str(detail.get("message", message))
        code = str(detail.get("code", code))
        hint = detail.get("hint")
    elif isinstance(detail, str):
        message = detail
    request_id = getattr(request.state, "request_id", uuid4().hex[:12])
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code=code, message=message, hint=hint, request_id=request_id),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", uuid4().hex[:12])
    logger.exception("unhandled_exception request_id=%s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_body(
            code="internal_error",
            message="服务内部错误，请稍后重试",
            hint="若持续出现，请联系管理员并提供 request_id",
            request_id=request_id,
        ),
    )
