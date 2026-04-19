import { useState, useEffect, useMemo, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getWikiArticle, listWiki, postChangelog, pollJob, getEnrichManifest, postEnrich } from '../lib/api.js'

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

export default function WikiPanel({ article, onBack, onNavigate, historyDepth = 0 }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [allArticles, setAllArticles] = useState([])
  const [changelogOpen, setChangelogOpen] = useState(false)
  const [changelogRunning, setChangelogRunning] = useState(false)
  const [changelogOutput, setChangelogOutput] = useState(null)
  const [changelogError, setChangelogError] = useState(null)
  const changelogIntervalRef = useRef(null)
  const [enrichManifest, setEnrichManifest] = useState(null)
  const [enrichOpen, setEnrichOpen] = useState(false)
  const [enrichRunning, setEnrichRunning] = useState(false)
  const [enrichOutput, setEnrichOutput] = useState(null)
  const [enrichError, setEnrichError] = useState(null)
  const enrichIntervalRef = useRef(null)
  const workspace = window.__WORKSPACE__ || '.'

  useEffect(() => {
    listWiki(workspace).then(setAllArticles).catch(() => {})
  }, [workspace])

  useEffect(() => {
    if (article.type !== 'indications') return
    setEnrichManifest(null)
    getEnrichManifest(article.slug, workspace).then(setEnrichManifest).catch(() => {})

    // Resume polling if a job was started before navigation
    const savedJobId = localStorage.getItem(`enrich-job-${article.slug}`)
    if (savedJobId) {
      setEnrichOpen(true)
      setEnrichRunning(true)
      enrichIntervalRef.current = setInterval(async () => {
        try {
          const job = await pollJob(savedJobId)
          if (job.status !== 'running') {
            clearInterval(enrichIntervalRef.current)
            localStorage.removeItem(`enrich-job-${article.slug}`)
            if (job.status === 'error') setEnrichError(job.output || 'Enrich failed.')
            else {
              setEnrichOutput(job.output)
              getEnrichManifest(article.slug, workspace).then(setEnrichManifest).catch(() => {})
            }
            setEnrichRunning(false)
          }
        } catch { clearInterval(enrichIntervalRef.current); setEnrichRunning(false) }
      }, 2000)
    }
  }, [article.type, article.slug, workspace])

  async function handleChangelog() {
    if (changelogOpen && !changelogRunning) { setChangelogOpen(false); return }
    if (changelogRunning) return
    setChangelogOpen(true)
    setChangelogRunning(true)
    setChangelogOutput(null)
    setChangelogError(null)
    try {
      const result = await postChangelog(article.slug, workspace)
      if (result.prereq_missing) {
        setChangelogError(result.message)
        setChangelogRunning(false)
        return
      }
      changelogIntervalRef.current = setInterval(async () => {
        const job = await pollJob(result.job_id)
        if (job.status !== 'running') {
          clearInterval(changelogIntervalRef.current)
          if (job.status === 'error') setChangelogError(job.output || 'Changelog failed.')
          else setChangelogOutput(job.output)
          setChangelogRunning(false)
        }
      }, 2000)
    } catch (e) {
      setChangelogError(e.message)
      setChangelogRunning(false)
    }
  }

  async function handleEnrich() {
    if (enrichOpen && !enrichRunning) { setEnrichOpen(false); return }
    if (enrichRunning) return
    setEnrichOpen(true)
    setEnrichRunning(true)
    setEnrichOutput(null)
    setEnrichError(null)
    try {
      const result = await postEnrich(article.slug, workspace)
      if (result.prereq_missing) {
        setEnrichError(result.message)
        setEnrichRunning(false)
        return
      }
      localStorage.setItem(`enrich-job-${article.slug}`, result.job_id)
      enrichIntervalRef.current = setInterval(async () => {
        try {
          const job = await pollJob(result.job_id)
          if (job.status !== 'running') {
            clearInterval(enrichIntervalRef.current)
            localStorage.removeItem(`enrich-job-${article.slug}`)
            if (job.status === 'error') setEnrichError(job.output || 'Enrich failed.')
            else {
              setEnrichOutput(job.output)
              getEnrichManifest(article.slug, workspace).then(setEnrichManifest).catch(() => {})
            }
            setEnrichRunning(false)
          }
        } catch { clearInterval(enrichIntervalRef.current); setEnrichRunning(false) }
      }, 2000)
    } catch (e) {
      setEnrichError(e.message)
      setEnrichRunning(false)
    }
  }

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
      <button className="wiki-back" onClick={onBack}>← {historyDepth > 0 ? 'Back' : 'Wiki'}</button>

      {loading && <div style={{ color: 'var(--text-dim)' }}>Loading…</div>}
      {error && <div style={{ color: 'var(--error)' }}>Error: {error}</div>}

      {data && (
        <>
          <h1 className="wiki-article-title">{article.title}</h1>

          {article.type === 'indications' && enrichManifest?.exists && enrichManifest.total_missing > 0 && (
            <div className="wiki-enrich-callout">
              <span>{enrichRunning ? '⟳' : '⚠'}</span>
              <span>{enrichRunning ? 'Enriching KB…' : [
                enrichManifest.missing_drugs > 0 && `${enrichManifest.missing_drugs} drugs`,
                enrichManifest.missing_companies > 0 && `${enrichManifest.missing_companies} companies`,
                enrichManifest.missing_targets > 0 && `${enrichManifest.missing_targets} targets`,
              ].filter(Boolean).join(' · ') + ' need profiling'}</span>
              {!enrichRunning && (
                <button onClick={() => {
                  handleEnrich()
                  setTimeout(() => document.querySelector('.wiki-enrich-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
                }}>Enrich →</button>
              )}
            </div>
          )}

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

          {article.type === 'indications' && (
            <div className="wiki-changelog">
              <button className="wiki-graph-btn" onClick={handleChangelog}>
                {changelogRunning ? '⟳ Running…' : changelogOpen ? '▲ Hide History' : '▼ History'}
              </button>
              {changelogOpen && (
                <div className="wiki-changelog-panel">
                  {changelogRunning && <div style={{ color: 'var(--text-dim)', padding: '12px 0' }}>Generating pipeline history…</div>}
                  {changelogError && <div style={{ color: 'var(--error)', padding: '12px 0' }}>{changelogError}</div>}
                  {changelogOutput && (() => {
                    const clean = changelogOutput
                      .split('\n')
                      .filter(l => !l.match(/^[▶✓✗]\s*(Wave|\[)/) && !l.match(/\] (running|success|error|skipped)/))
                      .join('\n')
                      .trim()
                    return clean ? (
                      <div className="wiki-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{clean}</ReactMarkdown>
                      </div>
                    ) : (
                      <div style={{ color: 'var(--text-dim)', padding: '12px 0', fontSize: '13px' }}>
                        No changelog data yet. Run <code>/landscape {article.slug}</code> first to generate pipeline history.
                      </div>
                    )
                  })()}
                </div>
              )}
            </div>
          )}

          {article.type === 'indications' && (
            <div className="wiki-changelog wiki-enrich-section">
              <button className="wiki-graph-btn" onClick={handleEnrich}>
                {enrichRunning ? '⟳ Enriching…' : enrichOpen ? '▲ Hide Enrich' : '▼ Enrich KB'}
              </button>
              {enrichOpen && (
                <div className="wiki-changelog-panel">
                  {!enrichRunning && !enrichOutput && !enrichError && (
                    <div style={{ color: 'var(--text-dim)', padding: '12px 0', fontSize: '13px' }}>
                      {enrichManifest?.total_missing > 0
                        ? `Runs drug-profile, pipeline, and target-profile for ${enrichManifest.total_missing} missing entities.`
                        : 'KB is complete — all priority entities have deep profiles.'}
                    </div>
                  )}
                  {enrichRunning && <div style={{ color: 'var(--text-dim)', padding: '12px 0' }}>Running drug-profile, pipeline, and target-profile skills…</div>}
                  {enrichError && <div style={{ color: 'var(--error)', padding: '12px 0' }}>{enrichError}</div>}
                  {enrichOutput && (() => {
                    const clean = enrichOutput
                      .split('\n')
                      .filter(l => !l.match(/^[▶✓✗]\s*(Wave|\[)/) && !l.match(/\] (running|success|error|skipped)/))
                      .join('\n')
                      .trim()
                    return clean ? (
                      <div className="wiki-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{clean}</ReactMarkdown>
                      </div>
                    ) : (
                      <div style={{ color: 'var(--text-dim)', padding: '12px 0', fontSize: '13px' }}>Enrich complete. Refresh to see updated article.</div>
                    )
                  })()}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
