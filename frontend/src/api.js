import axios from 'axios'

// 生产构建一般为 /api（经 Nginx 反代到后端）；路径不要再带 /api 前缀，否则会拼成 /api/api/... 导致 404
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

export const diagnoseResume = async (experience) => {
  const { data } = await api.post(
    '/resume-diagnosis',
    { experience },
    { timeout: 120000 },
  )
  return data
}

export const diagnoseResumeByFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/resume-diagnosis/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) return
      const percent = Math.round((event.loaded * 100) / event.total)
      onProgress(Math.min(100, Math.max(0, percent)))
    },
  })
  return data
}

export const matchJob = async (experience, targetJob, jd) => {
  const { data } = await api.post('/job-match', {
    experience,
    target_job: targetJob,
    jd,
  })
  return data
}

export const chatInterview = async (
  jobTitle,
  messages,
  sessionId,
  debug = false,
  forceAskInterviewer = false,
) => {
  const { data } = await api.post('/interview/chat', {
    job_title: jobTitle,
    messages,
    session_id: sessionId,
    debug,
    force_ask_interviewer: forceAskInterviewer,
  })
  return data
}

export const getInterviewHistory = async (sessionId) => {
  const { data } = await api.get(`/interview/history/${sessionId}`)
  return data
}

export const getInterviewSessions = async (limit = 20, offset = 0) => {
  const { data } = await api.get('/interview/sessions', { params: { limit, offset } })
  return data
}

export const deleteInterviewSession = async (sessionId) => {
  const { data } = await api.delete(`/interview/sessions/${sessionId}`)
  return data
}

export const ingestRagText = async (source, title, text) => {
  const { data } = await api.post('/rag/ingest-text', { source, title, text }, { timeout: 180000 })
  return data
}

export const ingestRagFile = async (file, source = 'upload', title = '') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('source', source)
  formData.append('title', title)
  const { data } = await api.post('/rag/ingest-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 240000,
  })
  return data
}

export const retrieveRag = async (query, topK = 3) => {
  const { data } = await api.post('/rag/retrieve', { query, top_k: topK })
  return data
}

export const listRagDocuments = async (limit = 50, offset = 0) => {
  const { data } = await api.get('/rag/documents', { params: { limit, offset } })
  return data
}

export const deleteRagDocument = async (documentId) => {
  const { data } = await api.delete(`/rag/documents/${documentId}`)
  return data
}

export const clearRagDocuments = async () => {
  const { data } = await api.post('/rag/clear')
  return data
}
