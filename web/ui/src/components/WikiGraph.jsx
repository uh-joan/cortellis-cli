import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

const TYPE_COLOR = {
  indication: '#4f8ef7',
  company: '#f59e0b',
  drug: '#22c55e',
  target: '#a78bfa',
}
const TYPE_VAL = { indication: 12, target: 5, drug: 3, company: 2 }
const TYPE_LABELS = { indication: 'Indications', company: 'Companies', drug: 'Drugs', target: 'Targets' }

const DEFAULT_SETTINGS = {
  search: '',
  show: { indication: true, company: true, drug: true, target: true },
  showOrphans: false,
  repel: 120,
  linkDist: 90,
  linkStrength: 0.25,
}

function nodeId(n) { return typeof n === 'object' ? n.id : n }

export default function WikiGraph({ workspace, onNodeClick, onBack }) {
  const containerRef = useRef(null)
  const fgRef = useRef(null)
  const [rawData, setRawData] = useState({ nodes: [], links: [] })
  const [dims, setDims] = useState({ w: 0, h: 0 })
  const [loading, setLoading] = useState(true)
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [selectedNode, setSelectedNode] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setDims({ w: width, h: height })
    })
    obs.observe(el)
    setDims({ w: el.clientWidth, h: el.clientHeight })
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    fetch(`/api/wiki/graph?workspace_path=${encodeURIComponent(workspace)}`)
      .then(r => r.json())
      .then(data => { setRawData(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [workspace])

  // Apply forces on mount and on slider changes
  useEffect(() => {
    if (!dims.w) return
    const t = setTimeout(() => {
      const fg = fgRef.current
      if (!fg) return
      fg.d3Force('charge')?.strength(-settings.repel)
      fg.d3Force('link')?.distance(settings.linkDist).strength(settings.linkStrength)
      fg.d3ReheatSimulation()
    }, 80)
    return () => clearTimeout(t)
  }, [dims.w, settings.repel, settings.linkDist, settings.linkStrength])

  // Nodes with at least one link
  const linkedNodeIds = useMemo(() => {
    const ids = new Set()
    for (const l of rawData.links) {
      ids.add(nodeId(l.source))
      ids.add(nodeId(l.target))
    }
    return ids
  }, [rawData.links])

  // Neighbours of hovered node
  const hoveredNeighbours = useMemo(() => {
    if (!hoveredNode) return null
    const ids = new Set()
    for (const l of rawData.links) {
      const s = nodeId(l.source), t = nodeId(l.target)
      if (s === hoveredNode.id) ids.add(t)
      if (t === hoveredNode.id) ids.add(s)
    }
    return ids
  }, [hoveredNode, rawData.links])

  const q = settings.search.toLowerCase()

  const graphData = useMemo(() => {
    const nodes = rawData.nodes.filter(n => {
      if (!settings.show[n.type]) return false
      if (!settings.showOrphans && !linkedNodeIds.has(n.id)) return false
      if (q && !n.title.toLowerCase().includes(q) && !n.slug.includes(q)) return false
      return true
    })
    const visibleIds = new Set(nodes.map(n => n.id))
    const links = rawData.links.filter(l =>
      visibleIds.has(nodeId(l.source)) && visibleIds.has(nodeId(l.target))
    )
    return { nodes, links }
  }, [rawData, settings.show, settings.showOrphans, linkedNodeIds, q])

  const drawNode = useCallback((node, ctx, globalScale) => {
    const r = Math.sqrt(TYPE_VAL[node.type] || 2) * 4
    const color = TYPE_COLOR[node.type] || '#6b7280'
    const isSelected = selectedNode?.id === node.id
    const isHovered = hoveredNode?.id === node.id
    const isNeighbour = hoveredNeighbours?.has(node.id)
    const isDimmed = hoveredNode && !isHovered && !isNeighbour

    if ((node.type === 'indication' || isSelected || isHovered) && !isDimmed) {
      ctx.shadowBlur = isHovered ? 24 : isSelected ? 20 : 12
      ctx.shadowColor = color
    }
    ctx.globalAlpha = isDimmed ? 0.15 : 1
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
    ctx.fillStyle = isSelected || isHovered ? '#fff' : color
    ctx.fill()
    if (isSelected || isHovered) {
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.stroke()
    }
    ctx.shadowBlur = 0

    const showLabel = node.type === 'indication' || isSelected || isHovered || isNeighbour || globalScale > 1.8
    if (showLabel && !isDimmed) {
      const fontSize = Math.max(8, 10 / globalScale)
      ctx.font = `${node.type === 'indication' || isSelected || isHovered ? 'bold ' : ''}${fontSize}px -apple-system, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = isSelected || isHovered ? '#fff' : 'rgba(226,232,240,0.85)'
      const label = node.title.length > 22 ? node.title.slice(0, 20) + '…' : node.title
      ctx.fillText(label, node.x, node.y + r + 2)
      ctx.textBaseline = 'alphabetic'
    }
    ctx.globalAlpha = 1
  }, [selectedNode, hoveredNode, hoveredNeighbours])

  const linkColor = useCallback(link => {
    if (!hoveredNode) return 'rgba(255,255,255,0.07)'
    const s = nodeId(link.source), t = nodeId(link.target)
    const connected = s === hoveredNode.id || t === hoveredNode.id
    return connected ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.02)'
  }, [hoveredNode])

  const linkWidth = useCallback(link => {
    if (!hoveredNode) return 0.8
    const s = nodeId(link.source), t = nodeId(link.target)
    return (s === hoveredNode.id || t === hoveredNode.id) ? 2 : 0.5
  }, [hoveredNode])

  function handleNodeClick(node) {
    setSelectedNode(prev => prev?.id === node.id ? null : node)
  }

  function set(key, val) { setSettings(prev => ({ ...prev, [key]: val })) }
  function toggleType(type) {
    setSettings(prev => ({ ...prev, show: { ...prev.show, [type]: !prev.show[type] } }))
  }

  const orphanCount = rawData.nodes.filter(n => !linkedNodeIds.has(n.id)).length

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div ref={containerRef} className="wiki-graph-container" style={{ flex: 1, position: 'relative' }}>
        {loading && <div className="wiki-graph-loading">Building graph…</div>}
        {dims.w > 0 && (
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            width={dims.w}
            height={dims.h}
            backgroundColor="#0f1117"
            nodeVal={node => TYPE_VAL[node.type] || 2}
            nodeLabel="title"
            linkColor={linkColor}
            linkWidth={linkWidth}
            onNodeClick={handleNodeClick}
            onNodeHover={node => setHoveredNode(node || null)}
            nodeCanvasObject={drawNode}
            nodeCanvasObjectMode={() => 'replace'}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            cooldownTicks={200}
          />
        )}
        <div className="wiki-graph-legend">
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <div key={type} className="wiki-graph-legend-item">
              <span className="wiki-graph-legend-dot" style={{ background: color }} />
              {type}s
            </div>
          ))}
        </div>
      </div>

      <div className="graph-settings-panel" style={{ width: 264 }}>
        <div className="graph-settings-section" style={{ borderBottom: '1px solid var(--border)' }}>
          <button className="wiki-back" onClick={onBack} style={{ marginBottom: 0 }}>← Wiki list</button>
        </div>

        {selectedNode && (
          <div className="graph-settings-section graph-node-card">
            <div className="graph-node-card-type" style={{ color: TYPE_COLOR[selectedNode.type] }}>
              {TYPE_LABELS[selectedNode.type]?.slice(0, -1) || selectedNode.type}
            </div>
            <div className="graph-node-card-title">{selectedNode.title}</div>
            <button className="graph-node-open-btn" onClick={() => onNodeClick(selectedNode)}>
              Open article →
            </button>
          </div>
        )}

        <div className="graph-settings-section">
          <div className="graph-settings-heading">Filters</div>
          <div className="graph-search-wrap">
            <span className="graph-search-icon">⌕</span>
            <input
              className="graph-search-input"
              placeholder="Search nodes…"
              value={settings.search}
              onChange={e => set('search', e.target.value)}
            />
            {settings.search && (
              <button className="graph-search-clear" onClick={() => set('search', '')}>×</button>
            )}
          </div>
          <div className="graph-group-row" style={{ marginTop: 10 }}>
            <label className="graph-group-label">
              <input
                type="checkbox"
                checked={settings.showOrphans}
                onChange={() => set('showOrphans', !settings.showOrphans)}
                className="graph-group-check"
              />
              Orphans
            </label>
            <span className="graph-group-count">{orphanCount}</span>
          </div>
        </div>

        <div className="graph-settings-section">
          <div className="graph-settings-heading">Groups</div>
          {Object.entries(TYPE_LABELS).map(([type, label]) => (
            <div key={type} className="graph-group-row">
              <label className="graph-group-label">
                <input
                  type="checkbox"
                  checked={settings.show[type]}
                  onChange={() => toggleType(type)}
                  className="graph-group-check"
                />
                <span className="graph-group-dot" style={{ background: TYPE_COLOR[type] }} />
                {label}
              </label>
              <span className="graph-group-count">
                {rawData.nodes.filter(n => n.type === type).length}
              </span>
            </div>
          ))}
        </div>

        <div className="graph-settings-section">
          <div className="graph-settings-heading">Forces</div>
          <div className="graph-force-row">
            <span className="graph-force-label">Repel force</span>
            <span className="graph-force-val">{settings.repel}</span>
          </div>
          <input type="range" min={20} max={500} step={10} value={settings.repel}
            onChange={e => set('repel', +e.target.value)} className="graph-slider" />
          <div className="graph-force-row">
            <span className="graph-force-label">Link distance</span>
            <span className="graph-force-val">{settings.linkDist}</span>
          </div>
          <input type="range" min={30} max={250} step={5} value={settings.linkDist}
            onChange={e => set('linkDist', +e.target.value)} className="graph-slider" />
          <div className="graph-force-row">
            <span className="graph-force-label">Link strength</span>
            <span className="graph-force-val">{settings.linkStrength.toFixed(2)}</span>
          </div>
          <input type="range" min={0.05} max={1} step={0.05} value={settings.linkStrength}
            onChange={e => set('linkStrength', +e.target.value)} className="graph-slider" />
          <button className="graph-reset-btn" onClick={() => setSettings(DEFAULT_SETTINGS)}>
            Reset defaults
          </button>
        </div>
      </div>
    </div>
  )
}
