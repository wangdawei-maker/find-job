import { useState } from 'react'
import { matchJob } from '../api'

const copyText = async (text) => {
  if (!text) return false
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

export default function JobMatchPage() {
  const [experience, setExperience] = useState('')
  const [targetJob, setTargetJob] = useState('')
  const [jd, setJd] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [copyStatus, setCopyStatus] = useState('')

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

  const buildFitSummary = () => {
    if (!result) return ''
    const score = Number(result.score || 0)
    const band = score >= 75 ? '高匹配，可优先投递' : score >= 55 ? '中匹配，建议补齐短板后投递' : '低匹配，建议先补核心能力'
    const topAdvantages = (result.advantages || []).slice(0, 3)
    const topGaps = (result.gaps || []).slice(0, 3)
    const actions = topGaps.map((g, idx) => `${idx + 1}. 针对「${g}」准备一个可量化案例`).join('\n')

    return [
      `岗位适配结论：${band}（${score}%）`,
      `匹配优势：${topAdvantages.join('；') || '暂无明显优势'}`,
      `主要缺口：${topGaps.join('；') || '暂无明显缺口'}`,
      `建议下一步：\n${actions || '1. 继续投递并优化简历中的量化成果'}`,
    ].join('\n')
  }

  const fitSummary = buildFitSummary()

  const handleCopySummary = async () => {
    const ok = await copyText(fitSummary)
    setCopyStatus(ok ? '岗位适配摘要已复制' : '复制失败，请手动复制')
    setTimeout(() => setCopyStatus(''), 1600)
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

            <div className="fit-summary-card">
              <div className="recap-head">
                <h4>岗位适配摘要</h4>
                <button type="button" onClick={handleCopySummary}>
                  一键复制摘要
                </button>
              </div>
              <p>{fitSummary.split('\n')[0]}</p>
              <p>{fitSummary.split('\n')[1]}</p>
              <p>{fitSummary.split('\n')[2]}</p>
              <p>{fitSummary.split('\n').slice(3).join('\n')}</p>
              {copyStatus && <p className="muted">{copyStatus}</p>}
            </div>
          </>
        )}
      </div>
    </section>
  )
}
