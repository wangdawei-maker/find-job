# Architecture Overview

一句话架构：**React 前端通过统一 `/api` 入口调用 FastAPI 后端；后端以“可切换 LLM（DeepSeek/Ollama）+ SQLite（会话/RAG）”实现求职场景能力，前端容器内 Nginx 负责静态托管与 API 反向代理。**

## 1) 系统组成

- `frontend`（React + Vite）
  - 页面：简历诊断、岗位匹配、模拟面试、RAG 管理
  - 模拟面试支持运行时模型切换（deepseek/ollama）与 A/B 对比视图
  - API 调用入口：`frontend/src/api.js`
- `backend`（FastAPI）
  - 路由层：`backend/routers/api.py`
  - 业务层：`backend/services/*.py`
  - 数据层：SQLite（`backend/data/app.db`）
  - LLM 适配层：`services/deepseek.py`（provider 分流）
- `nginx`（前端容器内）
  - 静态文件服务
  - `/api` 反向代理到 `backend:8000`

## 2) 请求流（Request Flow）

### 2.1 简历诊断（文件上传）

1. 前端 `FormData(file)` 调 `POST /api/resume-diagnosis/upload`
2. 后端解析文件（pdf/docx/txt/md）并抽取文本
3. 调用诊断服务生成建议
4. 返回结构化结果（建议列表；错误时返回统一 `error` 结构）

### 2.2 岗位匹配

1. 前端提交 `experience + target_job + jd`
2. 后端调用 LLM 生成匹配分、优势、差距
3. 前端渲染匹配结果与岗位适配摘要

### 2.3 模拟面试

1. 前端发送消息列表到 `POST /api/interview/chat`
2. 后端判断回合类型（作答/追问面试官）
3. 构造检索 query，召回 RAG 片段并注入 prompt
4. 调用当前 provider（DeepSeek/Ollama），返回回复 + 评分/建议（作答模式）
5. 将用户消息、助手消息（含 `reply_kind` 与 `rag_sources`）持久化

### 2.4 模型切换与 A/B 对比

1. 前端读取 `GET /api/llm/provider` 获取当前 provider
2. 切换时调用 `POST /api/llm/provider`（运行时生效，重启后按 `.env`）
3. 切到 `ollama` 前后端会探活本地服务与模型存在性（防误切）
4. A/B 对比走 `POST /api/interview/chat-compare`，同一输入并行对比两个 provider
5. 对比结果仅用于临时展示，不写入历史会话

### 2.5 RAG 管理与检索

1. 导入文本或文件到 `rag_documents + rag_chunks`
2. 检索时生成 query embedding，与 chunk embedding 点积打分
3. 按 `top_k` 和 `min_score` 过滤后返回结果

## 3) 数据流（Data Flow）

### 3.1 会话数据

- 表：`interview_sessions`、`interview_messages`
- 关键字段：
  - `reply_kind`：`answer` / `ask_interviewer`
  - `rag_sources_json`：本轮回答引用来源（复盘可追溯）

### 3.2 RAG 数据

- 表：`rag_documents`（元数据）
- 表：`rag_chunks`（chunk 文本 + `embedding_json`）
- 文件：上传原始文档保存于 `backend/data/rag_uploads`

### 3.3 错误与可观测

- 统一错误返回结构：
  - `ok: false`
  - `error.code / message / hint / request_id`
- 响应头包含 `X-Request-ID`
- 后端日志记录请求路径、状态与耗时
- 模型切换相关错误（如 `ollama_unavailable` / `ollama_model_missing`）也走统一错误结构

## 4) 部署拓扑（当前）

- 本地开发：
  - 前端：Vite dev server
  - 后端：uvicorn
  - Ollama（可选）：本地 `http://127.0.0.1:11434`
- Docker 运行：
  - `frontend` 容器（Nginx + 打包产物）
  - `backend` 容器（FastAPI）
  - `backend-data` volume 持久化 SQLite 数据

## 5) 已知边界与后续方向

- 当前 RAG 为 SQLite + 全量扫描（MVP），适合中小数据量
- LLM provider 的运行时切换为进程内状态；服务重启后回到 `.env` 默认值
- 可继续演进：
  - 更细粒度检索评估与重排
  - A/B 对比结果的自动评分与统计看板
  - 更完善的自动化测试覆盖
  - 生产级监控告警与外层网关策略
