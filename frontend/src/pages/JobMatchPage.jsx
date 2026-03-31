import { useState } from 'react'
import { matchJob } from '../api'

export default function JobMatchPage() {
  const [experience, setExperience] = useState('')
  const [targetJob, setTargetJob] = useState('')
  const [jd, setJd] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const onSubmit = async () => {
    if (!experience.trim() || !targetJob.trim() || !jd.trim()) return
    setLoading(true)
    try {
      const data = await matchJob(experience, targetJob, jd)
      setResult(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>岗位匹配</h2>
      <input
        placeholder="目标岗位，例如：AI 应用开发工程师"
        value={targetJob}
        onChange={(e) => setTargetJob(e.target.value)}
      />
      <textarea
        rows={6}
        placeholder="输入你的工作经历..."
        value={experience}
        onChange={(e) => setExperience(e.target.value)}
      />
      <textarea
        rows={8}
        placeholder="粘贴目标岗位 JD..."
        value={jd}
        onChange={(e) => setJd(e.target.value)}
      />
      <button onClick={onSubmit} disabled={loading}>
        {loading ? '分析中...' : '开始匹配'}
      </button>

      <div className="result-panel">
        <h3>匹配结果</h3>
        {!result ? (
          <p className="muted">暂无结果，填写信息后点击“开始匹配”。</p>
        ) : (
          <>
            <p>
              匹配度：<strong>{result.score}%</strong>
            </p>
            <h4>你的优势</h4>
            <ul>
              {result.advantages.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <h4>待补足差距</h4>
            <ul>
              {result.gaps.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  )
}
