import { useState } from 'react'
import { diagnoseResumeByFile, extractApiErrorMessage } from '../api'

const ACCEPTED_EXTS = ['pdf', 'docx', 'txt']
const MAX_FILE_SIZE = 8 * 1024 * 1024

export default function ResumeDiagnosisPage() {
  const [resumeFile, setResumeFile] = useState(null)
  const [result, setResult] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadDone, setUploadDone] = useState(false)

  const runFileDiagnosis = async () => {
    if (!resumeFile) return
    setLoading(true)
    setError('')
    setUploadDone(false)
    setUploadProgress(0)
    try {
      const data = await diagnoseResumeByFile(resumeFile, setUploadProgress)
      setResult(data.suggestions || [])
      setUploadProgress(100)
      setUploadDone(true)
    } catch (err) {
      setError(extractApiErrorMessage(err, '文件解析失败，请检查格式后重试'))
      setUploadDone(false)
    } finally {
      setLoading(false)
    }
  }

  const onChooseFile = (file) => {
    setUploadDone(false)
    setUploadProgress(0)
    setError('')
    if (!file) {
      setResumeFile(null)
      return
    }
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!ACCEPTED_EXTS.includes(ext)) {
      setResumeFile(null)
      setError('仅支持 .pdf / .docx / .txt 格式')
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setResumeFile(null)
      setError('文件大小超过 8MB，请压缩后再上传')
      return
    }
    setResumeFile(file)
  }

  return (
    <section>
      <h2>简历诊断</h2>
      <p className="muted">上传 PDF / Word(.docx) / txt 简历，自动提取内容并给出优化建议。</p>

      <div className="upload-card">
        <div className="upload-card-head">
          <h4>上传简历文件</h4>
          <span className="muted">支持 .pdf / .docx / .txt</span>
        </div>
        <label className="upload-dropzone">
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => onChooseFile(e.target.files?.[0] || null)}
          />
          <span className="upload-title">点击选择文件</span>
          <span className="upload-subtitle">或将简历拖拽到这里（最大 8MB）</span>
        </label>
        <div className="upload-actions">
          <span className="file-pill">
            {resumeFile ? `已选择：${resumeFile.name}` : '未选择文件'}
          </span>
          <button
            type="button"
            onClick={runFileDiagnosis}
            disabled={loading || !resumeFile}
            className={loading ? 'btn-with-spinner' : ''}
          >
            {loading ? (
              <>
                <span className="spinner" aria-hidden="true" />
                解析中...
              </>
            ) : (
              '仅用文件诊断'
            )}
          </button>
        </div>
        {(loading || uploadProgress > 0) && (
          <div className="upload-progress-wrap" aria-live="polite">
            <div className="upload-progress-track">
              <div
                className={`upload-progress-bar ${uploadDone ? 'done' : ''}`}
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <span className="upload-progress-text">
              {loading && !uploadDone ? (
                <>
                  <span className="spinner spinner-inline" aria-hidden="true" />
                  {uploadProgress >= 100
                    ? '文件已上传，AI 正在分析中...'
                    : `上传进度 ${uploadProgress}%`}
                </>
              ) : uploadDone ? (
                '上传完成，建议已生成'
              ) : (
                `上传进度 ${uploadProgress}%`
              )}
            </span>
          </div>
        )}
      </div>

      {error && <p className="muted">{error}</p>}

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
