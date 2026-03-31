# AI 求职助手 MVP

一个可运行的前后端骨架：
- 前端：React + Vite
- 后端：Python + FastAPI
- 功能：首页、简历诊断（文件上传）、岗位匹配、模拟面试（评分+历史会话）

## 1) 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# 复制配置并填写 DeepSeek Key
copy .env.example .env
uvicorn main:app --reload --port 8000
```

在 `backend/.env` 中配置：

```env
DEEPSEEK_API_KEY=你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

## 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认访问 `http://127.0.0.1:8000`。
如需改地址，可在 `frontend/.env` 配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 3) 一条命令启动（推荐）

直接在项目根目录运行：

```powershell
.\dev.ps1
```

停止后端/前端：按 `Ctrl + C`。

## 4) Docker 部署（建议提前演练）

1) 在 `backend/.env` 配置好 `DEEPSEEK_*` 和 `EMBEDDING_*`。

2) 根目录执行：

```bash
docker compose up -d --build
```

3) 访问：
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000/docs`

4) 停止：

```bash
docker compose down
```

说明：
- `docker-compose.yml` 已配置 `backend-data` volume，容器重启不会丢失 `backend/data` 下的 SQLite 数据。

## 5) 最小 RAG（已接入）

当前已支持：
- `POST /api/rag/ingest-text`：导入文本知识到 SQLite 向量库
- `POST /api/rag/retrieve`：按 query 召回 Top-K 知识片段
- 模拟面试接口会自动检索并注入相关知识片段

初始化种子数据：

```bash
cd backend
python scripts/seed_rag.py
```

## 6) 下一步建议

1. 将简历诊断/岗位匹配也接入 RAG 上下文。
2. 为 RAG 增加管理端（文档上传、删除、重建索引）。
3. 为模拟面试增加语音输入与实时转写。
