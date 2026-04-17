const BASE = '/api'

export async function listConversations(workspacePath) {
  const res = await fetch(`${BASE}/conversations?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) throw new Error('Failed to fetch conversations')
  return res.json()
}

export async function createConversation(workspacePath, title = 'New conversation') {
  const res = await fetch(`${BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_path: workspacePath, title }),
  })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function deleteConversation(convId) {
  await fetch(`${BASE}/conversations/${convId}`, { method: 'DELETE' })
}

export async function renameConversation(convId, title) {
  await fetch(`${BASE}/conversations/${convId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function listMessages(convId) {
  const res = await fetch(`${BASE}/conversations/${convId}/messages`)
  if (!res.ok) throw new Error('Failed to fetch messages')
  return res.json()
}

export async function sendMessage(convId, content, onEvent) {
  const res = await fetch(`${BASE}/conversations/${convId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || 'Failed to send message')
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { onEvent(JSON.parse(line.slice(6))) } catch { /* ignore */ }
      }
    }
  }
}

export async function listWiki(workspacePath) {
  const res = await fetch(`${BASE}/wiki?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) return []
  return res.json()
}

export async function getWikiArticle(type, slug, workspacePath) {
  const res = await fetch(`${BASE}/wiki/${type}/${slug}?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) throw new Error('Article not found')
  return res.json()
}

// Memory & intelligence endpoints
export async function getContextSummary(workspacePath) {
  const res = await fetch(`${BASE}/context-summary?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) return null
  return res.json()
}

export async function getSignals(workspacePath) {
  const res = await fetch(`${BASE}/memory/signals?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) return []
  return res.json()
}

export async function getInsights(workspacePath) {
  const res = await fetch(`${BASE}/memory/insights?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) return []
  return res.json()
}

export async function getSessions(workspacePath) {
  const res = await fetch(`${BASE}/memory/sessions?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) return []
  return res.json()
}

export async function getActivityLog(workspacePath) {
  const res = await fetch(`${BASE}/memory/log?workspace_path=${encodeURIComponent(workspacePath)}`)
  if (!res.ok) return []
  return res.json()
}

export async function importHistory(workspacePath) {
  const res = await fetch(`${BASE}/import-history?workspace_path=${encodeURIComponent(workspacePath)}`, {
    method: 'POST',
  })
  if (!res.ok) return { imported: 0 }
  return res.json()
}
