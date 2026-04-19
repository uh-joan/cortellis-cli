import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getSignalsReport, runSignals, pollSignalsJob } from '../lib/api.js'

export default function SignalsPage({ workspace }) {
  const [report, setReport] = useState(null)
  const [exists, setExists] = useState(false)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  async function fetchReport() {
    const data = await getSignalsReport(workspace)
    setReport(data.content)
    setExists(data.exists)
    setLoading(false)
  }

  useEffect(() => {
    fetchReport()
    return () => clearInterval(intervalRef.current)
  }, [workspace])

  async function handleRerun() {
    if (running) return
    setRunning(true)
    setError(null)
    try {
      const { job_id } = await runSignals(workspace)
      intervalRef.current = setInterval(async () => {
        const job = await pollSignalsJob(job_id)
        if (job.status !== 'running') {
          clearInterval(intervalRef.current)
          if (job.status === 'error') setError(job.output || 'Signals run failed.')
          else await fetchReport()
          setRunning(false)
        }
      }, 2000)
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  return (
    <div className="signals-page">
      <div className="signals-header">
        <div className="signals-header-left">
          <h1 className="signals-title">Signals</h1>
          <div className="signals-subtitle">Competitive intelligence briefing</div>
        </div>
        <button className="wiki-graph-btn" onClick={handleRerun} disabled={running}>
          {running ? '⟳ Running…' : '⟳ Re-run'}
        </button>
      </div>

      {loading && <div className="insights-loading">Loading…</div>}

      {!loading && !exists && !running && (
        <div className="insights-empty">
          <div className="empty-logo">⚡</div>
          <div className="empty-title">No signals report yet</div>
          <div className="empty-hint">Click Re-run to generate your first competitive intelligence briefing.</div>
        </div>
      )}

      {running && !report && (
        <div className="insights-loading">Scanning wiki and raw data for signals…</div>
      )}

      {error && <div className="signals-error">{error}</div>}

      {report && (
        <div className={`signals-body wiki-content ${running ? 'signals-body--stale' : ''}`}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}
