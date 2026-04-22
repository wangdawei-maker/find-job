# AI 求职助手 MVP

一个可运行的求职辅助应用：

- 前端：React + Vite
- 后端：Python + FastAPI
- 核心能力：简历诊断（文件上传）、岗位匹配、模拟面试（评分 + 历史会话）、RAG 知识导入与检索

## 1) 本地启动

### 1.1 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

`backend/.env` 最小配置示例：

```env
LLM_PROVIDER=deepseek

DEEPSEEK_API_KEY=你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
INTERVIEW_PROMPT_DEBUG=false

EMBEDDING_API_KEY=你的embedding_key
EMBEDDING_BASE_URL=https://你的embedding网关
EMBEDDING_MODEL=你的embedding模型名
```

如需切换到本地 Ollama（例如 `qwen3.5:7b`）：

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:7b
OLLAMA_TIMEOUT_SECONDS=60
```

切换后重启后端即可，无需改前端代码。

可选：若需查看模拟面试注入的 prompt 片段，可将 `INTERVIEW_PROMPT_DEBUG=true` 并在前端开启“显示RAG来源”。

### 1.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认访问 `http://127.0.0.1:8000/api`。  
如需修改，可在 `frontend/.env` 配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

### 1.3 一键启动（Windows，推荐）

在项目根目录运行：

```powershell
.\dev.ps1
```

停止服务：终端按 `Ctrl + C`。

## 2) 常见故障排查

### 2.1 前端请求 404（常见于 `/api/api/...`）

- 检查 `VITE_API_BASE_URL` 是否已经包含 `/api`。
- 若 baseURL 已是 `/api` 或 `http://127.0.0.1:8000/api`，前端请求路径不要再手写 `/api/...` 前缀。

### 2.2 RAG 导入失败：`EMBEDDING_* 未配置`

- 在 `backend/.env` 补齐 `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL`。
- 修改配置后重启后端。

### 2.3 上传 PDF 文本过少

- 这通常是扫描版 PDF（图片流）导致无法直接抽取文本。
- 建议转换为可复制文本 PDF 或 `.docx` 后重试。

### 2.4 请求报错但难定位

- 后端响应头含 `X-Request-ID`。
- 可在后端日志按 `request_id` 搜索对应请求链路（路径、状态码、耗时）。

### 2.5 面试历史为空或异常

- 确认 `backend/data/app.db` 可写（目录权限正常）。
- 若用 Docker，确认 volume 正常挂载（`backend-data`）。

## 3) Docker 部署要点

### 3.1 启动

1. 在 `backend/.env` 配置 `DEEPSEEK_*` 与 `EMBEDDING_*`。  
2. 根目录执行：

```bash
docker compose up -d --build
```

3. 访问：

- 前端：`http://localhost:5173`
- 后端文档：`http://localhost:8000/docs`

停止：

```bash
docker compose down
```

### 3.2 部署注意事项

- 前端容器内由 Nginx 托管静态资源并反代 `/api` 到后端服务。
- `docker-compose.yml` 已配置 `backend-data` volume，容器重启不会丢失 SQLite 数据。
- 若需公网部署，建议在外层网关做 HTTPS 终止、限流和访问日志聚合。

## 4) RAG 功能说明

已支持：

- `POST /api/rag/ingest-text`：导入纯文本
- `POST /api/rag/ingest-file`：上传文件导入（保留原文件）
- `POST /api/rag/retrieve`：向量检索（支持 `top_k` + `min_score`）
- 模拟面试自动注入 RAG 片段，并持久化每轮命中来源（用于复盘）

初始化种子数据：

```bash
cd backend
python scripts/seed_rag.py
```

## 5) 参考文档

- 架构说明：`ARCHITECTURE.md`
