import { useState, useEffect } from 'react'
import { getSessions } from '../lib/api.js'

export default function MemoryPanel({ workspace }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedSession, setExpandedSession] = useState(null)

  useEffect(() => {
    setLoading(true)
    getSessions(workspace)
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [workspace])

  if (loading) return <div className="memory-loading">Loading…</div>

  return (
    <div className="memory-panel">
      <div className="memory-body">
        {sessions.length === 0 ? (
          <div className="memory-empty">No session history found.</div>
        ) : sessions.map((s, i) => (
          <div
            key={i}
            className={`memory-session ${expandedSession === i ? 'expanded' : ''}`}
            onClick={() => setExpandedSession(expandedSession === i ? null : i)}
          >
            <div className="memory-session-header">
              <span className="memory-session-date">{s.date}</span>
              <span className="memory-session-time">{s.time}</span>
              <span className="memory-session-chevron">{expandedSession === i ? '▲' : '▼'}</span>
            </div>
            <div className="memory-session-preview">{s.summary.slice(0, 120)}…</div>
            {expandedSession === i && (
              <div className="memory-session-detail">
                <div className="memory-session-full">{s.summary}</div>
                {s.insights && (
                  <div className="memory-session-insights">
                    <div className="memory-section-label">Strategic Insights</div>
                    <div className="memory-session-full">{s.insights}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
