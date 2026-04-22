import { useState, useEffect, useCallback, useRef } from 'react'
import ConversationSidebar from './components/ConversationSidebar.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import WikiPanel from './components/WikiPanel.jsx'
import WikiGraph from './components/WikiGraph.jsx'
import WikiBrowsePage from './components/WikiBrowsePage.jsx'
import InsightsPage from './pages/InsightsPage.jsx'
import SignalsPage from './pages/SignalsPage.jsx'
import InternalDocsPage from './pages/InternalDocsPage.jsx'
import MemoryPanel from './components/MemoryPanel.jsx'
import { listConversations, createConversation, deleteConversation } from './lib/api.js'

export default function App() {
  const [workspace, setWorkspace] = useState(window.__WORKSPACE__ || null)
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [tab, setTab] = useState('chats')
  const [view, setView] = useState('chat') // 'chat' | 'insights' | 'memory' | 'cli-sessions' | 'signals' | 'internal-docs'
  const [pendingMessage, setPendingMessage] = useState(null)
  const [wikiMode, setWikiMode] = useState('list') // 'list' | 'graph'
  const [wikiArticle, setWikiArticle] = useState(null)
  const [wikiHistory, setWikiHistory] = useState([])
  const [engine, setEngine] = useState(() => localStorage.getItem('cortellis_engine') || 'claude')

  useEffect(() => { localStorage.setItem('cortellis_engine', engine) }, [engine])

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

  function handleNewChat() {
    setActiveConvId(null)
    setView('chat')
    setWikiArticle(null)
    setWikiMode('list')
    setTab('chats')
  }

  async function handleStartChat(message) {
    const conv = await createConversation(workspace)
    setConversations(prev => [conv, ...prev])
    setActiveConvId(conv.id)
    setTab('chats')
    setWikiArticle(null)
    setView('chat')
    setPendingMessage(message)
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
    setTab('chats')
    setWikiHistory([])
  }

  function handleWikiOpen(article) {
    setWikiHistory([])
    setWikiArticle(article)
    setWikiMode('list')
    setTab('wiki')
    setView('chat')
  }

  function handleWikiNavigate(article) {
    setWikiHistory(prev => wikiArticle ? [...prev, wikiArticle] : prev)
    setWikiArticle(article)
  }

  function handleWikiBack() {
    if (wikiHistory.length > 0) {
      const prev = wikiHistory[wikiHistory.length - 1]
      setWikiHistory(h => h.slice(0, -1))
      setWikiArticle(prev)
    } else {
      setWikiArticle(null)
    }
  }

  function handleConvTitleUpdate(convId, title) {
    setConversations(prev => prev.map(c => c.id === convId ? { ...c, title } : c))
  }

  function handleShowWiki() {
    setWikiMode('list')
    setTab('wiki')
    setWikiArticle(null)
    setWikiHistory([])
    setView('chat')
  }

  function handleShowGraph() {
    setWikiMode('graph')
    setTab('wiki')
    setWikiArticle(null)
    setView('chat')
  }

  function handleShowMemory() {
    setView('memory')
    setWikiArticle(null)
  }

  function handleShowCliSessions() {
    setView('cli-sessions')
    setActiveConvId(null)
    setWikiArticle(null)
  }

  function handleShowSignals() {
    setView('signals')
    setWikiArticle(null)
  }

  function handleShowInternalDocs() {
    setView('internal-docs')
    setWikiArticle(null)
  }

  function handleExitGraph() {
    setWikiMode('list')
    setTab('chats')
  }

  const showGraph = tab === 'wiki' && wikiMode === 'graph' && view === 'chat'
  const showWikiBrowse = tab === 'wiki' && wikiMode === 'list' && !wikiArticle && view === 'chat'
  const showWikiArticle = tab === 'wiki' && wikiMode === 'list' && !!wikiArticle && view === 'chat'
  const showInsights = view === 'insights'
  const showMemory = view === 'memory'
  const showCliSessions = view === 'cli-sessions'
  const showSignals = view === 'signals'
  const showInternalDocs = view === 'internal-docs'
  const showChat = view === 'chat' && !showGraph && !showWikiBrowse && !showWikiArticle

  return (
    <div className="app">
      <ConversationSidebar
        conversations={conversations}
        activeConvId={activeConvId}
        tab={tab}
        insightsActive={showInsights}
        memoryActive={showMemory}
        cliSessionsActive={showCliSessions}
        signalsActive={showSignals}
        internalDocsActive={showInternalDocs}
        onNewChat={handleNewChat}
        onSelectConv={handleSelectConv}
        onDeleteConv={handleDeleteConv}
        onShowWiki={handleShowWiki}
        onShowMemory={handleShowMemory}
        onShowCliSessions={handleShowCliSessions}
        onShowInsights={() => { setView('insights'); setWikiArticle(null) }}
        onShowSignals={handleShowSignals}
        onShowInternalDocs={handleShowInternalDocs}
        onGoHome={handleGoHome}
      />

      <div className="main">
        {showSignals && <SignalsPage workspace={workspace} />}
        {showInternalDocs && <InternalDocsPage workspace={workspace} onArticleOpen={handleWikiOpen} />}
        {showInsights && <InsightsPage workspace={workspace} />}

        {showMemory && (
          <div className="memory-main">
            <div className="memory-main-header">
              <h2>Memory</h2>
            </div>
            <MemoryPanel workspace={workspace} />
          </div>
        )}

        {showCliSessions && (
          <div className="memory-main">
            <div className="memory-main-header">
              <h2>Sessions</h2>
            </div>
            <div className="memory-body">
              {conversations.filter(c => c.title.startsWith('CLI — ')).map(conv => {
                const date = new Date(conv.updated_at)
                return (
                  <div key={conv.id} className="memory-session" onClick={() => handleSelectConv(conv.id)}>
                    <div className="memory-session-header">
                      <span className="memory-session-date">{date.toLocaleDateString()}</span>
                      <span className="memory-session-time">{date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div className="memory-session-preview">{conv.title.replace('CLI — ', '')}</div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {showWikiBrowse && (
          <WikiBrowsePage
            workspace={workspace}
            onArticleOpen={handleWikiOpen}
            onShowGraph={handleShowGraph}
          />
        )}

        {showGraph && (
          <WikiGraph
            workspace={workspace}
            onBack={handleShowWiki}
            onNodeClick={node => {
              const typeMap = { indication: 'indications', company: 'companies', drug: 'drugs', target: 'targets' }
              handleWikiOpen({ type: typeMap[node.type] || node.type, slug: node.slug, title: node.title })
            }}
          />
        )}

        {showWikiArticle && (
          <WikiPanel
            article={wikiArticle}
            onBack={handleWikiBack}
            onNavigate={handleWikiNavigate}
            historyDepth={wikiHistory.length}
          />
        )}

        {showChat && activeConvId && (
          <ChatPanel
            key={activeConvId}
            convId={activeConvId}
            workspace={workspace}
            initialMessage={pendingMessage}
            onReady={() => setPendingMessage(null)}
            onTitleUpdate={title => handleConvTitleUpdate(activeConvId, title)}
            readOnly={conversations.find(c => c.id === activeConvId)?.title.startsWith('CLI — ')}
            engine={engine}
          />
        )}

        {showChat && !activeConvId && (
          <EmptyState onStartChat={handleStartChat} engine={engine} onEngineChange={setEngine} />
        )}
      </div>
    </div>
  )
}

const SKILLS = [
  '/landscape',
  '/pipeline',
  '/drug-profile',
  '/target-profile',
  '/drug-comparison',
  '/signals',
  '/insights',
]

function EmptyState({ onStartChat, engine = 'claude', onEngineChange }) {
  const [input, setInput] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const inputRef = useRef(null)
  const suggestions = ['obesity landscape', 'Pfizer pipeline', 'GLP-1 receptor landscape', 'phase 3 trials for NASH']

  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e) {
      if (!menuRef.current?.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  function submit(msg) {
    const text = (msg ?? input).trim()
    if (text) onStartChat(text)
  }

  function pickSkill(skill) {
    setInput(skill + ' ')
    setMenuOpen(false)
    inputRef.current?.focus()
  }

  return (
    <div className="empty-state">
      <div className="empty-wordmark">
        <div className="empty-title">Cortellis</div>
        <div className="empty-subtitle">Pharmaceutical Intelligence</div>
      </div>
      <div className="empty-input-box">
        <input
          ref={inputRef}
          className="empty-input"
          placeholder="Ask about a drug, pipeline, or market..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          autoFocus
        />
        <div className="empty-input-toolbar">
          <div className="skill-menu-wrap" ref={menuRef}>
            <button
              className={`skill-menu-btn ${menuOpen ? 'open' : ''}`}
              onClick={() => setMenuOpen(o => !o)}
              title="Skills"
            >+</button>
            {menuOpen && (
              <div className="skill-menu">
                {SKILLS.map(s => (
                  <button key={s} className="skill-menu-item" onClick={() => pickSkill(s)}>{s}</button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="engine-selector">
        {['claude', 'codex', 'pi'].map(e => (
          <button
            key={e}
            className={`engine-pill${engine === e ? ' engine-pill-active' : ''}`}
            onClick={() => onEngineChange?.(e)}
          >{e.charAt(0).toUpperCase() + e.slice(1)}</button>
        ))}
      </div>
      <div className="empty-suggestions">
        {suggestions.map(s => (
          <button key={s} className="suggestion-chip" onClick={() => { setInput(s); inputRef.current?.focus() }}>{s}</button>
        ))}
      </div>
    </div>
  )
}
