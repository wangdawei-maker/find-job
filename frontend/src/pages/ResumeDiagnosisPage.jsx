import { useState } from 'react'
import { diagnoseResume } from '../api'

export default function ResumeDiagnosisPage() {
  const [experience, setExperience] = useState('')
  const [result, setResult] = useState([])
  const [loading, setLoading] = useState(false)

  const onSubmit = async () => {
    if (!experience.trim()) return
    setLoading(true)
    try {
      const data = await diagnoseResume(experience)
      setResult(data.suggestions || [])
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>简历诊断</h2>
      <textarea
        rows={8}
        placeholder="输入你的工作经历、项目、成果..."
        value={experience}
        onChange={(e) => setExperience(e.target.value)}
      />
      <button onClick={onSubmit} disabled={loading}>
        {loading ? '诊断中...' : '开始诊断'}
      </button>

      <div className="result-panel">
        <h3>AI 建议</h3>
        {result.length === 0 ? (
          <p className="muted">暂无建议，先输入内容后点击“开始诊断”。</p>
        ) : (
          <ul>
            {result.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
