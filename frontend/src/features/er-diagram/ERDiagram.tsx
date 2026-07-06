import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader, Card, Badge, EmptyState } from '../../components/ui'
import { useSchema } from '../../context/SchemaContext'
import { useProjects } from '../../context/ProjectContext'

export const ERDiagram = () => {
  const { tables, relationships, isLoading } = useSchema()
  const { activeProject } = useProjects()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<
    Array<{
      id: string
      x1: number
      y1: number
      x2: number
      y2: number
      name: string
      type: string
    }>
  >([])

  const [hoveredTableId, setHoveredTableId] = useState<string | null>(null)
  const [hoveredRelationId, setHoveredRelationId] = useState<string | null>(null)

  // Recalculate coordinates of column elements relative to the diagram container
  const updateCoordinates = () => {
    if (!containerRef.current || tables.length === 0 || relationships.length === 0) {
      setCoords([])
      return
    }

    const containerRect = containerRef.current.getBoundingClientRect()
    const newCoords: typeof coords = []

    relationships.forEach((rel) => {
      // Elements can be identified by the custom IDs we set:
      const sourceEl = document.getElementById(`col-node-${rel.sourceTableId}-${rel.sourceColumnId}`)
      const targetEl = document.getElementById(`col-node-${rel.targetTableId}-${rel.targetColumnId}`)

      if (sourceEl && targetEl) {
        const sourceRect = sourceEl.getBoundingClientRect()
        const targetRect = targetEl.getBoundingClientRect()

        // Calculate connection points (middle right of source / middle left of target or closest sides)
        const x1 = sourceRect.right - containerRect.left
        const y1 = sourceRect.top + sourceRect.height / 2 - containerRect.top
        const x2 = targetRect.left - containerRect.left
        const y2 = targetRect.top + targetRect.height / 2 - containerRect.top

        newCoords.push({
          id: rel.id,
          x1,
          y1,
          x2,
          y2,
          name: rel.name,
          type: rel.type,
        })
      }
    })

    setCoords(newCoords)
  }

  // Recalculate on mount, window resize, and layout changes
  useEffect(() => {
    updateCoordinates()
    window.addEventListener('resize', updateCoordinates)
    // Small delay to ensure browser layout is fully painted
    const timer = setTimeout(updateCoordinates, 300)

    return () => {
      window.removeEventListener('resize', updateCoordinates)
      clearTimeout(timer)
    }
  }, [tables, relationships, isLoading])

  if (isLoading) {
    return (
      <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-slate-100 flex flex-col items-center justify-center min-h-[400px]">
        <div className="animate-spin text-4xl">⚙️</div>
        <p className="text-slate-400 text-sm">Loading active ER Diagram schema...</p>
      </div>
    )
  }

  if (tables.length === 0) {
    return (
      <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left">
        <PageHeader
          title="ER Diagram Viewer"
          subtitle={`Visual entity-relationship mapper for project '${activeProject?.name || 'Default'}'.`}
        />
        <EmptyState
          title="No Tables Configured"
          description="Go to the Schema Designer to create tables and column schemas before viewing the ER diagram."
          actionLabel="Go to Schema Designer"
          onAction={() => navigate('/schema-generator')}
        />
      </div>
    )
  }

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-6 text-left animate-fade-in">
      <PageHeader
        title="ER Diagram Viewer"
        subtitle={`Visual representation of relational tables and foreign keys in project: ${activeProject?.name || 'Default'}`}
      />

      <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-4 flex gap-4 text-xs text-slate-400 items-center justify-between flex-wrap">
        <div className="flex gap-6 items-center flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 bg-indigo-500 rounded-full inline-block"></span>
            <span>Table Entities ({tables.length})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 bg-violet-400 rounded-full inline-block"></span>
            <span>Relationships ({relationships.length})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>🔑 Primary Key</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>🔗 Related Column</span>
          </div>
        </div>
        <div className="text-[10px] text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-md font-semibold tracking-wide uppercase">
          Interactive View
        </div>
      </div>

      {/* Relative container that coordinates SVG lines overlay and Table cards */}
      <div
        ref={containerRef}
        className="relative min-h-[600px] border border-slate-800/80 rounded-2xl bg-slate-950/80 p-8 overflow-hidden"
      >
        {/* SVG overlay to render paths between column ports */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-10">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#818cf8" />
            </marker>
          </defs>

          {coords.map((c) => {
            const rel = relationships.find((r) => r.id === c.id)
            const isHovered = hoveredRelationId === c.id
            const isRelatedToHoveredTable =
              hoveredTableId &&
              rel &&
              (rel.sourceTableId === hoveredTableId || rel.targetTableId === hoveredTableId)

            return (
              <g key={c.id}>
                {/* Glow/Hover helper path */}
                <path
                  d={`M ${c.x1} ${c.y1} C ${(c.x1 + c.x2) / 2} ${c.y1}, ${(c.x1 + c.x2) / 2} ${c.y2}, ${c.x2} ${c.y2}`}
                  fill="none"
                  stroke={isHovered || isRelatedToHoveredTable ? '#818cf8' : 'transparent'}
                  strokeWidth="8"
                  className="transition-all duration-200 opacity-20"
                />
                {/* Actual connector line */}
                <path
                  d={`M ${c.x1} ${c.y1} C ${(c.x1 + c.x2) / 2} ${c.y1}, ${(c.x1 + c.x2) / 2} ${c.y2}, ${c.x2} ${c.y2}`}
                  fill="none"
                  stroke={isHovered || isRelatedToHoveredTable ? '#a78bfa' : '#475569'}
                  strokeWidth={isHovered || isRelatedToHoveredTable ? '2.5' : '1.5'}
                  markerEnd="url(#arrow)"
                  className="transition-all duration-200"
                />
                {/* Small indicator label on hover */}
                {(isHovered || isRelatedToHoveredTable) && (
                  <text
                    x={(c.x1 + c.x2) / 2}
                    y={(c.y1 + c.y2) / 2 - 8}
                    fill="#a78bfa"
                    fontSize="9"
                    className="font-mono bg-slate-900 px-1 fill-indigo-300 font-semibold text-center select-none"
                    textAnchor="middle"
                  >
                    {c.name} ({c.type})
                  </text>
                )}
              </g>
            )
          })}
        </svg>

        {/* CSS Flex/Grid container for Table Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 relative z-20">
          {tables.map((table) => {
            const isHovered = hoveredTableId === table.id
            const hasHoveredRelation =
              hoveredRelationId &&
              relationships.some(
                (r) =>
                  r.id === hoveredRelationId &&
                  (r.sourceTableId === table.id || r.targetTableId === table.id)
              )

            return (
              <Card
                key={table.id}
                onMouseEnter={() => setHoveredTableId(table.id)}
                onMouseLeave={() => setHoveredTableId(null)}
                className={`
                  bg-slate-900/90 border transition-all duration-300 flex flex-col p-0 overflow-hidden shadow-xl
                  ${
                    isHovered
                      ? 'border-indigo-500 ring-2 ring-indigo-500/20 scale-[1.02]'
                      : hasHoveredRelation
                        ? 'border-violet-500 scale-[1.01]'
                        : 'border-slate-800'
                  }
                `}
              >
                {/* Card Title */}
                <div className="bg-slate-800/60 px-4 py-3 border-b border-slate-800/80 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span role="img" aria-hidden="true" className="text-sm">
                      📊
                    </span>
                    <span className="font-bold text-slate-200 text-sm tracking-wide font-mono">
                      {table.name}
                    </span>
                  </div>
                  <Badge variant="info" className="text-[9px] font-bold">
                    {table.columns.length} columns
                  </Badge>
                </div>

                {/* Columns Listing */}
                <div className="divide-y divide-slate-800/40 py-1">
                  {table.columns.map((col) => {
                    const isSource = relationships.some(
                      (r) => r.sourceTableId === table.id && r.sourceColumnId === col.id
                    )
                    const isTarget = relationships.some(
                      (r) => r.targetTableId === table.id && r.targetColumnId === col.id
                    )
                    const relatedRel = relationships.find(
                      (r) =>
                        (r.sourceTableId === table.id && r.sourceColumnId === col.id) ||
                        (r.targetTableId === table.id && r.targetColumnId === col.id)
                    )

                    return (
                      <div
                        key={col.id}
                        id={`col-node-${table.id}-${col.id}`}
                        onMouseEnter={() => relatedRel && setHoveredRelationId(relatedRel.id)}
                        onMouseLeave={() => setHoveredRelationId(null)}
                        className={`
                          px-4 py-2.5 flex items-center justify-between text-xs transition-colors
                          ${
                            isSource || isTarget
                              ? 'hover:bg-indigo-650/15 cursor-pointer'
                              : 'hover:bg-slate-800/20'
                          }
                        `}
                      >
                        <div className="flex items-center gap-2 overflow-hidden mr-2">
                          <span className="text-[10px]">
                            {col.isPrimaryKey ? '🔑' : isSource || isTarget ? '🔗' : '▪️'}
                          </span>
                          <span
                            className={`font-mono truncate ${
                              col.isPrimaryKey
                                ? 'text-amber-400 font-bold'
                                : isSource || isTarget
                                  ? 'text-indigo-300 font-semibold'
                                  : 'text-slate-300'
                            }`}
                          >
                            {col.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className="text-[9px] text-slate-500 font-mono uppercase bg-slate-950 px-1.5 py-0.5 rounded border border-slate-900">
                            {col.type}
                          </span>
                          {!col.isNullable && (
                            <span className="text-[8px] text-amber-500/80 font-bold" title="Not Null">
                              *
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
