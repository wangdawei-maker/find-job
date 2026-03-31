import { Link, Route, Routes } from 'react-router-dom'
import HomePage from './pages/HomePage'
import InterviewPage from './pages/InterviewPage'
import JobMatchPage from './pages/JobMatchPage'
import ResumeDiagnosisPage from './pages/ResumeDiagnosisPage'
import './App.css'

function App() {
  return (
    <div className="app-shell">
      <header className="top-nav">
        <div className="brand">AI Job Copilot</div>
        <nav>
          <Link to="/">首页</Link>
          <Link to="/resume">简历诊断</Link>
          <Link to="/job-match">岗位匹配</Link>
          <Link to="/interview">模拟面试</Link>
        </nav>
      </header>

      <main className="page-container">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/resume" element={<ResumeDiagnosisPage />} />
          <Route path="/job-match" element={<JobMatchPage />} />
          <Route path="/interview" element={<InterviewPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
