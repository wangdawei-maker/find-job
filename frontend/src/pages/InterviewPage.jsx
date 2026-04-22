import { useEffect, useState } from 'react'
import {
  chatInterview,
  chatInterviewCompare,
  deleteInterviewSession,
  getInterviewHistory,
  getLlmProvider,
  getInterviewSessions,
  setLlmProvider,
} from '../api'

const PAGE_SIZE = 10
const INITIAL_ASSISTANT_MESSAGE = {
  role: 'assistant',
  content: '你好，我们开始模拟面试。请先做一个 30 秒自我介绍。',
  score: null,
  strengths: [],
  improvements: [],
  replyKind: 'answer',
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
  const [forceAskInterviewer, setForceAskInterviewer] = useState(false)
  const [abCompare, setAbCompare] = useState(false)
  const [messages, setMessages] = useState([INITIAL_ASSISTANT_MESSAGE])
  const [openRagRefKeys, setOpenRagRefKeys] = useState({})
  const [llmProvider, setLlmProviderState] = useState('deepseek')
  const [llmSwitching, setLlmSwitching] = useState(false)
  const [llmProviderNotice, setLlmProviderNotice] = useState('')

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
    getLlmProvider()
      .then((data) => {
        if (data?.provider) setLlmProviderState(data.provider)
      })
      .catch(() => {})
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
      setMessages(
        data.messages?.length
          ? data.messages.map((m) => ({
              ...m,
              ragSources: m.rag_sources || [],
              replyKind: m.reply_kind || 'answer',
            }))
          : [INITIAL_ASSISTANT_MESSAGE],
      )
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
      if (abCompare) {
        const data = await chatInterviewCompare(
          jobTitle,
          nextMessages,
          sessionId || undefined,
          debugRag,
          forceAskInterviewer,
          ['deepseek', 'ollama'],
        )
        const compareMessages = (data.results || []).map((item) => ({
          role: 'assistant',
          content: item.error ? `[${item.provider}] ${item.error}` : `[${item.provider}] ${item.reply}`,
          score: item.score,
          strengths: item.strengths || [],
          improvements: item.improvements || [],
          ragSources: item.rag_sources || [],
          replyKind: item.turn_mode || 'answer',
        }))
        setMessages((prev) => [...prev, ...compareMessages])
        setForceAskInterviewer(false)
        return
      }
      const data = await chatInterview(
        jobTitle,
        nextMessages,
        sessionId || undefined,
        debugRag,
        forceAskInterviewer,
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
          replyKind: data.turn_mode || 'answer',
        },
      ])
      setForceAskInterviewer(false)
    } finally {
      setLoading(false)
    }
  }

  const toggleRagRefs = (key) => {
    setOpenRagRefKeys((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleProviderChange = async (nextProvider) => {
    if (!nextProvider || nextProvider === llmProvider) return
    setLlmSwitching(true)
    setLlmProviderNotice('')
    try {
      const data = await setLlmProvider(nextProvider)
      setLlmProviderState(data.provider)
      setLlmProviderNotice(`模型已切换为 ${data.provider}`)
    } catch {
      setLlmProviderNotice('模型切换失败，请检查后端服务状态')
    } finally {
      setLlmSwitching(false)
      setTimeout(() => setLlmProviderNotice(''), 1800)
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
        <label className="provider-picker">
          <span>模型</span>
          <select
            value={llmProvider}
            disabled={llmSwitching}
            onChange={(e) => handleProviderChange(e.target.value)}
          >
            <option value="deepseek">deepseek</option>
            <option value="ollama">ollama</option>
          </select>
        </label>
        <label className="debug-toggle switch-toggle">
          <input
            type="checkbox"
            checked={debugRag}
            onChange={(e) => setDebugRag(e.target.checked)}
          />
          <span>显示RAG来源</span>
        </label>
        <label className="debug-toggle switch-toggle" title="勾选后本句强制视为向面试官追问，不评分">
          <input
            type="checkbox"
            checked={forceAskInterviewer}
            onChange={(e) => setForceAskInterviewer(e.target.checked)}
          />
          <span>本句追问面试官</span>
        </label>
        <label className="debug-toggle switch-toggle" title="同一输入同时请求 deepseek 与 ollama，便于对比输出">
          <input
            type="checkbox"
            checked={abCompare}
            onChange={(e) => setAbCompare(e.target.checked)}
          />
          <span>A/B模型对比</span>
        </label>
      </div>
      {llmProviderNotice && <p className="muted">{llmProviderNotice}</p>}
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
              {msg.role === 'assistant' && msg.replyKind === 'ask_interviewer' && (
                <div className="interview-ask-meta">
                  <p className="interview-ask-badge">追问答复（未评分）</p>
                </div>
              )}
              {msg.role === 'assistant' && msg.replyKind === 'answer' && msg.score !== null && (
                <div className="interview-feedback">
                  <p>
                    本轮评分：<strong>{msg.score}</strong>/100
                  </p>
                  <p>亮点：{msg.strengths.join('；')}</p>
                  <p>改进：{msg.improvements.join('；')}</p>
                </div>
              )}
              {msg.role === 'assistant' && debugRag && msg.ragSources?.length > 0 && (
                <div className="rag-ref-wrap">
                  <button
                    type="button"
                    className="rag-ref-btn"
                    onClick={() => toggleRagRefs(`${msg.replyKind}-${idx}`)}
                  >
                    {openRagRefKeys[`${msg.replyKind}-${idx}`]
                      ? '收起AI参考资料'
                      : `查看AI参考资料（${msg.ragSources.length}）`}
                  </button>
                  {openRagRefKeys[`${msg.replyKind}-${idx}`] && (
                    <ul className="rag-ref-list">
                      {msg.ragSources.map((item) => (
                        <li key={`${idx}-${item}`}>{item}</li>
                      ))}
                    </ul>
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
          placeholder={
            forceAskInterviewer
              ? '向面试官提问（岗位、团队、流程等）...'
              : '输入你的回答；短句带问号也可能被识别为追问'
          }
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
