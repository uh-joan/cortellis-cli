import { useState, useEffect, useCallback } from 'react'
import { listWiki } from '../lib/api.js'
import MemoryPanel from './MemoryPanel.jsx'

const TYPE_LABELS = {
  indications: 'Indications',
  companies: 'Companies',
  drugs: 'Drugs',
  targets: 'Targets',
  internal: 'Internal Research',
  conferences: 'Conferences',
  sessions: 'Session Insights',
  root: 'Index',
}

export default function ConversationSidebar({
  conversations, activeConvId, tab, workspace,
  onTabChange, onNewChat, onSelectConv, onDeleteConv,
  onWikiOpen, onShowInsights, onShowGraph, onGoHome,
  activeWikiSlug, insightsActive,
}) {
  const [wikiArticles, setWikiArticles] = useState([])
  const [openTypes, setOpenTypes] = useState({})
  const [showCli, setShowCli] = useState(false)

  const loadWiki = useCallback(async () => {
    const articles = await listWiki(workspace)
    setWikiArticles(articles)
  }, [workspace])

  useEffect(() => {
    if (tab === 'wiki') loadWiki()
  }, [tab, loadWiki])

  const wikiByType = wikiArticles.reduce((acc, a) => {
    if (!acc[a.type]) acc[a.type] = []
    acc[a.type].push(a)
    return acc
  }, {})

  function toggleType(type) {
    setOpenTypes(prev => ({ ...prev, [type]: !prev[type] }))
  }

  const typeOrder = ['root', 'indications', 'companies', 'drugs', 'targets', 'internal', 'conferences', 'sessions']

  return (
    <div className="sidebar">
      <div className="sidebar-header" onClick={onGoHome} style={{ cursor: 'pointer' }}>
        <div>
          <div className="sidebar-title">Cortellis</div>
          <div className="sidebar-subtitle">Intelligence Platform</div>
        </div>
      </div>

      <div className="sidebar-tabs">
        {['chats', 'wiki', 'memory'].map(t => (
          <button
            key={t}
            className={`sidebar-tab ${tab === t && !insightsActive ? 'active' : ''}`}
            onClick={() => onTabChange(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="sidebar-body">
        {tab === 'chats' && (
          <>
            <button className="new-chat-btn" onClick={onNewChat}>+ New Chat</button>
            {(() => {
              const webConvs = conversations.filter(c => !c.title.startsWith('CLI — '))
              const cliConvs = conversations.filter(c => c.title.startsWith('CLI — '))
              return (
                <>
                  {webConvs.length === 0 && cliConvs.length === 0 && (
                    <div className="no-convs">No conversations yet</div>
                  )}
                  {webConvs.map(conv => (
                    <ConvItem key={conv.id} conv={conv}
                      active={conv.id === activeConvId && !insightsActive}
                      onSelect={() => onSelectConv(conv.id)}
                      onDelete={() => onDeleteConv(conv.id)} />
                  ))}
                  {cliConvs.length > 0 && (
                    <div className="cli-section">
                      <button className="cli-toggle" onClick={() => setShowCli(s => !s)}>
                        CLI sessions ({cliConvs.length}) {showCli ? '▲' : '▼'}
                      </button>
                      {showCli && cliConvs.map(conv => (
                        <ConvItem key={conv.id} conv={conv}
                          active={conv.id === activeConvId && !insightsActive}
                          onSelect={() => onSelectConv(conv.id)}
                          onDelete={() => onDeleteConv(conv.id)} />
                      ))}
                    </div>
                  )}
                </>
              )
            })()}
          </>
        )}

        {tab === 'wiki' && (
          <>
            <button className="wiki-graph-cta" onClick={onShowGraph}>◎ Graph view</button>

            {Object.keys(wikiByType).length === 0 ? (
              <div className="no-convs">No wiki articles yet</div>
            ) : (
              typeOrder.filter(t => wikiByType[t]?.length).map(type => {
                const articles = wikiByType[type]
                const isOpen = !!openTypes[type]
                return (
                  <div key={type}>
                    <div
                      className="wiki-type-header wiki-type-toggle"
                      onClick={() => toggleType(type)}
                    >
                      <span>{TYPE_LABELS[type] || type}</span>
                      <span className="wiki-type-count">{articles.length} {isOpen ? '▲' : '▼'}</span>
                    </div>
                    {isOpen && articles.map(a => (
                      <div
                        key={a.slug}
                        className={`wiki-item ${activeWikiSlug === a.slug ? 'active' : ''}`}
                        onClick={() => onWikiOpen(a)}
                      >
                        {a.title}
                      </div>
                    ))}
                  </div>
                )
              })
            )}
          </>
        )}

        {tab === 'memory' && <MemoryPanel workspace={workspace} />}
      </div>

      <div className="sidebar-footer">
        <button
          className={`insights-nav-btn ${insightsActive ? 'active' : ''}`}
          onClick={onShowInsights}
        >
          Strategic Insights
        </button>
      </div>
    </div>
  )
}

function ConvItem({ conv, active, onSelect, onDelete }) {
  const date = new Date(conv.updated_at)
  const label = isToday(date)
    ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' })
  const isCli = conv.title.startsWith('CLI — ')

  return (
    <div className={`conv-item ${active ? 'active' : ''}`} onClick={onSelect}>
      {isCli && <span className="conv-cli-badge">CLI</span>}
      <span className="conv-title">{conv.title.replace('CLI — ', '')}</span>
      <span className="conv-date">{label}</span>
      <button className="conv-delete" onClick={e => { e.stopPropagation(); onDelete() }} title="Delete">×</button>
    </div>
  )
}

function isToday(date) {
  const now = new Date()
  return date.getDate() === now.getDate() && date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear()
}
