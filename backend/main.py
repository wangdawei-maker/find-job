"""
AI Job Copilot 后端入口。

负责创建 FastAPI 应用、加载环境变量、配置 CORS，并挂载 ``/api`` 路由。
运行方式：在 ``backend`` 目录执行 ``uvicorn main:app --reload``。
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.api import router as api_router

load_dotenv()

app = FastAPI(title="AI Job Copilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
