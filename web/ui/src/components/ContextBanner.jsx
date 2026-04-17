import { useState, useEffect } from 'react'
import { getContextSummary } from '../lib/api.js'

const SEVERITY_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#6b7280' }
const SEVERITY_LABEL = { high: 'HIGH', medium: 'MED', low: 'LOW' }

export default function ContextBanner({ workspace }) {
  const [summary, setSummary] = useState(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    getContextSummary(workspace).then(setSummary).catch(() => {})
  }, [workspace])

  if (!summary || (summary.signal_count === 0 && summary.landscape_count === 0)) return null

  const hasSignals = summary.signal_count > 0

  return (
    <div className="context-banner">
      <div className="context-banner-bar" onClick={() => setExpanded(e => !e)}>
        <div className="context-banner-pills">
          {summary.high_signal_count > 0 && (
            <span className="context-pill high">{summary.high_signal_count} HIGH</span>
          )}
          {summary.medium_signal_count > 0 && (
            <span className="context-pill medium">{summary.medium_signal_count} MED</span>
          )}
          {summary.landscape_count > 0 && (
            <span className="context-pill neutral">{summary.landscape_count} landscapes</span>
          )}
          {summary.last_session && (
            <span className="context-pill neutral">last session: {summary.last_session}</span>
          )}
        </div>
        <span className="context-banner-toggle">{expanded ? '▲' : '▼'} signals</span>
      </div>

      {expanded && hasSignals && (
        <div className="context-banner-detail">
          {summary.top_signals.map((s, i) => (
            <div key={i} className="context-signal-row">
              <span
                className="context-signal-severity"
                style={{ color: SEVERITY_COLOR[s.severity] || '#6b7280' }}
              >
                {SEVERITY_LABEL[s.severity] || s.severity?.toUpperCase()}
              </span>
              <span className="context-signal-indication">{s.indication}</span>
              <span className="context-signal-summary">{s.summary}</span>
            </div>
          ))}
          {summary.signal_count > 3 && (
            <div className="context-signal-more">
              +{summary.signal_count - 3} more signals — see Memory tab
            </div>
          )}
        </div>
      )}
    </div>
  )
}
