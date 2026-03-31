import { useState } from 'react'
import { chatInterview } from '../api'

export default function InterviewPage() {
  const [jobTitle, setJobTitle] = useState('AI 应用开发工程师')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '你好，我们开始模拟面试。请先做一个 30 秒自我介绍。',
    },
  ])

  const onSend = async () => {
    if (!input.trim()) return
    const nextMessages = [...messages, { role: 'user', content: input.trim() }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    try {
      const data = await chatInterview(jobTitle, nextMessages)
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>模拟面试</h2>
      <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
      <div className="chat-box">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-row ${msg.role}`}>
            <div className="bubble">{msg.content}</div>
          </div>
        ))}
      </div>

      <div className="chat-input">
        <input
          placeholder="输入你的回答..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
        />
        <button onClick={onSend} disabled={loading}>
          {loading ? '思考中...' : '发送'}
        </button>
      </div>
    </section>
  )
}
