import { useState, useEffect, useRef, useCallback } from 'react'
import { listMessages, sendMessage, renameConversation } from '../lib/api.js'
import MessageList from './MessageList.jsx'
import MessageInput from './MessageInput.jsx'
import ContextBanner from './ContextBanner.jsx'

export default function ChatPanel({ convId, workspace, initialMessage, onReady, onTitleUpdate, readOnly = false }) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [toolCalls, setToolCalls] = useState([])
  const bottomRef = useRef(null)
  const isFirstMessage = useRef(true)
  const isStreamingRef = useRef(false)

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    listMessages(convId).then(msgs => {
      setMessages(msgs)
      isFirstMessage.current = msgs.filter(m => m.role === 'user').length === 0
      if (!readOnly) setTimeout(scrollToBottom, 50)
      if (initialMessage && msgs.length === 0) {
        onReady?.()
        handleSend(initialMessage)
      }
    })
  }, [convId, scrollToBottom])

  async function handleSend(content) {
    if (!content.trim() || isStreamingRef.current) return
    isStreamingRef.current = true

    const userMsg = {
      id: `tmp-${Date.now()}`,
      conv_id: convId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setStreaming(true)
    setToolCalls([])
    setTimeout(scrollToBottom, 50)

    if (isFirstMessage.current) {
      const title = content.slice(0, 60) + (content.length > 60 ? '…' : '')
      renameConversation(convId, title).catch(() => {})
      onTitleUpdate(title)
      isFirstMessage.current = false
    }

    const assistantMsgId = `tmp-assistant-${Date.now()}`
    let assistantText = ''

    try {
      await sendMessage(convId, content, (event) => {
        if (event.type === 'tool_call') {
          setToolCalls(prev => {
            if (prev.find(t => t.status === event.status)) return prev
            return [...prev.slice(-4), { status: event.status, id: Date.now() }]
          })
          scrollToBottom()
        } else if (event.type === 'result') {
          assistantText = event.text
          setToolCalls([])
          setMessages(prev => {
            const filtered = prev.filter(m => m.id !== assistantMsgId)
            return [...filtered, {
              id: assistantMsgId,
              conv_id: convId,
              role: 'assistant',
              content: assistantText,
              created_at: new Date().toISOString(),
            }]
          })
          setTimeout(scrollToBottom, 50)
        } else if (event.type === 'error') {
          setMessages(prev => [...prev, {
            id: `err-${Date.now()}`,
            conv_id: convId,
            role: 'assistant',
            content: `**Error:** ${event.text}`,
            created_at: new Date().toISOString(),
          }])
        }
      })
    } catch (e) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        conv_id: convId,
        role: 'assistant',
        content: `**Error:** ${e.message}`,
        created_at: new Date().toISOString(),
      }])
    } finally {
      isStreamingRef.current = false
      setStreaming(false)
      setToolCalls([])
    }
  }

  return (
    <>
      <div className={`chat-area ${readOnly ? 'chat-area-readonly' : ''}`}>
        <div className="messages-wrap">
          <MessageList messages={messages} />

          {streaming && toolCalls.length > 0 && (
            <div className="tool-calls">
              {toolCalls.map(tc => (
                <div key={tc.id} className="tool-call">
                  <div className="tool-call-dot" />
                  {tc.status}
                </div>
              ))}
            </div>
          )}

          {streaming && toolCalls.length === 0 && (
            <div className="thinking">
              <div className="thinking-dots">
                <span /><span /><span />
              </div>
              Thinking…
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {!readOnly && <MessageInput onSend={handleSend} disabled={streaming} />}
    </>
  )
}
