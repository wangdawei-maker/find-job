import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 10000,
})

export const diagnoseResume = async (experience) => {
  const { data } = await api.post('/api/resume-diagnosis', { experience })
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

export const chatInterview = async (jobTitle, messages) => {
  const { data } = await api.post('/api/interview/chat', {
    job_title: jobTitle,
    messages,
  })
  return data
}
