import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

export const diagnoseResume = async (experience) => {
  const { data } = await api.post(
    '/api/resume-diagnosis',
    { experience },
    { timeout: 120000 },
  )
  return data
}

export const diagnoseResumeByFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/api/resume-diagnosis/upload', formData, {
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
  const { data } = await api.post('/api/job-match', {
    experience,
    target_job: targetJob,
    jd,
  })
  return data
}

export const chatInterview = async (jobTitle, messages, sessionId, debug = false) => {
  const { data } = await api.post('/api/interview/chat', {
    job_title: jobTitle,
    messages,
    session_id: sessionId,
    debug,
  })
  return data
}

export const getInterviewHistory = async (sessionId) => {
  const { data } = await api.get(`/api/interview/history/${sessionId}`)
  return data
}

export const getInterviewSessions = async (limit = 20, offset = 0) => {
  const { data } = await api.get('/api/interview/sessions', { params: { limit, offset } })
  return data
}

export const deleteInterviewSession = async (sessionId) => {
  const { data } = await api.delete(`/api/interview/sessions/${sessionId}`)
  return data
}
