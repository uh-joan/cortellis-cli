import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getInsights } from '../lib/api.js'

const INDICATION_COLORS = {
  obesity: '#4f8ef7',
  diabetes: '#22c55e',
  cardiovascular: '#f59e0b',
  oncology: '#ef4444',
  masld: '#a78bfa',
  nash: '#a78bfa',
}

function indicationColor(indication) {
  const key = Object.keys(INDICATION_COLORS).find(k => indication?.toLowerCase().includes(k))
  return key ? INDICATION_COLORS[key] : '#6b7280'
}

export default function InsightsPage({ workspace }) {
  const [insights, setInsights] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    getInsights(workspace)
      .then(setInsights)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [workspace])

  if (loading) return <div className="insights-loading">Loading insights…</div>

  if (insights.length === 0) {
    return (
      <div className="insights-empty">
        <div className="empty-logo">🔬</div>
        <div className="empty-title">No compiled insights yet</div>
        <div className="empty-hint">Run a landscape analysis to generate strategic insights.</div>
        <code className="insights-hint-cmd">cortellis web</code>
        <div className="empty-hint">then ask: <em>obesity landscape</em></div>
      </div>
    )
  }

  if (selected) {
    return (
      <div className="insights-detail">
        <div className="insights-detail-header">
          <button className="wiki-back" onClick={() => setSelected(null)}>← All Insights</button>
          <div className="insights-detail-meta">
            <span
              className="insights-indication-badge"
              style={{ background: indicationColor(selected.meta?.indication) + '22', color: indicationColor(selected.meta?.indication) }}
            >
              {selected.meta?.indication}
            </span>
            <span className="insights-ts">{selected.meta?.timestamp?.slice(0, 10)}</span>
          </div>
        </div>
        <div className="insights-detail-body wiki-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.body}</ReactMarkdown>
        </div>
      </div>
    )
  }

  return (
    <div className="insights-page">
      <div className="insights-header">
        <h1 className="insights-title">Strategic Insights</h1>
        <div className="insights-subtitle">{insights.length} compiled landscape{insights.length !== 1 ? 's' : ''}</div>
      </div>

      <div className="insights-grid">
        {insights.map((ins, i) => (
          <InsightCard key={i} insight={ins} onClick={() => setSelected(ins)} />
        ))}
      </div>
    </div>
  )
}

function InsightCard({ insight, onClick }) {
  const { meta, preview } = insight
  const color = indicationColor(meta?.indication)

  // Extract a few bullet points from preview
  const bullets = preview
    .split('\n')
    .filter(l => l.trim().startsWith('-') || l.trim().match(/^\d+\./))
    .slice(0, 3)
    .map(l => l.replace(/^[-\d.]+\s*\*?\*?/, '').replace(/\*\*/g, '').trim())

  return (
    <div className="insight-card" onClick={onClick}>
      <div className="insight-card-top" style={{ borderTop: `3px solid ${color}` }}>
        <div className="insight-card-header">
          <span
            className="insights-indication-badge"
            style={{ background: color + '22', color }}
          >
            {meta?.indication || 'unknown'}
          </span>
          <span className="insight-ts">{meta?.timestamp?.slice(0, 10)}</span>
        </div>
        <h3 className="insight-card-title">{meta?.title}</h3>
      </div>

      {bullets.length > 0 && (
        <ul className="insight-card-bullets">
          {bullets.map((b, i) => <li key={i}>{b.slice(0, 100)}</li>)}
        </ul>
      )}

      {meta?.tags?.length > 0 && (
        <div className="insight-card-tags">
          {meta.tags.slice(0, 4).map(t => (
            <span key={t} className="insight-tag">{t}</span>
          ))}
        </div>
      )}

      <div className="insight-card-cta">View full analysis →</div>
    </div>
  )
}
