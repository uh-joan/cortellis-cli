import { useState, useEffect, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getWikiArticle, listWiki } from '../lib/api.js'

const TYPE_COLOR = { indications: '#4f8ef7', companies: '#f59e0b', drugs: '#22c55e', targets: '#a78bfa' }

// Strip YAML frontmatter from markdown content
function stripFrontmatter(content) {
  if (!content.startsWith('---')) return content
  const end = content.indexOf('\n---', 4)
  if (end === -1) return content
  return content.slice(end + 4).trimStart()
}

// Replace [[slug\|Title]] and [[slug|Title]] wikilinks with [Title](wiki://slug)
function parseWikilinks(content) {
  return content.replace(/\[\[([^\]|\\]+?)(?:[|\\]+([^\]]+?))?\]\]/g, (_, slug, title) => {
    const label = title ? title.trim() : slug.trim()
    return `[${label}](wiki://${slug.trim()})`
  })
}

export default function WikiPanel({ article, onBack, onNavigate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [allArticles, setAllArticles] = useState([])
  const workspace = window.__WORKSPACE__ || '.'

  useEffect(() => {
    listWiki(workspace).then(setAllArticles).catch(() => {})
  }, [workspace])

  // slug → {type, slug, title} lookup
  const slugLookup = useMemo(() => {
    const map = {}
    for (const a of allArticles) map[a.slug] = a
    return map
  }, [allArticles])

  useEffect(() => {
    setLoading(true)
    setError(null)
    setData(null)
    getWikiArticle(article.type, article.slug, workspace)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [article.type, article.slug, workspace])

  const processedContent = useMemo(() => {
    if (!data?.content) return ''
    return parseWikilinks(stripFrontmatter(data.content))
  }, [data?.content])

  function handleLinkClick(href) {
    if (!href?.startsWith('wiki://')) return false
    const slug = href.slice(7)
    const target = slugLookup[slug]
    if (target) onNavigate(target)
    return true
  }

  const components = {
    a({ href, children }) {
      // Obsidian [[wikilinks]] converted to wiki://slug
      if (href?.startsWith('wiki://')) {
        const slug = href.slice(7)
        const target = slugLookup[slug]
        const color = target ? TYPE_COLOR[target.type] : '#4f8ef7'
        return (
          <a href="#" className="wiki-inline-link"
            style={{ color, textDecoration: 'underline', textDecorationColor: color + '66' }}
            onClick={e => { e.preventDefault(); handleLinkClick(href) }}
          >{children}</a>
        )
      }
      // Relative markdown links: indications/slug.md, companies/slug.md, etc.
      const relMatch = href?.match(/^(indications|companies|drugs|targets|internal|conferences|sessions)\/([\w-]+)\.md$/)
      if (relMatch) {
        const [, type, slug] = relMatch
        const target = allArticles.find(a => a.type === type && a.slug === slug)
        const color = TYPE_COLOR[type] || '#4f8ef7'
        return (
          <a href="#" className="wiki-inline-link"
            style={{ color, textDecoration: 'underline', textDecorationColor: color + '66' }}
            onClick={e => { e.preventDefault(); onNavigate(target || { type, slug }) }}
          >{children}</a>
        )
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
    }
  }

  return (
    <div className="wiki-viewer">
      <button className="wiki-back" onClick={onBack}>← Back</button>

      {loading && <div style={{ color: 'var(--text-dim)' }}>Loading…</div>}
      {error && <div style={{ color: 'var(--error)' }}>Error: {error}</div>}

      {data && (
        <>
          <div className="wiki-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} urlTransform={u => u}>
              {processedContent}
            </ReactMarkdown>
          </div>

          {data.related?.length > 0 && (
            <div className="wiki-related">
              <div className="wiki-related-label">Related</div>
              <div className="wiki-related-chips">
                {data.related.map(rel => (
                  <button
                    key={rel.slug}
                    className="wiki-related-chip"
                    style={{ borderColor: TYPE_COLOR[rel.type] + '66', color: TYPE_COLOR[rel.type] }}
                    onClick={() => onNavigate({ type: rel.type, slug: rel.slug })}
                  >
                    {rel.slug.replace(/-/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
