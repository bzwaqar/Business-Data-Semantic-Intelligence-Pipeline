import { useState, useRef, useEffect, useCallback } from 'react'
import './App.css'

const STAGES = ['ingesting', 'embedding', 'clustering', 'naming', 'assigning', 'exporting']
const STAGE_PCT = {
  pending: 5, ingesting: 15, embedding: 35, clustering: 55,
  naming: 75, assigning: 90, exporting: 95, completed: 100,
}

function formatBytes(b) {
  if (!b) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(k))
  return (b / Math.pow(k, i)).toFixed(1) + ' ' + units[i]
}

// ─── Upload View ────────────────────────────────────────────
function UploadView({ onJobStarted }) {
  const [file, setFile] = useState(null)
  const [columns, setColumns] = useState([])
  const [column, setColumn] = useState('')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const inputRef = useRef()

  function handleFile(f) {
    setFile(f)
    setColumn('')
    const reader = new FileReader()
    reader.onload = (e) => {
      const firstLine = e.target.result.split(/\r?\n/)[0]
      const headers = firstLine.split(',').map(h => h.trim().replace(/^["']|["']$/g, ''))
      setColumns(headers.filter(Boolean))
    }
    reader.readAsText(f.slice(0, 10240))
  }

  async function handleSubmit() {
    if (!file || !column) return
    setSubmitting(true)
    const form = new FormData()
    form.append('file', file)
    form.append('category_column', column)
    try {
      const res = await fetch('/api/v1/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      const data = await res.json()
      onJobStarted(data.job_id)
    } catch (err) {
      alert(err.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="card">
      <h2>Upload File</h2>

      <div
        className={`drop-zone${dragging ? ' drag-over' : ''}`}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0])
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.txt"
          style={{ display: 'none' }}
          onChange={(e) => e.target.files.length && handleFile(e.target.files[0])}
        />
        <p><strong>Click to browse</strong> or drag &amp; drop</p>
        <p className="hint">Supports CSV, XLSX, XLS, TXT</p>
      </div>

      {file && (
        <div className="file-info">
          <strong>{file.name}</strong>
          <span>{formatBytes(file.size)}</span>
        </div>
      )}

      {columns.length > 0 && (
        <div className="field">
          <label>Category Column:</label>
          <select value={column} onChange={(e) => setColumn(e.target.value)}>
            <option value="" disabled>-- pick a column --</option>
            {columns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      )}

      <button
        className="btn btn-full"
        disabled={!file || !column || submitting}
        onClick={handleSubmit}
      >
        {submitting ? 'Uploading…' : 'Start Classification'}
      </button>
    </div>
  )
}

// ─── Progress View ──────────────────────────────────────────
function ProgressView({ jobId, onComplete, onError }) {
  const [status, setStatus] = useState('pending')

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/job/${jobId}`)
        if (!res.ok) return
        const data = await res.json()
        setStatus(data.status)

        if (data.status === 'completed') {
          clearInterval(timer)
          onComplete(jobId)
        } else if (data.status === 'failed') {
          clearInterval(timer)
          onError(data.error_message || 'Pipeline failed.')
        }
      } catch (e) {
        console.error('Poll error:', e)
      }
    }, 1200)
    return () => clearInterval(timer)
  }, [jobId, onComplete, onError])

  const pct = STAGE_PCT[status] || 0

  function pillClass(stage) {
    const idx = STAGES.indexOf(stage)
    const currentIdx = STAGES.indexOf(status)
    if (idx === currentIdx) return 'step-pill active'
    if (idx < currentIdx) return 'step-pill done'
    return 'step-pill'
  }

  return (
    <div className="card">
      <h2>Processing…</h2>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="status-text">{status}</p>
      <div className="steps">
        {STAGES.map(s => (
          <span key={s} className={pillClass(s)}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </span>
        ))}
      </div>
    </div>
  )
}

// ─── Results View ───────────────────────────────────────────
function ResultsView({ jobId, onReset }) {
  const [manifest, setManifest] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/v1/job/${jobId}/files`)
        if (!res.ok) throw new Error('Could not load results')
        setManifest(await res.json())
      } catch (e) {
        setError(e.message)
      }
    }
    load()
  }, [jobId])

  if (error) return <ErrorView message={error} onRetry={onReset} />
  if (!manifest) return <div className="card"><h2>Loading results…</h2></div>

  return (
    <div className="card">
      <h2>✅ Classification Complete</h2>
      {manifest.taxonomy_summary && <p>{manifest.taxonomy_summary}</p>}

      <div className="metrics">
        <div className="metric">
          <strong>{manifest.total_exported_rows.toLocaleString()}</strong>
          <span>Rows</span>
        </div>
        <div className="metric">
          <strong>{manifest.total_unique_categories.toLocaleString()}</strong>
          <span>Categories</span>
        </div>
        <div className="metric">
          <strong>{manifest.total_groups.toLocaleString()}</strong>
          <span>Groups</span>
        </div>
      </div>

      {manifest.groups?.length > 0 && (
        <table className="groups-table">
          <thead>
            <tr><th>#</th><th>Group</th><th>File</th><th>Rows</th></tr>
          </thead>
          <tbody>
            {manifest.groups.map((g, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{g.group_name}</td>
                <td>{g.filename}</td>
                <td>{g.row_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="actions">
        <a className="btn" href={`/api/v1/download/${jobId}`} download>
          Download ZIP
        </a>
        <button className="btn btn-outline" onClick={onReset}>New File</button>
      </div>
    </div>
  )
}

// ─── Error View ─────────────────────────────────────────────
function ErrorView({ message, onRetry }) {
  return (
    <div className="card card-error">
      <h2>❌ Error</h2>
      <p style={{ margin: '0.5rem 0 1rem', color: '#666' }}>{message}</p>
      <button className="btn" onClick={onRetry}>Try Again</button>
    </div>
  )
}

// ─── App ────────────────────────────────────────────────────
function App() {
  const [view, setView] = useState('upload')   // upload | progress | results | error
  const [jobId, setJobId] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')

  const handleJobStarted = useCallback((id) => {
    setJobId(id)
    setView('progress')
  }, [])

  const handleComplete = useCallback((id) => {
    setJobId(id)
    setView('results')
  }, [])

  const handleError = useCallback((msg) => {
    setErrorMsg(msg)
    setView('error')
  }, [])

  const handleReset = useCallback(() => {
    setJobId(null)
    setErrorMsg('')
    setView('upload')
  }, [])

  return (
    <div className="app">
      <header>
        <h1>📄 CSV Classifier</h1>
        <p>Upload a CSV or Excel file, pick a column, and let AI classify it.</p>
      </header>

      {view === 'upload' && <UploadView onJobStarted={handleJobStarted} />}
      {view === 'progress' && (
        <ProgressView jobId={jobId} onComplete={handleComplete} onError={handleError} />
      )}
      {view === 'results' && <ResultsView jobId={jobId} onReset={handleReset} />}
      {view === 'error' && <ErrorView message={errorMsg} onRetry={handleReset} />}
    </div>
  )
}

export default App
