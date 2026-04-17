import { useState, useEffect } from 'react'
import { getSignals, getSessions } from '../lib/api.js'

const SEV_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#6b7280' }

export default function MemoryPanel({ workspace }) {
  const [signals, setSignals] = useState([])
  const [sessions, setSessions] = useState([])
  const [section, setSection] = useState('signals')
  const [expandedSession, setExpandedSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([getSignals(workspace), getSessions(workspace)])
      .then(([s, sess]) => { setSignals(s); setSessions(sess) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [workspace])

  if (loading) return <div className="memory-loading">Loading…</div>

  return (
    <div className="memory-panel">
      <div className="memory-tabs">
        <button
          className={`memory-tab ${section === 'signals' ? 'active' : ''}`}
          onClick={() => setSection('signals')}
        >
          Signals{signals.length ? ` (${signals.length})` : ''}
        </button>
        <button
          className={`memory-tab ${section === 'sessions' ? 'active' : ''}`}
          onClick={() => setSection('sessions')}
        >
          History{sessions.length ? ` (${sessions.length})` : ''}
        </button>
      </div>

      <div className="memory-body">
        {section === 'signals' && (
          signals.length === 0 ? (
            <div className="memory-empty">No signals detected yet.<br />Run a landscape analysis to generate signals.</div>
          ) : (
            signals.map((s, i) => (
              <div key={i} className="memory-signal">
                <div className="memory-signal-header">
                  <span className="memory-signal-sev" style={{ color: SEV_COLOR[s.severity] }}>
                    {s.severity?.toUpperCase()}
                  </span>
                  <span className="memory-signal-indication">{s.indication}</span>
                </div>
                <div className="memory-signal-summary">{s.summary}</div>
                {s.action && <div className="memory-signal-action">→ {s.action}</div>}
              </div>
            ))
          )
        )}

        {section === 'sessions' && (
          sessions.length === 0 ? (
            <div className="memory-empty">No session history found in daily/</div>
          ) : (
            sessions.map((s, i) => (
              <div
                key={i}
                className="memory-session"
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
            ))
          )
        )}
      </div>
    </div>
  )
}
