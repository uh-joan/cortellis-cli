
const NAV_ITEMS = [
  { id: 'wiki',          label: 'Wiki',          icon: '◎' },
  { id: 'insights',      label: 'Insights',      icon: '✦' },
  { id: 'internal-docs', label: 'Internal', icon: '⬙' },
  { id: 'signals',       label: 'Signals',       icon: '◈' },
]

export default function ConversationSidebar({
  conversations, activeConvId, tab,
  insightsActive, memoryActive, cliSessionsActive, signalsActive, internalDocsActive,
  onNewChat, onSelectConv, onDeleteConv,
  onShowWiki, onShowMemory, onShowInsights, onShowCliSessions, onShowSignals, onShowInternalDocs, onGoHome,
}) {

  const webConvs = conversations.filter(c => !c.title.startsWith('CLI — '))
  const cliConvs = conversations.filter(c => c.title.startsWith('CLI — '))
  const convIsActive = !insightsActive && !memoryActive && !signalsActive && !internalDocsActive && tab === 'chats'

  function isNavActive(id) {
    if (id === 'wiki')          return tab === 'wiki' && !insightsActive && !memoryActive && !signalsActive && !internalDocsActive
    if (id === 'insights')      return insightsActive
    if (id === 'signals')       return signalsActive
    if (id === 'internal-docs') return internalDocsActive
    return false
  }

  function handleNavClick(id) {
    if (id === 'wiki')          onShowWiki()
    if (id === 'insights')      onShowInsights()
    if (id === 'signals')       onShowSignals()
    if (id === 'internal-docs') onShowInternalDocs()
  }

  return (
    <div className="sidebar">
      <div className="sidebar-header" onClick={onGoHome}>
        <div className="sidebar-title">Cortellis</div>
      </div>

      <nav className="sidebar-nav">
        <button className="sidebar-nav-item new-chat-item" onClick={onNewChat}>
          <span className="sidebar-nav-icon new-chat-icon">+</span>
          <span>New chat</span>
        </button>

        <div className="sidebar-nav-divider" />

        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`sidebar-nav-item ${isNavActive(item.id) ? 'active' : ''}`}
            onClick={() => handleNavClick(item.id)}
          >
            <span className="sidebar-nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-section-label">Recent</div>

      <div className="sidebar-body">
        {webConvs.length === 0 && cliConvs.length === 0 && (
          <div className="no-convs">No conversations yet</div>
        )}
        {webConvs.map(conv => (
          <ConvItem
            key={conv.id} conv={conv}
            active={convIsActive && conv.id === activeConvId}
            onSelect={() => onSelectConv(conv.id)}
            onDelete={() => onDeleteConv(conv.id)}
          />
        ))}
        {(
          <div className="cli-section">
            <button className={`cli-toggle memory-link ${memoryActive ? 'active' : ''}`} onClick={onShowMemory}>
              Memory
            </button>
            {cliConvs.length > 0 && (
              <button className={`cli-toggle memory-link ${cliSessionsActive ? 'active' : ''}`} onClick={onShowCliSessions}>
                Sessions
              </button>
            )}
          </div>
        )}
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
  return date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()
}
