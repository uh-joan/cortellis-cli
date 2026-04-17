import { useState, useEffect, useCallback } from 'react'
import ConversationSidebar from './components/ConversationSidebar.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import WikiPanel from './components/WikiPanel.jsx'
import WikiGraph from './components/WikiGraph.jsx'
import InsightsPage from './pages/InsightsPage.jsx'
import ContextBanner from './components/ContextBanner.jsx'
import { listConversations, createConversation, deleteConversation } from './lib/api.js'

export default function App() {
  const [workspace, setWorkspace] = useState(window.__WORKSPACE__ || null)
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [tab, setTab] = useState('chats')
  const [view, setView] = useState('chat') // 'chat' | 'insights'
  const [wikiMode, setWikiMode] = useState('list') // 'list' | 'graph'
  const [wikiArticle, setWikiArticle] = useState(null)

  useEffect(() => {
    if (!workspace) {
      fetch('/api/config').then(r => r.json()).then(d => setWorkspace(d.workspace_path)).catch(() => setWorkspace('.'))
    }
  }, [])

  const loadConversations = useCallback(async () => {
    if (!workspace) return
    try {
      const convs = await listConversations(workspace)
      setConversations(convs)
    } catch (e) {
      console.error(e)
    }
  }, [workspace])

  useEffect(() => { loadConversations() }, [loadConversations])

  function handleGoHome() {
    setActiveConvId(null)
    setView('chat')
    setWikiArticle(null)
    setWikiMode('list')
    setTab('chats')
  }

  async function handleNewChat() {
    const conv = await createConversation(workspace)
    setConversations(prev => [conv, ...prev])
    setActiveConvId(conv.id)
    setTab('chats')
    setWikiArticle(null)
    setView('chat')
  }

  async function handleDeleteConv(convId) {
    await deleteConversation(convId)
    setConversations(prev => prev.filter(c => c.id !== convId))
    if (activeConvId === convId) setActiveConvId(null)
  }

  function handleSelectConv(convId) {
    setActiveConvId(convId)
    setWikiArticle(null)
    setView('chat')
  }

  function handleWikiOpen(article) {
    setWikiArticle(article)
    setWikiMode('list')
    setTab('wiki')
    setView('chat')
  }

  function handleWikiNavigate(article) {
    setWikiArticle(article)
  }

  function handleConvTitleUpdate(convId, title) {
    setConversations(prev => prev.map(c => c.id === convId ? { ...c, title } : c))
  }

  function handleShowGraph() {
    setWikiMode('graph')
    setTab('wiki')
    setWikiArticle(null)
    setView('chat')
  }

  function handleExitGraph() {
    setWikiMode('list')
  }

  const showGraph = tab === 'wiki' && wikiMode === 'graph' && view !== 'insights'
  const showWikiArticle = tab === 'wiki' && wikiMode === 'list' && wikiArticle && view !== 'insights'
  const showInsights = view === 'insights'
  const showChat = !showInsights && !showGraph && !showWikiArticle

  return (
    <div className="app">
      <ConversationSidebar
        conversations={conversations}
        activeConvId={activeConvId}
        tab={tab}
        workspace={workspace}
        onTabChange={setTab}
        onNewChat={handleNewChat}
        onSelectConv={handleSelectConv}
        onDeleteConv={handleDeleteConv}
        onWikiOpen={handleWikiOpen}
        onShowInsights={() => { setView('insights'); setWikiArticle(null) }}
        onShowGraph={handleShowGraph}
        onGoHome={handleGoHome}
        activeWikiSlug={wikiArticle?.slug}
        insightsActive={view === 'insights'}
      />

      <div className="main">
        {showInsights && <InsightsPage workspace={workspace} />}

        {showGraph && (
          <WikiGraph
            workspace={workspace}
            onBack={handleExitGraph}
            onNodeClick={node => {
              const typeMap = { indication: 'indications', company: 'companies', drug: 'drugs', target: 'targets' }
              handleWikiOpen({ type: typeMap[node.type] || node.type, slug: node.slug, title: node.title })
            }}
          />
        )}

        {showWikiArticle && (
          <WikiPanel
            article={wikiArticle}
            onBack={() => { setWikiArticle(null); setWikiMode('list') }}
            onNavigate={handleWikiNavigate}
          />
        )}

        {showChat && activeConvId && (
          <ChatPanel
            key={activeConvId}
            convId={activeConvId}
            workspace={workspace}
            onTitleUpdate={title => handleConvTitleUpdate(activeConvId, title)}
          />
        )}

        {showChat && !activeConvId && (
          <EmptyState
            workspace={workspace}
            onNewChat={handleNewChat}
            onShowInsights={() => setView('insights')}
            onShowGraph={handleShowGraph}
          />
        )}
      </div>
    </div>
  )
}

const ASCII_BANNER = `  ╔═════════════════════════════════════════════════════════════════════════════╗
  ║                                                                             ║
  ║    ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗     ██╗     ██╗███████╗    ║
  ║   ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝██║     ██║     ██║██╔════╝    ║
  ║   ██║     ██║   ██║██████╔╝   ██║   █████╗  ██║     ██║     ██║███████╗    ║
  ║   ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝  ██║     ██║     ██║╚════██║    ║
  ║   ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗███████╗███████╗██║███████║    ║
  ║    ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝╚══════╝    ║
  ║                                                                             ║
  ║              P h a r m a c e u t i c a l   I n t e l l i g e n c e         ║
  ╚═════════════════════════════════════════════════════════════════════════════╝`

function EmptyState({ workspace, onNewChat, onShowInsights, onShowGraph }) {
  const suggestions = ['obesity landscape', 'Pfizer pipeline', 'deep dive on tirzepatide', 'GLP-1 receptor landscape', 'phase 3 trials for NASH']
  return (
    <div className="empty-state">
      <pre className="empty-banner">{ASCII_BANNER}</pre>
      <ContextBanner workspace={workspace} />
      <div className="empty-hint">Ask anything about drugs, pipelines, or competitive landscapes</div>
      <div className="empty-suggestions">
        {suggestions.map(s => <button key={s} className="suggestion-chip" onClick={onNewChat}>{s}</button>)}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button className="insights-cta-btn" onClick={onShowInsights}>View compiled insights →</button>
        <button className="insights-cta-btn" onClick={onShowGraph}>Open graph view →</button>
      </div>
    </div>
  )
}
