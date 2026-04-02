##接口总览:

最开始的router = APIRouter(prefix="/api")我的理解是设置了基本的路径。

路径:/api/health
调用service函数:没有调用service
是否调用deepseek函数:否
是否读写数据库:否
出错常见点:可能我配置错误了key但不会报错？
备注:用于检查deepseek的apikey是否配置正确,但没发现这个接口的实际调用地方，更像为了检查配置而先准备的

路径:/api/resume-diagnosis
调用service函数:resume_suggestions_from_text
是否调用deepseek函数:是
是否读写数据库:否
出错常见点:无
备注:解析简历经历的接口，但这是最初版的接口，目前来看暂时用不到，但功能是好的

路径:/api/resume-diagnosis/upload
调用service函数:resume_suggestions_from_text,extract_resume_text
是否调用deepseek函数:是
是否读写数据库:否
出错常见点:无
备注:解析简历经历的接口，但这是目前版本的接口，主要是文件上传和解析上传的内容进行简历解析

路径:/api/job-match
调用service函数:job_match_with_llm
是否调用deepseek函数:是
是否读写数据库:否
出错常见点:无
备注:根据输入的工作经历来和目标jd做匹配分析

路径:/api/interview/chat
调用service函数:ensure_session,interview_chat_with_llm,save_message
是否调用deepseek函数:是
是否读写数据库:是
出错常见点:无
备注:根据 force_ask_interviewer + 启发式判断 作答/追问 分支

路径:/api/interview/history/{session_id}
调用service函数:get_history
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:拉取一个会话的消息历史记录

路径:/api/interview/sessions
调用service函数:list_sessions
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:查询会话列表信息，按分页的形式

路径:/api/interview/sessions/{session_id}
调用service函数:delete_session
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:删除指定会话

路径:/api/rag/ingest-text
调用service函数:ingest_document_text
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:把纯文本直接做rag导入

路径:/api/rag/ingest-file
调用service函数:extract_resume_text,ingest_document_text
是否调用deepseek函数:否
是否读写数据库:是,落盘上传文件到backend/data/rag_uploads
出错常见点:无
备注:把文件先解析成文本再做rag导入

路径:/api/rag/retrieve
调用service函数:retrieve_chunks
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:对rag的文本做检索top的接口

路径:/api/rag/documents
调用service函数:list_rag_documents
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:对已入库的rag文档做分页

路径:/api/rag/documents/{document_id}
调用service函数:delete_rag_document
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:对已入库的rag文档删除

路径:/api/rag/clear
调用service函数:clear_rag_knowledge
是否调用deepseek函数:否
是否读写数据库:是
出错常见点:无
备注:清空rag文档


##核心调用链路:

/api/resume-diagnosis/upload
api.py::resume_diagnosis_upload() -> resume_parser::extract_resume_text() -> resume_service::resume_suggestions_from_text() -> deepseek::call_deepseek() -> deepseek::extract_json_obj() -> ResumeDiagnosisResponse

读写数据库：否
读写文件：读取上传文件内容（内存中处理）
调不调LLM： 是
读不读库:否
返回什么模型:ResumeDiagnosisResponse

/api/interview/chat
api.py::interview_chat() -> interview_repo::ensure_session() -> interview_service::interview_chat_with_llm() -> detect_ask_interviewer_intent() -> (_run_ask_interviewer_turn / _run_answer_turn) -> deepseek::call_deepseek() -> deepseek::extract_json_obj() -> InterviewChatResponse -> interview_repo::save_message(user) + save_message(assistant)

读写数据库：是（session + messages）
读写文件：否
调不调LLM：是
读不读库:读取、写入
返回什么模型:InterviewChatResponse


##数据库映射:
1) interview_sessions
用途：存每个模拟面试会话的元数据（会话ID、岗位、时间）
对应功能：会话列表、新建会话、会话更新时间
常见写入时机：/api/interview/chat 首次进入会话或更新岗位时
关键字段：session_id, job_title, created_at, updated_at
我自己的理解：把所有对话的索引用单独的一个表存起来，方便在interview_messages拿到对应的历史对话


2) interview_messages
用途：存每轮对话消息明细（用户/助手内容及评分信息）
对应功能：会话历史回放、评分展示、追问答复标识
常见写入时机：/api/interview/chat 每次发送后写入 user 和 assistant
关键字段：session_id, role, content, score, strengths_json, improvements_json, reply_kind, created_at
我自己的理解：通过interview_sessions拿到session_id后就可以在这个表里拿到历史对话了


3) rag_documents
用途：存 RAG 文档级元数据（来源、标题、上传文件信息）
对应功能：RAG 管理页文档列表、删除文档
常见写入时机：/api/rag/ingest-text、/api/rag/ingest-file
关键字段：id, source, title, file_name, file_path, mime_type, file_size, created_at
我自己的理解：和interview_sessions的设计相似，都是一个表用来存放id方便查询，另一个用来存放所有的信息


