import { useEffect, useRef, useState } from 'react'
import {
  clearRagDocuments,
  deleteRagDocument,
  ingestRagFile,
  ingestRagText,
  listRagDocuments,
  retrieveRag,
} from '../api'

export default function RagAdminPage() {
  const [source, setSource] = useState('manual')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [docs, setDocs] = useState([])
  const [retrieved, setRetrieved] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const fileInputRef = useRef(null)

  const ACCEPT_RAG = '.txt,.md,.pdf,.docx'

  const pickUploadFile = (file) => {
    if (!file) {
      setUploadFile(null)
      return
    }
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!['txt', 'md', 'pdf', 'docx'].includes(ext)) {
      setMessage('仅支持 .txt / .md / .pdf / .docx')
      setUploadFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    setMessage('')
    setUploadFile(file)
  }

  const loadDocs = async () => {
    const data = await listRagDocuments(100, 0)
    setDocs(data.documents || [])
  }

  useEffect(() => {
    loadDocs().catch(() => setMessage('加载文档列表失败，请稍后重试。'))
  }, [])

  const onIngest = async () => {
    if (!source.trim() || !title.trim() || !text.trim()) {
      setMessage(
        '文本导入需要填写下方「正文」。若只上传文件，请勿点本按钮，请点上面的「上传文件导入」。',
      )
      return
    }
    setLoading(true)
    setMessage('')
    try {
      const data = await ingestRagText(source.trim(), title.trim(), text.trim())
      setMessage(`导入成功，生成 ${data.chunks_count} 个 chunks。`)
      setText('')
      await loadDocs()
    } catch (err) {
      setMessage(err?.response?.data?.detail || '导入失败，请检查 embedding 配置。')
    } finally {
      setLoading(false)
    }
  }

  const onRetrieve = async () => {
    if (!query.trim()) {
      setMessage('请输入检索 query。')
      return
    }
    setLoading(true)
    setMessage('')
    try {
      const data = await retrieveRag(query.trim(), 5)
      setRetrieved(data.chunks || [])
      if (!data.chunks?.length) setMessage('未检索到结果。')
    } catch {
      setMessage('检索失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  const onIngestFile = async () => {
    if (!uploadFile) {
      setMessage('请先选择文件。')
      return
    }
    setLoading(true)
    setMessage('')
    try {
      const data = await ingestRagFile(uploadFile, source.trim() || 'upload', title.trim())
      setMessage(`文件导入成功，生成 ${data.chunks_count} 个 chunks。`)
      setUploadFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await loadDocs()
    } catch (err) {
      setMessage(err?.response?.data?.detail || '文件导入失败，请检查文件格式。')
    } finally {
      setLoading(false)
    }
  }

  const onDelete = async (id) => {
    if (!window.confirm('确认删除该文档及其全部 chunks？')) return
    setLoading(true)
    setMessage('')
    try {
      await deleteRagDocument(id)
      setDocs((prev) => prev.filter((d) => d.id !== id))
    } catch {
      setMessage('删除失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  const onClear = async () => {
    if (!window.confirm('确认清空整个 RAG 库？该操作不可恢复。')) return
    setLoading(true)
    setMessage('')
    try {
      const data = await clearRagDocuments()
      setRetrieved([])
      setDocs([])
      setMessage(`已清空：documents ${data.documents_deleted}，chunks ${data.chunks_deleted}`)
    } catch {
      setMessage('清空失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <div className="hero-panel rag-hero">
        <span className="hero-tag">RAG WORKSPACE</span>
        <h2>RAG 管理</h2>
        <p className="muted">管理知识片段：导入、检索验证、删除、清库。</p>
      </div>

      <div className="rag-admin-grid">
        <div className="rag-panel rag-import-panel">
          <h3>导入知识</h3>
          <p className="rag-import-lead muted">
            先填写来源与标题（两种方式共用）。再任选<strong>上传文件</strong>或<strong>粘贴正文</strong>其一完成导入。
          </p>

          <div className="rag-meta-grid">
            <label className="rag-field">
              <span>来源 source</span>
              <input
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="如 manual、jd、公司名"
                autoComplete="off"
              />
            </label>
            <label className="rag-field">
              <span>标题 title</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="文档标题，便于列表辨认"
                autoComplete="off"
              />
            </label>
          </div>

          <div className="upload-card rag-import-card">
            <div className="upload-card-head">
              <h4>方式一 · 上传文件</h4>
              <span className="muted">.txt / .md / .pdf / .docx</span>
            </div>
            <label
              className="upload-dropzone rag-dropzone"
              onDragOver={(e) => {
                e.preventDefault()
                e.stopPropagation()
              }}
              onDrop={(e) => {
                e.preventDefault()
                e.stopPropagation()
                const f = e.dataTransfer.files?.[0]
                if (f) pickUploadFile(f)
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPT_RAG}
                onChange={(e) => pickUploadFile(e.target.files?.[0] || null)}
              />
              <span className="upload-title">点击选择或拖入文件</span>
              <span className="upload-subtitle">解析后自动切块入库（需配置 Embedding）</span>
            </label>
            <div className="upload-actions">
              <span className="file-pill" title={uploadFile?.name}>
                {uploadFile ? uploadFile.name : '未选择文件'}
              </span>
              <button type="button" onClick={onIngestFile} disabled={loading || !uploadFile}>
                {loading ? '处理中…' : '导入文件到知识库'}
              </button>
            </div>
          </div>

          <div className="rag-or-divider" aria-hidden="true">
            <span>或</span>
          </div>

          <div className="upload-card rag-text-card">
            <div className="upload-card-head">
              <h4>方式二 · 粘贴正文</h4>
              <span className="muted">适合直接粘贴大段文字</span>
            </div>
            <label className="rag-field rag-field-block">
              <span>正文内容</span>
              <textarea
                rows={9}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="将知识全文粘贴到此处，再点击下方按钮（与方式一无需同时使用）。"
              />
            </label>
            <div className="rag-text-actions">
              <button type="button" className="rag-btn-secondary" onClick={onIngest} disabled={loading}>
                {loading ? '处理中…' : '导入正文到知识库'}
              </button>
            </div>
          </div>
        </div>

        <div className="rag-panel rag-retrieve-panel">
          <h3>检索测试</h3>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="输入 query 验证召回质量" />
          <button type="button" onClick={onRetrieve} disabled={loading}>
            {loading ? '检索中...' : '检索 Top-5'}
          </button>
          <div className="rag-results">
            {retrieved.map((item) => (
              <div key={item.chunk_id} className="rag-result-item">
                <p>
                  <strong>{item.title}</strong> · {item.source} · score {item.score}
                </p>
                <p className="muted">{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rag-panel">
        <div className="rag-header-row">
          <h3>已入库文档（{docs.length}）</h3>
          <button type="button" onClick={onClear} disabled={loading || docs.length === 0}>
            清空全部
          </button>
        </div>
        <div className="rag-doc-list">
          {docs.map((d) => (
            <div key={d.id} className="rag-doc-item">
              <div>
                <strong>{d.title}</strong>
                <p className="muted">
                  {d.source} · chunks {d.chunk_count} · {d.created_at}
                </p>
                {d.file_name && (
                  <p className="muted">
                    文件：{d.file_name}
                    {d.file_size ? ` (${Math.ceil(d.file_size / 1024)} KB)` : ''}
                  </p>
                )}
                {d.file_path && <p className="muted">路径：{d.file_path}</p>}
              </div>
              <button type="button" onClick={() => onDelete(d.id)} disabled={loading}>
                删除
              </button>
            </div>
          ))}
          {docs.length === 0 && <p className="muted">当前没有文档，先导入一份文本试试。</p>}
        </div>
      </div>

      {message && <p className="rag-message">{message}</p>}
    </section>
  )
}
