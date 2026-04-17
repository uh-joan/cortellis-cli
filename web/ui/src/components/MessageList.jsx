import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function MessageList({ messages }) {
  if (messages.length === 0) return null

  return (
    <>
      {messages.map(msg => (
        <Message key={msg.id} msg={msg} />
      ))}
    </>
  )
}

function Message({ msg }) {
  const time = new Date(msg.created_at).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit',
  })

  return (
    <div className="message">
      <div className="message-header">
        <span className={`message-role ${msg.role}`}>
          {msg.role === 'user' ? 'You' : 'Cortellis AI'}
        </span>
        <span className="message-time">{time}</span>
      </div>
      <div className="message-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {msg.content}
        </ReactMarkdown>
      </div>
    </div>
  )
}
