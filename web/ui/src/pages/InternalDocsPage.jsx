import { useState, useEffect, useRef } from 'react'
import { listInternalSources, uploadInternalFile, startIngest, pollIngestJob, listWiki } from '../lib/api.js'

const EXT_COLORS = {
  '.pdf': 'var(--error)',
  '.pptx': '#f59e0b',
  '.xlsx': '#22c55e',
  '.csv': '#22c55e',
  '.md': 'var(--text-dim)',
  '.txt': 'var(--text-dim)',
}

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function InternalDocsPage({ workspace, onArticleOpen }) {
  const [tab, setTab] = useState('sources')
  const [sources, setSources] = useState({})
  const [loading, setLoading] = useState(true)
  const [wikiInternal, setWikiInternal] = useState([])
  const [activeJobs, setActiveJobs] = useState({})
  const [dragOver, setDragOver] = useState(false)
  const [uploadIndication, setUploadIndication] = useState('')
  const [collapsed, setCollapsed] = useState({})
  const fileInputRef = useRef(null)

  async function reload() {
    const [src, wiki] = await Promise.all([
      listInternalSources(workspace),
      listWiki(workspace),
    ])
    setSources(src.indications || {})
    setWikiInternal(wiki.filter(a => a.type === 'internal'))
    setLoading(false)
  }

  useEffect(() => { reload() }, [workspace])

  function toggleCollapse(ind) {
    setCollapsed(prev => ({ ...prev, [ind]: !prev[ind] }))
  }

  async function handleUpload(files) {
    const ind = uploadIndication || 'general'
    for (const file of files) {
      try { await uploadInternalFile(ind, file, workspace) } catch {}
    }
    await reload()
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) handleUpload(files)
  }

  async function handleIngest(file) {
    try {
      const { job_id } = await startIngest(file.rel_path, workspace)
      setActiveJobs(prev => ({ ...prev, [job_id]: { file, status: 'running' } }))
      const interval = setInterval(async () => {
        const job = await pollIngestJob(job_id)
        if (job.status !== 'running') {
          clearInterval(interval)
          setActiveJobs(prev => ({ ...prev, [job_id]: { ...prev[job_id], status: job.status } }))
          await reload()
        }
      }, 2000)
    } catch (e) {
      console.error('Ingest failed:', e)
    }
  }

  const indications = Object.keys(sources)
  const totalFiles = Object.values(sources).flat().length

  return (
    <div className="internal-page">
      <div className="internal-header">
        <h1 className="internal-title">Internal</h1>
        <div className="internal-subtitle">Source files and compiled research articles</div>
      </div>

      <div className="internal-tabs">
        <button
          className={`internal-tab ${tab === 'sources' ? 'active' : ''}`}
          onClick={() => setTab('sources')}
        >
          Source Files <span className="internal-tab-count">{totalFiles}</span>
        </button>
        <button
          className={`internal-tab ${tab === 'articles' ? 'active' : ''}`}
          onClick={() => setTab('articles')}
        >
          Compiled Articles <span className="internal-tab-count">{wikiInternal.length}</span>
        </button>
      </div>

      <div className="internal-tab-body">
        {tab === 'sources' && (
          <>
            <div
              className={`internal-dropzone ${dragOver ? 'internal-dropzone--over' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <span className="internal-dropzone-icon">⬆</span>
              <span>Drop files here or click to upload</span>
              {indications.length > 0 && (
                <select
                  className="internal-ind-select"
                  value={uploadIndication}
                  onChange={e => setUploadIndication(e.target.value)}
                  onClick={e => e.stopPropagation()}
                >
                  <option value="">— pick folder —</option>
                  {indications.map(i => <option key={i} value={i}>{i}</option>)}
                  <option value="general">general</option>
                </select>
              )}
            </div>
            <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }}
              onChange={e => handleUpload(Array.from(e.target.files))} />

            {loading && <div className="internal-loading">Loading…</div>}
            {!loading && indications.length === 0 && (
              <div className="internal-empty">No source files found in raw/internal/</div>
            )}

            {indications.map(ind => (
              <div key={ind} className="internal-indication">
                <div className="internal-indication-header" onClick={() => toggleCollapse(ind)}>
                  <span className={`wiki-section-chevron ${collapsed[ind] ? 'collapsed' : ''}`}>›</span>
                  <span className="internal-indication-name">{ind}</span>
                  <span className="internal-panel-count">{sources[ind].length}</span>
                </div>
                {!collapsed[ind] && (
                  <div className="internal-file-list">
                    {sources[ind].map(file => {
                      const jobEntry = Object.entries(activeJobs).find(([, v]) => v.file?.rel_path === file.rel_path)
                      const jobStatus = jobEntry?.[1]?.status
                      const isIngested = jobStatus === 'done' || file.status === 'ingested'
                      const openIngest = () => handleIngest(file)
                      return (
                        <div key={file.name} className="internal-file-row">
                          <span className="internal-ext-badge" style={{ color: EXT_COLORS[file.ext] || 'var(--text-dim)' }}>
                            {file.ext.replace('.', '').toUpperCase()}
                          </span>
                          <span className="internal-file-name" title={file.name}>{file.name}</span>
                          <span className="internal-file-size">{fmtSize(file.size)}</span>
                          {jobStatus === 'running' ? (
                            <span className="internal-status-chip internal-status--running">ingesting…</span>
                          ) : jobStatus === 'error' ? (
                            <span className="internal-status-chip internal-status--error"
                              style={{cursor:'pointer'}} onClick={openIngest} title="Click to retry">error ↻</span>
                          ) : isIngested ? (
                            <span className="internal-ingest-meta">
                              {file.stale
                                ? <span className="internal-status-chip internal-status--stale">↻ Updated</span>
                                : <span className="internal-status-chip internal-status--ingested">✓ {file.ingested_at || 'ingested'}</span>
                              }
                              <button className="internal-reingest-btn" onClick={openIngest} title="Re-ingest">↻</button>
                            </span>
                          ) : (
                            <button className="internal-ingest-btn" onClick={openIngest}>Ingest</button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
          </>
        )}

        {tab === 'articles' && (
          wikiInternal.length === 0 ? (
            <div className="internal-empty">No ingested articles yet. Ingest a source file to get started.</div>
          ) : (
            <div className="internal-articles-list">
              {wikiInternal.map(a => (
                <div key={a.slug} className="internal-article-row" onClick={() => onArticleOpen(a)}>
                  <span className="internal-article-title">{a.title}</span>
                  <span className="internal-article-arrow">→</span>
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  )
}
