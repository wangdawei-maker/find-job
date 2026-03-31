import { useEffect, useState } from 'react'
import {
  chatInterview,
  deleteInterviewSession,
  getInterviewHistory,
  getInterviewSessions,
} from '../api'

const PAGE_SIZE = 10
const INITIAL_ASSISTANT_MESSAGE = {
  role: 'assistant',
  content: '你好，我们开始模拟面试。请先做一个 30 秒自我介绍。',
  score: null,
  strengths: [],
  improvements: [],
}

export default function InterviewPage() {
  const [jobTitle, setJobTitle] = useState('AI 应用开发工程师')
  const [sessionId, setSessionId] = useState('')
  const [sessions, setSessions] = useState([])
  const [sessionOffset, setSessionOffset] = useState(0)
  const [hasMoreSessions, setHasMoreSessions] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [debugRag, setDebugRag] = useState(false)
  const [messages, setMessages] = useState([INITIAL_ASSISTANT_MESSAGE])

  const loadSessions = async ({ reset = false } = {}) => {
    const offset = reset ? 0 : sessionOffset
    const data = await getInterviewSessions(PAGE_SIZE, offset)
    const next = data.sessions || []
    setSessions((prev) => (reset ? next : [...prev, ...next]))
    setSessionOffset(offset + next.length)
    setHasMoreSessions(Boolean(data.has_more))
  }

  useEffect(() => {
    loadSessions({ reset: true }).catch(() => {})
    // 产品行为：每次进入页面默认开启新会话，不自动恢复旧会话。
    startNewSession()
  }, [])

  const handleSelectSession = async (sid) => {
    if (!sid) {
      startNewSession()
      return
    }
    setSessionId(sid)
    try {
      const data = await getInterviewHistory(sid)
      setJobTitle(data.job_title || 'AI 应用开发工程师')
      setMessages(data.messages?.length ? data.messages : [INITIAL_ASSISTANT_MESSAGE])
    } catch {
      setMessages([INITIAL_ASSISTANT_MESSAGE])
    }
  }

  const startNewSession = () => {
    setSessionId('')
    setMessages([INITIAL_ASSISTANT_MESSAGE])
  }

  const handleDeleteSession = async () => {
    if (!sessionId) return
    const ok = window.confirm('确认删除当前会话吗？删除后不可恢复。')
    if (!ok) return
    try {
      await deleteInterviewSession(sessionId)
      startNewSession()
      setSessions([])
      setSessionOffset(0)
      await loadSessions({ reset: true })
    } catch {
      // ignore delete failure in UI
    }
  }

  const onSend = async () => {
    if (!input.trim()) return
    const nextMessages = [...messages, { role: 'user', content: input.trim() }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    try {
      const data = await chatInterview(
        jobTitle,
        nextMessages,
        sessionId || undefined,
        debugRag,
      )
      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id)
        setSessions([])
        setSessionOffset(0)
        await loadSessions({ reset: true })
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply,
          score: data.score,
          strengths: data.strengths || [],
          improvements: data.improvements || [],
          ragSources: data.rag_sources || [],
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>模拟面试</h2>
      <div className="chat-toolbar">
        <select
          value={sessionId}
          onChange={(e) => handleSelectSession(e.target.value)}
        >
          <option value="">当前会话（新）</option>
          {sessions.map((item) => (
            <option key={item.session_id} value={item.session_id}>
              {item.job_title} · {item.updated_at}
            </option>
          ))}
        </select>
        <button type="button" onClick={startNewSession}>
          新建会话
        </button>
        <button type="button" onClick={handleDeleteSession} disabled={!sessionId}>
          删除会话
        </button>
        <label className="debug-toggle">
          <input
            type="checkbox"
            checked={debugRag}
            onChange={(e) => setDebugRag(e.target.checked)}
          />
          显示RAG来源
        </label>
      </div>
      {hasMoreSessions && (
        <button type="button" onClick={() => loadSessions()} className="load-more-btn">
          加载更多历史
        </button>
      )}
      <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
      <div className="chat-box">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-row ${msg.role}`}>
            <div className="bubble">
              <p>{msg.content}</p>
              {msg.role === 'assistant' && msg.score !== null && (
                <div className="interview-feedback">
                  <p>
                    本轮评分：<strong>{msg.score}</strong>/100
                  </p>
                  <p>亮点：{msg.strengths.join('；')}</p>
                  <p>改进：{msg.improvements.join('；')}</p>
                  {msg.ragSources?.length > 0 && (
                    <p>来源：{msg.ragSources.join('；')}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="chat-input">
        <textarea
          className="chat-textarea"
          rows={3}
          placeholder="输入你的回答..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              onSend()
            }
          }}
        />
        <button onClick={onSend} disabled={loading}>
          {loading ? '思考中...' : '发送'}
        </button>
      </div>
    </section>
  )
}