4) rag_chunks
用途：存文档切块后的文本和向量，用于检索排序
对应功能：/api/rag/retrieve 召回 Top-K；面试/RAG 检索
常见写入时机：文档导入时按 chunk 批量写入
关键字段：document_id, chunk_index, chunk_text, embedding_json, created_at
我自己的理解：和interview_messages类似，都是通过id查询他所属的数据


---

## Day 2：从「路由」往下钻三层

Day 1 是「有哪些接口、两条主链路、四张表」。Day 2 补三块：**LLM 怎么调**、**前后端契约**、**RAG 怎么从文本进库再被搜出来**（以及面试里怎么用）。

### 1) LLM 层：`services/deepseek.py`

- **环境变量**：`DEEPSEEK_API_KEY`（必填）、`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）、`DEEPSEEK_MODEL`（默认 `deepseek-chat`）、`DEEPSEEK_TIMEOUT_SECONDS`（默认 40）。
- **`call_deepseek(messages, temperature, timeout_seconds)`**：走 OpenAI 兼容的 `POST .../chat/completions`，取 `choices[0].message.content`；缺 Key 返回 500，HTTP/解析失败返回 502。
- **`extract_json_obj(text)`**：从模型**纯文本**里抠 JSON（支持 \`\`\`json 代码块或正文里的 `{...}`），供简历诊断/岗位匹配/面试等「要结构化结果」的场景。
- **自测点**：Key 错或网络问题会在**调用 LLM 的接口**上体现为 502/500，不是「静默失败」。

### 2) 契约层：`schemas.py` + FastAPI

- 每个 `POST` 的 body / 响应对应一个 **Pydantic `BaseModel`**，FastAPI 自动校验 + 生成 `/docs`。
- 和面试相关的要点：`InterviewChatRequest` 里 `force_ask_interviewer`、`debug`；`InterviewChatResponse` 里 `turn_mode`（`answer` vs `ask_interviewer`）、`score` 在追问模式下可为 `None`。
- **自测点**：改字段名要同时改前端 `api.js` 和页面，否则 422 或字段对不上。

### 3) RAG 流水线：`services/rag_service.py`（结合 Day1 的 `rag_documents` / `rag_chunks`）

- **Embedding**：`OpenAIEmbeddings`（LangChain），依赖 `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`；未配置时**首次调用 RAG 相关逻辑会报错**（`RuntimeError` 文案里会提示补 `.env`）。
- **维度**：`VECTOR_DIM = 256`，`embed_text` 会对向量**截断或零填充**到 256 维，入库和检索必须同一套规则。
- **切块**：`chunk_text(text, chunk_size=150, overlap=30)` → 多段字符串。
- **入库**：`ingest_document_text` → `create_document` 写 `rag_documents`，再对每个 chunk `insert_chunk(..., embed_text(chunk))` 写 `rag_chunks`。
- **检索**：`retrieve_chunks(query, top_k)` → 对查询做 `embed_text(query)`，与库里每条 chunk 的向量做 **`cosine_similarity`（实现上是点积）**，按分排序取 Top-K；注释里写了 MVP 未做 L2 归一化。
- **自测点**：只有导入过文档 + Embedding 配置正确，`/api/rag/retrieve` 和面试里的 RAG 块才有意义。

### 4) 面试里 RAG + 分支：`services/interview_service.py`（Day2 只记骨架）

- **`detect_ask_interviewer_intent`**：`force_ask_interviewer=True` 直接追问；否则用长度 + 正则 + 问号等启发式判断是「向面试官提问」还是「正常作答」。
- **`retrieve_chunks`**：在拼 prompt 前拉知识片段（具体拼法看 `_build_rag_block` 与两条分支的 prompt）。
- **自测点**：开 `INTERVIEW_PROMPT_DEBUG=true` + 前端 `debug`，可看注入与 RAG 来源（与 README 一致）。

### Day 2 建议动手顺序（约 1～2 小时）

1. 读一遍 `deepseek.py` 两个公开函数 + `extract_json_obj`。
2. 打开 `schemas.py`，对照 `api.py` 里同名路由的 `response_model` / 参数类型。
3. 顺着 `ingest_document_text` → `retrieve_chunks` 画一张「文本 → chunk → 向量 → SQLite → 检索」的草图。
4. 扫 `interview_service.py` 里 `detect_ask_interviewer_intent` 和 `_build_rag_block`（不必背正则，知道「何时追问、RAG 从哪来」即可）。

---

rag流程:
文本-->ingest_document_text(): init_rag_tables + chunk_text()-->create_document(生成 document_id)-->对每个 chunk: embed_text(chunk)-->insert_chunk(写 rag_chunks.embedding_json)-->rag数据导入成功(返回chunk数)

模拟面试何时追问?
通过detect_ask_interviewer_intent来做判断,判断规则有两个，一个是前端显式指定，一个是通过对user_text做出的正则判定

rag的来源?
_build_rag_block()-->retrieve_chunks()-->查询最相似的chunk

---

## Day 3：精读 `interview_service.py`（追问/作答、RAG query）

### 上午（3h）
1. 通读 `interview_service.py` 的核心分支逻辑：
   - 什么时候走「向面试官追问」：`detect_ask_interviewer_intent()`（前端 `force_ask_interviewer` + 启发式）
   - 什么时候走「作答评估」：否则按作答评分分支
2. 精读 `_build_rag_block()`：
   - `query` 从哪里来（`interview_chat_with_llm()` 里按分支拼接）
   - `retrieve_chunks()` 返回的 chunk 如何拼进 `rag_context` 和 `rag_sources`
3. 精读两条回合的 prompt 拼装：
   - `_run_answer_turn()`：输出结构化 JSON（reply/score/strengths/improvements）
   - `_run_ask_interviewer_turn()`：追问模式只输出 `{"reply":"..."}`（不评分）

### 下午（3h）
1. 打开 `backend/data/app.db`：
   - 看表结构：`interview_sessions`、`interview_messages`、`rag_documents`、`rag_chunks`（至少把列名扫一遍）
   - 把你自己的架构草图画出来：路由 -> service -> deepseek -> repo/db（RAG：入库 -> 检索 -> 注入 prompt）
2. 跟代码理解 `job_match_service`：
   - 它 prompt 里哪些字段会被当作输入（`target_job` / `experience` / `jd`）
3. 精读 `interview_repo.py`：
   - 用 SQLite 看「会话」和「消息」的保存/读取逻辑
4. 走一遍 RAG 管理相关接口：
   - 看 `rag_uploads` 目录与 `rag_documents`/索引关系
   - 跑 `list / delete / retrieve` 的数据链路（至少理解“文件 -> 文本 -> 入库 -> 检索”）
5. 自己改两小行才开门：
   - 例如把 `top_k` 改一档、或加一行日志（确保你能在响应/日志里观察到变化）
   - 然后提交 commit
6. 写「部署检查清单」10 条：
   - 端口、`.env`、卷/数据目录、重启方式、是否能访问 `/docs`、是否能初始化 RAG
7. 听回放/整理卡点，第二天再

---

## Day 4：精读 `rag_service.py` + `rag_repo.py`（入库/检索全链路）

### 上午（3h）
1. 精读 `rag_service.py`：
   - `chunk_text()` 怎么切块（chunk_size/overlap）
   - `embed_text()` 怎么归一化维度（截断/填充到 `VECTOR_DIM=256`）
   - `ingest_document_text()` 的入库流程（创建文档 -> 每块 embedding -> 写 chunk）
   - `retrieve_chunks()` 的检索流程（点积/余弦的实现细节 + top_k）
2. 精读 `rag_repo.py`：
   - `insert_chunk()`：`embedding` 是怎么 `json.dumps` 存到 `rag_chunks.embedding_json`
   - `fetch_all_chunks()`：检索侧是如何一次性把向量取出来比对的（MVP 方案）

### 下午（3h，可选）
1. 自己手工做一轮：
   - 导入一段短文本（`/api/rag/ingest-text`）
   - 用 `/api/rag/retrieve` 检索验证 top_k 是否命中你预期的内容
2. 观察 `rag_sources`（如果用于面试分支）是否符合你导入时的文档来源

---

## Day 5：故障练习（改 `.env` / 停启服务 / 看日志与 Network）

1. 改 `.env` 里至少一个关键配置并重启：
   - `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`
   - 或 `EMBEDDING_API_*`（用于 RAG embedding）
2. 停启服务：
   - 前后端各自重启一次，确认依赖加载时机是否正确
3. 看日志与 Network：
   - 重点看 DeepSeek / Embedding 请求失败时后端返回是什么状态码（500/502/报错细节）
   - 记录你遇到的“最容易踩坑点”

---

## Day 6：Docker / docker-compose 通读（本地 or 云上启动）

1. 通读 `docker-compose.yml` 与 Dockerfile（如果有）：
   - 服务端口映射
   - `backend/data` 的 volume（SQLite 数据是否持久化）
2. 演练一次：
   - 本地跑 `docker compose up` 后访问前端与 `/docs`
3. 记下“需要改的地方”（例如镜像环境变量、初始化 RAG seed、网络策略等）

---

## Day 7：休息半天或轻量任务

1. 录一遍 5 分钟口述（可手机录音）：
   - 口述你理解的 Day3+Day4：面试追问/作答 + RAG 入库/检索如何注入 prompt
2. 把“第二天要做什么”写成 3 条：
   - 例如接入简历诊断 RAG、稳定 prompt JSON 解析、补一条更小的自动化验证

