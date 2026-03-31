import { Link } from 'react-router-dom'

const cards = [
  {
    title: '简历诊断',
    desc: '输入工作经历，获取可执行的优化建议。',
    to: '/resume',
  },
  {
    title: '岗位匹配',
    desc: '对比你的经历与目标职位 JD，识别优势和差距。',
    to: '/job-match',
  },
  {
    title: '模拟面试',
    desc: '像聊天一样进行一问一答，练习真实面试场景。',
    to: '/interview',
  },
]

export default function HomePage() {
  return (
    <section>
      <h1>AI 求职助手</h1>
      <p className="muted">先做 MVP：先跑通核心链路，再逐步接入真实大模型。</p>
      <div className="card-grid">
        {cards.map((card) => (
          <Link key={card.title} className="feature-card" to={card.to}>
            <h3>{card.title}</h3>
            <p>{card.desc}</p>
            <span>进入功能</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
