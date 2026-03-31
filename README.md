# AI 求职助手 MVP

一个可运行的前后端骨架：
- 前端：React + Vite
- 后端：Python + FastAPI
- 功能：首页、简历诊断、岗位匹配、模拟面试

## 1) 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认访问 `http://127.0.0.1:8000`。

## 3) 下一步建议

1. 把 `backend/main.py` 里的伪 AI 逻辑替换成真实大模型调用（OpenAI / 通义 / 智谱）。
2. 为模拟面试增加会话保存（SQLite + SQLAlchemy）。
3. 加上登录系统和职位收藏。
