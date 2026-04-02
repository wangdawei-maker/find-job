import { NavLink, Route, Routes } from 'react-router-dom'
import CursorRibbon from './components/CursorRibbon'
import Live2DWidget from './components/Live2DWidget'
import HomePage from './pages/HomePage'
import InterviewPage from './pages/InterviewPage'
import JobMatchPage from './pages/JobMatchPage'
import RagAdminPage from './pages/RagAdminPage'
import ResumeDiagnosisPage from './pages/ResumeDiagnosisPage'
import './App.css'

function App() {
  return (
    <>
      <CursorRibbon />
      <Live2DWidget />
      <div className="app-shell">
        <header className="top-nav">
          <div className="brand">AI Job Copilot</div>
          <nav>
            <NavLink to="/">首页</NavLink>
            <NavLink to="/resume">简历诊断</NavLink>
            <NavLink to="/job-match">岗位匹配</NavLink>
            <NavLink to="/interview">模拟面试</NavLink>
            <NavLink to="/rag-admin">RAG管理</NavLink>
          </nav>
        </header>

        <main className="page-container">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/resume" element={<ResumeDiagnosisPage />} />
            <Route path="/job-match" element={<JobMatchPage />} />
            <Route path="/interview" element={<InterviewPage />} />
            <Route path="/rag-admin" element={<RagAdminPage />} />
          </Routes>
        </main>
      </div>
    </>
  )
}

export default App
