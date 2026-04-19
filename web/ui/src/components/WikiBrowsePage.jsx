import { useState, useEffect, useMemo } from 'react'
import { listWiki, postWikiRefresh, pollJob } from '../lib/api.js'

const TYPE_LABELS = {
  indications: 'Indications',
  drugs: 'Drugs',
  companies: 'Companies',
  targets: 'Targets',
  internal: 'Internal Research',
  conferences: 'Conferences',
  sessions: 'Session Insights',
  root: 'Index',
}

const TYPE_ORDER = ['indications', 'drugs', 'companies', 'targets', 'internal', 'conferences', 'sessions']

export default function WikiBrowsePage({ workspace, onArticleOpen, onShowGraph }) {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('list')
  const [search, setSearch] = useState('')
  const [collapsed, setCollapsed] = useState(
    TYPE_ORDER.reduce((acc, t) => ({ ...acc, [t]: true }), {})
  )
  const [refreshState, setRefreshState] = useState(null) // null | 'running' | 'done' | 'error'
  const [refreshMsg, setRefreshMsg] = useState('')

  function loadArticles() {
    return listWiki(workspace).then(a => { setArticles(a); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { loadArticles() }, [workspace])

  async function handleRefresh() {
    if (refreshState === 'running') return
    setRefreshState('running')
    setRefreshMsg('')
    try {
      const { job_id } = await postWikiRefresh(workspace)
      const interval = setInterval(async () => {
        const job = await pollJob(job_id)
        if (job.status !== 'running') {
          clearInterval(interval)
          await loadArticles()
          if (job.status === 'error') {
            setRefreshState('error')
            setRefreshMsg(job.output?.split('\n').slice(-3).join(' ') || 'Refresh failed.')
          } else {
            setRefreshState('done')
            setRefreshMsg('Wiki articles rebuilt successfully.')
            setTimeout(() => setRefreshState(null), 3000)
          }
        }
      }, 500)
    } catch (e) {
      setRefreshState('error')
      setRefreshMsg(e.message)
    }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return articles
    const q = search.toLowerCase()
    return articles.filter(a =>
      a.title.toLowerCase().includes(q) || a.slug.toLowerCase().includes(q)
    )
  }, [articles, search])

  const { rootFiles, byType } = useMemo(() => {
    const root = []
    const byT = {}
    for (const a of filtered) {
      if (a.type === 'root' || !a.type) {
        root.push(a)
      } else {
        if (!byT[a.type]) byT[a.type] = []
        byT[a.type].push(a)
      }
    }
    return { rootFiles: root, byType: byT }
  }, [filtered])

  function toggleCollapse(type) {
    setCollapsed(prev => ({ ...prev, [type]: !prev[type] }))
  }

  const sections = TYPE_ORDER.filter(t => byType[t]?.length)

  return (
    <div className="wiki-browse">
      <div className="wiki-browse-header">
        <h1 className="wiki-browse-title">Wiki</h1>
        <div className="wiki-browse-controls">
          <input
            className="wiki-search"
            placeholder="Search articles..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <div className="wiki-view-toggle">
            <button
              className={`wiki-view-btn ${view === 'list' ? 'active' : ''}`}
              onClick={() => setView('list')}
              title="List view"
            >≡</button>
            <button
              className={`wiki-view-btn ${view === 'cards' ? 'active' : ''}`}
              onClick={() => setView('cards')}
              title="Card view"
            >⊞</button>
          </div>
          <button className="wiki-graph-btn" onClick={onShowGraph}>◎ Graph</button>
          <button className={`wiki-graph-btn ${refreshState === 'running' ? 'disabled' : ''}`} onClick={handleRefresh} disabled={refreshState === 'running'}>
            {refreshState === 'running' ? '⟳ Refreshing…' : '⟳ Refresh'}
          </button>
        </div>
      </div>

      {refreshState && (
        <div className={`wiki-refresh-banner wiki-refresh-banner--${refreshState}`}>
          {refreshState === 'running' && <span className="wiki-refresh-spinner">⟳</span>}
          {refreshState === 'done'    && <span>✓</span>}
          {refreshState === 'error'   && <span>✗</span>}
          {refreshState === 'running' ? 'Rebuilding wiki articles from cached data… this may take 1–3 minutes.' : refreshMsg}
          {refreshState !== 'running' && (
            <button className="wiki-refresh-dismiss" onClick={() => setRefreshState(null)}>×</button>
          )}
        </div>
      )}

      <div className="wiki-browse-body">
        {loading ? (
          <div className="wiki-browse-loading">Loading…</div>
        ) : (
          <>
            {rootFiles.length > 0 && (
              <div className="wiki-root-files">
                {rootFiles.map(a => (
                  <div key={a.slug} className="wiki-root-file" onClick={() => onArticleOpen(a)}>
                    {a.title}
                  </div>
                ))}
              </div>
            )}
            {sections.length === 0 && rootFiles.length === 0 ? (
              <div className="wiki-browse-empty">No articles found</div>
            ) : sections.map(type => (
              <WikiSection
                key={type}
                type={type}
                articles={byType[type]}
                view={view}
                collapsed={!!collapsed[type]}
                onToggle={() => toggleCollapse(type)}
                onOpen={onArticleOpen}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}

function WikiSection({ type, articles, view, collapsed, onToggle, onOpen }) {
  return (
    <div className="wiki-section">
      <div className="wiki-section-header" onClick={onToggle}>
        <span className={`wiki-section-chevron ${collapsed ? 'collapsed' : ''}`}>›</span>
        <span className="wiki-section-name">{TYPE_LABELS[type] || type}</span>
        <span className="wiki-section-count">{articles.length}</span>
      </div>
      {!collapsed && (
        view === 'cards'
          ? (
            <div className="wiki-cards-grid">
              {articles.map(a => (
                <div key={a.slug} className="wiki-card" onClick={() => onOpen(a)}>
                  <div className="wiki-card-title">{a.title}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="wiki-list">
              {articles.map(a => (
                <div key={a.slug} className="wiki-list-item" onClick={() => onOpen(a)}>
                  {a.title}
                </div>
              ))}
            </div>
          )
      )}
    </div>
  )
}
