import { useState, useRef, useEffect } from 'react'

export default function MessageInput({ onSend, disabled }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [value])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  return (
    <div className="input-bar">
      <div className="input-wrap">
        <textarea
          ref={textareaRef}
          className="input-textarea"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about drugs, pipelines, landscapes… (Enter to send, Shift+Enter for newline)"
          disabled={disabled}
          rows={1}
        />
        <button
          className="send-btn"
          onClick={submit}
          disabled={disabled || !value.trim()}
          title="Send"
        >
          ↑
        </button>
      </div>
      <div className="input-hint">
        Try: <em>obesity landscape</em> · <em>/pipeline Novo Nordisk</em> · <em>drug profile tirzepatide</em>
      </div>
    </div>
  )
}
