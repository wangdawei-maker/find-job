import { useEffect, useState } from 'react'
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

  const loadDocs = async () => {
    const data = await listRagDocuments(100, 0)
    setDocs(data.documents || [])
  }

  useEffect(() => {
    loadDocs().catch(() => setMessage('加载文档列表失败，请稍后重试。'))
  }, [])

  const onIngest = async () => {
    if (!source.trim() || !title.trim() || !text.trim()) {
      setMessage('source、title、text 不能为空。')
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
        <div className="rag-panel">
          <h3>导入文本</h3>
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="source" />
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="title" />
          <div className="rag-upload-row">
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            />
            <button type="button" onClick={onIngestFile} disabled={loading || !uploadFile}>
              {loading ? '处理中...' : '上传文件导入'}
            </button>
          </div>
          {uploadFile && <p className="muted">已选择：{uploadFile.name}</p>}
          <textarea
            rows={8}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="粘贴知识文本内容..."
          />
          <button type="button" onClick={onIngest} disabled={loading}>
            {loading ? '处理中...' : '导入到 RAG'}
          </button>
        </div>

        <div className="rag-panel">
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
